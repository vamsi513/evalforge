"""
scripts/analyze_judge_agreement.py — Statistical analysis of a completed
run_judge_benchmark.py result file: percentage agreement, Cohen's kappa
(local judge vs each paid judge, on the same cases), and a bootstrap 95%
confidence interval on each provider's average score.

Agreement/kappa are computed on the pass/fail label (score >= 0.7, same
threshold judge.py itself uses), since that's the natural binary decision a
judge makes -- raw score correlation is also reported for reference.

Usage:
    python -m scripts.analyze_judge_agreement path/to/results.json
"""

import argparse
import json
import math
import random
from collections import Counter
from statistics import mean

_PASS_THRESHOLD = 0.7


def _cohens_kappa(labels_a: list[bool], labels_b: list[bool]) -> float:
    n = len(labels_a)
    if n == 0:
        return float("nan")
    po = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n

    p_a_true = sum(labels_a) / n
    p_b_true = sum(labels_b) / n
    pe = p_a_true * p_b_true + (1 - p_a_true) * (1 - p_b_true)

    if pe == 1.0:
        return 1.0 if po == 1.0 else float("nan")
    return (po - pe) / (1 - pe)


def _pearson_r(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx, my = mean(xs), mean(ys)
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    varx = sum((x - mx) ** 2 for x in xs)
    vary = sum((y - my) ** 2 for y in ys)
    if varx == 0 or vary == 0:
        return float("nan")
    return cov / (varx * vary) ** 0.5


def _bootstrap_ci(values: list[float], n_resamples: int = 2000, seed: int = 42) -> dict:
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        resample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(mean(resample))
    means.sort()
    lo_idx = int(0.025 * n_resamples)
    hi_idx = int(0.975 * n_resamples) - 1
    return {
        "point_estimate": round(mean(values), 4),
        "ci_95_low": round(means[lo_idx], 4),
        "ci_95_high": round(means[hi_idx], 4),
        "n_resamples": n_resamples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results_path")
    args = parser.parse_args()

    with open(args.results_path) as f:
        data = json.load(f)

    records = [r for r in data["records"] if r["error"] is None and r["used_fallback"] is False]

    by_provider: dict[str, dict[str, float]] = {}
    for r in records:
        by_provider.setdefault(r["provider"], {})[r["prompt"]] = r["score"]

    providers = sorted(by_provider.keys())
    print(f"Providers with real results: {providers}")
    for p in providers:
        print(f"  {p}: n={len(by_provider[p])}")

    print("\n" + "=" * 70)
    print("BOOTSTRAP 95% CI ON AVERAGE SCORE (per provider)")
    print("=" * 70)
    ci_results = {}
    for p in providers:
        scores = list(by_provider[p].values())
        ci = _bootstrap_ci(scores)
        ci_results[p] = ci
        print(f"{p}: avg={ci['point_estimate']} 95% CI=[{ci['ci_95_low']}, {ci['ci_95_high']}] (n={len(scores)}, {ci['n_resamples']} resamples)")

    if "ollama" not in by_provider:
        print("\nNo local (ollama) results in this file -- skipping agreement/kappa (nothing to compare against).")
        return

    print("\n" + "=" * 70)
    print("AGREEMENT: local (ollama) vs each paid provider")
    print(f"(pass/fail label, threshold score >= {_PASS_THRESHOLD}; pearson_r on raw scores for reference)")
    print("=" * 70)
    agreement_results = {}
    local_prompts = set(by_provider["ollama"].keys())
    for p in providers:
        if p == "ollama":
            continue
        shared_prompts = sorted(local_prompts & set(by_provider[p].keys()))
        if not shared_prompts:
            print(f"{p}: no overlapping cases with ollama")
            continue

        local_scores = [by_provider["ollama"][pr] for pr in shared_prompts]
        paid_scores = [by_provider[p][pr] for pr in shared_prompts]
        local_pass = [s >= _PASS_THRESHOLD for s in local_scores]
        paid_pass = [s >= _PASS_THRESHOLD for s in paid_scores]

        pct_agree = sum(1 for a, b in zip(local_pass, paid_pass) if a == b) / len(shared_prompts)
        kappa = _cohens_kappa(local_pass, paid_pass)
        r = _pearson_r(local_scores, paid_scores)

        agreement_results[p] = {
            "n_shared_cases": len(shared_prompts),
            "percent_agreement": round(pct_agree, 4),
            "cohens_kappa": round(kappa, 4) if not math.isnan(kappa) else None,
            "pearson_r_raw_scores": round(r, 4) if not math.isnan(r) else None,
        }
        print(
            f"ollama vs {p}: n={len(shared_prompts)} "
            f"percent_agreement={pct_agree:.1%} "
            f"cohens_kappa={kappa:.4f} "
            f"pearson_r={r:.4f}"
        )

    print("\n" + "=" * 70)
    print("SCORE DISTRIBUTION per provider (pass/fail counts)")
    print("=" * 70)
    for p in providers:
        counts = Counter(s >= _PASS_THRESHOLD for s in by_provider[p].values())
        print(f"{p}: pass={counts.get(True, 0)} fail={counts.get(False, 0)}")

    out_path = args.results_path.replace(".json", "_analysis.json")
    with open(out_path, "w") as f:
        json.dump({
            "bootstrap_ci": ci_results,
            "agreement_vs_local": agreement_results,
        }, f, indent=2)
    print(f"\nAnalysis written to {out_path}")


if __name__ == "__main__":
    main()
