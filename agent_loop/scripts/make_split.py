"""Write agent_loop/data/split.json from the task file.

Deterministic: same task file plus same seed gives the same split. The task file
hash is recorded so a later run can tell whether the tasks changed underneath an
existing split, which would invalidate the held out guarantee.

Usage:
    python -m agent_loop.scripts.make_split
    python -m agent_loop.scripts.make_split --check
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from agent_loop.splitting import (
    DEFAULT_DEV_SIZE,
    DEFAULT_SEED,
    file_sha256,
    stratified_split,
)
from agent_loop.tasks import DATA_DIR, TASKS_PATH, load_tasks

SPLIT_PATH = DATA_DIR / "split.json"


def build_split(
    tasks_path: Path = TASKS_PATH, *, seed: int = DEFAULT_SEED, dev_size: int = DEFAULT_DEV_SIZE
) -> dict:
    tasks = load_tasks(tasks_path)
    dev, held_out = stratified_split(tasks, dev_size=dev_size, seed=seed)
    by_id = {task["id"]: task for task in tasks}

    return {
        "seed": seed,
        "tasks_file": tasks_path.name,
        "tasks_sha256": file_sha256(tasks_path),
        "total_tasks": len(tasks),
        "development_size": len(dev),
        "held_out_size": len(held_out),
        "development_counts": dict(sorted(Counter(by_id[i]["category"] for i in dev).items())),
        "held_out_counts": dict(sorted(Counter(by_id[i]["category"] for i in held_out).items())),
        "held_out_policy": (
            "The held out ids are scored exactly twice: once before the fix and once "
            "after it. Held out failures are never inspected, and no task or fix is "
            "changed after a held out run."
        ),
        "development_ids": dev,
        "held_out_ids": held_out,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the split on disk still matches the task file, write nothing",
    )
    args = parser.parse_args()

    split = build_split()

    if args.check:
        if not SPLIT_PATH.exists():
            raise SystemExit(f"{SPLIT_PATH} does not exist")
        on_disk = json.loads(SPLIT_PATH.read_text())
        for field in ("tasks_sha256", "development_ids", "held_out_ids"):
            if on_disk.get(field) != split[field]:
                raise SystemExit(
                    f"split.json disagrees with the task file on {field}. "
                    "The tasks changed after the split was drawn."
                )
        print(f"split.json matches {TASKS_PATH.name} (sha256 {split['tasks_sha256'][:12]})")
        return

    SPLIT_PATH.write_text(json.dumps(split, indent=2) + "\n")
    print(f"wrote {SPLIT_PATH}")
    print(f"  development {split['development_size']}: {split['development_counts']}")
    print(f"  held out    {split['held_out_size']}: {split['held_out_counts']}")


if __name__ == "__main__":
    main()
