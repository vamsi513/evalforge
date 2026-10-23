"""Export development runs to a blind human review sheet.

Usage:
    python -m agent_loop.scripts.make_review_sheet --label dev_baseline
    python -m agent_loop.scripts.make_review_sheet --label dev_baseline --per-category 10

The sheet carries no rule verdict, no judge score and no suggested label. It
carries the question, what the task required, the source the agent used, the
passages it was shown and the answer it gave, which is what a reviewer needs to
decide correctness and faithfulness without being anchored.

Rows are drawn evenly: the same number from each of the four categories, so
every per category agreement figure rests on the same sample size. Selection
sees only task ids and the seed. It has no access to a rule result or a judge
score, so a row cannot be picked because it failed, and the draw is
reproducible.

Regenerating is safe. Existing labels are carried forward where the agent's
answer is unchanged, the previous file is backed up first, and a label whose
answer has changed is cleared with a note rather than silently reused.
"""

import argparse
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
RESULTS_DIR = REPO_ROOT / "results" / "agent_loop"
TRACES_DIR = RESULTS_DIR / "traces"
REVIEW_DIR = RESULTS_DIR / "review"

DEFAULT_PER_CATEGORY = 10
DEFAULT_SEED = 5


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="dev_baseline")
    parser.add_argument("--per-category", type=int, default=DEFAULT_PER_CATEGORY)
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED)
    parser.add_argument(
        "--discard-existing-labels",
        action="store_true",
        help="start the sheet over, after backing up what is there",
    )
    args = parser.parse_args()

    from agent_loop.review_sheet import COLUMNS, HUMAN_COLUMNS, write_review_sheet
    from agent_loop.splitting import even_sample
    from agent_loop.tasks import DATA_DIR, load_tasks

    tasks_by_id = {task["id"]: task for task in load_tasks()}
    split = json.loads((DATA_DIR / "split.json").read_text())
    development = set(split["development_ids"])

    folder = TRACES_DIR / args.label
    if not folder.exists():
        raise SystemExit(f"no traces at {folder}")
    traces = [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]

    # Held out runs must never reach a review sheet: labelling them would be
    # inspecting held out behaviour, which is the one thing the split forbids.
    off_limits = [t["task_id"] for t in traces if t["task_id"] not in development]
    if off_limits:
        raise SystemExit(
            f"{len(off_limits)} traces in {args.label} are not development tasks "
            f"(first few: {off_limits[:5]}). Reviewing held out runs would break the split."
        )

    # Only the id and the category are handed to the sampler. Nothing about how
    # a run turned out is in scope, by construction rather than by discipline.
    selectable = [
        {"id": t["task_id"], "category": tasks_by_id[t["task_id"]]["category"]} for t in traces
    ]
    picked = set(even_sample(selectable, per_category=args.per_category, seed=args.seed))
    chosen = [t for t in traces if t["task_id"] in picked]

    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    out = REVIEW_DIR / f"{args.label}_review.csv"
    report = write_review_sheet(
        chosen, tasks_by_id, out, discard_existing_labels=args.discard_existing_labels
    )

    counts: dict[str, int] = {}
    for trace in chosen:
        category = tasks_by_id[trace["task_id"]]["category"]
        counts[category] = counts.get(category, 0) + 1

    print(f"wrote {report['path']}")
    print(f"  rows: {report['rows']}, {args.per_category} per category (seed {args.seed})")
    print(f"  counts: {dict(sorted(counts.items()))}")
    print(f"  columns: {', '.join(COLUMNS)}")
    print(f"  to fill in: {', '.join(HUMAN_COLUMNS)} (exported blank)")
    if report["backup_written"]:
        print(f"  previous sheet backed up to: {report['backup_written']}")
    if report["labels_found_on_disk"]:
        print(f"  labels carried forward: {len(report['labels_carried_forward'])}")
        print(f"  cleared, answer changed: {report['labels_not_carried_answer_changed']}")
        print(f"  orphaned: {report['labels_orphaned_row_no_longer_exported']}")

    guide = REVIEW_DIR / "HOW_TO_LABEL.md"
    guide.write_text(_LABELLING_GUIDE)
    print(f"  labelling guide: {guide}")


_LABELLING_GUIDE = """# How to label the review sheet

The sheet holds 40 rows, 10 from each of the four task categories, drawn from
the development split only with a fixed seed. The sampler is given nothing but
task ids and their category, so no row is here because it failed.

Fill in four columns per row. Everything else is there to inform the judgment,
not to be edited.

The sheet deliberately shows you no rule result and no judge score. That is the
point: the agreement numbers are only meaningful if your label was formed
independently of the automation.

## What 40 rows costs

40 rows instead of 60 means every agreement figure is less certain. Cohen's
kappa on 40 paired labels has a noticeably wider bootstrap interval than on 60,
and the per category figures rest on 10 rows each, where a single disagreement
moves kappa a long way. Treat the per category numbers as indicative and the
overall figure as the one worth quoting. This is recorded in the limitations
section of agent_loop/README.md as well.

## human_correct

The overall verdict on whether the agent did the right thing for this task.
Use the `requirement` column as the standard.

- `pass` the response meets the requirement
- `fail` it does not
- `ambiguous` you genuinely cannot decide, or the task itself is unclear

`ambiguous` is not folded into pass or fail. It is reported separately and
excluded from the agreement statistics, so use it rather than guessing.

## human_faithful

Whether every specific claim is supported by `passages_shown`.

- `yes` every figure, name and date in the answer is in the passages
- `no` at least one specific claim is not supported, even if it is true
- `not_applicable` no passages were retrieved, so there is nothing to be
  faithful to. Typical for the direct route
- `ambiguous` you cannot tell

A correct answer can be unfaithful: if the agent stated a right figure that was
not in the passages it was shown, that is `human_correct=pass` and
`human_faithful=no`. Recording that combination is one of the more useful
things this sheet can surface.

## human_reasoning

Quality of the reasoning, separate from whether the final answer is right.

- `good` addresses the question directly and follows from the evidence
- `adequate` arrives somewhere reasonable but is vague, padded or partly off topic
- `poor` incoherent, evasive, or contradicts itself
- `ambiguous` you cannot tell

## human_notes

Free text. Worth using when you pick `ambiguous`, when correct and faithful
disagree, or when the task itself looks badly written. A note saying a task is
flawed is a useful result.

## Practical points

- Label every row. A blank `human_correct` counts as unlabelled, not as a pass.
- Values are lowercase and must match exactly. `Pass` is reported as an
  unrecognised value rather than counted, so it will not quietly become a
  disagreement.
- Save as CSV in place. Regenerating the sheet preserves your labels, backs up
  the previous file first, and clears only labels whose answer has changed.
"""


if __name__ == "__main__":
    main()
