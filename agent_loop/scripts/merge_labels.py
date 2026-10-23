"""Merge a returned label file into the review sheet, by run id.

Usage:
    python -m agent_loop.scripts.merge_labels --label dev_baseline \\
        --labels-csv path/to/returned.csv \\
        --flag-run-ids dnt-026,msr-017

Validation runs before anything is written, and a problem stops the merge
rather than being repaired. Quietly dropping an unknown id or coercing a
mistyped label would change what the annotator said, and every agreement
figure downstream rests on that being untouched.

Checked:
  the id sets match exactly, with no missing, extra or duplicate ids
  every label value is in the documented vocabulary
  the sheet itself has no duplicate run ids

Labels are copied across verbatim. The only thing this writes that the
annotator did not is an appended note on a flagged row, which records that the
row's automated verdict had already been seen before labelling and that its
independence is therefore compromised.
"""

import argparse
import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEW_DIR = REPO_ROOT / "results" / "agent_loop" / "review"

FLAG_NOTE = "saw verdict earlier"


def validate(sheet_rows: list[dict], label_rows: list[dict]) -> list[str]:
    """Every reason this merge must not proceed. Empty means it may."""
    from agent_loop.review_sheet import (
        CORRECT_LABELS,
        FAITHFUL_LABELS,
        REASONING_LABELS,
        RUN_ID,
    )

    problems: list[str] = []

    sheet_ids = [r[RUN_ID] for r in sheet_rows]
    label_ids = [r[RUN_ID] for r in label_rows]

    for name, ids in (("sheet", sheet_ids), ("label file", label_ids)):
        duplicates = sorted({i for i in ids if ids.count(i) > 1})
        if duplicates:
            problems.append(f"duplicate run ids in the {name}: {duplicates}")

    missing = sorted(set(sheet_ids) - set(label_ids))
    extra = sorted(set(label_ids) - set(sheet_ids))
    if missing:
        problems.append(f"{len(missing)} sheet rows have no label: {missing}")
    if extra:
        problems.append(f"{len(extra)} labelled ids are not in the sheet: {extra}")

    vocabularies = {
        "human_correct": CORRECT_LABELS,
        "human_faithful": FAITHFUL_LABELS,
        "human_reasoning": REASONING_LABELS,
    }
    for row in label_rows:
        for column, vocabulary in vocabularies.items():
            value = (row.get(column) or "").strip()
            if column == "human_correct" and not value:
                problems.append(f"{row[RUN_ID]}: human_correct is blank")
                continue
            if value and value not in vocabulary:
                problems.append(
                    f"{row[RUN_ID]}: {column}={value!r} is not one of {list(vocabulary)}"
                )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="dev_baseline")
    parser.add_argument("--labels-csv", required=True)
    parser.add_argument(
        "--flag-run-ids",
        default="",
        help="comma separated run ids whose automated verdict was seen before labelling",
    )
    parser.add_argument("--flag-note", default=FLAG_NOTE)
    args = parser.parse_args()

    from agent_loop.review_sheet import HUMAN_COLUMNS, RUN_ID

    sheet_path = REVIEW_DIR / f"{args.label}_review.csv"
    labels_path = Path(args.labels_csv)
    for path in (sheet_path, labels_path):
        if not path.exists():
            raise SystemExit(f"missing {path}")

    with open(sheet_path, newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        sheet_rows = list(reader)
    with open(labels_path, newline="") as handle:
        label_rows = list(csv.DictReader(handle))

    problems = validate(sheet_rows, label_rows)
    if problems:
        print(f"REFUSED. {len(problems)} problem(s), nothing was written:")
        for problem in problems:
            print(f"  - {problem}")
        raise SystemExit(1)

    print(f"validation passed: {len(label_rows)} labels match {len(sheet_rows)} sheet rows exactly")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = sheet_path.with_suffix(f".bak-{stamp}.csv")
    shutil.copy2(sheet_path, backup)
    print(f"backed up the sheet to {backup}")

    flagged = {i.strip() for i in args.flag_run_ids.split(",") if i.strip()}
    unknown = sorted(flagged - {r[RUN_ID] for r in sheet_rows})
    if unknown:
        raise SystemExit(f"cannot flag ids that are not in the sheet: {unknown}")

    by_id = {row[RUN_ID]: row for row in label_rows}
    merged = 0
    for row in sheet_rows:
        label = by_id[row[RUN_ID]]
        for column in HUMAN_COLUMNS:
            row[column] = (label.get(column) or "").strip()
        merged += 1
        if row[RUN_ID] in flagged:
            existing = row["human_notes"].strip()
            row["human_notes"] = f"{existing} [{args.flag_note}]".strip()

    with open(sheet_path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sheet_rows)

    print(f"merged {merged} labels into {sheet_path}")
    if flagged:
        print(f"annotated {len(flagged)} row(s) with [{args.flag_note}]: {sorted(flagged)}")


if __name__ == "__main__":
    main()
