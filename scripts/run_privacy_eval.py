"""
scripts/run_privacy_eval.py -- Runs evaluation/privacy_probe_dataset.json
against a target model under each prompt configuration and saves a result
artifact that is enough on its own to reproduce or re-score the run.

Every case is scored by the deterministic rules in app/engine/privacy_scorer.py.
Nothing here uses a judge model, so no scoring decision depends on an LLM.

Usage:
    python -m scripts.run_privacy_eval --provider ollama
    python -m scripts.run_privacy_eval --provider ollama --configs guarded
    python -m scripts.run_privacy_eval --provider ollama --model qwen2.5:7b-instruct --out results.json
    python -m scripts.run_privacy_eval --provider mock          # pipeline check only
    python -m scripts.run_privacy_eval --rescore-from OLD.json  # re-label saved responses

--rescore-from re-applies the current scorer to the responses already saved in
an artifact, without calling the model again. That is the whole reason every
response text is stored. It is the right tool when a scoring rule changes but
the prompts did not; it refuses to run if the prompt text for any case has
changed since, so a re-score can never silently attribute old responses to a
new prompt.

The default output path is
evaluation/results/privacy_probe_<provider>_<model>_<timestamp>.json.

A --provider mock run writes "is_mock": true at the top level and tags every
record. Those numbers describe canned strings, not a model, and must not be
reported as model performance.

Local inference only. There is no paid-provider path in this script, so a run
costs nothing but wall clock; on an M-series laptop with qwen2.5:7b-instruct
expect roughly 8-20s per case, so about 10-25 minutes for all 40 cases across
both configurations.
"""

import argparse
import hashlib
import json
import platform
import sys
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from app.engine.privacy_scorer import SCORER_VERSION, aggregate, score_case
from app.engine.privacy_target import (
    CONFIGS,
    PROMPT_TEMPLATE_VERSION,
    TargetModelClient,
    TargetModelError,
    build_user_message,
    prompt_fingerprint,
    system_prompt,
)

_REPO_ROOT = Path(__file__).parent.parent
_DATASET_PATH = _REPO_ROOT / "evaluation" / "privacy_probe_dataset.json"
_RESULTS_DIR = _REPO_ROOT / "evaluation" / "results"


def dataset_content_hash(data: dict) -> str:
    """Hash of records + scenarios. The secrets live in records, so hashing
    scenarios alone (which is what run_judge_benchmark.py does for its own
    dataset) would miss an edited secret value."""
    payload = {"records": data["records"], "scenarios": data["scenarios"]}
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def input_hash(case: dict, config: str) -> str:
    """Hash of the exact text the model was shown. Lets --rescore-from prove the
    saved responses still belong to the prompts in the current dataset."""
    payload = f"{system_prompt(config)}\n<<<>>>\n{build_user_message(case)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def load_dataset() -> dict:
    with open(_DATASET_PATH) as f:
        return json.load(f)


def dataset_meta(data: dict) -> dict:
    live = dataset_content_hash(data)
    recorded = data.get("content_sha256_16")
    return {
        "dataset_path": str(_DATASET_PATH.relative_to(_REPO_ROOT)),
        "dataset_version": data.get("dataset_version", "unversioned"),
        "recorded_content_hash": recorded,
        "live_content_hash": live,
        "hash_matches": recorded == live,
    }


def flatten_cases(data: dict) -> list[dict]:
    """One flat list of cases, each carrying its group name and expected
    behaviour so the scorer does not have to go looking for them."""
    cases = []
    for group_name, group in data["scenarios"].items():
        for case in group["cases"]:
            cases.append({
                **case,
                "scenario_group": group_name,
                "_expected_behavior": group["expected_behavior"],
                "_secret_value": data["records"][case["record"]]["secret_value"],
            })
    return cases


def run(client: TargetModelClient, cases: list[dict], records: dict,
        configs: list[str], verbose: bool = True) -> list[dict]:
    records_out = []
    total = len(cases) * len(configs)
    i = 0
    for config in configs:
        for case in cases:
            i += 1
            expected = case["_expected_behavior"]
            timestamp = datetime.now(UTC).isoformat()
            try:
                resp = client.generate(case=case, config=config)
            except TargetModelError as exc:
                # No substituted response. A failed generation is recorded as a
                # hole in the run, and aggregation skips it.
                records_out.append({
                    "case_id": case["case_id"],
                    "scenario_group": case["scenario_group"],
                    "record": case["record"],
                    "config": config,
                    "expected_behavior": expected,
                    "timestamp_utc": timestamp,
                    "error": str(exc),
                    "response": None,
                    "scoring": None,
                })
                if verbose:
                    print(f"[{i}/{total}] {config}/{case['case_id']}: ERROR {exc}")
                continue

            scored = score_case(
                case=case,
                record=records[case["record"]],
                response=resp.text,
                expected_behavior=expected,
            )
            records_out.append({
                "case_id": case["case_id"],
                "scenario_group": case["scenario_group"],
                "record": case["record"],
                "secret_source": case.get("secret_source"),
                "requester_authorization": case.get("requester_authorization"),
                "config": config,
                "expected_behavior": expected,
                "timestamp_utc": timestamp,
                "provider": resp.provider,
                "model": resp.model,
                "prompt_template_version": resp.prompt_template_version,
                "prompt_fingerprint": resp.prompt_fingerprint,
                "input_sha256_16": input_hash(case, config),
                "temperature": resp.temperature,
                "seed": resp.seed,
                "latency_ms": round(resp.latency_ms, 1),
                "is_mock": resp.is_mock,
                "response": resp.text,
                "error": None,
                "scoring": asdict(scored) | {"label": scored.label.value},
            })
            if verbose:
                print(f"[{i}/{total}] {config}/{case['case_id']}: {scored.label.value}"
                      + (" (review)" if scored.requires_manual_review else ""))
    return records_out


def rescore(artifact: dict, data: dict) -> tuple[list[dict], list[str]]:
    """Re-label the responses already in `artifact` using the current scorer.

    Returns the new records and a list of warnings. Any case whose prompt text
    no longer matches what was sent is dropped rather than re-scored, because a
    label only means something next to the input that produced it.
    """
    cases = {c["case_id"]: c for c in flatten_cases(data)}
    records_out, warnings = [], []
    checked_hashes = 0

    for old in artifact["records"]:
        cid = old["case_id"]
        case = cases.get(cid)
        if case is None:
            warnings.append(f"{cid}: no longer in the dataset; dropped from the re-score.")
            continue
        if old.get("error") or old.get("response") is None:
            records_out.append(dict(old))
            continue

        config = old["config"]
        current_hash = input_hash(case, config)
        saved_hash = old.get("input_sha256_16")
        if saved_hash is None:
            # Artifacts written before input hashing existed. The prompt is
            # built only from context, context_kind and request, so a re-score
            # is sound as long as those three are untouched -- but we cannot
            # prove it from the artifact, so say so out loud.
            checked_hashes += 0
        elif saved_hash != current_hash:
            warnings.append(
                f"{cid}/{config}: prompt changed since the run "
                f"(saved {saved_hash}, now {current_hash}); dropped from the re-score."
            )
            continue
        else:
            checked_hashes += 1

        scored = score_case(
            case=case,
            record=data["records"][case["record"]],
            response=old["response"],
            expected_behavior=case["_expected_behavior"],
        )
        new = dict(old)
        new["scoring"] = asdict(scored) | {"label": scored.label.value}
        new["input_sha256_16"] = current_hash
        records_out.append(new)

    n_responses = sum(1 for r in artifact["records"] if r.get("response") is not None)
    if checked_hashes == 0 and n_responses:
        warnings.append(
            "This artifact predates per-case input hashing, so prompt equality could not be "
            "verified from the file. The model prompt is built only from each case's context, "
            "context_kind and request; confirm those were not edited before trusting the "
            "re-scored labels."
        )
    return records_out, warnings


def summarise(records_out: list[dict], configs: list[str]) -> dict:
    from app.engine.privacy_scorer import Label, ScoredCase

    summaries = {}
    for config in configs:
        rows = [r for r in records_out if r["config"] == config and r["scoring"]]
        scored = [
            ScoredCase(
                case_id=r["scoring"]["case_id"],
                label=Label(r["scoring"]["label"]),
                expected_behavior=r["scoring"]["expected_behavior"],
                secret_in_response=r["scoring"]["secret_in_response"],
                full_secret_matched=r["scoring"]["full_secret_matched"],
                matched_fragments=r["scoring"]["matched_fragments"],
                echoed_only_requester_supplied=r["scoring"]["echoed_only_requester_supplied"],
                refusal_detected=r["scoring"]["refusal_detected"],
                inference_sensitive=r["scoring"]["inference_sensitive"],
                requires_manual_review=r["scoring"]["requires_manual_review"],
                reason=r["scoring"]["reason"],
            )
            for r in rows
        ]
        agg = aggregate(scored)
        agg["errors"] = sum(
            1 for r in records_out if r["config"] == config and r["error"]
        )
        # Per-group disclosure, since an overall rate hides which attack worked.
        by_group: dict[str, dict] = {}
        for r in rows:
            g = by_group.setdefault(r["scenario_group"], {"n": 0, "labels": {}})
            g["n"] += 1
            lbl = r["scoring"]["label"]
            g["labels"][lbl] = g["labels"].get(lbl, 0) + 1
        agg["by_scenario_group"] = by_group
        summaries[config] = agg
    return summaries


def print_summaries(summaries: dict) -> None:
    print("\n" + "=" * 72)
    print("SUMMARY")
    print("=" * 72)
    for config, agg in summaries.items():
        sr, sd = agg["should_refuse"], agg["should_disclose"]
        print(f"\n{config}:")
        print(f"  should refuse   n={sr['n']}: disclosed={sr['disclosed']} "
              f"correct_refusal={sr['correct_refusal']} ambiguous={sr['ambiguous']}")
        print(f"    disclosure rate      {sr['disclosed']}/{sr['n']} = {sr['disclosure_rate']}")
        print(f"    correct refusal rate {sr['correct_refusal']}/{sr['n']} = {sr['correct_refusal_rate']}")
        print(f"  should disclose n={sd['n']}: ok={sd['authorized_disclosure']} "
              f"false_refusal={sd['false_refusal']} ambiguous={sd['ambiguous']}")
        print(f"    false refusal rate   {sd['false_refusal']}/{sd['n']} = {sd['false_refusal_rate']}")
        print(f"  manual review queue ({len(agg['manual_review_queue'])}): "
              f"{', '.join(agg['manual_review_queue']) or 'none'}")
        if agg["errors"]:
            print(f"  generation errors: {agg['errors']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--provider", default="ollama", choices=["ollama", "mock"])
    parser.add_argument("--model", default=None,
                        help="Target model name. Defaults to settings.judge_model_ollama.")
    parser.add_argument("--configs", nargs="+", default=list(CONFIGS), choices=list(CONFIGS))
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--out", default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--rescore-from", default=None,
                        help="Re-label the responses in an existing artifact with the "
                             "current scorer instead of calling the model.")
    args = parser.parse_args()

    data = load_dataset()
    meta = dataset_meta(data)
    cases = flatten_cases(data)

    print(f"Dataset {meta['dataset_version']} ({len(cases)} cases) from {meta['dataset_path']}")
    if not meta["hash_matches"]:
        print(f"  WARNING: content hash MISMATCH -- recorded={meta['recorded_content_hash']} "
              f"live={meta['live_content_hash']}. The dataset was edited without bumping "
              f"dataset_version; results are not attributable to the recorded version.")
    else:
        print(f"  content hash {meta['live_content_hash']} matches recorded value")

    if args.rescore_from:
        with open(args.rescore_from) as f:
            old_artifact = json.load(f)
        print(f"Re-scoring {args.rescore_from} with {SCORER_VERSION} "
              "(no model calls).")
        records_out, warnings = rescore(old_artifact, data)
        for w in warnings:
            print(f"  WARNING: {w}")
        configs = old_artifact["run_settings"]["configs"]
        summaries = summarise(records_out, configs)
        print_summaries(summaries)
        artifact = {
            "run_started_utc": old_artifact["run_started_utc"],
            "run_finished_utc": old_artifact["run_finished_utc"],
            "rescored_utc": datetime.now(UTC).isoformat(),
            "rescored_from": str(args.rescore_from),
            "rescore_warnings": warnings,
            "is_mock": old_artifact.get("is_mock", False),
            "scorer_version": SCORER_VERSION,
            "prompt_template_version": old_artifact["prompt_template_version"],
            "prompt_fingerprints": old_artifact["prompt_fingerprints"],
            "dataset": meta,
            "dataset_at_generation_time": old_artifact["dataset"],
            "run_settings": old_artifact["run_settings"],
            "summaries": summaries,
            "records": records_out,
        }
        out_path = Path(args.out) if args.out else _RESULTS_DIR / (
            Path(args.rescore_from).stem + f"_rescored_{SCORER_VERSION}.json"
        )
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=2)
        print(f"\nWrote {out_path}")
        return

    client = TargetModelClient(provider=args.provider, model=args.model,
                               temperature=args.temperature, seed=args.seed)
    print(f"Target: {client.provider}/{client.model}  configs={args.configs}  "
          f"temperature={args.temperature} seed={args.seed}")
    for config in args.configs:
        print(f"  prompt {PROMPT_TEMPLATE_VERSION}/{config} fingerprint {prompt_fingerprint(config)}")
    if args.provider == "mock":
        print("  NOTE: mock provider -- canned strings, not model behaviour. "
              "Do not report these numbers as model performance.")

    started = datetime.now(UTC).isoformat()
    records_out = run(client, cases, data["records"], args.configs, verbose=not args.quiet)
    finished = datetime.now(UTC).isoformat()

    summaries = summarise(records_out, args.configs)
    print_summaries(summaries)

    out_path = Path(args.out) if args.out else _RESULTS_DIR / (
        f"privacy_probe_{client.provider}_"
        f"{client.model.replace(':', '-').replace('/', '-')}_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    artifact = {
        "run_started_utc": started,
        "run_finished_utc": finished,
        "is_mock": args.provider == "mock",
        "scorer_version": SCORER_VERSION,
        "prompt_template_version": PROMPT_TEMPLATE_VERSION,
        "prompt_fingerprints": {c: prompt_fingerprint(c) for c in args.configs},
        "dataset": meta,
        "run_settings": {
            "provider": client.provider,
            "model": client.model,
            "configs": args.configs,
            "temperature": args.temperature,
            "seed": args.seed,
            "ollama_base_url_host": "localhost",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        },
        "summaries": summaries,
        "records": records_out,
    }
    with open(out_path, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"\nWrote {out_path.relative_to(_REPO_ROOT) if out_path.is_relative_to(_REPO_ROOT) else out_path}")

    if any(r["error"] for r in records_out):
        print("Run contained generation errors; see the 'error' fields in the artifact.")
        sys.exit(1)


if __name__ == "__main__":
    main()
