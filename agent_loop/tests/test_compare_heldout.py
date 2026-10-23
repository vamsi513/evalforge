"""Checks on the before and after comparison.

The risk this guards against is a fix that raises the average while quietly
breaking a slice. A mean hides that; these tests make sure the report does not.
"""

import pytest

from agent_loop.scripts.compare_heldout import _compare

CATEGORIES = {
    "a1": "multi_step_retrieval",
    "a2": "multi_step_retrieval",
    "b1": "direct_no_tools",
    "b2": "direct_no_tools",
}


def _outcomes(**kwargs) -> dict[str, bool]:
    return dict(kwargs)


def test_only_tasks_present_in_both_runs_are_compared() -> None:
    """A task missing from one side cannot be a paired observation."""
    before = _outcomes(a1=True, a2=False, b1=True)
    after = _outcomes(a1=True, a2=True)
    result = _compare(before, after, CATEGORIES)
    assert result["n"] == 2


def test_no_shared_tasks_is_refused() -> None:
    with pytest.raises(SystemExit, match="share no tasks"):
        _compare({"a1": True}, {"b1": True}, CATEGORIES)


def test_a_clean_improvement_is_reported_as_one() -> None:
    before = _outcomes(a1=False, a2=False, b1=True, b2=True)
    after = _outcomes(a1=True, a2=True, b1=True, b2=True)
    result = _compare(before, after, CATEGORIES)
    assert result["overall"]["difference"] == 0.5
    assert result["mcnemar"]["improved_fail_to_pass"] == 2
    assert result["mcnemar"]["regressed_pass_to_fail"] == 0
    assert result["tasks_changed"]["fixed"] == ["a1", "a2"]
    assert result["tasks_changed"]["broken"] == []


def test_a_category_that_got_worse_is_named_even_when_the_average_rose() -> None:
    """The case this report exists to catch.

    Retrieval gains two, direct loses one. The mean improves, and shipping it
    would still be a regression for anyone who only asks direct questions.
    """
    before = _outcomes(a1=False, a2=False, b1=True, b2=True)
    after = _outcomes(a1=True, a2=True, b1=False, b2=True)
    result = _compare(before, after, CATEGORIES)

    assert result["overall"]["difference"] > 0
    worse = result["categories_that_got_worse"]
    assert [w["category"] for w in worse] == ["direct_no_tools"]
    assert worse[0]["difference"] == -0.5
    assert result["tasks_changed"]["broken"] == ["b1"]


def test_no_change_produces_a_zero_difference_and_no_regressions() -> None:
    outcomes = _outcomes(a1=True, a2=False, b1=True, b2=False)
    result = _compare(outcomes, dict(outcomes), CATEGORIES)
    assert result["overall"]["difference"] == 0.0
    assert result["mcnemar"]["discordant"] == 0
    assert result["mcnemar"]["p_value"] == 1.0
    assert result["categories_that_got_worse"] == []


def test_an_offsetting_swap_shows_zero_overall_but_names_the_damage() -> None:
    """One fixed and one broken nets to nothing, and is not nothing."""
    before = _outcomes(a1=False, a2=True, b1=True, b2=True)
    after = _outcomes(a1=True, a2=False, b1=True, b2=True)
    result = _compare(before, after, CATEGORIES)

    assert result["overall"]["difference"] == 0.0
    assert result["mcnemar"]["improved_fail_to_pass"] == 1
    assert result["mcnemar"]["regressed_pass_to_fail"] == 1
    assert result["tasks_changed"]["fixed"] == ["a1"]
    assert result["tasks_changed"]["broken"] == ["a2"]


def test_per_category_counts_are_reported_as_counts_not_only_rates() -> None:
    before = _outcomes(a1=False, a2=False, b1=True, b2=True)
    after = _outcomes(a1=True, a2=False, b1=True, b2=True)
    entry = _compare(before, after, CATEGORIES)["by_category"]["multi_step_retrieval"]
    assert entry["n"] == 2
    assert entry["before_passed"] == 0
    assert entry["after_passed"] == 1


def test_a_small_improvement_has_an_interval_that_includes_zero() -> None:
    """Two tasks changing out of four is not evidence of anything."""
    before = _outcomes(a1=False, a2=True, b1=True, b2=True)
    after = _outcomes(a1=True, a2=True, b1=True, b2=True)
    overall = _compare(before, after, CATEGORIES)["overall"]
    assert overall["ci_95_low"] <= 0 <= overall["ci_95_high"]


def test_an_unknown_task_category_does_not_crash_the_report() -> None:
    result = _compare({"zz": True}, {"zz": False}, {})
    assert "unknown" in result["by_category"]
