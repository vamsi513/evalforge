"""Checks on the sub question guard.

Two properties matter most. The guard must decide to fire from the agent's own
output and nothing else, because a guard that consulted the expected answer
would be cheating rather than fixing. And a failed decomposition must leave the
original answer standing, because a fix that can turn a working run into a
crash is worse than no fix.
"""

import pytest

from agent_loop.guards import (
    MAX_SUB_QUESTIONS,
    compose_answer,
    decompose,
    needs_retry,
    parse_sub_questions,
)


def _trace(**overrides) -> dict:
    base = {
        "route_decision": "retrieval",
        "answer": "The provided context does not contain information about this.",
        "invoke_exception": None,
    }
    base.update(overrides)
    return base


class _Reply:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeLLM:
    def __init__(self, content: str = "", raises: bool = False) -> None:
        self.content = content
        self.raises = raises
        self.calls = 0

    def invoke(self, messages):
        self.calls += 1
        if self.raises:
            raise RuntimeError("provider down")
        return _Reply(self.content)


# --- when the guard fires --------------------------------------------------------


def test_it_fires_on_a_retrieval_run_that_reports_missing_evidence() -> None:
    assert needs_retry(_trace()) is True


def test_it_does_not_fire_on_a_retrieval_run_that_answered() -> None:
    assert needs_retry(_trace(answer="BERT-Base has 110M parameters.")) is False


def test_it_does_not_fire_off_the_retrieval_route() -> None:
    """A direct or web answer has no retrieved chunks to re-query."""
    for route in ("direct", "web_search", "blocked"):
        assert needs_retry(_trace(route_decision=route)) is False


def test_it_does_not_fire_when_the_run_crashed() -> None:
    assert needs_retry(_trace(invoke_exception="RuntimeError: boom")) is False


def test_it_does_not_fire_on_an_empty_answer() -> None:
    assert needs_retry(_trace(answer="")) is False


def test_the_decision_uses_only_the_trace() -> None:
    """needs_retry takes one argument, the trace. There is no path by which a
    task's expected answer could influence whether the guard fires."""
    import inspect

    assert list(inspect.signature(needs_retry).parameters) == ["trace"]


# --- decomposition ---------------------------------------------------------------


def test_a_multi_part_question_decomposes() -> None:
    llm = _FakeLLM("What is the ECE of GPT-4?\nWhat is the ECE of LLaMA 2 70B?")
    assert len(decompose("What ECE do GPT-4 and LLaMA 2 70B achieve?", llm)) == 2


def test_a_single_part_question_does_not_decompose() -> None:
    """One sub question is not a decomposition, and re-running the same query
    would just spend money to get the same answer."""
    llm = _FakeLLM("What is the ECE of GPT-4?")
    assert decompose("What is the ECE of GPT-4?", llm) == []


def test_a_provider_failure_leaves_the_original_answer_standing() -> None:
    assert decompose("anything", _FakeLLM(raises=True)) == []


def test_decomposition_is_capped() -> None:
    llm = _FakeLLM("\n".join(f"Sub question number {i} about something?" for i in range(10)))
    assert len(decompose("a big question", llm)) == MAX_SUB_QUESTIONS


def test_numbering_and_bullets_are_stripped() -> None:
    parsed = parse_sub_questions(
        "1. What is the ECE of GPT-4?\n- What is the ECE of LLaMA 2 70B?", "orig"
    )
    assert parsed == ["What is the ECE of GPT-4?", "What is the ECE of LLaMA 2 70B?"]


def test_duplicates_are_dropped() -> None:
    parsed = parse_sub_questions(
        "What is the ECE of GPT-4?\nwhat is the ece of gpt-4?\nWhat about LLaMA 2 70B then?",
        "orig",
    )
    assert len(parsed) == 2


def test_an_echo_of_the_original_is_not_a_sub_question() -> None:
    original = "What ECE do GPT-4 and LLaMA 2 70B achieve?"
    assert parse_sub_questions(f"{original}\nWhat is the ECE of GPT-4?", original) == [
        "What is the ECE of GPT-4?"
    ]


def test_fragments_too_short_to_be_questions_are_dropped() -> None:
    assert parse_sub_questions("ok\nyes\nWhat is the ECE of GPT-4?", "orig") == [
        "What is the ECE of GPT-4?"
    ]


def test_empty_output_decomposes_to_nothing() -> None:
    assert parse_sub_questions("", "orig") == []


# --- composition -----------------------------------------------------------------


def test_sub_answers_are_presented_with_their_questions() -> None:
    composed = compose_answer([("What is A?", "A is 1."), ("What is B?", "B is 2.")])
    assert "What is A?" in composed
    assert "A is 1." in composed
    assert "B is 2." in composed


def test_composition_of_nothing_is_empty() -> None:
    assert compose_answer([]) == ""


@pytest.mark.parametrize(
    "answer",
    [
        "The context does not contain this.",
        "I cannot answer that from the available documents.",
        "No information about this is provided.",
        "The documents do not mention it.",
    ],
)
def test_common_refusal_phrasings_all_trigger(answer) -> None:
    assert needs_retry(_trace(answer=answer)) is True
