"""Score a batch of traces with layer 1 rules and, optionally, the layer 2 judge.

Usage:
    python -m agent_loop.scripts.score_runs --label dev_baseline --rules-only
    python -m agent_loop.scripts.score_runs --label dev_baseline

Layer 1 is free and deterministic, so --rules-only is the default way to look at
a batch. The judge costs money and is only run when asked for.

Judge spending goes through the same ledger as agent runs, and the cap is
checked before any call is made rather than after.
"""

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"
TRACES_DIR = RESULTS_DIR / "traces"
SCORES_DIR = RESULTS_DIR / "scores"
LEDGER_PATH = RESULTS_DIR / "cost_ledger.jsonl"


def _ledger_total() -> float:
    if not LEDGER_PATH.exists():
        return 0.0
    return sum(
        json.loads(line).get("cost_usd", 0.0)
        for line in LEDGER_PATH.read_text().splitlines()
        if line.strip()
    )


def load_traces(label: str) -> list[dict]:
    folder = TRACES_DIR / label
    if not folder.exists():
        raise SystemExit(f"no traces at {folder}")
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]


def summarise_rules(results: list[dict]) -> dict:
    by_category: dict[str, dict] = defaultdict(lambda: {"n": 0, "passed": 0})
    tag_counts: Counter = Counter()
    check_counts: dict[str, dict] = defaultdict(lambda: {"applicable": 0, "passed": 0})

    for result in results:
        bucket = by_category[result["category"]]
        bucket["n"] += 1
        bucket["passed"] += int(result["rule_pass"])
        tag_counts.update(result["failure_tags"])
        for name, check in result["checks"].items():
            if check["applicable"]:
                check_counts[name]["applicable"] += 1
                check_counts[name]["passed"] += int(check["passed"])

    for bucket in by_category.values():
        bucket["accuracy"] = round(bucket["passed"] / bucket["n"], 4) if bucket["n"] else 0.0

    total = len(results)
    passed = sum(1 for r in results if r["rule_pass"])
    return {
        "n": total,
        "passed": passed,
        "accuracy": round(passed / total, 4) if total else 0.0,
        "by_category": dict(sorted(by_category.items())),
        "failure_tag_counts": dict(tag_counts.most_common()),
        "per_check": {
            name: {**counts, "pass_rate": round(counts["passed"] / counts["applicable"], 4)}
            for name, counts in sorted(check_counts.items())
            if counts["applicable"]
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True, help="trace folder under results/agent_loop/traces")
    parser.add_argument("--rules-only", action="store_true", help="skip the paid judge")
    parser.add_argument("--max-total-usd", type=float, default=1.50)
    parser.add_argument(
        "--judge-limit",
        type=int,
        default=None,
        help="judge only the first N traces, for a cheap probe before the full batch",
    )
    parser.add_argument(
        "--judge-suffix",
        default="judge",
        help="output suffix, so a probe does not overwrite the real judgments",
    )
    parser.add_argument(
        "--judge-ids",
        default=None,
        help="comma separated task ids to judge, for a probe that covers several categories",
    )
    args = parser.parse_args()

    # Credentials and judge configuration must both be in the environment
    # before anything imports app.core.config, which builds EvalForge's
    # settings singleton and reads them once. agent_loop.credentials and
    # agent_loop.judging are safe to import here because neither touches app
    # at module scope; agent_loop.runner is not, and is imported later.
    if not args.rules_only:
        from agent_loop.credentials import load_env_file
        from agent_loop.judging import configure_judge_env

        names = load_env_file()
        configure_judge_env()
        print(f"loaded {len(names)} credentials: {', '.join(sorted(names))}")

    from agent_loop.rules import check_trace
    from agent_loop.tasks import load_tasks

    tasks_by_id = {task["id"]: task for task in load_tasks()}
    traces = load_traces(args.label)
    print(f"scoring {len(traces)} traces from {args.label}")

    rule_results = [check_trace(trace, tasks_by_id[trace["task_id"]]) for trace in traces]
    rules_summary = summarise_rules(rule_results)

    SCORES_DIR.mkdir(parents=True, exist_ok=True)
    (SCORES_DIR / f"{args.label}_rules.json").write_text(
        json.dumps(
            {
                "label": args.label,
                "scored_at": datetime.now(UTC).isoformat(),
                "summary": rules_summary,
                "results": rule_results,
            },
            indent=2,
        )
        + "\n"
    )

    print("\nLAYER 1, RULES")
    print(f"  overall {rules_summary['passed']}/{rules_summary['n']} = {rules_summary['accuracy']:.1%}")
    for category, bucket in rules_summary["by_category"].items():
        print(f"    {category:<22}{bucket['passed']:>3}/{bucket['n']:<3} {bucket['accuracy']:>7.1%}")
    print(f"  failure tags: {rules_summary['failure_tag_counts']}")
    print("  per check:")
    for name, counts in rules_summary["per_check"].items():
        print(f"    {name:<10}{counts['passed']:>3}/{counts['applicable']:<3} {counts['pass_rate']:>7.1%}")

    if args.rules_only:
        print(f"\nwrote {SCORES_DIR / (args.label + '_rules.json')}  (judge skipped)")
        return

    spent = _ledger_total()
    if spent >= args.max_total_usd:
        raise SystemExit(f"ledger at ${spent:.4f}, at or over the ${args.max_total_usd:.2f} cap")
    print(f"\nledger before judging: ${spent:.4f} of ${args.max_total_usd:.2f}")

    from agent_loop.judging import JudgeFellBackError, judge_traces

    if args.judge_ids:
        wanted = {task_id.strip() for task_id in args.judge_ids.split(",") if task_id.strip()}
        to_judge = [t for t in traces if t["task_id"] in wanted]
        missing = wanted - {t["task_id"] for t in to_judge}
        if missing:
            raise SystemExit(f"no trace in {args.label} for: {sorted(missing)}")
    else:
        to_judge = traces[: args.judge_limit] if args.judge_limit else traces

    def _progress(index: int, total: int, judgment: dict) -> None:
        mark = "pass" if judgment["judge_passed"] else "FAIL"
        print(
            f"  [{index:>3}/{total}] {judgment['task_id']:<8} {mark}  "
            f"score={judgment['judge_score']:.2f}  ${judgment['cost_usd']:.5f}",
            flush=True,
        )

    try:
        judgments = judge_traces(to_judge, tasks_by_id, progress=_progress)
    except JudgeFellBackError as exc:
        # Those calls were already paid for. Persist them and record the spend
        # before failing, so a retry does not lose the data or the accounting.
        partial = exc.partial
        if partial:
            spent_partial = sum(j["cost_usd"] for j in partial)
            (SCORES_DIR / f"{args.label}_{args.judge_suffix}_partial.json").write_text(
                json.dumps({"label": args.label, "judgments": partial}, indent=2) + "\n"
            )
            with open(LEDGER_PATH, "a") as handle:
                handle.write(
                    json.dumps(
                        {
                            "label": f"{args.label}_{args.judge_suffix}_partial",
                            "run_at": datetime.now(UTC).isoformat(),
                            "tasks_run": len(partial),
                            "cost_usd": round(spent_partial, 8),
                            "usage_source": ["provider_reported"],
                        }
                    )
                    + "\n"
                )
            print(f"\nkept {len(partial)} judgments worth ${spent_partial:.4f} before the failure")
        raise SystemExit(str(exc)) from exc

    judge_cost = sum(j["cost_usd"] for j in judgments)

    judged_pass = sum(1 for j in judgments if j["judge_passed"])
    by_category: dict[str, dict] = defaultdict(lambda: {"n": 0, "passed": 0})
    for judgment in judgments:
        bucket = by_category[judgment["category"]]
        bucket["n"] += 1
        bucket["passed"] += int(judgment["judge_passed"])
    for bucket in by_category.values():
        bucket["accuracy"] = round(bucket["passed"] / bucket["n"], 4)

    judge_summary = {
        "n": len(judgments),
        "passed": judged_pass,
        "accuracy": round(judged_pass / len(judgments), 4) if judgments else 0.0,
        "by_category": dict(sorted(by_category.items())),
        "judge_provider": judgments[0]["judge_provider"] if judgments else None,
        "judge_model": judgments[0]["judge_model"] if judgments else None,
        "judge_prompt_fingerprint": judgments[0]["judge_prompt_fingerprint"] if judgments else None,
        "cost_usd": round(judge_cost, 8),
        "references_truncated": sum(1 for j in judgments if j["reference_was_truncated"]),
    }

    (SCORES_DIR / f"{args.label}_{args.judge_suffix}.json").write_text(
        json.dumps(
            {
                "label": args.label,
                "scored_at": datetime.now(UTC).isoformat(),
                "summary": judge_summary,
                "judgments": judgments,
            },
            indent=2,
        )
        + "\n"
    )

    with open(LEDGER_PATH, "a") as handle:
        handle.write(
            json.dumps(
                {
                    "label": f"{args.label}_{args.judge_suffix}",
                    "run_at": datetime.now(UTC).isoformat(),
                    "tasks_run": len(judgments),
                    "cost_usd": round(judge_cost, 8),
                    "usage_source": ["provider_reported"],
                }
            )
            + "\n"
        )

    print("\nLAYER 2, JUDGE")
    print(f"  model {judge_summary['judge_model']} via {judge_summary['judge_provider']}")
    print(f"  overall {judged_pass}/{judge_summary['n']} = {judge_summary['accuracy']:.1%}")
    for category, bucket in judge_summary["by_category"].items():
        print(f"    {category:<22}{bucket['passed']:>3}/{bucket['n']:<3} {bucket['accuracy']:>7.1%}")
    print(f"  references truncated to fit the sample cap: {judge_summary['references_truncated']}")
    print(f"  judge cost ${judge_cost:.4f}; ledger now ${spent + judge_cost:.4f}")


if __name__ == "__main__":
    main()
