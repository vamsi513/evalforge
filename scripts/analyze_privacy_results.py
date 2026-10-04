"""
scripts/analyze_privacy_results.py -- Breaks down a saved privacy-probe
artifact: counts with denominators, per-group and per-record failures, a paired
baseline-vs-guarded comparison, and the manual review queue.

Counts come first and every rate is printed as numerator/denominator, because
with 32 should-refuse cases a single case is worth about three percentage
points and a bare percentage reads as more precise than it is.

The baseline-vs-guarded comparison is paired: both configurations see the same
40 cases, so the informative quantity is how many individual cases changed
label, not the difference of two independent proportions. Discordant pairs are
listed by case id.

Confidence intervals are bootstrap over cases, with the same hand-rolled
approach used in scripts/analyze_judge_agreement.py so this script adds no
dependency beyond the standard library.

Usage:
    python -m scripts.analyze_privacy_results evaluation/results/privacy_probe_*.json
    python -m scripts.analyze_privacy_results RESULTS.json --out analysis.json
    python -m scripts.analyze_privacy_results RESULTS.json --review-csv review.csv
    python -m scripts.analyze_privacy_results RESULTS.json --manual-labels review.csv

--review-csv writes every case the scorer could not decide, plus every
disclosure, to a CSV with an empty manual_label column for a human to fill in.
--manual-labels reads that file back and reports agreement with the automated
label. Until somebody actually fills it in, the agreement section says so
rather than reporting a number.
"""

import argparse
import csv
import json
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean

_FAILURE_LABELS = ("disclosed", "false_refusal")
_REVIEW_EXPORT_LABELS = ("ambiguous", "disclosed", "false_refusal")
_MANUAL_LABEL_FIELD = "manual_label"


def _bootstrap_ci(values: list[float], n_resamples: int = 2000,
                  seed: int = 12345) -> dict | None:
    """Percentile bootstrap 95% CI on a mean. With n=32 this interval is wide;
    that width is the point of reporting it."""
    if not values:
        return None
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_resamples):
        means.append(mean(rng.choice(values) for _ in range(n)))
    means.sort()
    lo = means[int(0.025 * n_resamples)]
    hi = means[int(0.975 * n_resamples) - 1]
    return {
        "point_estimate": round(mean(values), 4),
        "ci_95_low": round(lo, 4),
        "ci_95_high": round(hi, 4),
        "n": n,
        "n_resamples": n_resamples,
    }


def _scored_records(artifact: dict, config: str) -> list[dict]:
    return [r for r in artifact["records"] if r["config"] == config and r.get("scoring")]


def _rate_line(num: int, den: int) -> str:
    pct = f"{num / den:.1%}" if den else "n/a"
    return f"{num}/{den} = {pct}"


def analyse_config(artifact: dict, config: str) -> dict:
    rows = _scored_records(artifact, config)
    refuse = [r for r in rows if r["expected_behavior"] == "refuse"]
    disclose = [r for r in rows if r["expected_behavior"] == "disclose"]

    disclosed_flags = [1.0 if r["scoring"]["label"] == "disclosed" else 0.0 for r in refuse]
    false_refusal_flags = [
        1.0 if r["scoring"]["label"] == "false_refusal" else 0.0 for r in disclose
    ]

    by_group: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_group[r["scenario_group"]][r["scoring"]["label"]] += 1

    by_record: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_record[r["record"]][r["scoring"]["label"]] += 1

    by_source: dict[str, Counter] = defaultdict(Counter)
    for r in refuse:
        by_source[r.get("secret_source") or "unknown"][r["scoring"]["label"]] += 1

    latencies = [r["latency_ms"] for r in rows if r.get("latency_ms")]

    return {
        "config": config,
        "n_scored": len(rows),
        "n_errors": sum(1 for r in artifact["records"]
                        if r["config"] == config and r.get("error")),
        "should_refuse": {
            "n": len(refuse),
            "label_counts": dict(Counter(r["scoring"]["label"] for r in refuse)),
            "disclosure_rate_ci": _bootstrap_ci(disclosed_flags),
        },
        "should_disclose": {
            "n": len(disclose),
            "label_counts": dict(Counter(r["scoring"]["label"] for r in disclose)),
            "false_refusal_rate_ci": _bootstrap_ci(false_refusal_flags),
        },
        "by_scenario_group": {k: dict(v) for k, v in sorted(by_group.items())},
        "by_record": {k: dict(v) for k, v in sorted(by_record.items())},
        "by_secret_source_should_refuse": {k: dict(v) for k, v in sorted(by_source.items())},
        "latency_ms": {
            "n": len(latencies),
            "avg": round(mean(latencies), 1) if latencies else None,
            "min": round(min(latencies), 1) if latencies else None,
            "max": round(max(latencies), 1) if latencies else None,
        },
        "failures": sorted(
            r["case_id"] for r in rows if r["scoring"]["label"] in _FAILURE_LABELS
        ),
        "manual_review_queue": sorted(
            r["case_id"] for r in rows if r["scoring"]["requires_manual_review"]
        ),
    }


def paired_comparison(artifact: dict, config_a: str, config_b: str) -> dict:
    """Same cases under both configs, so compare case by case."""
    a = {r["case_id"]: r for r in _scored_records(artifact, config_a)}
    b = {r["case_id"]: r for r in _scored_records(artifact, config_b)}
    shared = sorted(set(a) & set(b))

    changed = []
    for cid in shared:
        la, lb = a[cid]["scoring"]["label"], b[cid]["scoring"]["label"]
        if la != lb:
            changed.append({"case_id": cid, config_a: la, config_b: lb})

    def failures(d: dict) -> set[str]:
        return {cid for cid, r in d.items() if r["scoring"]["label"] in _FAILURE_LABELS}

    fa, fb = failures(a), failures(b)
    return {
        "config_a": config_a,
        "config_b": config_b,
        "n_shared_cases": len(shared),
        "n_label_changes": len(changed),
        "label_changes": changed,
        "failures_only_in_a": sorted(fa - fb),
        "failures_only_in_b": sorted(fb - fa),
        "failures_in_both": sorted(fa & fb),
        "n_failures_a": len(fa),
        "n_failures_b": len(fb),
    }


def write_review_csv(artifact: dict, path: Path) -> int:
    """Export the cases a human needs to look at.

    Includes disclosures and false refusals as well as ambiguous cases: the
    automated label should be checked where it claims a failure, not only where
    it admits uncertainty.
    """
    fields = ["case_id", "config", "scenario_group", "expected_behavior",
              "automated_label", "automated_reason", "response", _MANUAL_LABEL_FIELD,
              "manual_notes"]
    n = 0
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in artifact["records"]:
            if not r.get("scoring"):
                continue
            if r["scoring"]["label"] not in _REVIEW_EXPORT_LABELS:
                continue
            writer.writerow({
                "case_id": r["case_id"],
                "config": r["config"],
                "scenario_group": r["scenario_group"],
                "expected_behavior": r["expected_behavior"],
                "automated_label": r["scoring"]["label"],
                "automated_reason": r["scoring"]["reason"],
                "response": r["response"],
                _MANUAL_LABEL_FIELD: "",
                "manual_notes": "",
            })
            n += 1
    return n


def manual_agreement(artifact: dict, path: Path) -> dict:
    """Compare filled-in human labels against the automated ones.

    Returns a status rather than a number when the file has no labels yet, so
    an unreviewed run cannot be written up as though it had been adjudicated.
    """
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))

    labelled = [r for r in rows if (r.get(_MANUAL_LABEL_FIELD) or "").strip()]
    if not labelled:
        return {
            "status": "no_manual_labels_recorded",
            "n_rows_in_file": len(rows),
            "note": (f"{path.name} has no {_MANUAL_LABEL_FIELD} values filled in. "
                     "No human adjudication has happened, so no agreement figure exists."),
        }

    automated = {(r["case_id"], r["config"]): r["scoring"]["label"]
                 for r in artifact["records"] if r.get("scoring")}
    agree, disagree = 0, []
    for row in labelled:
        key = (row["case_id"], row["config"])
        auto = automated.get(key)
        manual = row[_MANUAL_LABEL_FIELD].strip()
        if auto is None:
            continue
        if auto == manual:
            agree += 1
        else:
            disagree.append({"case_id": row["case_id"], "config": row["config"],
                             "automated": auto, "manual": manual,
                             "notes": row.get("manual_notes", "")})
    n = agree + len(disagree)
    return {
        "status": "manual_labels_present",
        "n_compared": n,
        "n_agree": agree,
        "n_disagree": len(disagree),
        "percent_agreement": round(agree / n, 4) if n else None,
        "disagreements": disagree,
    }


def representative_examples(artifact: dict, per_label: int = 2,
                            excerpt_chars: int = 320) -> dict:
    """A couple of actual responses per label, so the write-up quotes real
    output instead of describing it."""
    out: dict[str, list[dict]] = defaultdict(list)
    for r in artifact["records"]:
        if not r.get("scoring"):
            continue
        label = r["scoring"]["label"]
        if len(out[label]) >= per_label:
            continue
        text = r["response"] or ""
        out[label].append({
            "case_id": r["case_id"],
            "config": r["config"],
            "scenario_group": r["scenario_group"],
            "reason": r["scoring"]["reason"],
            "response_excerpt": text[:excerpt_chars]
                                + ("..." if len(text) > excerpt_chars else ""),
        })
    return dict(out)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", help="Path to a privacy_probe_*.json artifact.")
    parser.add_argument("--out", default=None, help="Write the full analysis as JSON.")
    parser.add_argument("--review-csv", default=None,
                        help="Write the manual review queue to this CSV.")
    parser.add_argument("--manual-labels", default=None,
                        help="Read a filled-in review CSV and report agreement.")
    args = parser.parse_args()

    with open(args.results) as f:
        artifact = json.load(f)

    if artifact.get("is_mock"):
        print("WARNING: this artifact is from a mock run (is_mock=true). The numbers below "
              "describe canned strings, not model behaviour.\n")

    configs = artifact["run_settings"]["configs"]
    ds = artifact["dataset"]
    print(f"Artifact: {args.results}")
    print(f"Model:    {artifact['run_settings']['provider']}/{artifact['run_settings']['model']}"
          f"  temperature={artifact['run_settings']['temperature']}"
          f"  seed={artifact['run_settings']['seed']}")
    print(f"Dataset:  {ds['dataset_version']} hash={ds['live_content_hash']}"
          f" matches_recorded={ds['hash_matches']}")
    print(f"Scorer:   {artifact['scorer_version']}  prompts={artifact['prompt_template_version']}")

    analysis = {
        "source_artifact": str(args.results),
        "is_mock": artifact.get("is_mock", False),
        "dataset": ds,
        "run_settings": artifact["run_settings"],
        "scorer_version": artifact["scorer_version"],
        "per_config": {},
    }

    for config in configs:
        a = analyse_config(artifact, config)
        analysis["per_config"][config] = a
        sr, sd = a["should_refuse"], a["should_disclose"]
        print(f"\n--- {config} ---")
        print(f"  scored {a['n_scored']} responses, {a['n_errors']} generation errors")
        print(f"  should refuse (n={sr['n']}):")
        for label, count in sorted(sr["label_counts"].items()):
            print(f"      {label:<24} {_rate_line(count, sr['n'])}")
        if sr["disclosure_rate_ci"]:
            ci = sr["disclosure_rate_ci"]
            print(f"      disclosure rate 95% CI   [{ci['ci_95_low']}, {ci['ci_95_high']}]"
                  f" (bootstrap, n={ci['n']})")
        print(f"  should disclose (n={sd['n']}):")
        for label, count in sorted(sd["label_counts"].items()):
            print(f"      {label:<24} {_rate_line(count, sd['n'])}")
        print("  by scenario group:")
        for group, counts in a["by_scenario_group"].items():
            total = sum(counts.values())
            detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"      {group:<20} n={total}  {detail}")
        print("  by secret source (should-refuse cases only):")
        for source, counts in a["by_secret_source_should_refuse"].items():
            total = sum(counts.values())
            detail = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            print(f"      {source:<20} n={total}  {detail}")
        if a["latency_ms"]["avg"] is not None:
            lat = a["latency_ms"]
            print(f"  latency ms: avg={lat['avg']} min={lat['min']} max={lat['max']}")
        print(f"  failures ({len(a['failures'])}): {', '.join(a['failures']) or 'none'}")
        print(f"  manual review ({len(a['manual_review_queue'])}): "
              f"{', '.join(a['manual_review_queue']) or 'none'}")

    if len(configs) >= 2:
        comp = paired_comparison(artifact, configs[0], configs[1])
        analysis["paired_comparison"] = comp
        print(f"\n--- paired: {comp['config_a']} vs {comp['config_b']} "
              f"({comp['n_shared_cases']} shared cases) ---")
        print(f"  failures: {comp['n_failures_a']} ({comp['config_a']}) "
              f"vs {comp['n_failures_b']} ({comp['config_b']})")
        print(f"  label changed on {comp['n_label_changes']} cases")
        print(f"  fixed by {comp['config_b']} ({len(comp['failures_only_in_a'])}): "
              f"{', '.join(comp['failures_only_in_a']) or 'none'}")
        print(f"  broken by {comp['config_b']} ({len(comp['failures_only_in_b'])}): "
              f"{', '.join(comp['failures_only_in_b']) or 'none'}")
        print(f"  failing under both ({len(comp['failures_in_both'])}): "
              f"{', '.join(comp['failures_in_both']) or 'none'}")

    analysis["representative_examples"] = representative_examples(artifact)

    if args.review_csv:
        n = write_review_csv(artifact, Path(args.review_csv))
        print(f"\nWrote {n} rows needing review to {args.review_csv} "
              f"(fill in the {_MANUAL_LABEL_FIELD} column).")

    if args.manual_labels:
        agreement = manual_agreement(artifact, Path(args.manual_labels))
        analysis["manual_agreement"] = agreement
        print("\n--- automated vs manual labels ---")
        if agreement["status"] == "no_manual_labels_recorded":
            print(f"  {agreement['note']}")
        else:
            print(f"  compared {agreement['n_compared']}: agree={agreement['n_agree']} "
                  f"disagree={agreement['n_disagree']} "
                  f"({agreement['percent_agreement']})")
            for d in agreement["disagreements"]:
                print(f"    {d['case_id']}/{d['config']}: automated={d['automated']} "
                      f"manual={d['manual']} {d['notes']}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(analysis, f, indent=2)
        print(f"\nWrote analysis to {args.out}")


if __name__ == "__main__":
    main()
