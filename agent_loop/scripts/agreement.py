"""Judge versus human and rule versus human agreement on the review sample.

Usage:
    python -m agent_loop.scripts.agreement --label dev_baseline

Reads the filled review CSV, the layer 1 rule results and the layer 2 judge
results, and compares the three on the rows a human actually labelled.

Percent agreement and Cohen's kappa are both reported, because on a sample this
size and this unbalanced they say different things: when the agent passes most
tasks, two raters agree most of the time by luck alone, and only kappa
discounts that. Each kappa comes with a bootstrap 95 percent interval, since a
point estimate on sixty items is not worth much by itself.

Rows the human marked ambiguous are excluded and counted, not folded into pass
or fail. Forcing them to a side would manufacture agreement or disagreement
that the reviewer explicitly declined to assert.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"
SCORES_DIR = RESULTS_DIR / "scores"
REVIEW_DIR = RESULTS_DIR / "review"
AGREEMENT_DIR = RESULTS_DIR / "agreement"

# Below this, a layer is not reliable enough to stand in for a human on that
# slice. Landis and Koch call 0.40 to 0.60 moderate; anything under 0.40 is
# fair at best and is reported as unreliable here.
_UNRELIABLE_KAPPA = 0.40
_MIN_SLICE = 5

# Marker written into human_notes by merge_labels for a row whose automated
# verdict the annotator had already seen.
FLAG_MARKER = "saw verdict earlier"



def _print_block(source: dict) -> None:
    for key in ("rule_vs_human", "judge_vs_human", "rule_vs_judge"):
        block = source.get(key)
        if not block:
            continue
        kappa = block["cohens_kappa"]
        interval = (
            f"[{kappa['ci_95_low']}, {kappa['ci_95_high']}]"
            if kappa["point_estimate"] is not None
            else "n/a"
        )
        print(
            f"  {block['pair']:<18} n={block['n']:<3} "
            f"agreement={block['percent_agreement']:>6.1%}  "
            f"kappa={kappa['point_estimate']}  95% CI {interval}"
        )
        print(f"      {block['confusion']}")
        if kappa.get("constant_rater"):
            print("      NOTE: one rater constant, kappa degenerate")
        if kappa.get("uninformative"):
            print("      NOTE: interval spans most of the range, kappa uninformative")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="dev_baseline")
    parser.add_argument("--review-csv", default=None)
    args = parser.parse_args()

    from agent_loop.metrics import agreement_report, bootstrap_kappa_ci
    from agent_loop.review_sheet import human_label, load_human_labels

    review_path = Path(args.review_csv) if args.review_csv else REVIEW_DIR / f"{args.label}_review.csv"
    rules_path = SCORES_DIR / f"{args.label}_rules.json"
    judge_path = SCORES_DIR / f"{args.label}_judge.json"

    for path in (review_path, rules_path):
        if not path.exists():
            raise SystemExit(f"missing {path}")

    human = load_human_labels(review_path)
    if not human["labels"]:
        raise SystemExit(
            f"{review_path} has no labels yet. Fill in human_correct and run this again."
        )

    rules = {r["task_id"]: r for r in json.loads(rules_path.read_text())["results"]}
    judge: dict[str, dict] = {}
    if judge_path.exists():
        judge = {j["task_id"]: j for j in json.loads(judge_path.read_text())["judgments"]}
    else:
        print(f"note: {judge_path} does not exist, reporting rule versus human only")

    categories: dict[str, str] = {task_id: rules[task_id]["category"] for task_id in rules}

    paired: list[dict] = []
    ambiguous: list[str] = []
    for run_id, entry in human["labels"].items():
        label = human_label(entry)
        if label is None:
            ambiguous.append(run_id)
            continue
        if run_id not in rules:
            continue
        paired.append(
            {
                "task_id": run_id,
                "category": categories.get(run_id, "unknown"),
                "human": label,
                "rule": rules[run_id]["rule_pass"],
                "judge": bool(judge[run_id]["judge_passed"]) if run_id in judge else None,
                "human_faithful": entry.get("human_faithful"),
                "notes": entry.get("human_notes", ""),
            }
        )

    if not paired:
        raise SystemExit("no usable pairs: every labelled row was ambiguous or unmatched")

    report: dict = {
        "label": args.label,
        "computed_at": datetime.now(UTC).isoformat(),
        "review_csv": str(review_path),
        "rows_in_sheet": human["n_labelled"] + len(human["unlabelled"]),
        "rows_labelled": human["n_labelled"],
        "rows_unlabelled": len(human["unlabelled"]),
        "rows_ambiguous_excluded": len(ambiguous),
        "ambiguous_ids": sorted(ambiguous),
        "unrecognised_values": human["unrecognised_values"],
        "n_compared": len(paired),
        "annotators": 1,
        "annotator_caveat": (
            "One annotator, who also wrote the tasks. These figures measure agreement "
            "with that person's judgment, not with ground truth, and carry no "
            "inter-annotator reliability estimate."
        ),
    }

    def _comparisons(pairs: list[dict]) -> dict:
        block: dict = {}
        if not pairs:
            return block
        block["rule_vs_human"] = agreement_report(
            "rule", [p["rule"] for p in pairs], "human", [p["human"] for p in pairs]
        )
        judged_here = [p for p in pairs if p["judge"] is not None]
        if judged_here:
            block["judge_vs_human"] = agreement_report(
                "judge",
                [p["judge"] for p in judged_here],
                "human",
                [p["human"] for p in judged_here],
            )
            block["rule_vs_judge"] = agreement_report(
                "rule",
                [p["rule"] for p in judged_here],
                "judge",
                [p["judge"] for p in judged_here],
            )
        return block

    # A flagged row is one whose automated verdict the annotator had already
    # seen before labelling. Its label is not independent of the automation,
    # so the comparison is reported with and without those rows.
    flagged = [p["task_id"] for p in paired if FLAG_MARKER in (p["notes"] or "").lower()]
    clean = [p for p in paired if p["task_id"] not in set(flagged)]

    report["overall"] = _comparisons(paired)
    report["flagged_rows"] = sorted(flagged)
    report["flagged_reason"] = (
        "The annotator had already been shown this row's automated verdict in an "
        "earlier report, so the label is not independent of the automation."
    )
    report["excluding_flagged"] = _comparisons(clean)
    report["n_excluding_flagged"] = len(clean)

    # Kept at the top level for compatibility with the per category section below.
    report.update(report["overall"])

    # Where each layer is unreliable, by category.
    by_category: dict[str, list[dict]] = defaultdict(list)
    for pair in paired:
        by_category[pair["category"]].append(pair)

    slices: dict[str, dict] = {}
    for category, pairs in sorted(by_category.items()):
        entry: dict = {"n": len(pairs)}
        if len(pairs) >= _MIN_SLICE:
            entry["rule_vs_human"] = bootstrap_kappa_ci(
                [p["rule"] for p in pairs], [p["human"] for p in pairs]
            )
            judged_slice = [p for p in pairs if p["judge"] is not None]
            if len(judged_slice) >= _MIN_SLICE:
                entry["judge_vs_human"] = bootstrap_kappa_ci(
                    [p["judge"] for p in judged_slice], [p["human"] for p in judged_slice]
                )
        else:
            entry["note"] = f"fewer than {_MIN_SLICE} labelled rows, no kappa computed"
        slices[category] = entry
    report["by_category"] = slices

    unreliable: list[dict] = []
    for category, entry in slices.items():
        for layer in ("judge_vs_human", "rule_vs_human"):
            block = entry.get(layer) or {}
            kappa = block.get("point_estimate")
            if kappa is None or kappa >= _UNRELIABLE_KAPPA:
                continue
            if block.get("constant_rater"):
                reading = (
                    "degenerate, not disagreement: one rater gave the same label to every "
                    "row in this slice, so kappa is 0 however closely the two agree. Read "
                    "the percent agreement and the confusion counts instead."
                )
            else:
                reading = f"below {_UNRELIABLE_KAPPA}, genuinely weak agreement on this slice"
            unreliable.append(
                {
                    "category": category,
                    "comparison": layer,
                    "cohens_kappa": kappa,
                    "n": entry["n"],
                    "constant_rater": block.get("constant_rater"),
                    "reading": reading,
                }
            )
    report["unreliable_slices"] = unreliable

    report["disagreements"] = [
        {
            "task_id": p["task_id"],
            "category": p["category"],
            "human": "pass" if p["human"] else "fail",
            "rule": "pass" if p["rule"] else "fail",
            "judge": None if p["judge"] is None else ("pass" if p["judge"] else "fail"),
            "notes": p["notes"],
        }
        for p in paired
        if p["rule"] != p["human"] or (p["judge"] is not None and p["judge"] != p["human"])
    ]

    AGREEMENT_DIR.mkdir(parents=True, exist_ok=True)
    out = AGREEMENT_DIR / f"{args.label}_agreement.json"
    out.write_text(json.dumps(report, indent=2) + "\n")

    print(f"labelled {report['rows_labelled']} of {report['rows_in_sheet']} rows")
    print(f"  ambiguous excluded: {report['rows_ambiguous_excluded']}")
    print(f"  unrecognised values: {len(report['unrecognised_values'])}")
    print(f"  compared: {report['n_compared']}")
    for heading, source in (
        (f"OVERALL (n={len(paired)})", report["overall"]),
        (
            f"EXCLUDING {len(report['flagged_rows'])} FLAGGED ROW(S) "
            f"(n={report['n_excluding_flagged']})",
            report["excluding_flagged"],
        ),
    ):
        print(f"\n{'=' * 64}\n{heading}\n{'=' * 64}")
        _print_block(source)

    if report["flagged_rows"]:
        print(f"\nflagged rows: {report['flagged_rows']}")
        print(f"  {report['flagged_reason']}")

    for key in ():
        block = report.get(key)
        if not block:
            continue
        kappa = block["cohens_kappa"]
        interval = (
            f"[{kappa['ci_95_low']}, {kappa['ci_95_high']}]"
            if kappa["point_estimate"] is not None
            else "n/a"
        )
        flags = []
        if kappa.get("constant_rater"):
            flags.append("one rater constant, kappa degenerate")
        if kappa.get("uninformative"):
            flags.append("interval spans most of the range, kappa uninformative")
        print(
            f"\n{block['pair']}: n={block['n']} "
            f"agreement={block['percent_agreement']:.1%} "
            f"kappa={kappa['point_estimate']} 95% CI {interval}"
        )
        print(f"  {block['confusion']}")
        for flag in flags:
            print(f"  NOTE: {flag}")

    if unreliable:
        print("\nwhere a layer is not reliable:")
        for item in unreliable:
            print(
                f"  {item['comparison']:<16}{item['category']:<22}"
                f"kappa={item['cohens_kappa']} (n={item['n']})"
            )
            print(f"    {item['reading']}")
    else:
        print("\nno slice fell below the unreliability threshold")

    print(f"\ndisagreements: {len(report['disagreements'])}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
