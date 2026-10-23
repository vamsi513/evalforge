"""Checks on how a trace is turned into something the stock judge can score.

The first judge probe failed two correct refusals because expected_keyword was
set to the literal word "decline". EvalForge's judge prompt instructs the model
to score the candidate "against the expected keyword", so that field is a
string the judge goes looking for, not a label for the kind of task. The tests
below exist so that cannot come back.

Nothing here calls a model. build_sample and judge_rubric are pure.
"""

import pytest

from agent_loop.judging import (
    JUDGE_MODEL,
    JUDGE_PROVIDER,
    JudgeFellBackError,
    build_sample,
    judge_rubric,
)


def _task(**overrides) -> dict:
    base = {
        "id": "msr-006",
        "category": "multi_step_retrieval",
        "question": "Name the three stages of RLHF.",
        "expected_route": "retrieval",
        "expected_answer": {"required": [["supervised fine-tuning", "sft"], ["ppo"]]},
        "expected_behavior": None,
        "must_not_contain": [],
        "source_docs": ["Reinforcement Learning from Human Feedback (RLHF)"],
    }
    base.update(overrides)
    return base


def _trace(**overrides) -> dict:
    base = {
        "task_id": "msr-006",
        "answer": "The three stages are supervised fine-tuning, reward modelling and PPO.",
        "context": "[Source 1] The process has three stages: SFT, reward model training, PPO.",
        "route_decision": "retrieval",
        "variant": "baseline",
        "settings": {"openai_model": "gpt-4o-mini"},
    }
    base.update(overrides)
    return base


# --- the regression --------------------------------------------------------------


def test_a_decline_task_does_not_ask_the_judge_to_find_the_word_decline() -> None:
    """The exact bug: "decline" as a keyword made correct refusals score zero."""
    task = _task(
        category="unanswerable_decline",
        expected_answer=None,
        expected_behavior="Decline. The documents give no training cost.",
    )
    sample = build_sample(_trace(answer="The context does not provide a training cost."), task)
    assert sample.expected_keyword != "decline"
    assert "do not provide" in sample.expected_keyword


def test_a_decline_task_gets_a_criterion_that_rewards_refusing() -> None:
    names = [criterion.name for criterion in judge_rubric("unanswerable_decline")]
    assert "appropriate_refusal" in names
    criterion = next(c for c in judge_rubric("unanswerable_decline") if c.name == "appropriate_refusal")
    assert "must score well" in criterion.description


def test_a_non_decline_task_has_no_refusal_criterion() -> None:
    """Rewarding refusal on an answerable question would invert the test."""
    for category in ("multi_step_retrieval", "direct_no_tools", "tool_selection"):
        names = [criterion.name for criterion in judge_rubric(category)]
        assert "appropriate_refusal" not in names


def test_a_behaviour_only_task_does_not_ask_the_judge_to_find_a_route_name() -> None:
    """An earlier version passed "direct" here, which is a routing decision,
    not anything a greeting would contain."""
    task = _task(
        category="direct_no_tools",
        expected_answer=None,
        expected_behavior="Greet the user briefly.",
        expected_route="direct",
    )
    sample = build_sample(_trace(answer="Hello, how can I help?", context=""), task)
    assert sample.expected_keyword != "direct"
    assert "conversational" in sample.expected_keyword


def test_an_answerable_task_uses_a_required_fact_as_the_keyword() -> None:
    sample = build_sample(_trace(), _task())
    assert sample.expected_keyword == "supervised fine-tuning"


# --- the rest of the sample -------------------------------------------------------


def test_the_retrieved_passages_become_the_reference() -> None:
    """Faithfulness is judged against what the agent was actually shown."""
    sample = build_sample(_trace(), _task())
    assert "three stages" in sample.reference_answer


def test_a_run_with_no_passages_has_no_reference() -> None:
    sample = build_sample(_trace(context=""), _task())
    assert sample.reference_answer is None


def test_an_over_long_reference_is_truncated_to_fit_the_sample_cap() -> None:
    """EvalSample caps reference_answer at 2000 characters, and real retrieved
    context runs longer than that."""
    sample = build_sample(_trace(context="x" * 5000), _task())
    assert len(sample.reference_answer) == 2000


def test_an_empty_answer_becomes_a_placeholder_rather_than_failing_validation() -> None:
    """EvalSample requires a non-empty candidate_output, and an agent that
    returned nothing is a result worth judging, not a crash."""
    sample = build_sample(_trace(answer=""), _task())
    assert sample.candidate_output == "(the agent returned an empty answer)"


def test_the_category_and_route_are_carried_as_scenario_and_slice() -> None:
    sample = build_sample(_trace(), _task())
    assert sample.scenario == "multi_step_retrieval"
    assert sample.slice_name == "retrieval"


def test_both_rubric_criteria_are_always_present() -> None:
    for category in ("multi_step_retrieval", "unanswerable_decline", "direct_no_tools"):
        names = [criterion.name for criterion in judge_rubric(category)]
        assert "reasoning_quality" in names
        assert "faithfulness" in names


def test_rubric_weights_stay_inside_the_schema_bounds() -> None:
    for category in ("multi_step_retrieval", "unanswerable_decline"):
        for criterion in judge_rubric(category):
            assert 0.0 < criterion.weight <= 1.0


# --- the fallback guard -----------------------------------------------------------


def test_the_configured_judge_is_a_different_family_from_the_agent() -> None:
    assert JUDGE_PROVIDER == "anthropic"
    assert JUDGE_MODEL.startswith("claude-")


def test_the_fallback_error_carries_the_judgments_already_paid_for() -> None:
    error = JudgeFellBackError("boom", partial=[{"task_id": "a"}, {"task_id": "b"}])
    assert len(error.partial) == 2


def test_the_fallback_error_defaults_to_an_empty_partial_list() -> None:
    assert JudgeFellBackError("boom").partial == []


@pytest.mark.parametrize("category", ["unanswerable_decline", "multi_step_retrieval"])
def test_build_sample_never_returns_an_empty_keyword(category) -> None:
    task = _task(category=category, expected_answer=None, expected_behavior="Something.")
    assert build_sample(_trace(), task).expected_keyword.strip()
