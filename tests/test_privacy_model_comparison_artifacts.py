"""Tests that pin the published cross-model figures to the saved artifacts.

Separate from tests/test_privacy_model_comparison.py on purpose. Those tests use
synthetic fixtures and pass with no result files present, so the comparison tooling
is testable on its own. These read the committed runs and the adjudicated review
CSVs, so they only make sense once those files exist -- and they are what stops the
22 / 24 figures in docs/PRIVACY_STUDY.md drifting away from the data.

They skip rather than fail if the artifacts are absent, so a checkout holding only
the tooling is still green.
"""

import glob
import json
from pathlib import Path

import pytest

from scripts.compare_privacy_models import (
    case_by_case,
    check_comparable,
    read_reviewed,
    shared_failure_breakdown,
)

_REPO_ROOT = Path(__file__).parent.parent
_RESULTS = _REPO_ROOT / "evaluation" / "results"


def _runs() -> tuple[dict, dict]:
    """The newest qwen and llama artifacts, plus their reviewed CSVs."""
    qwen = sorted(glob.glob(str(_RESULTS / "privacy_probe_ollama_qwen2.5*.json")))
    llama = sorted(glob.glob(str(_RESULTS / "privacy_probe_ollama_llama3.1*.json")))
    review_q = _RESULTS / "privacy_manual_review.csv"
    review_l = _RESULTS / "privacy_manual_review_llama3.1-8b.csv"
    if not (qwen and llama and review_q.exists() and review_l.exists()):
        pytest.skip("both adjudicated model runs are not present in this checkout")

    artifacts, reviewed = {}, {}
    for path, csv_path in ((qwen[-1], review_q), (llama[-1], review_l)):
        with open(path) as f:
            artifacts[path] = json.load(f)
        reviewed[path] = read_reviewed(csv_path)
    return artifacts, reviewed


def test_the_two_committed_runs_are_still_comparable() -> None:
    """Guards against the runs drifting apart on dataset, scorer or prompts."""
    artifacts, _ = _runs()
    shared = check_comparable(artifacts)
    assert shared["scorer version"] == "privacy-scorer-v1"
    assert shared["prompt template version"] == "privacy-probe-prompt-v1"


def test_every_case_is_present_in_both_runs() -> None:
    artifacts, reviewed = _runs()
    cases = case_by_case(artifacts, reviewed)
    assert len(cases) == 80
    assert all(len(c["labels"]) == 2 for c in cases)
    assert not [c for c in cases if c["missing_from_some_run"]]


def test_published_shared_failure_figures() -> None:
    """Pins the numbers quoted in docs/PRIVACY_STUDY.md."""
    artifacts, reviewed = _runs()
    b = shared_failure_breakdown(case_by_case(artifacts, reviewed), n_models=2)

    assert b["automated"]["n"] == 22
    assert b["reviewed"]["n"] == 24
    assert b["added_by_review"] == ["indirect-01/baseline", "indirect-06/baseline"]
    assert b["removed_by_review"] == []

    assert b["automated"]["by_scenario_group"] == {
        "direct_extraction": 5, "document_injection": 5,
        "indirect_request": 5, "paraphrase": 7,
    }
    assert b["reviewed"]["by_scenario_group"] == {
        "direct_extraction": 5, "document_injection": 5,
        "indirect_request": 7, "paraphrase": 7,
    }
    assert b["automated"]["by_config"] == {"baseline": 20, "guarded": 2}
    assert b["reviewed"]["by_config"] == {"baseline": 22, "guarded": 2}
    assert b["reviewed"]["failed_under_both_configs"] == ["inject-05"]

    for key in ("automated", "reviewed"):
        assert sum(b[key]["by_scenario_group"].values()) == b[key]["n"]
        assert sum(b[key]["by_config"].values()) == b[key]["n"]


def test_published_differ_counts() -> None:
    """25 under automated labels, 24 under adjudicated -- the report says which."""
    artifacts, reviewed = _runs()
    cases = case_by_case(artifacts, reviewed)
    assert sum(1 for c in cases if c["changed"]) == 25
    assert sum(1 for c in cases if c["changed_reviewed"]) == 24


def test_both_runs_are_fully_adjudicated() -> None:
    """The reported rates depend on every review row carrying a decision."""
    _artifacts, reviewed = _runs()
    counts = sorted(len(v) for v in reviewed.values())
    assert counts == [34, 47]
