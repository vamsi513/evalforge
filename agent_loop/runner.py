"""Run one task against AgentIQ and capture everything the run exposed.

Why this calls the graph rather than api.streaming.run_agent_sync: the graph
state carries an `error` key that a node sets when it fails, and run_agent_sync
does not copy that key into its response dict. A failed node there returns a
canned apology string and the run looks successful from the outside. Since the
whole point of this exercise is to find failures, the error has to survive, so
the graph is invoked directly. That is still public API and still read only.

Three things are captured that the return value does not give on its own:

  stage timings   agent/nodes.py logs "stage_timing stage=<node> duration_ms=<n>"
                  at INFO. A handler on that logger collects them per run, which
                  is how per node latency gets into the trace.
  tool calls      observability/audit.py emits one JSON line per tool call when
                  AUDIT_LOG_ENABLED is set. Only web_search is decorated, so
                  FAISS retrieval evidence comes from graph state instead.
  token usage     a callback on the LLM calls. ChatOpenAI is constructed with
                  streaming=True, which can leave usage unreported, so the meter
                  records which source each number came from rather than
                  presenting an estimate as a measurement.
"""

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from agent_loop.credentials import ENV_FILE, load_env_file  # noqa: F401  (re-exported)

_STAGE_TIMING = re.compile(r"stage_timing stage=(?P<stage>\S+) duration_ms=(?P<ms>[\d.]+)")

# Which usage number a trace is based on. A reader should never have to guess
# whether a cost line was measured or inferred.
USAGE_REPORTED = "provider_reported"
USAGE_ESTIMATED = "tiktoken_estimate"
USAGE_NONE = "no_llm_calls"

# Chat completion envelope, per OpenAI's documented counting rules.
_CHAT_TOKENS_PER_MESSAGE = 3
_CHAT_PRIMING_TOKENS = 3


class _LogCapture(logging.Handler):
    """Collect stage timings and audit records emitted during one run."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.stage_timings: list[dict[str, Any]] = []
        self.audit_records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # pragma: no cover - a broken log line must not stop a run
            return

        if record.name == "agentiq.audit":
            try:
                self.audit_records.append(json.loads(message))
            except json.JSONDecodeError:
                self.audit_records.append({"unparsed": message[:500]})
            return

        match = _STAGE_TIMING.search(message)
        if match:
            self.stage_timings.append(
                {"stage": match["stage"], "duration_ms": float(match["ms"])}
            )


class TokenMeter:
    """Per run token accounting for the agent's LLM calls.

    Implemented as a LangChain callback handler. Every provider reported number
    is preferred; a tiktoken estimate is only used when the provider gave
    nothing, and the trace records which happened.
    """

    def __init__(self, model: str) -> None:
        self.model = model
        self.calls: list[dict[str, Any]] = []
        self.raise_error = False
        self.ignore_llm = False
        self.ignore_chain = True
        self.ignore_agent = True
        self.ignore_retriever = True
        self.ignore_chat_model = False
        self.ignore_custom_event = True
        self.run_inline = True
        self._pending_prompts: dict[str, list[str]] = {}

    # LangChain calls these; unused hooks are no-ops.
    def __getattr__(self, name: str):
        if name.startswith("on_"):
            return lambda *args, **kwargs: None
        raise AttributeError(name)

    def on_chat_model_start(self, serialized, messages, *, run_id=None, **kwargs) -> None:
        flat = [getattr(m, "content", str(m)) for batch in messages for m in batch]
        self._pending_prompts[str(run_id)] = [t for t in flat if isinstance(t, str)]

    def on_llm_start(self, serialized, prompts, *, run_id=None, **kwargs) -> None:
        self._pending_prompts[str(run_id)] = list(prompts)

    def on_llm_end(self, response, *, run_id=None, **kwargs) -> None:
        prompts = self._pending_prompts.pop(str(run_id), [])
        usage = self._reported_usage(response)
        source = USAGE_REPORTED

        if usage is None:
            completion = ""
            for generation_batch in getattr(response, "generations", []):
                for generation in generation_batch:
                    completion += getattr(generation, "text", "") or ""
            # Chat completions charge a few tokens of envelope per message plus
            # a priming allowance for the reply, on top of the content itself.
            # Adding them keeps the estimate slightly high rather than low,
            # which is the safe direction when a spend cap depends on it.
            envelope = _CHAT_TOKENS_PER_MESSAGE * len(prompts) + _CHAT_PRIMING_TOKENS
            usage = {
                "input_tokens": _count_tokens("\n".join(prompts), self.model) + envelope,
                "output_tokens": _count_tokens(completion, self.model),
            }
            source = USAGE_ESTIMATED

        self.calls.append({**usage, "usage_source": source})

    @staticmethod
    def _reported_usage(response) -> dict[str, int] | None:
        """Pull usage out of whichever shape the provider returned."""
        output = getattr(response, "llm_output", None) or {}
        reported = output.get("token_usage") or output.get("usage")
        if reported:
            prompt = reported.get("prompt_tokens", reported.get("input_tokens"))
            completion = reported.get("completion_tokens", reported.get("output_tokens"))
            if prompt is not None and completion is not None:
                return {"input_tokens": int(prompt), "output_tokens": int(completion)}

        for generation_batch in getattr(response, "generations", []):
            for generation in generation_batch:
                message = getattr(generation, "message", None)
                metadata = getattr(message, "usage_metadata", None)
                if isinstance(metadata, dict) and metadata.get("input_tokens") is not None:
                    return {
                        "input_tokens": int(metadata["input_tokens"]),
                        "output_tokens": int(metadata.get("output_tokens", 0)),
                    }
        return None

    def totals(self) -> dict[str, Any]:
        input_tokens = sum(call["input_tokens"] for call in self.calls)
        output_tokens = sum(call["output_tokens"] for call in self.calls)
        estimated = any(call["usage_source"] == USAGE_ESTIMATED for call in self.calls)
        if not self.calls:
            # Distinct from a measured zero. A mock run makes no LLM calls at
            # all, and that must not read as "the provider reported nothing".
            source = USAGE_NONE
        else:
            source = USAGE_ESTIMATED if estimated else USAGE_REPORTED
        return {
            "llm_calls": len(self.calls),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost_usd": round(token_cost(self.model, input_tokens, output_tokens), 8),
            "usage_source": source,
        }


def _count_tokens(text: str, model: str) -> int:
    if not text:
        return 0
    try:
        import tiktoken

        try:
            encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            encoding = tiktoken.get_encoding("o200k_base")
        return len(encoding.encode(text))
    except Exception:  # pragma: no cover - a missing encoder must not stop a run
        return max(1, len(text) // 4)


def token_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Cost in USD using EvalForge's published pricing table.

    Imported inside the function on purpose. At module scope this pulls in
    app.core.config, whose settings singleton reads credentials and the judge
    provider from the environment the moment it is built. Importing it early
    once meant the judge ran as the mock without anything saying so.
    """
    from app.engine.judge import _TOKEN_PRICING_USD

    pricing = next(
        (rates for name, rates in _TOKEN_PRICING_USD.items() if model.startswith(name)),
        None,
    )
    if pricing is None:
        return 0.0
    return input_tokens * pricing["prompt"] + output_tokens * pricing["completion"]


def settings_snapshot() -> dict[str, Any]:
    """The agent configuration a run was executed under.

    Recorded in every trace so a later run can be shown to have used the same
    settings, which is what makes the before and after comparison meaningful.
    """
    from config import settings

    return {
        "openai_model": settings.openai_model,
        "embedding_model": settings.embedding_model,
        "temperature": settings.temperature,
        "max_tokens": settings.max_tokens,
        "top_k_retrieval": settings.top_k_retrieval,
        "max_web_results": settings.max_web_results,
        "enable_query_rewriting": settings.enable_query_rewriting,
        "budgets_enabled": settings.budgets_enabled,
        "audit_log_enabled": settings.audit_log_enabled,
        "mock_llm": settings.mock_llm,
        "mock_tavily": settings.mock_tavily,
    }


async def run_task(graph, task: dict, *, variant: str = "baseline") -> dict:
    """Run one task and return its full trace.

    `variant` records which wrapper produced the run. Phase 5 adds a second
    variant, and a trace has to say which one it came from.
    """
    from config import settings
    from langchain_core.messages import HumanMessage

    session_id = f"agentloop-{task['id']}-{uuid.uuid4().hex[:8]}"
    meter = TokenMeter(settings.openai_model)
    capture = _LogCapture()

    nodes_logger = logging.getLogger("agent.nodes")
    audit_logger = logging.getLogger("agentiq.audit")
    for logger in (nodes_logger, audit_logger):
        logger.addHandler(capture)
        logger.setLevel(logging.INFO)

    initial_state = {
        "messages": [HumanMessage(content=task["question"])],
        "query": task["question"],
        "context": "",
        "sources": [],
        "route_decision": "direct",
        "session_id": session_id,
        "turn_count": 0,
        "retrieval_score": 0.0,
        "error": None,
        "metadata": {},
    }

    started = time.perf_counter()
    failure: str | None = None
    state: dict[str, Any] = {}
    try:
        state = await graph.ainvoke(initial_state, config={"callbacks": [meter]})
    except Exception as exc:  # a crash is a result, not a reason to stop the sweep
        failure = f"{type(exc).__name__}: {exc}"
    finally:
        latency_ms = (time.perf_counter() - started) * 1000
        for logger in (nodes_logger, audit_logger):
            logger.removeHandler(capture)

    messages = state.get("messages", [])
    answer = messages[-1].content if messages else ""

    return {
        "task_id": task["id"],
        "category": task["category"],
        "question": task["question"],
        "variant": variant,
        "session_id": session_id,
        "route_decision": state.get("route_decision"),
        "answer": answer,
        "context": state.get("context", ""),
        "sources": state.get("sources", []),
        "retrieved_titles": [s.get("title") for s in state.get("sources", [])],
        "retrieval_score": state.get("retrieval_score", 0.0),
        "turn_count": state.get("turn_count", 0),
        "state_error": state.get("error"),
        "invoke_exception": failure,
        "metadata": state.get("metadata") or {},
        "latency_ms": round(latency_ms, 1),
        "stage_timings": capture.stage_timings,
        "tool_calls": capture.audit_records,
        "usage": meter.totals(),
        "settings": settings_snapshot(),
    }


async def run_task_with_guard(graph, task: dict, *, variant: str) -> dict:
    """Run a task, and on a retrieval run that reported missing evidence, run
    its sub questions through the same graph and present them together.

    The guard's own costs are folded into the trace's usage, so the comparison
    against baseline charges this fix for what it actually spends.
    """
    from langchain_openai import ChatOpenAI

    from agent_loop.guards import compose_answer, decompose, needs_retry
    from config import settings

    first = await run_task(graph, task, variant=variant)
    first["guard"] = {"triggered": False, "reason": "answer did not report missing evidence"}
    if not needs_retry(first):
        return first

    llm = ChatOpenAI(
        model=settings.openai_model,
        temperature=settings.temperature,
        max_tokens=settings.max_tokens,
        api_key=settings.openai_api_key,
        timeout=30.0,
        max_retries=2,
    )
    meter = TokenMeter(settings.openai_model)
    sub_questions = decompose(task["question"], llm.with_config({"callbacks": [meter]}))
    if not sub_questions:
        first["guard"] = {"triggered": False, "reason": "question did not decompose"}
        return first

    parts: list[tuple[str, str]] = []
    sub_traces: list[dict] = []
    for sub in sub_questions:
        sub_trace = await run_task(graph, {**task, "question": sub}, variant=variant)
        parts.append((sub, sub_trace.get("answer") or ""))
        sub_traces.append(
            {
                "question": sub,
                "route": sub_trace.get("route_decision"),
                "retrieved_titles": sub_trace.get("retrieved_titles", []),
                "answer": sub_trace.get("answer"),
                "usage": sub_trace["usage"],
                "latency_ms": sub_trace["latency_ms"],
            }
        )

    decompose_usage = meter.totals()
    combined = first.copy()
    combined["answer"] = compose_answer(parts)
    combined["context"] = "\n\n---\n\n".join(
        t.get("context", "") for t in [first] + [{"context": ""}]
    ).strip() or first.get("context", "")
    combined["retrieved_titles"] = sorted(
        {t for st in sub_traces for t in st["retrieved_titles"]} | set(first["retrieved_titles"])
    )
    combined["latency_ms"] = round(
        first["latency_ms"] + sum(st["latency_ms"] for st in sub_traces), 1
    )
    combined["usage"] = {
        "llm_calls": first["usage"]["llm_calls"]
        + decompose_usage["llm_calls"]
        + sum(st["usage"]["llm_calls"] for st in sub_traces),
        "input_tokens": first["usage"]["input_tokens"]
        + decompose_usage["input_tokens"]
        + sum(st["usage"]["input_tokens"] for st in sub_traces),
        "output_tokens": first["usage"]["output_tokens"]
        + decompose_usage["output_tokens"]
        + sum(st["usage"]["output_tokens"] for st in sub_traces),
        "cost_usd": round(
            first["usage"]["cost_usd"]
            + decompose_usage["cost_usd"]
            + sum(st["usage"]["cost_usd"] for st in sub_traces),
            8,
        ),
        "usage_source": first["usage"]["usage_source"],
    }
    combined["guard"] = {
        "triggered": True,
        "reason": "retrieval run reported missing evidence",
        "sub_questions": sub_questions,
        "sub_traces": sub_traces,
        "first_answer": first.get("answer"),
    }
    return combined
