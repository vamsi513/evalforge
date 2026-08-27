import { api } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import RunsTable from "@/components/RunsTable";
import ScoreChart from "@/components/ScoreChart";
import { CheckCircle, FlaskConical, Zap, DollarSign } from "lucide-react";

export const revalidate = 30;

function scoreColor(s: number) {
  if (s >= 0.8) return "var(--green)";
  if (s >= 0.5) return "var(--yellow)";
  return "var(--red)";
}

export default async function DashboardPage() {
  const [health, telemetry, runs] = await Promise.all([
    api.health().catch(() => ({ status: "error" })),
    api.telemetry().catch(() => ({ total_runs: 0, average_score: 0, total_cost_usd: 0, average_latency_ms: 0 })),
    api.runs().catch(() => []),
  ]);

  const online = health.status === "ok";
  const score = telemetry.average_score ?? 0;

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 12, fontWeight: 600, padding: "4px 10px", borderRadius: 20,
            background: online ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            color: online ? "var(--green)" : "var(--red)",
            border: `1px solid ${online ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
          }}>
            <span style={{ width: 6, height: 6, borderRadius: "50%", background: online ? "var(--green)" : "var(--red)" }} />
            {online ? "All systems operational" : "API unreachable"}
          </span>
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Overview</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Real-time quality metrics for your AI evaluations
        </p>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 32 }}>
        <MetricCard label="Avg Quality Score" value={`${Math.round(score * 100)}%`}
          sub={score >= 0.8 ? "Above threshold" : score >= 0.5 ? "Near threshold" : "Below threshold"}
          icon={CheckCircle} color={scoreColor(score)} />
        <MetricCard label="Total Eval Runs" value={String(telemetry.total_runs)}
          sub="Across all workspaces" icon={FlaskConical} />
        <MetricCard label="Avg Latency" value={`${Math.round(telemetry.average_latency_ms)} ms`}
          sub="Per test case" icon={Zap} color="var(--yellow)" />
        <MetricCard label="Compute Cost" value={`$${telemetry.total_cost_usd.toFixed(4)}`}
          sub="Total OpenAI spend" icon={DollarSign} color="var(--green)" />
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1.2fr 1fr", gap: 16 }}>
        <ScoreChart runs={runs} />
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 16 }}>Recent Runs</h2>
          <RunsTable runs={runs.slice(0, 6)} compact />
        </div>
      </div>
    </div>
  );
}
