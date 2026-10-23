"""Checks on splitting and sampling.

The point of most of these is contamination. The held out set only means
something if it is disjoint from development, stable across runs, and not
quietly re-drawn when the task file changes. The last one is why split.json
carries a hash.
"""

import json

import pytest

from agent_loop.scripts.make_split import SPLIT_PATH, build_split
from agent_loop.splitting import (
    DEFAULT_DEV_SIZE,
    DEFAULT_SEED,
    _allocate,
    even_sample,
    file_sha256,
    stratified_sample,
    stratified_split,
)
from agent_loop.tasks import TASKS_PATH, load_tasks


@pytest.fixture(scope="module")
def tasks() -> list[dict]:
    return load_tasks()


def _counts(ids: list[str], tasks: list[dict]) -> dict[str, int]:
    by_id = {task["id"]: task for task in tasks}
    counts: dict[str, int] = {}
    for task_id in ids:
        category = by_id[task_id]["category"]
        counts[category] = counts.get(category, 0) + 1
    return counts


# --- the split ------------------------------------------------------------------


def test_the_split_is_ninety_and_sixty(tasks) -> None:
    dev, held_out = stratified_split(tasks)
    assert len(dev) == 90
    assert len(held_out) == 60


def test_development_and_held_out_do_not_overlap(tasks) -> None:
    dev, held_out = stratified_split(tasks)
    assert set(dev).isdisjoint(set(held_out))


def test_every_task_lands_on_exactly_one_side(tasks) -> None:
    dev, held_out = stratified_split(tasks)
    assert set(dev) | set(held_out) == {task["id"] for task in tasks}


def test_the_split_is_stable_for_a_fixed_seed(tasks) -> None:
    assert stratified_split(tasks) == stratified_split(tasks)


def test_a_different_seed_gives_a_different_split(tasks) -> None:
    dev_a, _ = stratified_split(tasks, seed=DEFAULT_SEED)
    dev_b, _ = stratified_split(tasks, seed=DEFAULT_SEED + 1)
    assert dev_a != dev_b


def test_the_split_does_not_depend_on_the_order_of_the_file(tasks) -> None:
    """Re-ordering tasks.jsonl must not move a task between sides."""
    shuffled = list(reversed(tasks))
    assert stratified_split(tasks) == stratified_split(shuffled)


def test_every_category_is_represented_on_both_sides(tasks) -> None:
    dev, held_out = stratified_split(tasks)
    categories = {task["category"] for task in tasks}
    assert set(_counts(dev, tasks)) == categories
    assert set(_counts(held_out, tasks)) == categories


def test_category_proportions_are_preserved(tasks) -> None:
    """60 percent of each category goes to development, give or take rounding."""
    dev, _ = stratified_split(tasks)
    dev_counts = _counts(dev, tasks)
    total_counts = _counts([task["id"] for task in tasks], tasks)
    for category, total in total_counts.items():
        expected = total * DEFAULT_DEV_SIZE / len(tasks)
        assert abs(dev_counts[category] - expected) < 1


def test_a_dev_size_larger_than_the_task_set_is_refused(tasks) -> None:
    with pytest.raises(ValueError, match="cannot take"):
        stratified_split(tasks, dev_size=len(tasks) + 1)


# --- allocation -----------------------------------------------------------------


def test_allocation_sums_to_exactly_the_requested_total() -> None:
    from collections import OrderedDict

    sizes = OrderedDict([("a", 40), ("b", 40), ("c", 35), ("d", 35)])
    for wanted in range(0, 151):
        allocation = _allocate(sizes, wanted)
        assert sum(allocation.values()) == wanted


def test_allocation_never_exceeds_a_group_it_draws_from() -> None:
    from collections import OrderedDict

    sizes = OrderedDict([("a", 2), ("b", 98)])
    allocation = _allocate(sizes, 100)
    assert allocation == {"a": 2, "b": 98}


# --- the review sheet sample ----------------------------------------------------


def test_a_sample_returns_the_requested_size(tasks) -> None:
    assert len(stratified_sample(tasks, n=60, seed=7)) == 60


def test_a_sample_is_stratified_by_category(tasks) -> None:
    picked = stratified_sample(tasks, n=60, seed=7)
    counts = _counts(picked, tasks)
    assert set(counts) == {task["category"] for task in tasks}
    # 60 of 150 is 40 percent, so no category should be far off 40 percent of itself.
    total_counts = _counts([task["id"] for task in tasks], tasks)
    for category, total in total_counts.items():
        assert abs(counts[category] - total * 0.4) < 1


def test_a_sample_is_stable_for_a_fixed_seed(tasks) -> None:
    assert stratified_sample(tasks, n=60, seed=7) == stratified_sample(tasks, n=60, seed=7)


def test_a_sample_has_no_duplicates(tasks) -> None:
    picked = stratified_sample(tasks, n=60, seed=7)
    assert len(set(picked)) == len(picked)


# --- the even review sample -----------------------------------------------------


def test_an_even_sample_takes_the_same_count_from_every_category(tasks) -> None:
    dev_ids = set(json.loads(SPLIT_PATH.read_text())["development_ids"])
    development = [t for t in tasks if t["id"] in dev_ids]

    picked = even_sample(development, per_category=10, seed=5)

    assert len(picked) == 40
    counts = _counts(picked, tasks)
    assert counts == {
        "direct_no_tools": 10,
        "multi_step_retrieval": 10,
        "tool_selection": 10,
        "unanswerable_decline": 10,
    }


def test_an_even_sample_is_stable_for_a_fixed_seed(tasks) -> None:
    assert even_sample(tasks, per_category=10, seed=5) == even_sample(
        tasks, per_category=10, seed=5
    )


def test_a_different_seed_draws_different_rows(tasks) -> None:
    assert even_sample(tasks, per_category=10, seed=5) != even_sample(
        tasks, per_category=10, seed=6
    )


def test_an_even_sample_does_not_depend_on_file_order(tasks) -> None:
    assert even_sample(tasks, per_category=10, seed=5) == even_sample(
        list(reversed(tasks)), per_category=10, seed=5
    )


def test_an_even_sample_has_no_duplicates(tasks) -> None:
    picked = even_sample(tasks, per_category=10, seed=5)
    assert len(set(picked)) == len(picked)


def test_a_category_with_too_few_members_is_an_error_not_a_short_column(tasks) -> None:
    """Silently returning 7 rows for one category would make its agreement
    figure quietly weaker than the others."""
    with pytest.raises(ValueError, match="fewer"):
        even_sample(tasks, per_category=40, seed=5)


def test_the_even_sample_cannot_see_an_outcome(tasks) -> None:
    """Selection depends only on ids and the seed.

    Attaching an outcome to every item must not change which rows are drawn,
    which is what makes "not chosen because it failed" a property rather than
    a promise.
    """
    plain = even_sample(tasks, per_category=10, seed=5)
    with_outcomes = even_sample(
        [{**t, "rule_pass": i % 2 == 0} for i, t in enumerate(tasks)],
        per_category=10,
        seed=5,
    )
    assert plain == with_outcomes


# --- the split on disk ----------------------------------------------------------


def test_the_split_on_disk_matches_a_fresh_build() -> None:
    """Guards against split.json drifting away from the task file unnoticed."""
    on_disk = json.loads(SPLIT_PATH.read_text())
    fresh = build_split()
    assert on_disk["development_ids"] == fresh["development_ids"]
    assert on_disk["held_out_ids"] == fresh["held_out_ids"]
    assert on_disk["tasks_sha256"] == fresh["tasks_sha256"]


def test_the_recorded_hash_is_the_hash_of_the_task_file() -> None:
    on_disk = json.loads(SPLIT_PATH.read_text())
    assert on_disk["tasks_sha256"] == file_sha256(TASKS_PATH)


def test_editing_the_task_file_changes_the_recorded_hash(tmp_path) -> None:
    """The hash is the thing that makes a changed benchmark visible."""
    copy = tmp_path / "tasks.jsonl"
    copy.write_bytes(TASKS_PATH.read_bytes())
    before = file_sha256(copy)
    with open(copy, "a") as handle:
        handle.write("\n")
    assert file_sha256(copy) != before
