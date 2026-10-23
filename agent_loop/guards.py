"""The sub-question retrieval guard.

## Why this and not the setting

The first candidate fix was AgentIQ's own `ENABLE_QUERY_REWRITING`. On the 90
development tasks it changed nothing: the retrieved context was byte for byte
identical on every retrieval failure, because `retriever_node` merges the
paraphrase results and then cuts to the best 3 chunks by score, and the
original phrasing's chunks already scored highest. It cost one extra model call
per retrieval run and fixed nothing. That candidate is recorded as rejected at
development validation.

What the traces actually show is a different problem. The corpus is 50 chunks
and the retriever keeps 3. The failing questions are multi part: they ask for
two or three facts that live in different chunks, and a single embedding of the
whole question matches the average of those parts rather than any one of them,
so none of the right chunks makes the top 3.

Querying per part fixes that, and it can be checked without the agent. Asking
FAISS directly with one sub question at a time surfaced facts that the whole
question missed on three of three failures tested, including both facts for
`msr-039`. The mechanism was verified before any of this was built.

## What the guard does

Run the question normally. If the agent took the retrieval route and its answer
says the evidence is missing, decompose the question into standalone sub
questions and run each one through the same graph, then present the sub answers
together.

It is a guard step in this wrapper. AgentIQ is unchanged, and the decision to
retry uses only the agent's own output, never anything from the task
definition, so it is a thing the system could actually do in production.

## What could go wrong

A question that genuinely cannot be answered will decline, trigger the guard,
and be asked again in pieces. If a piece then finds something to say, a correct
refusal could turn into an answer, which would be a real regression on the
decline tasks. That is the main risk and development validation is where it
shows up.
"""

import re

# Decomposition is capped: more sub questions means more calls and more chance
# of drifting away from what was asked.
MAX_SUB_QUESTIONS = 3
MIN_SUB_QUESTION_CHARS = 12

_DECOMPOSE_PROMPT = (
    "Split this question into the separate factual questions it is really asking. "
    "Each one must stand alone, naming its own subject, so it can be answered "
    "without reading the others. Output one question per line, no numbering, no "
    "commentary. If the question only asks one thing, output it unchanged.\n\n"
    "Question: {question}"
)


def needs_retry(trace: dict) -> bool:
    """Whether the guard should fire for this run.

    Only on the retrieval route, and only when the agent itself reported that
    its context did not carry the answer. Nothing from the task is consulted.
    """
    from agent_loop.rules import declines

    if trace.get("route_decision") != "retrieval":
        return False
    if trace.get("invoke_exception"):
        return False
    declined, _ = declines(trace.get("answer") or "")
    return declined


def parse_sub_questions(text: str, original: str) -> list[str]:
    """Read the decomposition back, defensively."""
    lines = [
        re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        for line in (text or "").splitlines()
    ]
    questions = [
        line for line in lines if len(line) >= MIN_SUB_QUESTION_CHARS and line != original
    ]
    # Deduplicate while keeping order.
    seen: set[str] = set()
    unique = []
    for question in questions:
        key = question.lower()
        if key not in seen:
            seen.add(key)
            unique.append(question)
    return unique[:MAX_SUB_QUESTIONS]


def decompose(question: str, llm) -> list[str]:
    """Ask the model to split the question. Returns [] when it does not split."""
    try:
        response = llm.invoke([{"role": "user", "content": _DECOMPOSE_PROMPT.format(question=question)}])
    except Exception:
        # A failed decomposition must leave the original answer standing, not
        # take the run down with it.
        return []
    parts = parse_sub_questions(getattr(response, "content", "") or "", question)
    return parts if len(parts) >= 2 else []


def compose_answer(parts: list[tuple[str, str]]) -> str:
    """Join the sub answers into one response."""
    return "\n\n".join(f"**{question}**\n\n{answer}".strip() for question, answer in parts)
