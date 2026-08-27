const base = "/api/ef";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${base}/${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

export interface Telemetry {
  total_runs: number;
  average_score: number;
  total_cost_usd: number;
  average_latency_ms: number;
}

export interface EvalRun {
  id: string;
  dataset_name: string;
  model_name: string;
  prompt_version: string;
  average_score: number;
  created_at: string;
  results: { score: number; latency_ms: number; cost_usd: number; passed: boolean }[];
}

export interface Dataset {
  name: string;
  case_count: number;
  created_at: string;
}

export interface LeaderboardItem {
  experiment_name: string;
  model_name: string;
  average_score: number;
  run_count: number;
  average_latency_ms: number;
}

export const api = {
  health: () => get<{ status: string }>("health"),
  telemetry: () => get<Telemetry>("api/v1/telemetry/summary"),
  runs: () => get<EvalRun[]>("api/v1/evals"),
  datasets: () => get<Dataset[]>("api/v1/datasets"),
  leaderboard: () =>
    get<{ items: LeaderboardItem[] }>("api/v1/experiments/leaderboard?lookback_runs=20&limit=10"),
  releaseGates: () => get<Record<string, unknown>[]>("api/v1/release-gates"),
};
