from pydantic import BaseModel


class TelemetrySummary(BaseModel):
    total_runs: int
    average_score: float
    total_cost_usd: float
    average_latency_ms: float
    structured_output_pass_rate: float
    structured_output_failure_count: int
    groundedness_average: float
    groundedness_failure_count: int
