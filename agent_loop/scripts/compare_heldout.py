"""Compare two runs of the same tasks, before and after the fix.

Usage:
    python -m agent_loop.scripts.compare_heldout \\
        --before heldout_baseline --after heldout_fix

Reports accuracy by category, a paired exact McNemar test and a bootstrap 95
percent interval on the difference, for layer 1 rules and, where both runs were
judged, for the judge as well.

Rules are the primary measure. They are deterministic, so the comparison is
reproducible, and on the review sample they agreed with the human on 94.6
percent of rows. The judge is reported as a secondary check because its own
agreement with the human was weaker.

Any category that got worse is called out explicitly. A fix that lifts the
average while breaking a slice is not an improvement anyone should ship, and
burying that in a mean would be the easiest dishonesty available here.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"
SCORES_DIR = RESULTS_DIR / "scores"
COMPARE_DIR = RESULTS_DIR / "comparison"


def _rule_outcomes(label: str) -> dict[str, bool]:
    path = SCORES_DIR / f"{label}_rules.json"
    if not path.exists():
        raise SystemExit(f"missing {path}")
    return {r["task_id"]: r["rule_pass"] for r in json.loads(path.read_text())["results"]}


def _judge_outcomes(label: str) -> dict[str, bool]:
    path = SCORES_DIR / f"{label}_judge.json"
    if not path.exists():
        return {}
    return {
        j["task_id"]: bool(j["judge_passed"]) for j in json.loads(path.read_text())["judgments"]
    }


def _compare(before: dict[str, bool], after: dict[str, bool], categories: dict[str, str]) -> dict:
    from agent_loop.metrics import mcnemar_exact, paired_difference_ci

    shared = sorted(set(before) & set(after))
    if not shared:
        raise SystemExit("the two runs share no tasks")

    b = [before[t] for t in shared]
    a = [after[t] for t in shared]

    by_category: dict[str, dict] = defaultdict(lambda: {"n": 0, "before": 0, "after": 0})
    for task_id in shared:
        bucket = by_category[categories.get(task_id, "unknown")]
        bucket["n"] += 1
        bucket["before"] += int(before[task_id])
        bucket["after"] += int(after[task_id])

    categories_out = {}
    regressions = []
    for name, bucket in sorted(by_category.items()):
        before_acc = bucket["before"] / bucket["n"]
        after_acc = bucket["after"] / bucket["n"]
        entry = {
            "n": bucket["n"],
            "before_passed": bucket["before"],
            "after_passed": bucket["after"],
            "before_accuracy": round(before_acc, 4),
            "after_accuracy": round(after_acc, 4),
            "difference": round(after_acc - before_acc, 4),
        }
        categories_out[name] = entry
        if after_acc < before_acc:
            regressions.append({"category": name, **entry})

    changed = {
        "fixed": [t for t in shared if not before[t] and after[t]],
        "broken": [t for t in shared if before[t] and not after[t]],
    }

    return {
        "n": len(shared),
        "overall": paired_difference_ci(b, a),
        "mcnemar": mcnemar_exact(b, a),
        "by_category": categories_out,
        "categories_that_got_worse": regressions,
        "tasks_changed": changed,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", default="heldout_comparison")
    args = parser.parse_args()

    from agent_loop.tasks import load_tasks

    categories = {task["id"]: task["category"] for task in load_tasks()}

    report: dict = {
        "before_label": args.before,
        "after_label": args.after,
        "compared_at": datetime.now(UTC).isoformat(),
        "primary_measure": "layer 1 rules",
    }

    report["rules"] = _compare(
        _rule_outcomes(args.before), _rule_outcomes(args.after), categories
    )

    judge_before, judge_after = _judge_outcomes(args.before), _judge_outcomes(args.after)
    if judge_before and judge_after:
        report["judge"] = _compare(judge_before, judge_after, categories)

    # Record the settings each run actually used, so the claim that only one
    # thing changed is checkable from the artifacts rather than taken on trust.
    settings = {}
    for role, label in (("before", args.before), ("after", args.after)):
        summary_path = RESULTS_DIR / "runs" / f"{label}_summary.json"
        if summary_path.exists():
            summary = json.loads(summary_path.read_text())
            settings[role] = {
                "variant": summary.get("variant"),
                "variant_env": summary.get("variant_env"),
                "settings": summary.get("settings"),
            }
    report["run_settings"] = settings
    if len(settings) == 2:
        a, b = settings["before"]["settings"] or {}, settings["after"]["settings"] or {}
        report["settings_differences"] = {
            k: {"before": a.get(k), "after": b.get(k)}
            for k in sorted(set(a) | set(b))
            if a.get(k) != b.get(k)
        }

    COMPARE_DIR.mkdir(parents=True, exist_ok=True)
    out = COMPARE_DIR / f"{args.out}.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    for measure in ("rules", "judge"):
        block = report.get(measure)
        if not block:
            continue
        overall, mcnemar = block["overall"], block["mcnemar"]
        print(f"\n{'=' * 64}")
        print(f"{measure.upper()}  n={block['n']}")
        print("=" * 64)
        print(
            f"  accuracy {overall['accuracy_before']:.1%} -> {overall['accuracy_after']:.1%}  "
            f"difference {overall['difference']:+.4f}  "
            f"95% CI [{overall['ci_95_low']:+.4f}, {overall['ci_95_high']:+.4f}]"
        )
        print(
            f"  McNemar: {mcnemar['improved_fail_to_pass']} fixed, "
            f"{mcnemar['regressed_pass_to_fail']} broken, "
            f"{mcnemar['discordant']} discordant, p={mcnemar['p_value']}"
        )
        straddles = overall["ci_95_low"] <= 0 <= overall["ci_95_high"]
        print(
            "  the interval includes zero, so this is not distinguishable from noise"
            if straddles
            else "  the interval excludes zero"
        )
        print("  by category:")
        for name, entry in block["by_category"].items():
            print(
                f"    {name:<22}{entry['before_passed']:>3}/{entry['n']:<3} -> "
                f"{entry['after_passed']:>3}/{entry['n']:<3}  {entry['difference']:+.4f}"
            )
        worse = block["categories_that_got_worse"]
        print(f"  categories that got worse: {[w['category'] for w in worse] or 'none'}")
        print(f"  fixed: {block['tasks_changed']['fixed']}")
        print(f"  broken: {block['tasks_changed']['broken']}")

    if report.get("settings_differences"):
        print(f"\nsettings that differ between the runs: {report['settings_differences']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
