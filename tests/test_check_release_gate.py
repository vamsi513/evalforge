import importlib.util
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "check_release_gate.py"
spec = importlib.util.spec_from_file_location("check_release_gate", SCRIPT_PATH)
check_release_gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check_release_gate)


def test_not_evaluated_blocks_when_required():
    payload = {"status": "not_evaluated", "allow_deploy": False}
    assert check_release_gate._evaluate_decision(payload, require_gate_decision=True) == 1


def test_not_evaluated_allows_when_not_required():
    payload = {"status": "not_evaluated", "allow_deploy": False}
    assert check_release_gate._evaluate_decision(payload, require_gate_decision=False) == 0


def test_evaluated_and_allowed_passes_regardless_of_requirement():
    payload = {"status": "evaluated", "allow_deploy": True}
    assert check_release_gate._evaluate_decision(payload, require_gate_decision=True) == 0
    assert check_release_gate._evaluate_decision(payload, require_gate_decision=False) == 0


def test_evaluated_but_disallowed_blocks():
    payload = {"status": "evaluated", "allow_deploy": False}
    assert check_release_gate._evaluate_decision(payload, require_gate_decision=False) == 1
