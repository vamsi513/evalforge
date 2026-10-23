"""Run tasks against AgentIQ and store one trace per run.

Usage:
    python -m agent_loop.scripts.run_agent --split dev --mock
    python -m agent_loop.scripts.run_agent --split dev --limit 10 --label pilot
    python -m agent_loop.scripts.run_agent --split held_out --variant baseline

Settings are fixed for every run in a batch and recorded in every trace, so a
later batch can be shown to have used the same configuration.

Spending is bounded in two ways. A running ledger at
results/agent_loop/cost_ledger.jsonl accumulates what every batch has spent, and
--max-total-usd refuses to start, and aborts mid sweep, once the ledger plus the
current batch would cross the cap. Mock runs cost nothing and are not recorded
against it.
"""

import argparse
import asyncio
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"
TRACES_DIR = RESULTS_DIR / "traces"
LEDGER_PATH = RESULTS_DIR / "cost_ledger.jsonl"

DEFAULT_CAP_USD = 1.50


def _ledger_total() -> float:
    if not LEDGER_PATH.exists():
        return 0.0
    total = 0.0
    for line in LEDGER_PATH.read_text().splitlines():
        if line.strip():
            total += json.loads(line).get("cost_usd", 0.0)
    return total


def _append_ledger(entry: dict) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a") as handle:
        handle.write(json.dumps(entry) + "\n")


def _select_tasks(split: str, limit: int | None, seed: int) -> list[dict]:
    from agent_loop.splitting import stratified_sample
    from agent_loop.tasks import DATA_DIR, load_tasks

    tasks = load_tasks()
    by_id = {task["id"]: task for task in tasks}
    split_file = json.loads((DATA_DIR / "split.json").read_text())

    if split == "dev":
        ids = split_file["development_ids"]
    elif split == "held_out":
        ids = split_file["held_out_ids"]
    elif split == "all":
        ids = [task["id"] for task in tasks]
    else:
        raise SystemExit(f"unknown split {split!r}")

    chosen = [by_id[task_id] for task_id in ids]
    if limit is not None and limit < len(chosen):
        # Stratified so a short pilot still covers all four categories.
        picked = set(stratified_sample(chosen, n=limit, seed=seed))
        chosen = [task for task in chosen if task["id"] in picked]
    return chosen


async def _run_batch(tasks: list[dict], args, label: str) -> dict:
    from agent.graph import build_graph

    from agent_loop.runner import run_task, run_task_with_guard
    from agent_loop.variants import uses_guard

    guarded = uses_guard(args.variant)

    # No checkpointer: every task is a fresh session, so nothing one task says
    # can leak into the next one's context.
    graph = build_graph(checkpointer=None)

    out_dir = TRACES_DIR / label
    out_dir.mkdir(parents=True, exist_ok=True)

    spent_before = 0.0 if args.mock else _ledger_total()
    batch_cost = 0.0
    traces: list[dict] = []
    aborted: str | None = None

    for index, task in enumerate(tasks, start=1):
        trace = await (
            run_task_with_guard(graph, task, variant=args.variant)
            if guarded
            else run_task(graph, task, variant=args.variant)
        )
        trace["label"] = label
        trace["run_at"] = datetime.now(UTC).isoformat()
        batch_cost += trace["usage"]["cost_usd"]
        traces.append(trace)

        (out_dir / f"{task['id']}.json").write_text(json.dumps(trace, indent=2) + "\n")

        route = trace["route_decision"]
        problem = trace["invoke_exception"] or trace["state_error"] or ""
        print(
            f"[{index:>3}/{len(tasks)}] {task['id']:<8} {task['category']:<21} "
            f"route={route:<12} {trace['latency_ms']:>7.0f}ms "
            f"${batch_cost:.4f}{'  ERROR: ' + problem[:50] if problem else ''}"
        )

        if not args.mock and spent_before + batch_cost > args.max_total_usd:
            aborted = (
                f"stopped after {index} of {len(tasks)} tasks: ledger "
                f"{spent_before:.4f} plus batch {batch_cost:.4f} crossed the "
                f"{args.max_total_usd:.2f} cap"
            )
            print(f"\nABORTED. {aborted}", file=sys.stderr)
            break

    summary = {
        "label": label,
        "variant": args.variant,
        "split": args.split,
        "mock": args.mock,
        "run_at": datetime.now(UTC).isoformat(),
        "tasks_requested": len(tasks),
        "tasks_run": len(traces),
        "aborted": aborted,
        "cost_usd": round(batch_cost, 8),
        "cost_per_task_usd": round(batch_cost / len(traces), 8) if traces else 0.0,
        "usage_source": (
            sorted({t["usage"]["usage_source"] for t in traces}) if traces else []
        ),
        "llm_calls": sum(t["usage"]["llm_calls"] for t in traces),
        "input_tokens": sum(t["usage"]["input_tokens"] for t in traces),
        "output_tokens": sum(t["usage"]["output_tokens"] for t in traces),
        "routes": _tally(t["route_decision"] for t in traces),
        "errors": sum(1 for t in traces if t["invoke_exception"] or t["state_error"]),
        "guard_triggered": sum(1 for t in traces if (t.get("guard") or {}).get("triggered")),
        "settings": traces[0]["settings"] if traces else {},
        "variant_env": _variant_env(args.variant),
        "ledger_before_usd": round(spent_before, 8),
        "ledger_after_usd": round(spent_before + batch_cost, 8),
    }

    (RESULTS_DIR / "runs").mkdir(parents=True, exist_ok=True)
    (RESULTS_DIR / "runs" / f"{label}_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n"
    )

    if not args.mock and batch_cost > 0:
        _append_ledger(
            {
                "label": label,
                "run_at": summary["run_at"],
                "tasks_run": summary["tasks_run"],
                "cost_usd": summary["cost_usd"],
                "usage_source": summary["usage_source"],
            }
        )

    return summary


def _variant_env(name: str) -> dict:
    from agent_loop.variants import variant_env

    return variant_env(name)


def _tally(values) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        key = str(value)
        counts[key] = counts.get(key, 0) + 1
    return dict(sorted(counts.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--split", default="dev", choices=("dev", "held_out", "all"))
    parser.add_argument("--limit", type=int, default=None, help="run a stratified subset")
    parser.add_argument("--task-ids", default=None, help="comma separated task ids to run")
    parser.add_argument("--seed", type=int, default=11, help="seed for --limit sampling")
    parser.add_argument(
        "--variant",
        default="baseline",
        help="wrapper configuration from agent_loop/variants.py",
    )
    parser.add_argument("--label", default=None, help="output folder name under traces/")
    parser.add_argument("--mock", action="store_true", help="free run with AgentIQ's fakes")
    parser.add_argument(
        "--max-total-usd",
        type=float,
        default=DEFAULT_CAP_USD,
        help="hard cap on cumulative spend across every recorded batch",
    )
    args = parser.parse_args()

    # The environment has to be set before AgentIQ's config singleton is built,
    # which happens on first import of `config`. Every agent import below is
    # therefore deliberately late.
    from agent_loop.variants import apply_variant

    applied = apply_variant(args.variant)
    print(f"variant {args.variant}: {applied or 'AgentIQ defaults, nothing overridden'}")

    if args.mock:
        os.environ["AGENTIQ_MOCK_LLM"] = "1"
        os.environ["AGENTIQ_MOCK_TAVILY"] = "1"
    else:
        from agent_loop.runner import load_env_file

        names = load_env_file()
        print(f"loaded {len(names)} credentials from the env file: {', '.join(sorted(names))}")

    # One JSON line per tool call, which is where web_search arguments come from.
    os.environ.setdefault("AUDIT_LOG_ENABLED", "true")

    tasks = _select_tasks(args.split, args.limit, args.seed)
    if args.task_ids:
        wanted = {t.strip() for t in args.task_ids.split(",") if t.strip()}
        tasks = [t for t in tasks if t["id"] in wanted]
        missing = wanted - {t["id"] for t in tasks}
        if missing:
            raise SystemExit(f"not in the {args.split} split: {sorted(missing)}")
    label = args.label or f"{args.split}_{args.variant}{'_mock' if args.mock else ''}"

    if not args.mock:
        spent = _ledger_total()
        if spent >= args.max_total_usd:
            raise SystemExit(
                f"ledger already at ${spent:.4f}, at or over the ${args.max_total_usd:.2f} cap. "
                "Nothing was run."
            )
        print(f"ledger so far: ${spent:.4f} of ${args.max_total_usd:.2f}")

    print(f"running {len(tasks)} tasks, split={args.split}, label={label}, mock={args.mock}")
    summary = asyncio.run(_run_batch(tasks, args, label))

    print("\n" + "=" * 68)
    print(f"ran {summary['tasks_run']} of {summary['tasks_requested']} tasks")
    print(f"routes: {summary['routes']}")
    print(f"errors: {summary['errors']}")
    print(f"llm calls: {summary['llm_calls']}  usage source: {summary['usage_source']}")
    print(f"tokens in/out: {summary['input_tokens']}/{summary['output_tokens']}")
    print(f"cost: ${summary['cost_usd']:.6f}  per task: ${summary['cost_per_task_usd']:.6f}")
    if not summary["mock"]:
        print(f"ledger now: ${summary['ledger_after_usd']:.4f} of ${args.max_total_usd:.2f}")
    print(f"traces: {TRACES_DIR / label}")


if __name__ == "__main__":
    main()
