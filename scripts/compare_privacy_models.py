"""
scripts/compare_privacy_models.py -- Pairs two or more privacy-probe runs
case-by-case and reports where the models behaved differently.

The comparison is paired on (case_id, config): every model sees the same 40
cases under the same two prompt configurations, so the informative quantity is
which individual cases changed label, not the difference between two rates.

Before comparing anything it checks that the runs are actually comparable --
same dataset version and content hash, same scorer version, same prompt
template and fingerprints. A cross-model number computed across two dataset
versions or two prompt texts is not a model comparison, it is a confound, so
mismatches abort rather than warn.

Automated and reviewed labels are kept apart and never merged. The headline
cross-model table uses automated labels, because those exist for every run and
are reproducible from the artifacts alone. Reviewed labels are reported per
model only, and if one model has been adjudicated and another has not, the
script says so and refuses to put the two in the same column -- comparing one
model's reviewed rate against another's automated rate would be a false
comparison.

Usage:
    python -m scripts.compare_privacy_models RUN_A.json RUN_B.json
    python -m scripts.compare_privacy_models A.json B.json --out comparison.json
    python -m scripts.compare_privacy_models A.json B.json \\
        --reviewed A.json=review_a.csv --reviewed B.json=review_b.csv
"""

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from scripts.analyze_privacy_results import _MANUAL_LABEL_FIELD, MANUAL_LABELS

_FAILURE_LABELS = ("disclosed", "false_refusal")

# Fields that must agree across runs for a comparison to mean anything.
_COMPARABILITY_KEYS = (
    ("dataset version", lambda a: a["dataset"]["dataset_version"]),
    ("dataset content hash", lambda a: a["dataset"]["live_content_hash"]),
    ("scorer version", lambda a: a["scorer_version"]),
    ("prompt template version", lambda a: a["prompt_template_version"]),
    ("prompt fingerprints", lambda a: json.dumps(a["prompt_fingerprints"], sort_keys=True)),
)


class NotComparable(RuntimeError):
    """Raised when the runs do not share the inputs a comparison depends on."""


def model_label(artifact: dict) -> str:
    rs = artifact["run_settings"]
    return f"{rs['provider']}/{rs['model']}"


def check_comparable(artifacts: dict[str, dict]) -> dict:
    """Abort unless every run shares dataset, scorer and prompts."""
    problems = []
    shared = {}
    for name, getter in _COMPARABILITY_KEYS:
        values = {path: getter(a) for path, a in artifacts.items()}
        distinct = set(values.values())
        if len(distinct) > 1:
            detail = "; ".join(f"{Path(p).name}={v}" for p, v in values.items())
            problems.append(f"{name} differs across runs: {detail}")
        else:
            shared[name] = next(iter(distinct))

    mock = [p for p, a in artifacts.items() if a.get("is_mock")]
    if mock:
        problems.append(
            f"mock run(s) included, which describe canned strings and not model "
            f"behaviour: {', '.join(Path(p).name for p in mock)}"
        )

    if problems:
        raise NotComparable(
            "These runs cannot be compared:\n  - " + "\n  - ".join(problems)
            + "\nRerun the odd one out against the same dataset, scorer and prompts."
        )
    return shared


def _scored(artifact: dict) -> dict[tuple[str, str], dict]:
    return {(r["case_id"], r["config"]): r
            for r in artifact["records"] if r.get("scoring")}


def per_model_summary(artifact: dict, reviewed: dict[tuple[str, str], str] | None) -> dict:
    """Automated counts, and reviewed counts only when labels are present.

    The two are separate keys. `reviewed` is None when that run has not been
    adjudicated, which is different from an empty count.
    """
    rows = _scored(artifact)

    def counts(use_reviewed: bool) -> dict[str, Counter]:
        out: dict[str, Counter] = {"refuse": Counter(), "disclose": Counter()}
        for key, r in rows.items():
            label = r["scoring"]["label"]
            if use_reviewed and reviewed:
                label = reviewed.get(key, label)
            out[r["expected_behavior"]][label] += 1
        return out

    def block(c: dict[str, Counter]) -> dict:
        nr, nd = sum(c["refuse"].values()), sum(c["disclose"].values())
        return {
            "should_refuse": {
                "n": nr,
                "counts": dict(c["refuse"]),
                "disclosure_rate": round(c["refuse"]["disclosed"] / nr, 4) if nr else None,
                "abstained": c["refuse"]["ambiguous"],
            },
            "should_disclose": {
                "n": nd,
                "counts": dict(c["disclose"]),
                "false_refusal_rate": (round(c["disclose"]["false_refusal"] / nd, 4)
                                       if nd else None),
            },
        }

    out = {
        "model": model_label(artifact),
        "automated": block(counts(False)),
        "reviewed": None,
        "n_rows": len(rows),
    }
    if reviewed:
        out["reviewed"] = block(counts(True))
        out["reviewed"]["n_rows_with_human_label"] = sum(1 for k in rows if k in reviewed)
    return out


def case_by_case(artifacts: dict[str, dict],
                 reviewed: dict[str, dict[tuple[str, str], str]] | None = None) -> list[dict]:
    """One row per (case_id, config), with each model's label under both label sets.

    `labels` holds the automated label per model and `reviewed_labels` the
    adjudicated one, falling back to the automated label where no human decision
    exists. The two are never merged into one field, so a breakdown can always say
    which label set it came from. Cases present in some runs but not others are
    reported rather than dropped.
    """
    reviewed = reviewed or {}
    scored = {p: _scored(a) for p, a in artifacts.items()}
    all_keys = sorted(set().union(*(set(s) for s in scored.values())))

    out = []
    for key in all_keys:
        auto, rev = {}, {}
        for path, s in scored.items():
            model = model_label(artifacts[path])
            r = s.get(key)
            auto[model] = r["scoring"]["label"] if r else None
            if r is None:
                rev[model] = None
            else:
                rev[model] = reviewed.get(path, {}).get(key, r["scoring"]["label"])
        present = [v for v in auto.values() if v is not None]
        present_rev = [v for v in rev.values() if v is not None]
        any_model = next(s[key] for s in scored.values() if key in s)
        out.append({
            "case_id": key[0],
            "config": key[1],
            "scenario_group": any_model["scenario_group"],
            "expected_behavior": any_model["expected_behavior"],
            "labels": auto,
            "reviewed_labels": rev,
            "changed": len(set(present)) > 1,
            "changed_reviewed": len(set(present_rev)) > 1,
            "missing_from_some_run": len(present) != len(auto),
            "failed_in": sorted(m for m, v in auto.items() if v in _FAILURE_LABELS),
            "failed_in_reviewed": sorted(m for m, v in rev.items() if v in _FAILURE_LABELS),
        })
    return out


def shared_failure_breakdown(cases: list[dict], n_models: int) -> dict:
    """Rows that failed in every model, under each label set, with group counts.

    Computed here rather than written into the report by hand, because the two
    label sets give different answers -- adjudication can turn an abstention into a
    failure -- and a by-group table copied from one while the total came from the
    other is exactly the mistake this function exists to prevent.
    """
    def block(fail_key: str, label_key: str) -> dict:
        rows = [c for c in cases if len(c[fail_key]) == n_models]
        by_group = Counter(c["scenario_group"] for c in rows)
        by_config = Counter(c["config"] for c in rows)
        per_case: dict[str, set] = {}
        for c in rows:
            per_case.setdefault(c["case_id"], set()).add(c["config"])
        both_configs = sorted(cid for cid, cfgs in per_case.items()
                              if cfgs == {"baseline", "guarded"})
        total = sum(by_group.values())
        assert total == len(rows), "group counts must sum to the total"
        return {
            "label_set": label_key,
            "n": len(rows),
            "by_scenario_group": dict(sorted(by_group.items())),
            "by_config": dict(sorted(by_config.items())),
            "group_counts_sum_to_total": total == len(rows),
            "failed_under_both_configs": both_configs,
            "rows": [{"case_id": c["case_id"], "config": c["config"],
                      "scenario_group": c["scenario_group"]} for c in rows],
        }

    automated = block("failed_in", "automated")
    adjudicated = block("failed_in_reviewed", "reviewed")
    auto_keys = {(r["case_id"], r["config"]) for r in automated["rows"]}
    rev_keys = {(r["case_id"], r["config"]) for r in adjudicated["rows"]}
    return {
        "automated": automated,
        "reviewed": adjudicated,
        "added_by_review": sorted(f"{c}/{g}" for c, g in rev_keys - auto_keys),
        "removed_by_review": sorted(f"{c}/{g}" for c, g in auto_keys - rev_keys),
    }


def read_reviewed(path: Path) -> dict[tuple[str, str], str]:
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            label = (row.get(_MANUAL_LABEL_FIELD) or "").strip()
            if label in MANUAL_LABELS:
                out[(row["case_id"], row["config"])] = label
    return out


def parse_reviewed_arg(raw: str) -> tuple[str, str]:
    if "=" not in raw:
        raise argparse.ArgumentTypeError(
            f"{raw!r} is not of the form ARTIFACT.json=review.csv"
        )
    artifact, csv_path = raw.split("=", 1)
    return artifact.strip(), csv_path.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("runs", nargs="+", help="Two or more privacy_probe_*.json artifacts.")
    parser.add_argument("--reviewed", action="append", type=parse_reviewed_arg, default=[],
                        metavar="ARTIFACT=CSV",
                        help="Attach a reviewed CSV to one artifact. Repeatable.")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if len(args.runs) < 2:
        raise SystemExit("Need at least two runs to compare.")

    artifacts = {}
    for path in args.runs:
        with open(path) as f:
            artifacts[path] = json.load(f)

    try:
        shared = check_comparable(artifacts)
    except NotComparable as exc:
        raise SystemExit(str(exc)) from exc

    reviewed_map: dict[str, dict] = {}
    for artifact_path, csv_path in args.reviewed:
        if artifact_path not in artifacts:
            raise SystemExit(f"--reviewed names {artifact_path}, which is not one of the runs.")
        reviewed_map[artifact_path] = read_reviewed(Path(csv_path))

    print("Comparable runs. Shared inputs:")
    for name, value in shared.items():
        print(f"  {name}: {value}")
    print()

    summaries = {}
    for path, a in artifacts.items():
        summaries[path] = per_model_summary(a, reviewed_map.get(path))

    print("=" * 78)
    print("AUTOMATED LABELS (reproducible from the artifacts alone)")
    print("=" * 78)
    for path, s in summaries.items():
        sr = s["automated"]["should_refuse"]
        sd = s["automated"]["should_disclose"]
        print(f"\n{s['model']}")
        print(f"  should refuse  n={sr['n']}: disclosed={sr['counts'].get('disclosed', 0)} "
              f"correct_refusal={sr['counts'].get('correct_refusal', 0)} "
              f"abstained={sr['abstained']}")
        print(f"    disclosure rate {sr['counts'].get('disclosed', 0)}/{sr['n']} = "
              f"{sr['disclosure_rate']}")
        print(f"  should disclose n={sd['n']}: "
              f"ok={sd['counts'].get('authorized_disclosure', 0)} "
              f"false_refusal={sd['counts'].get('false_refusal', 0)}")
        print(f"    false refusal rate {sd['counts'].get('false_refusal', 0)}/{sd['n']} = "
              f"{sd['false_refusal_rate']}")

    reviewed_present = {p: s for p, s in summaries.items() if s["reviewed"]}
    print("\n" + "=" * 78)
    print("REVIEWED LABELS (per model; not combined into a cross-model rate)")
    print("=" * 78)
    if not reviewed_present:
        print("  No reviewed labels supplied for any run.")
    else:
        for path, s in reviewed_present.items():
            sr = s["reviewed"]["should_refuse"]
            print(f"\n{s['model']} ({s['reviewed']['n_rows_with_human_label']} rows reviewed)")
            print(f"  should refuse  n={sr['n']}: disclosed={sr['counts'].get('disclosed', 0)} "
                  f"correct_refusal={sr['counts'].get('correct_refusal', 0)} "
                  f"abstained={sr['abstained']}")
            print(f"    disclosure rate {sr['counts'].get('disclosed', 0)}/{sr['n']} = "
                  f"{sr['disclosure_rate']}")
        if len(reviewed_present) != len(summaries):
            unreviewed = [summaries[p]["model"] for p in summaries if p not in reviewed_present]
            print(f"\n  NOT COMPARABLE across models: {', '.join(unreviewed)} "
                  f"{'has' if len(unreviewed) == 1 else 'have'} no reviewed labels. "
                  "A reviewed rate for one model and an automated rate for another are "
                  "different measurements and are not placed in the same column. Use the "
                  "automated table above for cross-model claims until every run is "
                  "adjudicated.")

    cases = case_by_case(artifacts, reviewed_map)
    changed = [c for c in cases if c["changed"]]
    models = sorted({m for c in cases for m in c["labels"]})

    changed_rev = [c for c in cases if c["changed_reviewed"]]
    print("\n" + "=" * 78)
    print(f"CASE-BY-CASE: {len(changed)} of {len(cases)} rows differ between models "
          "under AUTOMATED labels")
    if reviewed_map:
        print(f"              {len(changed_rev)} of {len(cases)} differ under "
              "REVIEWED labels")
    print("=" * 78)
    width = max(len(m) for m in models)
    for group in ["authorized_request", "direct_extraction", "indirect_request",
                  "paraphrase", "document_injection"]:
        rows = [c for c in changed if c["scenario_group"] == group]
        if not rows:
            continue
        print(f"\n{group} ({len(rows)} differing)")
        for c in rows:
            print(f"  {c['case_id']:<12} {c['config']:<9} expected={c['expected_behavior']}")
            for m in models:
                print(f"      {m:<{width}} : {c['labels'][m]}")

    breakdown = shared_failure_breakdown(cases, len(models))
    print("\n" + "=" * 78)
    print("ROWS THAT FAILED IN EVERY MODEL")
    print("=" * 78)
    for key in ("automated", "reviewed"):
        b = breakdown[key]
        if key == "reviewed" and not reviewed_map:
            print(f"\n  {key}: no reviewed labels supplied; identical to automated.")
            continue
        groups = ", ".join(f"{g}={n}" for g, n in b["by_scenario_group"].items())
        configs = ", ".join(f"{c}={n}" for c, n in b["by_config"].items())
        print(f"\n  {key} labels: {b['n']} of {len(cases)} rows")
        print(f"    by group : {groups}  (sums to {sum(b['by_scenario_group'].values())})")
        print(f"    by config: {configs}")
        print(f"    failed under BOTH configs: "
              f"{', '.join(b['failed_under_both_configs']) or 'none'}")
    if breakdown["added_by_review"]:
        print(f"\n  added by review   : {', '.join(breakdown['added_by_review'])}")
    if breakdown["removed_by_review"]:
        print(f"  removed by review : {', '.join(breakdown['removed_by_review'])}")

    missing = [c for c in cases if c["missing_from_some_run"]]
    if missing:
        print(f"\nWARNING: {len(missing)} case(s) absent from at least one run: "
              f"{', '.join(c['case_id'] + '/' + c['config'] for c in missing)}")

    if args.out:
        payload = {
            "shared_inputs": shared,
            "runs": {p: {"model": summaries[p]["model"], "artifact": p} for p in artifacts},
            "per_model": {summaries[p]["model"]: summaries[p] for p in summaries},
            "case_by_case": cases,
            "n_cases": len(cases),
            "n_changed_automated_labels": len(changed),
            "n_changed_reviewed_labels": len(changed_rev),
            "reviewed_labels_supplied_for": sorted(
                summaries[p]["model"] for p in reviewed_map
            ),
            "shared_failures": breakdown,
        }
        with open(args.out, "w") as f:
            json.dump(payload, f, indent=2)
        print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
