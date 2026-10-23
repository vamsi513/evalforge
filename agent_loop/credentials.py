"""Loading API keys from outside the repository.

This lives in its own module, importing nothing from EvalForge or AgentIQ, for
a specific reason. Both projects build a settings singleton at import time that
reads credentials straight out of the environment, so the keys have to be in
place before the first of those imports happens. A loader that itself pulled in
app.core.config would be too late by definition, which is exactly the bug that
made the first judge probe run silently against the mock judge.
"""

import os
from pathlib import Path

ENV_FILE = Path.home() / ".agent_loop.env"


def load_env_file(path: Path = ENV_FILE) -> list[str]:
    """Load API keys from a file outside the repository.

    Returns the names of the variables it set. Values are never returned,
    logged or echoed. Variables already present in the environment win, so one
    can be overridden for a single run without editing the file.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"{path} does not exist. It holds the API keys and is deliberately "
            "outside any repository."
        )
    loaded: list[str] = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, _, value = stripped.partition("=")
        name = name.strip()
        value = value.strip().strip("'\"")
        if name and not os.environ.get(name):
            os.environ[name] = value
            loaded.append(name)
    return loaded
