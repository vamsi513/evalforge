"""
scripts/run_judge_benchmark.py — Reproducible per-provider judge latency/cost
benchmark against the expanded evaluation dataset.

Runs every sample in evaluation/judge_benchmark_dataset.json through each
configured judge provider (openai, anthropic, mistral) via the same
JudgeClient the API uses, and reports real measured latency and cost per
call -- nothing here is estimated. A provider is skipped with a clear
message if its API key isn't configured; results for it simply aren't
reported rather than being backfilled with a guess.

Usage:
    python -m scripts.run_judge_benchmark
    python -m scripts.run_judge_benchmark --providers openai mistral
    python -m scripts.run_judge_benchmark --out results.json
    python -m scripts.run_judge_benchmark --providers mistral --delay-seconds 2

This makes real, billed API calls to whichever providers are configured.
Check the sample count before running against all three providers if you're
mindful of cost -- see the dataset file's total sample count and each
provider's per-token pricing in app/engine/judge.py.

--delay-seconds: firing all 30 samples back-to-back with no pacing tripped
Mistral's rate limit partway through a full run, and every call after that
point silently fell back to the mock heuristic judge (judge.py's own
graceful-degradation behavior -- correct for production, but it means those
results were mock, not real API calls, and had to be discarded and rerun
paced). OpenAI and Anthropic did not hit this in testing. Use a delay when
re-running a provider that's rate-limit-sensitive.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import mean

from app.core import config
from app.engine.judge import JudgeClient
from app.models.eval_run import EvalSample

_DATASET_PATH = Path(__file__).parent.parent / "evaluation" / "judge_benchmark_dataset.json"
_ALL_PROVIDERS = ["openai", "anthropic", "mistral"]

_PROVIDER_KEY_ATTR = {
    "openai": "openai_api_key",
    "anthropic": "anthropic_api_key",
    "mistral": "mistral_api_key",
}


def _load_samples() -> list[dict]:
    with open(_DATASET_PATH) as f:
        data = json.load(f)
    samples = []
    for scenario_key, scenario in data["scenarios"].items():
        for raw in scenario["samples"]:
            samples.append({**raw, "scenario_group": scenario_key})
    return samples


_MAX_FALLBACK_RETRIES = 3


def _call_once(client: JudgeClient, provider: str, raw: dict) -> dict:
    sample = EvalSample(
        prompt=raw["prompt"],
        expected_keyword=raw["expected_keyword"],
        candidate_output=raw["candidate_output"],
        reference_answer=raw.get("reference_answer"),
        scenario=raw.get("scenario", "general"),
        slice_name=raw.get("slice_name", "default"),
        severity=raw.get("severity", "medium"),
    )
    try:
        resp = client.evaluate(
            dataset_name=f"benchmark-{raw['scenario_group']}",
            prompt_version="benchmark-v1",
            model_name="benchmark-run",
            samples=[sample],
        )
        r = resp.results[0]
        return {
            "provider": provider,
            "judge_model": resp.judge_model,
            "scenario_group": raw["scenario_group"],
            "prompt": raw["prompt"],
            "used_fallback": getattr(r, "used_fallback", None),
            "latency_ms": getattr(r, "latency_ms", None),
            "cost_usd": getattr(r, "cost_usd", None),
            "score": r.score,
            "error": None,
        }
    except Exception as exc:
        return {
            "provider": provider,
            "judge_model": None,
            "scenario_group": raw["scenario_group"],
            "prompt": raw["prompt"],
            "used_fallback": None,
            "latency_ms": None,
            "cost_usd": None,
            "score": None,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_provider(client: JudgeClient, provider: str, samples: list[dict], delay_seconds: float = 0.0) -> list[dict]:
    config.settings.judge_provider = provider
    records = []
    for i, raw in enumerate(samples):
        if delay_seconds and i > 0:
            time.sleep(delay_seconds)

        record = _call_once(client, provider, raw)

        # judge.py catches provider failures (e.g. a 429) and silently
        # substitutes the mock heuristic judge so the request still
        # "succeeds" -- error is None but the result isn't a real API call.
        # Retry with backoff rather than reporting a mock result as real.
        attempt = 1
        while record["used_fallback"] is True and attempt <= _MAX_FALLBACK_RETRIES:
            backoff = delay_seconds * (attempt + 1) if delay_seconds else 5.0 * attempt
            print(f"[{provider}] fallback detected on attempt {attempt}, retrying in {backoff:.1f}s...")
            time.sleep(backoff)
            record = _call_once(client, provider, raw)
            attempt += 1

        records.append(record)
        print(f"[{provider}] {raw['scenario_group']}: {records[-1]}")
    return records


def _summarize(records: list[dict], provider: str) -> dict:
    # used_fallback=True means the call never actually reached the provider
    # (judge.py caught a failure -- e.g. a 429 -- and silently substituted
    # the mock heuristic judge so the request still succeeds for the caller).
    # error is None either way in that case, so filtering on error alone
    # would silently count mock results as if they were real API calls.
    rows = [
        r for r in records
        if r["provider"] == provider and r["error"] is None and r["used_fallback"] is False
    ]
    fallback_count = sum(
        1 for r in records if r["provider"] == provider and r["used_fallback"] is True
    )
    if not rows:
        return {"provider": provider, "n": 0, "note": "no successful (non-fallback) calls",
                "fallback_count": fallback_count}
    lat = [r["latency_ms"] for r in rows]
    cost = [r["cost_usd"] for r in rows]
    scores = [r["score"] for r in rows]
    return {
        "provider": provider,
        "judge_model": rows[0]["judge_model"],
        "n": len(rows),
        "latency_ms": {"min": min(lat), "max": max(lat), "avg": round(mean(lat), 1)},
        "cost_usd": {"min": min(cost), "max": max(cost), "avg": round(mean(cost), 6),
                     "total": round(sum(cost), 6)},
        "avg_score": round(mean(scores), 4),
        "fallback_count": fallback_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--providers", nargs="+", default=_ALL_PROVIDERS, choices=_ALL_PROVIDERS)
    parser.add_argument("--out", default=None, help="Optional path to write full raw results JSON.")
    parser.add_argument("--delay-seconds", type=float, default=0.0,
                         help="Pause between calls to the same provider (avoids rate-limit fallback).")
    args = parser.parse_args()

    samples = _load_samples()
    print(f"Loaded {len(samples)} samples from {_DATASET_PATH}")

    client = JudgeClient()
    all_records = []
    run_started = datetime.now(UTC).isoformat()

    for provider in args.providers:
        key_attr = _PROVIDER_KEY_ATTR[provider]
        if not getattr(config.settings, key_attr, ""):
            print(f"\nSkipping {provider}: {key_attr} is not configured.")
            continue
        print(f"\nRunning {len(samples)} samples against {provider}...")
        all_records.extend(_run_provider(client, provider, samples, delay_seconds=args.delay_seconds))

    run_finished = datetime.now(UTC).isoformat()

    print("\n" + "=" * 70)
    print("SUMMARY (real measured values only)")
    print("=" * 70)
    summaries = []
    grand_total_cost = 0.0
    for provider in args.providers:
        summary = _summarize(all_records, provider)
        summaries.append(summary)
        if summary.get("n"):
            grand_total_cost += summary["cost_usd"]["total"]
            print(
                f"{provider} ({summary['judge_model']}): n={summary['n']} "
                f"latency_ms(min/max/avg)={summary['latency_ms']['min']:.0f}/"
                f"{summary['latency_ms']['max']:.0f}/{summary['latency_ms']['avg']:.1f} "
                f"cost_usd(min/max/avg)={summary['cost_usd']['min']:.6f}/"
                f"{summary['cost_usd']['max']:.6f}/{summary['cost_usd']['avg']:.6f} "
                f"total=${summary['cost_usd']['total']:.6f} "
                f"avg_score={summary['avg_score']:.3f} "
                f"fallback_count={summary['fallback_count']}"
            )
        else:
            print(f"{provider}: {summary.get('note', 'no data')}")

    print(f"\nTotal real spend this run: ${grand_total_cost:.6f}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({
                "run_started_utc": run_started,
                "run_finished_utc": run_finished,
                "sample_count": len(samples),
                "records": all_records,
                "summaries": summaries,
                "total_cost_usd": round(grand_total_cost, 6),
            }, f, indent=2)
        print(f"Full results written to {args.out}")


if __name__ == "__main__":
    main()
