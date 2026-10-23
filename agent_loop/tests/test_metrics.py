"""Checks on the agreement and comparison statistics.

Most of these pin behaviour at the edges, because that is where an agreement
number quietly becomes wrong: perfect agreement by luck, a rater who never
changes their answer, zero discordant pairs, an interval that should straddle
zero and does not.
"""

import pytest

from agent_loop.metrics import (
    PASS_THRESHOLD,
    agreement_report,
    bootstrap_kappa_ci,
    cohens_kappa,
    mcnemar_exact,
    paired_difference_ci,
    percent_agreement,
)


def test_the_reused_threshold_is_the_repository_wide_one() -> None:
    """Imported from the existing judge analysis script, not restated here."""
    assert PASS_THRESHOLD == 0.7


# --- agreement ------------------------------------------------------------------


def test_identical_labels_agree_completely() -> None:
    labels = [True, False, True, True, False]
    assert percent_agreement(labels, labels) == 1.0
    assert cohens_kappa(labels, labels) == 1.0


def test_opposite_labels_disagree_completely() -> None:
    a = [True, False, True, False]
    b = [False, True, False, True]
    assert percent_agreement(a, b) == 0.0
    assert cohens_kappa(a, b) < 0


def test_chance_agreement_is_discounted() -> None:
    """Two raters who both almost always say pass agree often by luck.

    Percent agreement looks high; kappa should not.
    """
    a = [True] * 18 + [False, True]
    b = [True] * 18 + [True, False]
    assert percent_agreement(a, b) == 0.9
    assert cohens_kappa(a, b) < 0.5


def test_percent_agreement_on_an_empty_list_is_not_a_number() -> None:
    value = percent_agreement([], [])
    assert value != value


def test_agreement_report_counts_the_four_cells() -> None:
    rule = [True, True, False, False]
    human = [True, False, True, False]
    report = agreement_report("rule", rule, "human", human)
    assert report["n"] == 4
    assert report["confusion"]["both_pass"] == 1
    assert report["confusion"]["both_fail"] == 1
    assert report["confusion"]["rule_pass_human_fail"] == 1
    assert report["confusion"]["rule_fail_human_pass"] == 1


def test_the_report_names_which_pair_it_describes() -> None:
    report = agreement_report("judge", [True], "human", [True])
    assert report["pair"] == "judge vs human"


# --- kappa interval -------------------------------------------------------------


def test_the_kappa_interval_brackets_its_point_estimate() -> None:
    a = [True, True, True, False, False, False, True, False, True, False] * 3
    b = [True, True, False, False, False, True, True, False, True, False] * 3
    result = bootstrap_kappa_ci(a, b)
    assert result["ci_95_low"] <= result["point_estimate"] <= result["ci_95_high"]


def test_the_kappa_interval_is_deterministic_for_a_fixed_seed() -> None:
    a = [True, False] * 15
    b = [True, True, False, False] * 7 + [True, False]
    assert bootstrap_kappa_ci(a, b, seed=1) == bootstrap_kappa_ci(a, b, seed=1)


def test_a_small_imperfect_sample_gives_a_wide_interval() -> None:
    """The point of reporting the interval at all.

    Eight items with two disagreements: the point estimate looks respectable
    and the interval shows how little it is worth.
    """
    a = [True, True, True, True, False, False, False, False]
    b = [True, True, True, False, True, False, False, False]
    result = bootstrap_kappa_ci(a, b)
    assert result["ci_95_high"] - result["ci_95_low"] > 0.5


def test_perfect_agreement_gives_a_zero_width_interval() -> None:
    """Every resample of two identical label lists agrees perfectly too.

    EvalForge's _cohens_kappa returns 1.0 rather than NaN in that degenerate
    case, so nothing is dropped and the interval collapses onto the estimate.
    """
    a = [True] * 9 + [False]
    result = bootstrap_kappa_ci(a, list(a), n_resamples=500)
    assert result["point_estimate"] == 1.0
    assert result["ci_95_low"] == result["ci_95_high"] == 1.0
    assert result["undefined_resamples"] == 0


def test_an_empty_comparison_returns_nothing_rather_than_a_number() -> None:
    result = bootstrap_kappa_ci([], [])
    assert result["point_estimate"] is None
    assert result["n"] == 0


# --- McNemar --------------------------------------------------------------------


def test_no_change_gives_no_discordant_pairs_and_p_of_one() -> None:
    outcomes = [True, False, True, False]
    result = mcnemar_exact(outcomes, outcomes)
    assert result["discordant"] == 0
    assert result["p_value"] == 1.0


def test_only_discordant_pairs_count() -> None:
    before = [False, False, True, True, True]
    after = [True, True, True, True, True]
    result = mcnemar_exact(before, after)
    assert result["improved_fail_to_pass"] == 2
    assert result["regressed_pass_to_fail"] == 0
    assert result["discordant"] == 2


def test_a_clear_one_sided_improvement_is_significant() -> None:
    before = [False] * 12 + [True] * 8
    after = [True] * 12 + [True] * 8
    result = mcnemar_exact(before, after)
    assert result["improved_fail_to_pass"] == 12
    assert result["p_value"] < 0.001


def test_a_balanced_swap_is_not_significant() -> None:
    """Five fixed and five broken is exactly what the null predicts."""
    before = [False] * 5 + [True] * 5
    after = [True] * 5 + [False] * 5
    result = mcnemar_exact(before, after)
    assert result["improved_fail_to_pass"] == 5
    assert result["regressed_pass_to_fail"] == 5
    assert result["p_value"] == 1.0


def test_a_regression_is_reported_not_hidden() -> None:
    before = [True] * 10
    after = [False] * 4 + [True] * 6
    result = mcnemar_exact(before, after)
    assert result["regressed_pass_to_fail"] == 4
    assert result["improved_fail_to_pass"] == 0


def test_mismatched_lengths_are_refused() -> None:
    with pytest.raises(ValueError, match="same number"):
        mcnemar_exact([True, False], [True])


# --- paired difference ----------------------------------------------------------


def test_the_difference_is_after_minus_before() -> None:
    before = [False, False, True, True]
    after = [True, True, True, True]
    result = paired_difference_ci(before, after)
    assert result["accuracy_before"] == 0.5
    assert result["accuracy_after"] == 1.0
    assert result["difference"] == 0.5


def test_an_unchanged_run_has_a_difference_of_zero() -> None:
    outcomes = [True, False, True, False, True]
    result = paired_difference_ci(outcomes, outcomes)
    assert result["difference"] == 0.0
    assert result["ci_95_low"] == 0.0
    assert result["ci_95_high"] == 0.0


def test_a_noisy_small_change_has_an_interval_that_includes_zero() -> None:
    """A one-task improvement on twenty tasks is not evidence of anything."""
    before = [True] * 19 + [False]
    after = [True] * 20
    result = paired_difference_ci(before, after)
    assert result["ci_95_low"] <= 0 <= result["ci_95_high"]


def test_a_regression_shows_a_negative_difference() -> None:
    before = [True] * 10
    after = [False] * 5 + [True] * 5
    result = paired_difference_ci(before, after)
    assert result["difference"] == -0.5
    assert result["ci_95_high"] < 0


def test_the_interval_is_deterministic_for_a_fixed_seed() -> None:
    before = [True, False] * 10
    after = [True, True] * 10
    assert paired_difference_ci(before, after, seed=3) == paired_difference_ci(
        before, after, seed=3
    )


def test_mismatched_lengths_are_refused_here_too() -> None:
    with pytest.raises(ValueError, match="same number"):
        paired_difference_ci([True], [True, False])
