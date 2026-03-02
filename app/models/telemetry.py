from pydantic import BaseModel


class TelemetrySummary(BaseModel):
    total_runs: int
    average_score: float
    total_cost_usd: float
    average_latency_ms: float

