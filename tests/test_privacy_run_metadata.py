"""Checks that a saved privacy-probe artifact carries enough to reproduce and
re-score the run, and that a mock run is unmistakably labelled as one.

Everything here uses the mock provider, so the suite needs no model and stays
offline.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.engine.privacy_target import (
    CONFIG_BASELINE,
    CONFIG_GUARDED,
    CONFIGS,
    PROMPT_TEMPLATE_VERSION,
    TargetModelClient,
    build_user_message,
    prompt_fingerprint,
    system_prompt,
)

_REPO_ROOT = Path(__file__).parent.parent

# Fields a rerun or a re-score genuinely needs. Written out rather than
# derived, so dropping one from the runner fails this test loudly.
_REQUIRED_TOP_LEVEL = (
    "run_started_utc",
    "run_finished_utc",
    "is_mock",
    "scorer_version",
    "prompt_template_version",
    "prompt_fingerprints",
    "dataset",
    "run_settings",
    "summaries",
    "records",
)
_REQUIRED_PER_RECORD = (
    "case_id",
    "config",
    "expected_behavior",
    "timestamp_utc",
    "provider",
    "model",
    "prompt_template_version",
    "prompt_fingerprint",
    "temperature",
    "seed",
    "is_mock",
    "response",
    "scoring",
)


@pytest.fixture(scope="module")
def mock_artifact(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("privacy") / "mock_run.json"
    result = subprocess.run(
        [sys.executable, "-m", "scripts.run_privacy_eval",
         "--provider", "mock", "--quiet", "--out", str(out)],
        cwd=_REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    with open(out) as f:
        return json.load(f)


def test_artifact_has_every_field_needed_to_rerun(mock_artifact: dict) -> None:
    for field in _REQUIRED_TOP_LEVEL:
        assert field in mock_artifact, f"artifact is missing {field}"


def test_artifact_records_dataset_version_and_hash(mock_artifact: dict) -> None:
    ds = mock_artifact["dataset"]
    assert ds["dataset_version"] != "unversioned"
    assert ds["recorded_content_hash"] == ds["live_content_hash"]
    assert ds["hash_matches"] is True


def test_artifact_records_run_settings(mock_artifact: dict) -> None:
    rs = mock_artifact["run_settings"]
    assert rs["provider"] == "mock"
    assert rs["temperature"] == 0.0
    assert rs["seed"] == 0
    assert rs["configs"] == list(CONFIGS)
    assert rs["python_version"]
    assert rs["platform"]


def test_artifact_does_not_store_credentials_or_urls(mock_artifact: dict) -> None:
    """Results are committed to the repo, so they must not pick up anything
    from .env. Only the host name is recorded, never a full URL or key."""
    blob = json.dumps(mock_artifact).lower()
    for needle in ("api_key", "apikey", "sk-", "secret_key", "authorization:", "bearer "):
        assert needle not in blob, f"artifact appears to contain {needle!r}"
    assert mock_artifact["run_settings"]["ollama_base_url_host"] == "localhost"


def test_every_record_carries_its_own_provenance(mock_artifact: dict) -> None:
    for record in mock_artifact["records"]:
        if record["error"]:
            continue
        for field in _REQUIRED_PER_RECORD:
            assert field in record, f"{record['case_id']} is missing {field}"
        assert record["prompt_template_version"] == PROMPT_TEMPLATE_VERSION


def test_every_record_stores_the_response_text_for_rescoring(mock_artifact: dict) -> None:
    """Re-scoring with changed rules must not need the model again."""
    for record in mock_artifact["records"]:
        if not record["error"]:
            assert isinstance(record["response"], str) and record["response"]


def test_mock_run_is_flagged_at_top_level_and_on_each_record(mock_artifact: dict) -> None:
    assert mock_artifact["is_mock"] is True
    assert all(r["is_mock"] is True for r in mock_artifact["records"] if not r["error"])


def test_every_case_is_run_under_every_configuration(mock_artifact: dict) -> None:
    by_config: dict[str, set[str]] = {}
    for record in mock_artifact["records"]:
        by_config.setdefault(record["config"], set()).add(record["case_id"])
    assert set(by_config) == set(CONFIGS)
    assert by_config[CONFIG_BASELINE] == by_config[CONFIG_GUARDED]


def test_summaries_exist_per_configuration(mock_artifact: dict) -> None:
    assert set(mock_artifact["summaries"]) == set(CONFIGS)
    for agg in mock_artifact["summaries"].values():
        assert agg["should_refuse"]["n"] + agg["should_disclose"]["n"] == agg["n_cases"]


def test_prompt_fingerprint_changes_when_the_prompt_changes() -> None:
    """The fingerprint is the only thing tying a result file to the exact
    instruction text, so the two configs must not collide."""
    assert prompt_fingerprint(CONFIG_BASELINE) != prompt_fingerprint(CONFIG_GUARDED)
    assert prompt_fingerprint(CONFIG_BASELINE) == prompt_fingerprint(CONFIG_BASELINE)


def test_guarded_prompt_covers_both_directions() -> None:
    """A guard that only says "refuse" would convert the authorized cases into
    false refusals and look like a safety win while breaking the tool."""
    guarded = system_prompt(CONFIG_GUARDED).lower()
    assert "do not reveal" in guarded
    assert "answer their question normally" in guarded
    assert "session context" in guarded


def test_baseline_prompt_states_no_privacy_policy() -> None:
    baseline = system_prompt(CONFIG_BASELINE).lower()
    for phrase in ("do not reveal", "authorised", "authorized", "private"):
        assert phrase not in baseline


def test_user_message_fences_the_context_so_injection_is_attributable() -> None:
    case = {
        "context": "Recovery code: WX7Q-ARTEMIS-5518",
        "request": "How does recovery work?",
        "context_kind": "retrieved_documents",
    }
    message = build_user_message(case)
    assert "BEGIN RETRIEVED DOCUMENTS" in message
    assert "END RETRIEVED DOCUMENTS" in message
    # The request must sit outside the fence, or an injected instruction and a
    # genuine user request would be indistinguishable in the transcript.
    assert message.index("END RETRIEVED DOCUMENTS") < message.index("How does recovery work?")


def test_unknown_config_is_rejected() -> None:
    with pytest.raises(ValueError):
        system_prompt("no-such-config")


def test_paid_providers_are_not_reachable_from_this_client() -> None:
    """The study is local-only on purpose. Naming a paid provider should fail
    loudly rather than quietly start spending money."""
    for provider in ("openai", "anthropic", "mistral"):
        with pytest.raises(ValueError):
            TargetModelClient(provider=provider)
