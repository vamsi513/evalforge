"""Tests for scripts/compare_privacy_models.py.

The comparability guards are the point of most of these. A cross-model number
computed across two dataset versions, two scorer versions or two prompt texts is
a confound rather than a comparison, and the failure is silent unless something
checks. So is quietly putting one model's reviewed rate next to another model's
automated rate.
"""

import pytest

from scripts.compare_privacy_models import (
    NotComparable,
    shared_failure_breakdown,
    case_by_case,
    check_comparable,
    model_label,
    parse_reviewed_arg,
    per_model_summary,
    read_reviewed,
)


# Mirrors the real dataset's grouping, so a group-count test exercises more than
# one bucket.
_GROUP_BY_PREFIX = {
    "auth": "authorized_request",
    "direct": "direct_extraction",
    "indirect": "indirect_request",
    "para": "paraphrase",
    "inject": "document_injection",
}


def _artifact(model: str, labels: dict[tuple[str, str], str], **overrides) -> dict:
    """A minimal artifact. `labels` maps (case_id, config) -> scorer label."""
    records = []
    for (case_id, config), label in labels.items():
        expected = "disclose" if case_id.startswith("auth") else "refuse"
        records.append({
            "case_id": case_id, "config": config,
            "scenario_group": _GROUP_BY_PREFIX[case_id.split("-")[0]],
            "expected_behavior": expected,
            "response": f"response for {case_id}/{config}",
            "error": None,
            "scoring": {"label": label, "reason": "", "matched_fragments": []},
        })
    base = {
        "is_mock": False,
        "scorer_version": "privacy-scorer-v1",
        "prompt_template_version": "privacy-probe-prompt-v1",
        "prompt_fingerprints": {"baseline": "aaaa", "guarded": "bbbb"},
        "dataset": {"dataset_version": "0.4.0", "live_content_hash": "hash4"},
        "run_settings": {"provider": "ollama", "model": model,
                         "configs": ["baseline", "guarded"]},
        "records": records,
    }
    base.update(overrides)
    return base


_LABELS_A = {
    ("direct-01", "baseline"): "disclosed",
    ("direct-01", "guarded"): "disclosed",
    ("direct-02", "baseline"): "disclosed",
    ("auth-01", "baseline"): "authorized_disclosure",
}
_LABELS_B = {
    ("direct-01", "baseline"): "disclosed",
    ("direct-01", "guarded"): "correct_refusal",   # differs from A
    ("direct-02", "baseline"): "ambiguous",        # differs from A
    ("auth-01", "baseline"): "false_refusal",      # differs from A
}


# --- comparability guards ------------------------------------------------------

def test_matching_runs_are_comparable() -> None:
    shared = check_comparable({
        "a.json": _artifact("qwen2.5:7b-instruct", _LABELS_A),
        "b.json": _artifact("llama3.1:8b", _LABELS_B),
    })
    assert shared["dataset content hash"] == "hash4"
    assert shared["scorer version"] == "privacy-scorer-v1"


def test_differing_dataset_version_aborts() -> None:
    b = _artifact("llama3.1:8b", _LABELS_B)
    b["dataset"] = {"dataset_version": "0.3.0", "live_content_hash": "hash4"}
    with pytest.raises(NotComparable, match="dataset version differs"):
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})


def test_differing_dataset_content_hash_aborts() -> None:
    """Same version string, edited content. This is the sneaky one."""
    b = _artifact("llama3.1:8b", _LABELS_B)
    b["dataset"] = {"dataset_version": "0.4.0", "live_content_hash": "DIFFERENT"}
    with pytest.raises(NotComparable, match="dataset content hash differs"):
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})


def test_differing_scorer_version_aborts() -> None:
    b = _artifact("llama3.1:8b", _LABELS_B, scorer_version="privacy-scorer-v2")
    with pytest.raises(NotComparable, match="scorer version differs"):
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})


def test_differing_prompt_fingerprints_abort() -> None:
    b = _artifact("llama3.1:8b", _LABELS_B,
                  prompt_fingerprints={"baseline": "aaaa", "guarded": "CHANGED"})
    with pytest.raises(NotComparable, match="prompt fingerprints differ"):
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})


def test_mock_run_cannot_be_compared() -> None:
    b = _artifact("mock-canned-responses", _LABELS_B, is_mock=True)
    with pytest.raises(NotComparable, match="mock run"):
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})


def test_abort_message_names_every_problem_at_once() -> None:
    b = _artifact("llama3.1:8b", _LABELS_B, scorer_version="v2")
    b["dataset"] = {"dataset_version": "0.3.0", "live_content_hash": "other"}
    with pytest.raises(NotComparable) as exc:
        check_comparable({"a.json": _artifact("q", _LABELS_A), "b.json": b})
    message = str(exc.value)
    assert "dataset version" in message
    assert "dataset content hash" in message
    assert "scorer version" in message


# --- automated vs reviewed separation -----------------------------------------

def test_reviewed_is_none_when_a_run_has_no_human_labels() -> None:
    """None is not the same as zero. A run nobody reviewed must not render as a
    reviewed rate of zero."""
    s = per_model_summary(_artifact("llama3.1:8b", _LABELS_B), None)
    assert s["reviewed"] is None
    assert s["automated"]["should_refuse"]["n"] == 3


def test_automated_counts_ignore_reviewed_labels() -> None:
    """The automated block must stay reproducible from the artifact alone."""
    reviewed = {("direct-02", "baseline"): "disclosed"}
    s = per_model_summary(_artifact("llama3.1:8b", _LABELS_B), reviewed)
    assert s["automated"]["should_refuse"]["counts"]["ambiguous"] == 1
    assert "ambiguous" not in s["reviewed"]["should_refuse"]["counts"]


def test_reviewed_counts_apply_human_labels_over_automated() -> None:
    reviewed = {("direct-02", "baseline"): "disclosed"}
    s = per_model_summary(_artifact("llama3.1:8b", _LABELS_B), reviewed)
    auto = s["automated"]["should_refuse"]["counts"]
    rev = s["reviewed"]["should_refuse"]["counts"]
    assert auto.get("disclosed", 0) == 1
    assert rev["disclosed"] == 2
    assert s["reviewed"]["n_rows_with_human_label"] == 1


def test_false_refusal_rate_uses_the_should_disclose_denominator() -> None:
    s = per_model_summary(_artifact("llama3.1:8b", _LABELS_B), None)
    sd = s["automated"]["should_disclose"]
    assert sd["n"] == 1
    assert sd["false_refusal_rate"] == 1.0


# --- case-by-case -------------------------------------------------------------

def test_case_by_case_flags_only_the_rows_that_differ() -> None:
    cases = case_by_case({
        "a.json": _artifact("qwen2.5:7b-instruct", _LABELS_A),
        "b.json": _artifact("llama3.1:8b", _LABELS_B),
    })
    changed = {(c["case_id"], c["config"]) for c in cases if c["changed"]}
    assert changed == {("direct-01", "guarded"), ("direct-02", "baseline"),
                       ("auth-01", "baseline")}
    unchanged = [c for c in cases if not c["changed"]]
    assert [(c["case_id"], c["config"]) for c in unchanged] == [("direct-01", "baseline")]


def test_case_by_case_records_each_models_label() -> None:
    cases = case_by_case({
        "a.json": _artifact("qwen2.5:7b-instruct", _LABELS_A),
        "b.json": _artifact("llama3.1:8b", _LABELS_B),
    })
    row = next(c for c in cases if c["case_id"] == "direct-01" and c["config"] == "guarded")
    assert row["labels"]["ollama/qwen2.5:7b-instruct"] == "disclosed"
    assert row["labels"]["ollama/llama3.1:8b"] == "correct_refusal"


def test_case_by_case_reports_which_models_failed_a_row() -> None:
    cases = case_by_case({
        "a.json": _artifact("qwen2.5:7b-instruct", _LABELS_A),
        "b.json": _artifact("llama3.1:8b", _LABELS_B),
    })
    shared = next(c for c in cases if c["case_id"] == "direct-01" and c["config"] == "baseline")
    assert shared["failed_in"] == ["ollama/llama3.1:8b", "ollama/qwen2.5:7b-instruct"]
    # a false refusal on an authorized case is a failure too
    auth = next(c for c in cases if c["case_id"] == "auth-01")
    assert auth["failed_in"] == ["ollama/llama3.1:8b"]


def test_a_case_missing_from_one_run_is_reported_not_dropped() -> None:
    partial = dict(_LABELS_B)
    del partial[("direct-02", "baseline")]
    cases = case_by_case({
        "a.json": _artifact("qwen2.5:7b-instruct", _LABELS_A),
        "b.json": _artifact("llama3.1:8b", partial),
    })
    row = next(c for c in cases if c["case_id"] == "direct-02")
    assert row["missing_from_some_run"] is True
    assert row["labels"]["ollama/llama3.1:8b"] is None
    assert len(cases) == 4


def test_model_label_combines_provider_and_model() -> None:
    assert model_label(_artifact("llama3.1:8b", _LABELS_B)) == "ollama/llama3.1:8b"


# --- CLI plumbing -------------------------------------------------------------

def test_reviewed_argument_parses_artifact_equals_csv() -> None:
    assert parse_reviewed_arg("run.json=review.csv") == ("run.json", "review.csv")


def test_malformed_reviewed_argument_is_rejected() -> None:
    import argparse
    with pytest.raises(argparse.ArgumentTypeError):
        parse_reviewed_arg("run.json")


def test_read_reviewed_skips_blank_and_invalid_labels(tmp_path) -> None:
    path = tmp_path / "review.csv"
    path.write_text(
        "case_id,config,manual_label\n"
        "direct-01,baseline,disclosed\n"
        "direct-02,baseline,\n"
        "direct-03,baseline,Disclosed\n"       # wrong case, not accepted
        "direct-04,baseline,not-a-label\n"
    )
    out = read_reviewed(path)
    assert out == {("direct-01", "baseline"): "disclosed"}


def _two_models_with_review():
    labels_q = {
        ("direct-01", "baseline"): "disclosed",
        ("indirect-01", "baseline"): "ambiguous",
        ("para-01", "baseline"): "disclosed",
        ("auth-01", "baseline"): "authorized_disclosure",
    }
    labels_l = {
        ("direct-01", "baseline"): "disclosed",
        ("indirect-01", "baseline"): "ambiguous",
        ("para-01", "baseline"): "correct_refusal",
        ("auth-01", "baseline"): "authorized_disclosure",
    }
    artifacts = {
        "q.json": _artifact("qwen2.5:7b-instruct", labels_q),
        "l.json": _artifact("llama3.1:8b", labels_l),
    }
    # both reviewers call the shared abstention a disclosure
    reviewed = {
        "q.json": {("indirect-01", "baseline"): "disclosed"},
        "l.json": {("indirect-01", "baseline"): "disclosed"},
    }
    return artifacts, reviewed


def test_breakdown_totals_differ_between_label_sets() -> None:
    artifacts, reviewed = _two_models_with_review()
    cases = case_by_case(artifacts, reviewed)
    b = shared_failure_breakdown(cases, n_models=2)
    assert b["automated"]["n"] == 1       # direct-01 only
    assert b["reviewed"]["n"] == 2        # plus indirect-01 after review
    assert b["added_by_review"] == ["indirect-01/baseline"]
    assert b["removed_by_review"] == []


def test_group_counts_sum_to_the_total_in_each_label_set() -> None:
    """The reconciliation this function exists for."""
    artifacts, reviewed = _two_models_with_review()
    b = shared_failure_breakdown(case_by_case(artifacts, reviewed), n_models=2)
    for key in ("automated", "reviewed"):
        block = b[key]
        assert sum(block["by_scenario_group"].values()) == block["n"], key
        assert sum(block["by_config"].values()) == block["n"], key
        assert block["group_counts_sum_to_total"] is True


def test_breakdown_group_counts_move_with_the_label_set() -> None:
    artifacts, reviewed = _two_models_with_review()
    b = shared_failure_breakdown(case_by_case(artifacts, reviewed), n_models=2)
    assert b["automated"]["by_scenario_group"].get("indirect_request", 0) == 0
    assert b["reviewed"]["by_scenario_group"]["indirect_request"] == 1


def test_a_row_failing_in_only_one_model_is_not_shared() -> None:
    artifacts, reviewed = _two_models_with_review()
    b = shared_failure_breakdown(case_by_case(artifacts, reviewed), n_models=2)
    rows = {(r["case_id"], r["config"]) for r in b["reviewed"]["rows"]}
    assert ("para-01", "baseline") not in rows   # qwen disclosed, llama refused


def test_reviewed_labels_fall_back_to_automated_where_no_decision_exists() -> None:
    artifacts, reviewed = _two_models_with_review()
    cases = case_by_case(artifacts, reviewed)
    row = next(c for c in cases if c["case_id"] == "direct-01")
    assert row["labels"]["ollama/llama3.1:8b"] == "disclosed"
    assert row["reviewed_labels"]["ollama/llama3.1:8b"] == "disclosed"


def test_changed_is_reported_per_label_set() -> None:
    """A row can agree under one label set and differ under the other."""
    artifacts, reviewed = _two_models_with_review()
    cases = case_by_case(artifacts, reviewed)
    shared = next(c for c in cases if c["case_id"] == "indirect-01")
    assert shared["changed"] is False
    assert shared["changed_reviewed"] is False
    differing = next(c for c in cases if c["case_id"] == "para-01")
    assert differing["changed"] is True
    assert differing["changed_reviewed"] is True
