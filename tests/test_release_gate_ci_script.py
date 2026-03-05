import json
import subprocess
import sys
from pathlib import Path


def _run_script_with_payload(tmp_path: Path, payload: dict, *extra_args: str) -> subprocess.CompletedProcess:
    payload_path = tmp_path / "ci_decision.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "scripts/ci/check_release_gate.py",
            "--input-file",
            str(payload_path),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_ci_script_blocks_on_failed_decision(tmp_path: Path) -> None:
    result = _run_script_with_payload(
        tmp_path,
        {
            "status": "failed",
            "allow_deploy": False,
            "reason_codes": ["SCORE_DELTA_FAIL"],
            "summary": "Quality regression detected.",
        },
    )

    assert result.returncode == 1
    assert "Blocking deployment based on release-gate decision." in result.stdout


def test_ci_script_allows_when_decision_missing_and_override_disabled(tmp_path: Path) -> None:
    result = _run_script_with_payload(
        tmp_path,
        {
            "status": "not_evaluated",
            "allow_deploy": True,
            "reason_codes": [],
            "summary": "No release decision found.",
        },
        "--require-gate-decision",
        "false",
    )

    assert result.returncode == 0
    assert "Release gate status: not_evaluated" in result.stdout
