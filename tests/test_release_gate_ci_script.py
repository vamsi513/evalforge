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


def test_ci_script_writes_markdown_report(tmp_path: Path) -> None:
    trends_payload = {
        "total_decisions": 6,
        "overall_pass_rate": 0.5,
        "top_failure_codes": [{"code": "SCORE_DELTA_FAIL", "count": 2}],
    }
    trends_path = tmp_path / "trends.json"
    trends_path.write_text(json.dumps(trends_payload), encoding="utf-8")
    report_path = tmp_path / "report.md"

    result = _run_script_with_payload(
        tmp_path,
        {
            "status": "failed",
            "allow_deploy": False,
            "dataset_name": "support_golden_set_v2",
            "experiment_name": "nightly-eval",
            "decision_id": "decision-123",
            "reason_codes": ["SCORE_DELTA_FAIL"],
            "reason_details": ["Candidate score delta -0.08 is below threshold -0.02."],
            "summary": "Quality regression detected.",
        },
        "--trends-input-file",
        str(trends_path),
        "--report-out",
        str(report_path),
    )

    assert result.returncode == 1
    assert report_path.exists()
    report = report_path.read_text(encoding="utf-8")
    assert "EvalGate CI Report" in report
    assert "support_golden_set_v2" in report
    assert "SCORE_DELTA_FAIL" in report
    assert "30-Day Trend Snapshot" in report
