"""Checks on the blind review sheet export.

The first group is the one that matters most: no rule verdict, no judge score
and no suggested label may reach the sheet, in a column name or in a cell. If
one does, the human labels are no longer independent of the automation and the
agreement numbers built on them mean nothing.

The second group is about not destroying work. Regenerating a sheet after the
agent has been re-run must not silently wipe labelling a person spent an
afternoon on.
"""

import csv
from pathlib import Path

import pytest

from agent_loop.review_sheet import (
    ANSWER,
    COLUMNS,
    CONTEXT_COLUMNS,
    HUMAN_COLUMNS,
    RUN_ID,
    VerdictLeakError,
    assert_no_verdict_columns,
    describe_requirement,
    load_human_labels,
    human_label,
    read_sheet,
    write_review_sheet,
)


def _task(**overrides) -> dict:
    base = {
        "id": "msr-001",
        "category": "multi_step_retrieval",
        "question": "How many encoder layers did the original Transformer use?",
        "expected_route": "retrieval",
        "expected_answer": {"required": [["6 encoder", "six encoder"]]},
        "expected_behavior": None,
        "must_not_contain": [],
        "source_docs": ["Introduction to Transformer Architecture"],
    }
    base.update(overrides)
    return base


def _trace(**overrides) -> dict:
    base = {
        "task_id": "msr-001",
        "category": "multi_step_retrieval",
        "question": "How many encoder layers did the original Transformer use?",
        "route_decision": "retrieval",
        "answer": "The original Transformer used 6 encoder layers.",
        "context": "[Source 1] The original architecture uses 6 encoder layers.",
        "latency_ms": 2500.0,
        "state_error": None,
        "invoke_exception": None,
        "variant": "baseline",
    }
    base.update(overrides)
    return base


@pytest.fixture
def pair():
    task = _task()
    return [_trace()], {task["id"]: task}


# --- nothing that anchors the reviewer ------------------------------------------


def test_the_sheet_has_exactly_the_documented_columns(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    assert list(read_sheet(out)[0].keys()) == list(COLUMNS)


def test_no_column_name_carries_an_automated_verdict(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    header = list(read_sheet(out)[0].keys())
    for banned in ("rule", "judge", "automated", "score", "verdict", "predicted", "suggest"):
        offenders = [c for c in header if banned in c.lower() and c not in HUMAN_COLUMNS]
        assert not offenders, f"{offenders} leaks {banned!r} into the sheet"


def test_adding_a_verdict_column_breaks_the_export() -> None:
    """The guard runs on every export, not only in this test."""
    with pytest.raises(VerdictLeakError, match="rule_pass"):
        assert_no_verdict_columns([*COLUMNS, "rule_pass"])
    with pytest.raises(VerdictLeakError, match="judge_score"):
        assert_no_verdict_columns([*COLUMNS, "judge_score"])


def test_the_human_columns_are_exported_blank(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    row = read_sheet(out)[0]
    for column in HUMAN_COLUMNS:
        assert row[column] == "", f"{column} was pre-filled"


def test_no_cell_contains_a_rule_or_judge_outcome(pair, tmp_path) -> None:
    """A verdict could leak through a value as easily as a column name."""
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    blob = " ".join(" ".join(row.values()) for row in read_sheet(out)).lower()
    for banned in ("rule_pass", "judge_score", "judge_passed", "failure_tags", "automated"):
        assert banned not in blob


def test_the_requirement_states_the_task_not_a_verdict(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    requirement = read_sheet(out)[0]["requirement"]
    assert "6 encoder" in requirement
    # It says what is required, never how this particular answer did.
    for banned in ("pass", "fail", "correct", "incorrect", "wrong"):
        assert banned not in requirement.lower()


def test_a_decline_task_shows_its_behaviour_as_the_requirement() -> None:
    task = _task(
        category="unanswerable_decline",
        expected_answer=None,
        expected_behavior="Decline. The documents give no training cost.",
    )
    assert describe_requirement(task).startswith("Decline.")


# --- the reviewer still gets what they need to judge ----------------------------


def test_the_row_carries_the_question_the_answer_and_the_passages(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    row = read_sheet(out)[0]
    assert row["question"]
    assert row[ANSWER] == "The original Transformer used 6 encoder layers."
    assert "6 encoder layers" in row["passages_shown"]
    assert row["source_used"] == "retrieval"


def test_a_run_with_no_passages_says_so_rather_than_being_blank(tmp_path) -> None:
    task = _task()
    traces = [_trace(context="", route_decision="direct")]
    out = tmp_path / "review.csv"
    write_review_sheet(traces, {task["id"]: task}, out)
    assert read_sheet(out)[0]["passages_shown"] == "(no passages were retrieved)"


def test_every_context_column_is_populated_or_deliberately_empty(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    row = read_sheet(out)[0]
    for column in CONTEXT_COLUMNS:
        assert column in row


# --- regenerating must not destroy labelling ------------------------------------


def _fill(path, run_id, correct="pass", notes="my judgment") -> None:
    rows = read_sheet(path)
    fields = list(rows[0].keys())
    for row in rows:
        if row[RUN_ID] == run_id:
            row["human_correct"] = correct
            row["human_faithful"] = "yes"
            row["human_reasoning"] = "good"
            row["human_notes"] = notes
    with open(path, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_regenerating_keeps_labels_when_the_answer_is_unchanged(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001")

    report = write_review_sheet(traces, tasks, out)

    assert report["labels_carried_forward"] == ["msr-001"]
    row = read_sheet(out)[0]
    assert row["human_correct"] == "pass"
    assert row["human_notes"] == "my judgment"


def test_regenerating_backs_up_the_previous_file(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001")

    report = write_review_sheet(traces, tasks, out)

    assert report["backup_written"]
    assert ".bak-" in report["backup_written"]


def test_no_backup_is_written_for_a_sheet_that_does_not_exist_yet(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    report = write_review_sheet(traces, tasks, out)
    assert report["backup_written"] is None
    assert report["labels_found_on_disk"] == 0


def test_an_existing_unlabelled_sheet_is_still_backed_up(pair, tmp_path) -> None:
    """Resampling replaces which rows are up for review. That decision is worth
    keeping even when nobody has labelled anything yet."""
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)

    report = write_review_sheet(traces, tasks, out)

    assert report["labels_found_on_disk"] == 0
    assert report["backup_written"]
    assert Path(report["backup_written"]).exists()


def test_a_label_is_not_carried_forward_when_the_answer_changed(pair, tmp_path) -> None:
    """A label describes one specific response."""
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001")

    changed = [_trace(answer="A completely different reply.")]
    report = write_review_sheet(changed, tasks, out)

    assert report["labels_carried_forward"] == []
    assert report["labels_not_carried_answer_changed"] == ["msr-001"]
    row = read_sheet(out)[0]
    assert row["human_correct"] == ""
    assert "NOT CARRIED FORWARD" in row["human_notes"]


def test_a_label_whose_row_is_gone_is_reported_not_dropped_quietly(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001")

    other = _task(id="dnt-001", category="direct_no_tools")
    report = write_review_sheet(
        [_trace(task_id="dnt-001")], {**tasks, "dnt-001": other}, out
    )

    assert report["labels_orphaned_row_no_longer_exported"] == ["msr-001"]


def test_discarding_labels_is_opt_in_and_still_backs_up(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001")

    report = write_review_sheet(traces, tasks, out, discard_existing_labels=True)

    assert report["labels_carried_forward"] == []
    assert read_sheet(out)[0]["human_correct"] == ""
    assert report["backup_written"]


# --- reading the filled sheet back ----------------------------------------------


def test_an_unfilled_sheet_yields_no_labels(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    result = load_human_labels(out)
    assert result["n_labelled"] == 0
    assert result["unlabelled"] == ["msr-001"]


def test_a_filled_sheet_yields_its_labels(pair, tmp_path) -> None:
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001", correct="fail")
    result = load_human_labels(out)
    assert result["n_labelled"] == 1
    assert result["labels"]["msr-001"]["human_correct"] == "fail"


def test_a_value_outside_the_vocabulary_is_reported_not_counted(pair, tmp_path) -> None:
    """A capitalised variant must not read as a genuine disagreement."""
    traces, tasks = pair
    out = tmp_path / "review.csv"
    write_review_sheet(traces, tasks, out)
    _fill(out, "msr-001", correct="Pass")

    result = load_human_labels(out)

    assert result["n_labelled"] == 0
    assert [u["value"] for u in result["unrecognised_values"]] == ["Pass"]


def test_ambiguous_is_not_forced_to_a_side() -> None:
    assert human_label({"human_correct": "pass"}) is True
    assert human_label({"human_correct": "fail"}) is False
    assert human_label({"human_correct": "ambiguous"}) is None
