function buildRequest(path: string): [string, RequestInit] {
  if (typeof window !== "undefined") {
    // browser: go through the proxy route (keeps key server-side)
    return [`/api/ef/${path}`, { cache: "no-store" }];
  }
  // server component: call EC2 directly with the key
  const base = process.env.EVALFORGE_API_URL ?? "http://23.21.42.197:8001";
  const key = process.env.EVALFORGE_API_KEY ?? "";
  const headers: Record<string, string> = {};
  if (key) headers["X-API-Key"] = key;
  return [`${base}/${path}`, { cache: "no-store", headers }];
}

async function get<T>(path: string, timeoutMs = 8000): Promise<T> {
  const [url, init] = buildRequest(path);
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const res = await fetch(url, { ...init, signal: ctrl.signal });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    return res.json();
  } finally {
    clearTimeout(timer);
  }
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
