"""Seeded, stratified splitting and sampling.

Two things need to be reproducible and auditable here.

The development and held out split decides which failures I am allowed to look
at. If it moved between runs, the held out set would leak into the fix, so it is
derived from a fixed seed and written to disk with a hash of the task file. A
later run that produces a different split is a bug, and the hash is what makes
that visible instead of silent.

The review sheet sample decides which runs a human labels. It is stratified by
category so a 60 row sheet is not accidentally three quarters retrieval.

Allocation uses largest remainder, so the per category counts sum to exactly the
requested size rather than drifting by a task or two through rounding.
"""

import hashlib
import random
from collections import OrderedDict
from pathlib import Path

DEFAULT_SEED = 20261022
DEFAULT_DEV_SIZE = 90


def file_sha256(path: Path | str) -> str:
    """Hash of the task file, recorded alongside a split.

    A split only means something in relation to the exact task list it was drawn
    from. Storing the hash lets a later run assert that nothing moved underneath.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(65536), b""):
            digest.update(block)
    return digest.hexdigest()


def _allocate(group_sizes: "OrderedDict[str, int]", total_wanted: int) -> dict[str, int]:
    """Spread total_wanted across groups in proportion to their size.

    Largest remainder: floor every share, then hand the leftover one at a time to
    the groups with the largest fractional part. Ties break on group name so the
    result does not depend on dict ordering.
    """
    total = sum(group_sizes.values())
    if total_wanted > total:
        raise ValueError(f"cannot take {total_wanted} items from {total}")

    exact = {name: size * total_wanted / total for name, size in group_sizes.items()}
    allocation = {name: int(value) for name, value in exact.items()}

    leftover = total_wanted - sum(allocation.values())
    remainders = sorted(
        group_sizes, key=lambda name: (-(exact[name] - allocation[name]), name)
    )
    for name in remainders[:leftover]:
        allocation[name] += 1
    return allocation


def _grouped(items: list[dict], key: str) -> "OrderedDict[str, list[dict]]":
    groups: OrderedDict[str, list[dict]] = OrderedDict()
    for item in items:
        groups.setdefault(item[key], []).append(item)
    return OrderedDict(sorted(groups.items()))


def stratified_split(
    tasks: list[dict],
    *,
    dev_size: int = DEFAULT_DEV_SIZE,
    seed: int = DEFAULT_SEED,
    key: str = "category",
) -> tuple[list[str], list[str]]:
    """Split task ids into (development, held out), stratified by category.

    Shuffling happens on an id-sorted copy of each group, so the result depends
    only on the seed and the set of ids, never on the order of lines in the file.
    """
    groups = _grouped(tasks, key)
    allocation = _allocate(
        OrderedDict((name, len(members)) for name, members in groups.items()), dev_size
    )

    dev: list[str] = []
    held_out: list[str] = []
    for name, members in groups.items():
        ids = sorted(task["id"] for task in members)
        random.Random(f"{seed}:{name}").shuffle(ids)
        take = allocation[name]
        dev.extend(ids[:take])
        held_out.extend(ids[take:])

    return sorted(dev), sorted(held_out)


def even_sample(
    items: list[dict],
    *,
    per_category: int,
    seed: int,
    key: str = "category",
    id_field: str = "id",
) -> list[str]:
    """Take exactly `per_category` ids from every category.

    Different from stratified_sample, which mirrors the population. Even
    allocation gives each category the same number of labelled rows, so the per
    category agreement figures all rest on the same sample size and none is
    read off two or three items.

    Selection depends only on the seed and the set of ids. Nothing about a
    run's outcome is visible to it, so a row can never be chosen because it
    failed. A category with too few members is an error rather than a quietly
    short column.
    """
    groups = _grouped(items, key)
    short = {
        name: len(members) for name, members in groups.items() if len(members) < per_category
    }
    if short:
        raise ValueError(
            f"cannot take {per_category} from every category; these have fewer: {short}"
        )

    picked: list[str] = []
    for name, members in groups.items():
        ids = sorted(item[id_field] for item in members)
        random.Random(f"{seed}:even:{name}").shuffle(ids)
        picked.extend(ids[:per_category])
    return sorted(picked)


def stratified_sample(
    items: list[dict],
    *,
    n: int,
    seed: int,
    key: str = "category",
    id_field: str = "id",
) -> list[str]:
    """Pick n ids, spread across categories in proportion to their size."""
    groups = _grouped(items, key)
    allocation = _allocate(
        OrderedDict((name, len(members)) for name, members in groups.items()), n
    )

    picked: list[str] = []
    for name, members in groups.items():
        ids = sorted(item[id_field] for item in members)
        random.Random(f"{seed}:sample:{name}").shuffle(ids)
        picked.extend(ids[: allocation[name]])
    return sorted(picked)
