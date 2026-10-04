"""Structural checks on evaluation/privacy_probe_dataset.json.

These exist because the dataset is hand-edited. A case that references a
missing record, or whose context does not actually contain the secret it is
supposed to leak, would quietly produce a meaningless result rather than an
error.
"""

import json
from pathlib import Path

import pytest

from app.engine.privacy_scorer import normalise
from scripts.run_privacy_eval import dataset_content_hash, flatten_cases, load_dataset

_DATASET_PATH = Path(__file__).parent.parent / "evaluation" / "privacy_probe_dataset.json"

_REQUIRED_CASE_FIELDS = (
    "case_id",
    "record",
    "secret_source",
    "requester_authorization",
    "context_kind",
    "context",
    "request",
    "rationale",
)


@pytest.fixture(scope="module")
def dataset() -> dict:
    return load_dataset()


def test_dataset_file_is_valid_json() -> None:
    with open(_DATASET_PATH) as f:
        json.load(f)


def test_recorded_content_hash_matches_live_contents(dataset: dict) -> None:
    """Catches a dataset edited without re-stamping the hash, which would make
    every saved result file attribute itself to the wrong dataset state."""
    assert dataset["content_sha256_16"] == dataset_content_hash(dataset)


def test_dataset_is_versioned(dataset: dict) -> None:
    assert dataset["dataset_version"] != "unversioned"


def test_case_ids_are_unique(dataset: dict) -> None:
    ids = [c["case_id"] for c in flatten_cases(dataset)]
    assert len(ids) == len(set(ids))


def test_every_case_has_the_required_fields(dataset: dict) -> None:
    for case in flatten_cases(dataset):
        missing = [f for f in _REQUIRED_CASE_FIELDS if not case.get(f)]
        assert not missing, f"{case['case_id']} is missing {missing}"


def test_every_case_records_why_it_is_in_the_dataset(dataset: dict) -> None:
    for case in flatten_cases(dataset):
        assert len(case["rationale"]) > 40, f"{case['case_id']} rationale is too thin"


def test_every_case_references_a_real_record(dataset: dict) -> None:
    for case in flatten_cases(dataset):
        assert case["record"] in dataset["records"], case["case_id"]


def test_every_secret_actually_appears_in_its_case_context(dataset: dict) -> None:
    """If the value is not in the context, the case cannot test context-bound
    disclosure and a refusal would be trivially correct."""
    for case in flatten_cases(dataset):
        secret = dataset["records"][case["record"]]["secret_value"]
        assert normalise(secret) in normalise(case["context"]), case["case_id"]


def test_secret_fragments_are_substrings_of_their_secret(dataset: dict) -> None:
    for key, record in dataset["records"].items():
        whole = normalise(record["secret_value"])
        for fragment in record["secret_fragments"]:
            assert normalise(fragment) in whole, f"{key}: {fragment!r} is not part of the secret"


def test_expected_behavior_is_declared_per_scenario_group(dataset: dict) -> None:
    for name, group in dataset["scenarios"].items():
        assert group["expected_behavior"] in ("disclose", "refuse"), name
        assert len(group["why_this_group_exists"]) > 60, name


def test_both_authorized_and_unauthorized_cases_are_present(dataset: dict) -> None:
    """Needed in both directions: without authorized cases the study cannot
    measure over-refusal, and a refuse-everything model would score perfectly."""
    auth = {c["requester_authorization"] for c in flatten_cases(dataset)}
    assert {"authorized", "unauthorized"} <= auth


def test_both_secret_sources_are_covered(dataset: dict) -> None:
    sources = {c["secret_source"] for c in flatten_cases(dataset)}
    assert {"conversation_context", "retrieved_document"} <= sources


def test_all_injection_cases_are_retrieval_sourced(dataset: dict) -> None:
    for case in dataset["scenarios"]["document_injection"]["cases"]:
        assert case["secret_source"] == "retrieved_document", case["case_id"]
        assert case["context_kind"] == "retrieved_documents", case["case_id"]


def test_authorized_group_expects_disclosure_and_others_expect_refusal(dataset: dict) -> None:
    assert dataset["scenarios"]["authorized_request"]["expected_behavior"] == "disclose"
    for name, group in dataset["scenarios"].items():
        if name != "authorized_request":
            assert group["expected_behavior"] == "refuse", name


def test_dataset_stays_small_enough_to_inspect_by_hand(dataset: dict) -> None:
    """The study's method depends on every response being readable. If this
    fails, either raise the bound deliberately or stop claiming manual review."""
    assert len(flatten_cases(dataset)) <= 60


def test_dataset_documents_its_own_limitations(dataset: dict) -> None:
    limits = dataset["coverage_and_limitations"]
    assert len(limits["not_covered"]) >= 4
    joined = " ".join(limits["not_covered"]).lower()
    assert "memor" in joined, "the memorization limitation must be stated explicitly"


def test_non_english_cases_declare_their_expected_response_language(dataset: dict) -> None:
    """A case that asks for output in another language has to say so, otherwise
    the scorer will apply an English-only refusal detector to it and the label
    will be wrong rather than merely uncertain."""
    for case in flatten_cases(dataset):
        asks_for_translation = "translate" in case["request"].lower()
        if asks_for_translation:
            assert case.get("expected_response_language"), (
                f"{case['case_id']} asks for a translation but does not declare "
                "expected_response_language"
            )


def test_dataset_documents_the_refusal_detector_language_scope(dataset: dict) -> None:
    note = dataset["coverage_and_limitations"].get("refusal_detection_language_scope", "")
    assert "English" in note and "manual review" in note
