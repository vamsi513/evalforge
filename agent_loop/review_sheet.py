"""Layer 3: the blind human review sheet.

The sheet exists to produce a label that owes nothing to the automation, so it
carries no rule verdict, no judge score and no suggested answer. What it does
carry is the ground truth the task was written with and the evidence the agent
actually had, because a reviewer cannot judge faithfulness without seeing the
passages, and cannot judge correctness without knowing what the task required.
That distinction, between stating what the task demands and asserting how this
response did, is the whole line this module defends.

`assert_no_verdict_columns` runs on every export rather than only in the tests.
A verdict column added later should break the export, not slip into a sheet.

The carry-forward, backup and typo-reporting behaviour follows the pattern
already established by scripts/analyze_privacy_results.py in this repository:
regenerating a sheet must never silently destroy completed labelling, and a
label describes one specific response, so it is not carried across a changed
answer.
"""

import csv
import shutil
from datetime import UTC, datetime
from pathlib import Path

RUN_ID = "run_id"
ANSWER = "agent_answer"

# Evidence and ground truth the reviewer needs.
CONTEXT_COLUMNS = (
    RUN_ID,
    "category",
    "question",
    "requirement",
    "source_used",
    "passages_shown",
    ANSWER,
)

# The reviewer's own judgment. Always exported empty.
HUMAN_COLUMNS = (
    "human_correct",
    "human_faithful",
    "human_reasoning",
    "human_notes",
)

COLUMNS = CONTEXT_COLUMNS + HUMAN_COLUMNS

# Closed vocabularies. A value outside these is reported, not counted, so a
# capitalised variant never reads as the reviewer contradicting the automation.
CORRECT_LABELS = ("pass", "fail", "ambiguous")
FAITHFUL_LABELS = ("yes", "no", "not_applicable", "ambiguous")
REASONING_LABELS = ("good", "adequate", "poor", "ambiguous")

# Any column name containing one of these would be an automated opinion.
_VERDICT_MARKERS = (
    "rule",
    "judge",
    "automated",
    "score",
    "verdict",
    "predicted",
    "suggest",
    "expected_route",
    "expected_answer",
    "passed",
    "failure",
    "label_hint",
)

_PASSAGE_LIMIT = 4000


class VerdictLeakError(RuntimeError):
    """Raised when a column that carries an automated opinion reaches the sheet."""


def assert_no_verdict_columns(fieldnames) -> None:
    """Refuse to write a sheet that carries an automated opinion."""
    for name in fieldnames:
        if name in HUMAN_COLUMNS:
            continue
        lowered = name.lower()
        for marker in _VERDICT_MARKERS:
            if marker in lowered:
                raise VerdictLeakError(
                    f"column {name!r} looks like an automated verdict. The review sheet "
                    "must not anchor the reviewer with rule or judge output."
                )


def describe_requirement(task: dict) -> str:
    """What the task demands, stated without reference to this response."""
    if task["expected_answer"]:
        facts = [" or ".join(group) for group in task["expected_answer"]["required"]]
        return "The answer must state: " + "; ".join(facts)
    if task["expected_behavior"]:
        return task["expected_behavior"]
    if task["expected_route"]:
        return f"The agent should use the {task['expected_route']} source."
    return ""


def _row(trace: dict, task: dict) -> dict:
    passages = trace.get("context") or ""
    if len(passages) > _PASSAGE_LIMIT:
        passages = passages[:_PASSAGE_LIMIT] + " [truncated]"
    return {
        RUN_ID: trace["task_id"],
        "category": task["category"],
        "question": task["question"],
        "requirement": describe_requirement(task),
        "source_used": trace.get("route_decision") or "",
        "passages_shown": passages or "(no passages were retrieved)",
        ANSWER: trace.get("answer") or "",
        **{column: "" for column in HUMAN_COLUMNS},
    }


def read_sheet(path: Path) -> list[dict]:
    with open(path, newline="") as handle:
        return list(csv.DictReader(handle))


def _existing_labels(path: Path) -> dict[str, dict]:
    """Labels already on disk, keyed by run id, with the answer they describe."""
    if not path.exists():
        return {}
    labels: dict[str, dict] = {}
    for row in read_sheet(path):
        if any(row.get(column, "").strip() for column in HUMAN_COLUMNS):
            labels[row[RUN_ID]] = row
    return labels


def write_review_sheet(
    traces: list[dict],
    tasks_by_id: dict[str, dict],
    path: Path,
    *,
    discard_existing_labels: bool = False,
) -> dict:
    """Write the sheet, preserving any labelling already done.

    Returns a report of what was carried forward and what was not, so a
    regeneration is never a silent event.
    """
    assert_no_verdict_columns(COLUMNS)

    path = Path(path)
    existing = _existing_labels(path)
    backup: str | None = None
    if path.exists():
        # Any existing sheet is backed up, labelled or not. An unlabelled sheet
        # still represents a decision about which rows were to be reviewed, and
        # replacing it silently would erase the record of that draw.
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        backup_path = path.with_suffix(f".bak-{stamp}.csv")
        shutil.copy2(path, backup_path)
        backup = str(backup_path)

    rows = [_row(trace, tasks_by_id[trace["task_id"]]) for trace in traces]
    exported_ids = {row[RUN_ID] for row in rows}

    carried: list[str] = []
    not_carried_changed: list[str] = []
    orphaned = sorted(set(existing) - exported_ids)

    if not discard_existing_labels:
        for row in rows:
            previous = existing.get(row[RUN_ID])
            if not previous:
                continue
            if previous.get(ANSWER, "") != row[ANSWER]:
                # A label describes one specific response. If the answer moved,
                # the old judgment does not transfer and must not be reused.
                row["human_notes"] = (
                    "NOT CARRIED FORWARD: the agent's answer changed since this was labelled."
                )
                not_carried_changed.append(row[RUN_ID])
                continue
            for column in HUMAN_COLUMNS:
                row[column] = previous.get(column, "")
            carried.append(row[RUN_ID])

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS))
        writer.writeheader()
        writer.writerows(rows)

    return {
        "path": str(path),
        "rows": len(rows),
        "labels_found_on_disk": len(existing),
        "labels_carried_forward": sorted(carried),
        "labels_not_carried_answer_changed": sorted(not_carried_changed),
        "labels_orphaned_row_no_longer_exported": orphaned,
        "backup_written": backup,
    }


def load_human_labels(path: Path) -> dict:
    """Read a filled sheet back, separating usable labels from problems."""
    rows = read_sheet(Path(path))
    labels: dict[str, dict] = {}
    unrecognised: list[dict] = []
    unlabelled: list[str] = []

    vocabularies = {
        "human_correct": CORRECT_LABELS,
        "human_faithful": FAITHFUL_LABELS,
        "human_reasoning": REASONING_LABELS,
    }

    for row in rows:
        run_id = row[RUN_ID]
        value = (row.get("human_correct") or "").strip()
        if not value:
            unlabelled.append(run_id)
            continue

        entry: dict = {}
        ok = True
        for column, vocabulary in vocabularies.items():
            raw = (row.get(column) or "").strip()
            if not raw:
                entry[column] = None
                continue
            if raw not in vocabulary:
                unrecognised.append({"run_id": run_id, "column": column, "value": raw})
                if column == "human_correct":
                    ok = False
                continue
            entry[column] = raw
        if ok:
            entry["human_notes"] = (row.get("human_notes") or "").strip()
            labels[run_id] = entry

    return {
        "labels": labels,
        "n_labelled": len(labels),
        "unlabelled": sorted(unlabelled),
        "unrecognised_values": unrecognised,
    }


def human_label(entry: dict) -> bool | None:
    """The binary this layer contributes. Ambiguous is not forced to a side."""
    value = entry.get("human_correct")
    if value == "pass":
        return True
    if value == "fail":
        return False
    return None
