"""Agreement and comparison statistics.

Cohen's kappa, the bootstrap and Pearson's r are not reimplemented here. They
already exist in scripts/analyze_judge_agreement.py, along with this
repository's pass threshold of 0.7, and this module imports them so there is
one definition of each rather than two that can drift apart.

What is added is the part that script does not cover:

  bootstrap_kappa_ci     a confidence interval on kappa itself, which needs the
                         pairs resampled and kappa recomputed, not the mean of
                         a list of numbers
  mcnemar_exact          the paired before and after test for phase 5
  paired_difference_ci   a bootstrap interval on the accuracy difference

Kappa is reported with its interval because on 60 items a point estimate of
agreement is not worth much on its own.
"""

import random
from statistics import mean

# One definition of each, imported rather than restated.
from scripts.analyze_judge_agreement import (  # noqa: F401
    _PASS_THRESHOLD as PASS_THRESHOLD,
)
from scripts.analyze_judge_agreement import (
    _bootstrap_ci as bootstrap_mean_ci,
)
from scripts.analyze_judge_agreement import (
    _cohens_kappa as cohens_kappa,
)
from scripts.analyze_judge_agreement import (
    _pearson_r as pearson_r,
)

DEFAULT_RESAMPLES = 2000
DEFAULT_SEED = 42


def percent_agreement(labels_a: list[bool], labels_b: list[bool]) -> float:
    if not labels_a:
        return float("nan")
    return sum(1 for a, b in zip(labels_a, labels_b) if a == b) / len(labels_a)


def bootstrap_kappa_ci(
    labels_a: list[bool],
    labels_b: list[bool],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Percentile bootstrap interval on Cohen's kappa.

    Pairs are resampled together, since the two raters' labels for one item are
    not independent. Resamples where kappa is undefined, which happens when a
    resample is all one class, are dropped and counted rather than coerced to a
    number, because a degenerate resample is missing information and not a
    kappa of zero.
    """
    n = len(labels_a)
    if n == 0:
        return {"point_estimate": None, "ci_95_low": None, "ci_95_high": None, "n": 0}

    rng = random.Random(seed)
    values: list[float] = []
    undefined = 0
    for _ in range(n_resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        kappa = cohens_kappa([labels_a[i] for i in indices], [labels_b[i] for i in indices])
        if kappa != kappa:  # NaN
            undefined += 1
            continue
        values.append(kappa)

    point = cohens_kappa(labels_a, labels_b)

    # When one rater never varies, kappa collapses to 0 however well the two
    # actually agree, because there is no variance for chance correction to
    # work against. That is a property of the sample, not a disagreement, and
    # reporting 0.0 without saying so invites exactly the wrong reading.
    constant = []
    if len(set(labels_a)) == 1:
        constant.append("a")
    if len(set(labels_b)) == 1:
        constant.append("b")

    if not values:
        return {
            "point_estimate": None if point != point else round(point, 4),
            "ci_95_low": None,
            "ci_95_high": None,
            "n": n,
            "n_resamples": n_resamples,
            "undefined_resamples": undefined,
            "constant_rater": constant or None,
        }

    values.sort()
    low = round(values[int(0.025 * len(values))], 4)
    high = round(values[min(len(values) - 1, int(0.975 * len(values)))], 4)
    return {
        "point_estimate": None if point != point else round(point, 4),
        "ci_95_low": low,
        "ci_95_high": high,
        "n": n,
        "n_resamples": n_resamples,
        "undefined_resamples": undefined,
        "constant_rater": constant or None,
        # An interval this wide carries no information about the true value.
        "uninformative": (high - low) >= 0.8,
    }


def agreement_report(
    name_a: str,
    labels_a: list[bool],
    name_b: str,
    labels_b: list[bool],
    *,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Percent agreement and kappa with an interval, plus the confusion counts."""
    both_true = sum(1 for a, b in zip(labels_a, labels_b) if a and b)
    both_false = sum(1 for a, b in zip(labels_a, labels_b) if not a and not b)
    a_only = sum(1 for a, b in zip(labels_a, labels_b) if a and not b)
    b_only = sum(1 for a, b in zip(labels_a, labels_b) if not a and b)

    return {
        "pair": f"{name_a} vs {name_b}",
        "n": len(labels_a),
        "percent_agreement": round(percent_agreement(labels_a, labels_b), 4),
        "cohens_kappa": bootstrap_kappa_ci(labels_a, labels_b, seed=seed),
        "confusion": {
            "both_pass": both_true,
            "both_fail": both_false,
            f"{name_a}_pass_{name_b}_fail": a_only,
            f"{name_a}_fail_{name_b}_pass": b_only,
        },
    }


def mcnemar_exact(before: list[bool], after: list[bool]) -> dict:
    """Exact McNemar test on paired pass or fail outcomes.

    Only the discordant pairs carry information: items that changed from fail to
    pass, and from pass to fail. Under the null they are equally likely, so the
    two-sided exact binomial test on those counts is the test. The exact form is
    used rather than the chi-square approximation because the discordant count
    here is small.
    """
    if len(before) != len(after):
        raise ValueError("paired test needs the same number of before and after outcomes")

    improved = sum(1 for b, a in zip(before, after) if not b and a)
    regressed = sum(1 for b, a in zip(before, after) if b and not a)
    discordant = improved + regressed

    if discordant == 0:
        p_value = 1.0
    else:
        from scipy.stats import binomtest

        p_value = binomtest(improved, discordant, 0.5, alternative="two-sided").pvalue

    return {
        "n_pairs": len(before),
        "improved_fail_to_pass": improved,
        "regressed_pass_to_fail": regressed,
        "discordant": discordant,
        "p_value": round(float(p_value), 6),
        "test": "exact McNemar, two sided binomial on discordant pairs",
    }


def paired_difference_ci(
    before: list[bool],
    after: list[bool],
    *,
    n_resamples: int = DEFAULT_RESAMPLES,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Bootstrap interval on the accuracy difference, after minus before.

    Items are resampled as pairs, which is what keeps the interval honest about
    the two runs being on the same tasks.
    """
    if len(before) != len(after):
        raise ValueError("paired comparison needs the same number of outcomes")
    n = len(before)
    if n == 0:
        return {"difference": None, "ci_95_low": None, "ci_95_high": None, "n": 0}

    rng = random.Random(seed)
    differences: list[float] = []
    for _ in range(n_resamples):
        indices = [rng.randrange(n) for _ in range(n)]
        differences.append(
            mean(after[i] for i in indices) - mean(before[i] for i in indices)
        )
    differences.sort()

    return {
        "accuracy_before": round(mean(before), 4),
        "accuracy_after": round(mean(after), 4),
        "difference": round(mean(after) - mean(before), 4),
        "ci_95_low": round(differences[int(0.025 * n_resamples)], 4),
        "ci_95_high": round(differences[min(n_resamples - 1, int(0.975 * n_resamples))], 4),
        "n": n,
        "n_resamples": n_resamples,
    }
