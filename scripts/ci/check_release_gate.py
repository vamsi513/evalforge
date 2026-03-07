#!/usr/bin/env python3
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _fetch_trends(
    api_url: str,
    dataset_name: str,
    experiment_name: str,
    workspace_id: str,
    api_key: str,
    lookback_days: int = 30,
) -> Dict[str, Any]:
    url = f"{api_url.rstrip('/')}/api/v1/release-gates/trends"
    params: Dict[str, Any] = {"dataset_name": dataset_name, "lookback_days": lookback_days}
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


def _render_report(
    payload: Dict[str, Any],
    trends_payload: Optional[Dict[str, Any]] = None,
    require_gate_decision: bool = True,
) -> str:
    status = str(payload.get("status", "unknown"))
    allow_deploy = bool(payload.get("allow_deploy", False))
    decision_id = str(payload.get("decision_id", ""))
    dataset = str(payload.get("dataset_name", ""))
    experiment = str(payload.get("experiment_name", ""))
    summary = str(payload.get("summary", ""))
    reason_codes = [str(code) for code in payload.get("reason_codes", [])]
    reason_details = [str(reason) for reason in payload.get("reason_details", [])]
    generated_at = datetime.now(timezone.utc).isoformat()

    lines = [
        "# EvalGate CI Report",
        "",
        f"- Generated at (UTC): `{generated_at}`",
        f"- Require gate decision: `{require_gate_decision}`",
        f"- Dataset: `{dataset}`",
        f"- Experiment: `{experiment or 'n/a'}`",
        f"- Decision ID: `{decision_id or 'n/a'}`",
        f"- Status: `{status}`",
        f"- Allow deploy: `{allow_deploy}`",
        "",
        "## Summary",
        "",
        summary or "No summary provided by release-gate API.",
        "",
        "## Failure Reasons",
        "",
    ]
    if reason_codes:
        for code in reason_codes:
            lines.append(f"- Code: `{code}`")
    else:
        lines.append("- No failure codes.")

    if reason_details:
        lines.append("")
        lines.append("### Reason Details")
        lines.append("")
        for detail in reason_details:
            lines.append(f"- {detail}")

    if trends_payload:
        lines.extend(
            [
                "",
                "## 30-Day Trend Snapshot",
                "",
                f"- Total decisions: `{trends_payload.get('total_decisions', 0)}`",
                f"- Overall pass rate: `{trends_payload.get('overall_pass_rate', 0.0)}`",
            ]
        )
        top_codes = trends_payload.get("top_failure_codes", [])
        if top_codes:
            lines.append("- Top failure codes:")
            for item in top_codes:
                code = item.get("code", "")
                count = item.get("count", 0)
                lines.append(f"  - `{code}`: `{count}`")
    return "\n".join(lines) + "\n"


def _write_report(report_path: Path, content: str) -> None:
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(content, encoding="utf-8")


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
    parser.add_argument(
        "--trends-input-file",
        default="",
        help="Optional JSON file containing release-gate trends payload.",
    )
    parser.add_argument(
        "--report-out",
        default=os.getenv("EVALFORGE_REPORT_PATH", ""),
        help="Optional output path for generated Markdown report artifact.",
    )
    args = parser.parse_args()

    require_gate = _truthy(str(args.require_gate_decision))
    trends_payload: Optional[Dict[str, Any]] = None

    if args.input_file:
        payload = _load_decision_from_file(Path(args.input_file))
        if args.trends_input_file:
            trends_payload = _load_decision_from_file(Path(args.trends_input_file))
        if args.report_out:
            _write_report(
                Path(args.report_out),
                _render_report(payload, trends_payload=trends_payload, require_gate_decision=require_gate),
            )
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
        try:
            trends_payload = _fetch_trends(
                api_url=args.api_url,
                dataset_name=args.dataset,
                experiment_name=args.experiment,
                workspace_id=args.workspace,
                api_key=args.api_key,
                lookback_days=30,
            )
        except Exception as trends_exc:  # noqa: BLE001
            print(f"Warning: unable to fetch release-gate trends: {trends_exc}")
    except Exception as exc:  # noqa: BLE001
        print(f"Failed to fetch release-gate decision: {exc}")
        return 1

    if args.report_out:
        _write_report(
            Path(args.report_out),
            _render_report(payload, trends_payload=trends_payload, require_gate_decision=require_gate),
        )

    return _evaluate_decision(payload, require_gate)


if __name__ == "__main__":
    raise SystemExit(main())
