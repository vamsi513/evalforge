from sqlalchemy.orm import Session

from app.services.eval_service import eval_service
from app.models.telemetry import TelemetrySummary


class TelemetryService:
    def summary(self, db: Session) -> TelemetrySummary:
        runs = eval_service.list_runs(db)
        case_results = [result for run in runs for result in run.results]
        total_runs = len(runs)
        average_score = round(
            sum(run.average_score for run in runs) / total_runs, 4
        ) if total_runs else 0.0
        total_cost_usd = round(sum(result.cost_usd for result in case_results), 6)
        average_latency_ms = round(
            sum(result.latency_ms for result in case_results) / len(case_results), 2
        ) if case_results else 0.0
        return TelemetrySummary(
            total_runs=total_runs,
            average_score=average_score,
            total_cost_usd=total_cost_usd,
            average_latency_ms=average_latency_ms,
        )


telemetry_service = TelemetryService()
