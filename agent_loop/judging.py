"""Layer 2: the LLM judge, scoring reasoning quality and faithfulness.

This is EvalForge's own judge, unmodified. `JudgeClient._score_with_anthropic`
forces a tool call against the judge response schema, so the result is already a
parsed dict, and it prices the call from real token usage rather than the
model's self report. None of that is restated here.

Two things this module adds on top.

A rubric. The stock judge scores a candidate against an expected keyword and a
reference; what is wanted here is specifically reasoning quality and
faithfulness to the passages the agent actually retrieved, so the retrieved
context is handed in as the reference answer and the rubric names the two
dimensions.

A refusal to accept a silent fallback. `judge.py` degrades to the mock heuristic
judge when the key is missing or the call fails, marking `used_fallback` and
carrying on. That behaviour is right for a dashboard and wrong for a
measurement: a heuristic score reported as a judge score would quietly corrupt
the agreement numbers. Any fallback raises here instead.

The judge model is deliberately a different family from the agent's gpt-4o-mini,
so judge and agent do not share a failure mode.
"""

import os

JUDGE_PROVIDER = "anthropic"
JUDGE_MODEL = "claude-haiku-4-5"

# EvalSample caps reference_answer at 2000 characters. Retrieved context runs
# longer than that, so it is truncated and the truncation is recorded in the
# judgment rather than hidden.
_REFERENCE_LIMIT = 2000

_PLACEHOLDER_EMPTY = "(the agent returned an empty answer)"


class JudgeFellBackError(RuntimeError):
    """Raised when the judge degraded to the heuristic fallback.

    Carries the judgments completed before the failure. Those calls were paid
    for, so the caller can persist them and record the spend rather than
    throwing away both the data and the accounting.
    """

    def __init__(self, message: str, partial: list[dict] | None = None) -> None:
        super().__init__(message)
        self.partial = partial or []


def configure_judge_env() -> None:
    """Point EvalForge's settings at the judge before its config is imported.

    `app.core.config` builds its settings singleton at import time, so this has
    to run first. The API key itself is loaded separately from the env file and
    is never written down here.
    """
    os.environ["JUDGE_PROVIDER"] = JUDGE_PROVIDER
    os.environ["JUDGE_MODEL_ANTHROPIC"] = JUDGE_MODEL


def judge_rubric(category: str | None = None):
    """Reasoning quality and faithfulness, plus refusal where it applies."""
    from app.models.eval_run import RubricCriterion

    declining = category == "unanswerable_decline"
    base_weight = 0.3 if declining else 0.5

    rubric = [
        RubricCriterion(
            name="reasoning_quality",
            description=(
                "Does the answer actually address the question asked, with a correct and "
                "coherent line of reasoning, and without leaps the evidence does not support?"
            ),
            weight=base_weight,
        ),
        RubricCriterion(
            name="faithfulness",
            description=(
                "Is every factual claim supported by the retrieved passages in the reference? "
                "A specific figure, name or date that is not in the reference is a failure, "
                "even if it happens to be true."
            ),
            weight=base_weight,
        ),
    ]

    if declining:
        rubric.append(
            RubricCriterion(
                name="appropriate_refusal",
                description=(
                    "The question cannot be answered from the evidence. Does the answer say so, "
                    "or correct a false premise in the question, rather than supplying a figure, "
                    "name or date the passages do not contain? Any wording counts. Declining "
                    "is the correct behaviour here and must score well, not badly."
                ),
                weight=0.4,
            )
        )
    return rubric


def build_sample(trace: dict, task: dict):
    """Turn one trace into an EvalSample the stock judge can score."""
    from app.models.eval_run import EvalSample

    answer = (trace.get("answer") or "").strip() or _PLACEHOLDER_EMPTY
    context = (trace.get("context") or "").strip()

    # EvalForge's judge prompt tells the model to score the candidate "against
    # the expected keyword", so whatever goes in this field is something the
    # judge will look for in the answer. An instruction word like "decline"
    # therefore reads as a required string, and the first probe duly failed
    # correct refusals for not containing it. The keyword has to describe
    # content a correct answer would actually carry.
    if task["expected_answer"]:
        keyword = task["expected_answer"]["required"][0][0]
    elif task["category"] == "unanswerable_decline":
        keyword = "a statement that the available documents do not provide this"
    else:
        keyword = "a brief, direct conversational reply"

    reference = context[:_REFERENCE_LIMIT] if context else None

    return EvalSample(
        prompt=task["question"],
        expected_keyword=keyword,
        candidate_output=answer,
        scenario=task["category"],
        slice_name=trace.get("route_decision") or "unknown",
        severity="medium",
        reference_answer=reference,
        rubric=judge_rubric(task["category"]),
    )


def judge_traces(
    traces: list[dict], tasks_by_id: dict[str, dict], *, progress=None
) -> list[dict]:
    """Score every trace. Raises rather than reporting a fallback as a judgment."""
    from app.engine.judge import JudgeClient, judge_prompt_fingerprint

    client = JudgeClient()
    judgments: list[dict] = []

    for index, trace in enumerate(traces, start=1):
        task = tasks_by_id[trace["task_id"]]
        sample = build_sample(trace, task)

        response = client.evaluate(
            dataset_name="agent-loop-development",
            prompt_version=trace.get("variant", "baseline"),
            model_name=trace["settings"]["openai_model"],
            samples=[sample],
        )
        result = response.results[0]

        # Two different ways a heuristic score can arrive wearing a judge's
        # clothes, and only the first sets used_fallback.
        #
        #   used_fallback   the provider was anthropic but the key was missing
        #                   or the call failed, so judge.py substituted the mock
        #   mock provider   JUDGE_PROVIDER was never anthropic in the first
        #                   place, so evaluate() took the mock branch and
        #                   nothing was marked at all
        #
        # The second is the quieter of the two and is what a stale settings
        # singleton produces. Both are refused.
        if result.used_fallback:
            raise JudgeFellBackError(
                f"the judge fell back to the heuristic scorer on {trace['task_id']} "
                f"({index} of {len(traces)}): {result.feedback}. That judgment was not "
                "recorded. Fix the credential or the endpoint and run again rather than "
                "reporting heuristic scores as judge scores.",
                partial=judgments,
            )
        if result.judge_provider != JUDGE_PROVIDER or result.judge_model != JUDGE_MODEL:
            raise JudgeFellBackError(
                f"expected {JUDGE_MODEL} via {JUDGE_PROVIDER} but the judge reported "
                f"{result.judge_model!r} via {result.judge_provider!r} on "
                f"{trace['task_id']} ({index} of {len(traces)}). EvalForge's settings "
                "singleton is built on first import of app.core.config, so the judge "
                "environment must be configured before any module that imports it.",
                partial=judgments,
            )

        judgments.append(
            {
                "task_id": trace["task_id"],
                "category": task["category"],
                "variant": trace.get("variant", "baseline"),
                "judge_provider": result.judge_provider,
                "judge_model": result.judge_model,
                "judge_prompt_fingerprint": judge_prompt_fingerprint(),
                "judge_score": result.judge_score,
                "judge_passed": result.passed,
                "judge_reasoning": result.judge_reasoning,
                "criterion_scores": result.criterion_scores,
                "groundedness_score": result.groundedness_score,
                "unsupported_terms": result.unsupported_terms,
                "cost_usd": result.cost_usd,
                "latency_ms": result.latency_ms,
                "reference_was_truncated": bool(
                    trace.get("context") and len(trace["context"]) > _REFERENCE_LIMIT
                ),
                "reference_chars": min(len(trace.get("context") or ""), _REFERENCE_LIMIT),
            }
        )
        if progress is not None:
            progress(index, len(traces), judgments[-1])

    return judgments


def judge_label(judgment: dict) -> bool:
    """The single pass or fail this layer contributes to agreement analysis."""
    return bool(judgment["judge_passed"])
