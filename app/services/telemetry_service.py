from sqlalchemy.orm import Session

from app.services.eval_service import eval_service
from app.models.eval_run import EvalRunResponse
from app.models.telemetry import TelemetryRollup, TelemetrySummary


class TelemetryService:
    def summary(self, db: Session, workspace_id: str = "default") -> TelemetrySummary:
        runs = eval_service.list_runs(db, workspace_id=workspace_id)
        case_results = [result for run in runs for result in run.results]
        total_runs = len(runs)
        average_score = round(
            sum(run.average_score for run in runs) / total_runs, 4
        ) if total_runs else 0.0
        total_cost_usd = round(sum(result.cost_usd for result in case_results), 6)
        average_latency_ms = round(
            sum(result.latency_ms for result in case_results) / len(case_results), 2
        ) if case_results else 0.0
        structured_cases = [result for result in case_results if getattr(result, "required_json_fields", [])]
        structured_output_failure_count = sum(
            1 for result in structured_cases if not getattr(result, "structured_output_valid", False)
        )
        structured_output_pass_rate = round(
            (
                sum(1 for result in structured_cases if getattr(result, "structured_output_valid", False))
                / len(structured_cases)
            ),
            4,
        ) if structured_cases else 1.0
        grounded_cases = [result for result in case_results if getattr(result, "reference_answer", None)]
        groundedness_average = round(
            sum(getattr(result, "groundedness_score", 1.0) for result in grounded_cases) / len(grounded_cases),
            4,
        ) if grounded_cases else 1.0
        groundedness_failure_count = sum(
            1 for result in grounded_cases if getattr(result, "groundedness_score", 1.0) < 0.5
        )
        experiment_rollups = self._build_rollups(
            runs,
            key_fn=lambda run: run.experiment_name or "unassigned",
        )
        use_case_rollups = self._build_rollups(
            runs,
            key_fn=lambda run: str((run.run_metadata or {}).get("use_case", "unspecified")),
        )
        return TelemetrySummary(
            total_runs=total_runs,
            average_score=average_score,
            total_cost_usd=total_cost_usd,
            average_latency_ms=average_latency_ms,
            structured_output_pass_rate=structured_output_pass_rate,
            structured_output_failure_count=structured_output_failure_count,
            groundedness_average=groundedness_average,
            groundedness_failure_count=groundedness_failure_count,
            experiment_rollups=experiment_rollups,
            use_case_rollups=use_case_rollups,
        )

    @staticmethod
    def _build_rollups(
        runs: list[EvalRunResponse],
        key_fn,
    ) -> list[TelemetryRollup]:
        grouped: dict[str, list[EvalRunResponse]] = {}
        for run in runs:
            key = key_fn(run)
            grouped.setdefault(key, []).append(run)

        rollups: list[TelemetryRollup] = []
        for key, grouped_runs in grouped.items():
            grouped_cases = [result for run in grouped_runs for result in run.results]
            total_runs = len(grouped_runs)
            average_score = round(sum(run.average_score for run in grouped_runs) / total_runs, 4) if total_runs else 0.0
            total_cost_usd = round(sum(result.cost_usd for result in grouped_cases), 6)
            average_latency_ms = round(
                sum(result.latency_ms for result in grouped_cases) / len(grouped_cases), 2
            ) if grouped_cases else 0.0
            rollups.append(
                TelemetryRollup(
                    key=key,
                    total_runs=total_runs,
                    average_score=average_score,
                    total_cost_usd=total_cost_usd,
                    average_latency_ms=average_latency_ms,
                )
            )

        return sorted(rollups, key=lambda item: (-item.total_runs, item.key))


telemetry_service = TelemetryService()
