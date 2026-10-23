"""Checks on the task file itself and on normalised answer matching.

The file is the benchmark. If a task loses its check, or two tasks share an id,
every number downstream is quietly wrong, so those are assertions rather than
something to notice later.
"""

import json

import pytest

from agent_loop.tasks import (
    CATEGORIES,
    REQUIRED_FIELDS,
    TASKS_PATH,
    answer_matches,
    load_tasks,
    term_present,
    validate_task,
)

EXPECTED_COUNTS = {
    "tool_selection": 40,
    "multi_step_retrieval": 40,
    "direct_no_tools": 35,
    "unanswerable_decline": 35,
}


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    return load_tasks()


def test_the_file_holds_one_hundred_and_fifty_tasks(tasks) -> None:
    assert len(tasks) == 150


def test_each_category_has_the_documented_count(tasks) -> None:
    counts: dict[str, int] = {}
    for task in tasks:
        counts[task["category"]] = counts.get(task["category"], 0) + 1
    assert counts == EXPECTED_COUNTS


def test_ids_are_unique(tasks) -> None:
    ids = [task["id"] for task in tasks]
    assert len(set(ids)) == len(ids)


def test_every_task_carries_at_least_one_check(tasks) -> None:
    for task in tasks:
        assert task["expected_route"] or task["expected_answer"] or task["expected_behavior"], (
            f"{task['id']} has nothing to score against"
        )


def test_every_task_has_the_same_fields(tasks) -> None:
    for task in tasks:
        assert tuple(sorted(task)) == tuple(sorted(REQUIRED_FIELDS))


def test_retrieval_tasks_name_their_source_documents(tasks) -> None:
    """A retrieval answer is only checkable if I recorded where it came from."""
    for task in tasks:
        if task["category"] == "multi_step_retrieval":
            assert task["source_docs"], f"{task['id']} has no provenance"


def test_decline_tasks_state_a_behaviour_and_no_answer(tasks) -> None:
    for task in tasks:
        if task["category"] == "unanswerable_decline":
            assert task["expected_behavior"], f"{task['id']} must say what declining looks like"
            assert task["expected_answer"] is None, (
                f"{task['id']} is unanswerable, so it cannot have a checkable answer"
            )


def test_direct_and_tool_selection_tasks_name_an_expected_route(tasks) -> None:
    for task in tasks:
        if task["category"] in ("tool_selection", "direct_no_tools"):
            assert task["expected_route"] is not None, f"{task['id']} has no expected route"


def test_categories_constant_matches_the_file(tasks) -> None:
    assert set(CATEGORIES) == {task["category"] for task in tasks}


# --- validation rejects what it should -----------------------------------------


def _task(**overrides) -> dict:
    base = {
        "id": "x-001",
        "category": "tool_selection",
        "question": "a question",
        "expected_route": "direct",
        "expected_answer": None,
        "expected_behavior": None,
        "must_not_contain": [],
        "source_docs": [],
    }
    base.update(overrides)
    return base


def test_a_task_with_no_check_is_rejected() -> None:
    with pytest.raises(ValueError, match="no check"):
        validate_task(_task(expected_route=None), seen_ids=set())


def test_a_duplicate_id_is_rejected() -> None:
    with pytest.raises(ValueError, match="duplicate"):
        validate_task(_task(), seen_ids={"x-001"})


def test_an_unknown_category_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown category"):
        validate_task(_task(category="freeform"), seen_ids=set())


def test_an_unknown_route_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown route"):
        validate_task(_task(expected_route="sql_query"), seen_ids=set())


def test_a_malformed_expected_answer_is_rejected() -> None:
    with pytest.raises(ValueError, match="malformed"):
        validate_task(_task(expected_answer={"required": []}), seen_ids=set())


def test_a_missing_field_is_rejected() -> None:
    broken = _task()
    del broken["source_docs"]
    with pytest.raises(ValueError, match="missing fields"):
        validate_task(broken, seen_ids=set())


def test_a_line_that_is_not_json_names_its_line_number(tmp_path) -> None:
    path = tmp_path / "tasks.jsonl"
    path.write_text(json.dumps(_task()) + "\nnot json at all\n")
    with pytest.raises(ValueError, match=":2"):
        load_tasks(path)


# --- normalised matching --------------------------------------------------------


def test_digit_separators_do_not_decide_a_match() -> None:
    assert term_present("4096", "the context window is 4,096 tokens")
    assert term_present("27,540", "trained on 27540 demonstrations")


def test_a_short_numeric_term_does_not_match_inside_a_longer_number() -> None:
    """The required term 8 must not be satisfied by 48 or 0.87."""
    assert not term_present("8", "the answer is 48")
    assert not term_present("8", "a score of 0.87")
    assert term_present("8", "8 attention heads")


def test_a_decimal_term_does_not_match_a_longer_decimal() -> None:
    assert not term_present("0.25", "a perplexity of 10.25")
    assert term_present("0.25", "only 0.25 perplexity increase")


# These four are regressions. The first matcher rejected every one of them, and
# scored three correct agent answers as wrong on the first development run.


def test_a_number_at_the_end_of_a_sentence_is_found() -> None:
    assert term_present("8", "48 divided by 6 is 8.")
    assert term_present("168", "There are 168 hours in a week.")


def test_a_number_followed_by_a_unit_suffix_is_found() -> None:
    assert term_present("3.24", "a 3.24x inference speedup on an A100")
    assert term_present("220", "reaching 220 TFLOPs/s")


def test_a_short_term_followed_by_punctuation_is_found() -> None:
    assert term_present("h2o", "The chemical formula for water is H₂O.")
    assert term_present("nf4", "quantized with NF4, which is optimal")


def test_a_magnitude_word_and_its_suffix_are_the_same_quantity() -> None:
    assert term_present("77m", "T5-Small, which has 77 million parameters")
    assert term_present("11b", "the target model is T5-XXL at 11 billion parameters")
    assert term_present("2 trillion", "trained on 2T tokens")


def test_a_short_term_is_still_not_found_inside_a_longer_word() -> None:
    assert not term_present("3x", "a 13x improvement")
    assert not term_present("nf4", "nf40 is not a thing")


def test_case_and_dash_style_do_not_decide_a_match() -> None:
    # The dash is built with chr() rather than typed, so this source file stays
    # ASCII while the test still exercises the fold on a real en dash.
    en_dash = chr(0x2013)
    assert term_present("t5-xxl", f"T5{en_dash}XXL was the target model")
    assert term_present("NF4", "quantized with nf4")


def test_big_o_terms_are_distinguished() -> None:
    answer = "it needs O(N) memory instead of O(N²)"
    assert term_present("o(n)", answer)
    assert term_present("o(n²)", answer)
    assert not term_present("o(n²)", "it needs O(N) memory")


def test_a_group_is_satisfied_by_any_one_surface_form() -> None:
    expected = {"required": [["10,000x", "10000 times"], ["3x", "three times"]]}
    matched, missing = answer_matches(expected, "reduces parameters 10000 times and memory 3x")
    assert matched
    assert missing == []


def test_an_unmatched_group_is_reported_not_swallowed() -> None:
    expected = {"required": [["10,000x"], ["3x"]]}
    matched, missing = answer_matches(expected, "reduces trainable parameters 10,000x")
    assert not matched
    assert missing == [["3x"]]


def test_a_task_with_no_expected_answer_is_not_failed_by_this_check() -> None:
    assert answer_matches(None, "anything at all") == (True, [])


def test_the_shipped_file_loads_from_its_default_path() -> None:
    assert TASKS_PATH.exists()
    assert len(load_tasks(TASKS_PATH)) == 150
