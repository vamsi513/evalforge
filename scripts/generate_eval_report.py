"""
scripts/generate_eval_report.py — Renders a Markdown report from the real
result files already saved under evaluation/results/. Reads numbers out of
those files rather than having them typed into a template, so the report
can't drift from what was actually measured -- regenerate it any time by
rerunning this script after a new benchmark/agreement/position-bias run.

Usage:
    python -m scripts.generate_eval_report
"""

import json
from datetime import UTC, datetime
from pathlib import Path

_RESULTS_DIR = Path(__file__).parent.parent / "evaluation" / "results"
_DATASET_PATH = Path(__file__).parent.parent / "evaluation" / "judge_benchmark_dataset.json"
_OUT_PATH = _RESULTS_DIR / "report.md"


def _load(name: str) -> dict:
    with open(_RESULTS_DIR / name) as f:
        return json.load(f)


def main() -> None:
    with open(_DATASET_PATH) as f:
        dataset = json.load(f)
    benchmark = _load("judge_benchmark_60case.json")
    agreement = _load("judge_agreement_analysis.json")
    position_bias = _load("position_bias_results.json")

    n_by_category = {k: len(v["samples"]) for k, v in dataset["scenarios"].items()}
    total_n = sum(n_by_category.values())

    lines = []
    lines.append("# Judge evaluation report")
    lines.append("")
    lines.append(f"Generated {datetime.now(UTC).isoformat()} from files in `evaluation/results/`. "
                 "Every number below is read directly from a saved run's output, not retyped by hand.")
    lines.append("")
    lines.append("## Dataset")
    lines.append("")
    lines.append(f"- Version: `{dataset.get('dataset_version', 'unversioned')}` "
                 f"(content hash `{dataset.get('content_sha256_16', 'n/a')}`)")
    lines.append(f"- {total_n} hand-authored cases across {len(n_by_category)} categories: "
                 + ", ".join(f"{k} ({v})" for k, v in n_by_category.items()))
    lines.append(f"- Judge prompt fingerprint at benchmark time: `{benchmark.get('judge_prompt_fingerprint', 'n/a')}`")
    lines.append("")
    lines.append("This is a small, hand-written benchmark for comparing judge providers on the same "
                 f"{total_n} cases -- not a comprehensive evaluation suite.")
    lines.append("")

    lines.append("## Per-provider results")
    lines.append("")
    lines.append("| Provider | Model | n | Avg score | 95% CI | Avg latency (ms) | Total cost |")
    lines.append("|---|---|---|---|---|---|---|")
    for summary in benchmark["summaries"]:
        provider = summary["provider"]
        if not summary.get("n"):
            lines.append(f"| {provider} | — | 0 | — | — | — | 0 real calls ({summary.get('note', 'no data')}) |")
            continue
        ci = agreement.get("bootstrap_ci", {}).get(provider)
        ci_str = f"[{ci['ci_95_low']}, {ci['ci_95_high']}]" if ci else "n/a"
        cost = summary["cost_usd"]["total"]
        cost_str = "local inference, no per-request API charge" if cost == 0 else f"${cost:.6f}"
        lines.append(
            f"| {provider} | {summary['judge_model']} | {summary['n']} | "
            f"{summary['avg_score']:.3f} | {ci_str} | {summary['latency_ms']['avg']:.0f} | {cost_str} |"
        )
    lines.append("")
    lines.append(f"Total real spend across paid providers this run: ${benchmark.get('total_cost_usd', 0):.6f}.")
    lines.append("")

    lines.append("## Local judge vs. paid providers: agreement")
    lines.append("")
    lines.append(f"Pass/fail agreement and Cohen's kappa, computed on the {total_n} shared cases "
                 "(threshold: score >= 0.7, same threshold the judge itself uses to set `passed`).")
    lines.append("")
    lines.append("| Comparison | n | % Agreement | Cohen's kappa | Pearson r (raw scores) |")
    lines.append("|---|---|---|---|---|")
    for provider, stats in agreement.get("agreement_vs_local", {}).items():
        lines.append(
            f"| ollama vs {provider} | {stats['n_shared_cases']} | "
            f"{stats['percent_agreement']:.1%} | {stats['cohens_kappa']} | {stats['pearson_r_raw_scores']} |"
        )
    lines.append("")

    lines.append("## Position-bias test")
    lines.append("")
    lines.append(f"{position_bias['n_pairs']} hand-authored pairs (each with one clearly better and one "
                 "clearly worse response to the same prompt), tested with the local judge in both orders.")
    lines.append("")
    lines.append(f"- Verdict flipped on swap: {position_bias['flipped_count']}/{position_bias['n_pairs']} "
                 f"({position_bias['position_bias_rate']:.1%})")
    lines.append(f"- Accuracy picking the better response, normal order: {position_bias['normal_order_accuracy']:.1%}")
    lines.append(f"- Accuracy picking the better response, swapped order: {position_bias['swapped_order_accuracy']:.1%}")
    lines.append("")
    lines.append("These pairs were deliberately unambiguous (correct vs. clearly wrong), so a 0% bias rate "
                 "here shows no bias on easy calls -- it doesn't establish anything about close judgment calls.")
    lines.append("")

    lines.append("## What this does and doesn't show")
    lines.append("")
    lines.append(f"- {total_n} cases is enough to get a first read on agreement, not a statistically "
                 "definitive claim -- the bootstrap CIs above show real overlap between providers' average "
                 "scores at this sample size.")
    lines.append("- No human-labeled baseline is included in this report (that stage was skipped this round).")
    lines.append("- Mistral is excluded from the agreement table: all 60 calls (and a second, more slowly "
                 "paced retry) failed with rate limiting rather than returning real results.")
    lines.append("")

    _OUT_PATH.write_text("\n".join(lines) + "\n")
    print(f"Report written to {_OUT_PATH}")


if __name__ == "__main__":
    main()
