#!/usr/bin/env python3
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx


def _truthy(value: str) -> bool:
    return value.strip().lower() not in {"", "0", "false", "no"}


def _load_decision_from_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _fetch_decision(
    api_url: str,
    dataset_name: str,
    experiment_name: str,
    workspace_id: str,
    api_key: str,
) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/api/v1/release-gates/ci-decision"
    params = {"dataset_name": dataset_name}
    if experiment_name:
        params["experiment_name"] = experiment_name

    headers = {"Accept": "application/json"}
    if workspace_id:
        headers["X-Workspace-ID"] = workspace_id
    if api_key:
        headers["X-API-Key"] = api_key

    with httpx.Client(timeout=15.0) as client:
        response = client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()


def _evaluate_decision(payload: Dict[str, Any], require_gate_decision: bool) -> int:
    status = str(payload.get("status", "unknown"))
    allow_deploy = bool(payload.get("allow_deploy", False))
    reason_codes: List[str] = list(payload.get("reason_codes", []))
    summary = str(payload.get("summary", ""))

    print(f"Release gate status: {status}")
    print(f"Allow deploy: {allow_deploy}")
    print(f"Reason codes: {reason_codes}")
    print(f"Summary: {summary}")

    if status == "not_evaluated" and require_gate_decision:
        print("Blocking deployment: no release-gate decision found.")
        return 1

    if not allow_deploy:
        print("Blocking deployment based on release-gate decision.")
        return 1

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch and enforce EvalForge release-gate CI decision.")
    parser.add_argument("--api-url", default=os.getenv("EVALFORGE_API_URL", ""))
    parser.add_argument("--dataset", default=os.getenv("EVALFORGE_DATASET", ""))
    parser.add_argument("--experiment", default=os.getenv("EVALFORGE_EXPERIMENT", ""))
    parser.add_argument("--workspace", default=os.getenv("EVALFORGE_WORKSPACE", ""))
    parser.add_argument("--api-key", default=os.getenv("EVALFORGE_API_KEY", ""))
    parser.add_argument(
        "--require-gate-decision",
        default=os.getenv("EVALFORGE_REQUIRE_GATE_DECISION", "true"),
        help="Whether missing gate decisions should block deployment.",
    )
    parser.add_argument(
        "--input-file",
        default="",
        help="Optional JSON file to read decision payload from (skips API call).",
    )
    args = parser.parse_args()

    require_gate = _truthy(str(args.require_gate_decision))
    if args.input_file:
        payload = _load_decision_from_file(Path(args.input_file))
        return _evaluate_decision(payload, require_gate)

    if not args.api_url:
        print("Missing required argument: --api-url (or EVALFORGE_API_URL).")
        return 2
    if not args.dataset:
        print("Missing required argument: --dataset (or EVALFORGE_DATASET).")
        return 2

    try:
        payload = _fetch_decision(
            api_url=args.api_url,
            dataset_name=args.dataset,
            experiment_name=args.experiment,
            workspace_id=args.workspace,
            api_key=args.api_key,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch release-gate decision: {exc}")
        return 1

    return _evaluate_decision(payload, require_gate)


if __name__ == "__main__":
    raise SystemExit(main())

