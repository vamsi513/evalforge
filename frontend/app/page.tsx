import { api } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import RunsTable from "@/components/RunsTable";
import ScoreChart from "@/components/ScoreChart";
import DemoButton from "@/components/DemoButton";
import { CheckCircle, FlaskConical, Zap, TrendingUp } from "lucide-react";

export const dynamic = "force-dynamic";

function scoreColor(s: number) {
  if (s >= 0.8) return "var(--green)";
  if (s >= 0.65) return "var(--yellow)";
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

  const allResults = runs.flatMap(r => r.results ?? []);
  const passRate = allResults.length > 0
    ? allResults.filter(r => r.passed).length / allResults.length
    : 0;

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      {/* Header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 10 }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 12, fontWeight: 600, padding: "4px 10px", borderRadius: 20,
            background: online ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
            color: online ? "var(--green)" : "var(--red)",
            border: `1px solid ${online ? "rgba(34,197,94,0.25)" : "rgba(239,68,68,0.25)"}`,
          }}>
            <span style={{
              width: 6, height: 6, borderRadius: "50%",
              background: online ? "var(--green)" : "var(--red)",
              boxShadow: online ? "0 0 6px #22c55e" : "none",
            }} />
            {online ? "All systems operational" : "API unreachable"}
          </span>
        </div>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Overview</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Real-time quality metrics across your AI evaluation pipeline
        </p>
      </div>

      {/* Demo widget */}
      <DemoButton />

      {/* Metric cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 16, marginBottom: 28 }}>
        <MetricCard
          label="Avg Quality Score"
          value={`${Math.round(score * 100)}%`}
          sub={score >= 0.8 ? "Above threshold" : score >= 0.65 ? "Near threshold" : "Below threshold"}
          icon={CheckCircle}
          color={scoreColor(score)}
        />
        <MetricCard
          label="Pass Rate"
          value={allResults.length > 0 ? `${Math.round(passRate * 100)}%` : "—"}
          sub={allResults.length > 0 ? `${allResults.filter(r => r.passed).length} of ${allResults.length} cases` : "No cases yet"}
          icon={TrendingUp}
          color={passRate >= 0.8 ? "var(--green)" : passRate >= 0.65 ? "var(--yellow)" : "var(--red)"}
        />
        <MetricCard
          label="Total Eval Runs"
          value={String(telemetry.total_runs)}
          sub="Across all workspaces"
          icon={FlaskConical}
        />
        <MetricCard
          label="Avg Latency"
          value={`${Math.round(telemetry.average_latency_ms)} ms`}
          sub="Per test case"
          icon={Zap}
          color="var(--yellow)"
        />
      </div>

      {/* Charts row */}
      <div style={{ display: "grid", gridTemplateColumns: "1.3fr 1fr", gap: 16 }}>
        <ScoreChart runs={runs} />
        <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 16 }}>
            <h2 style={{ fontSize: 14, fontWeight: 600 }}>Recent Runs</h2>
            {runs.length > 0 && (
              <a href="/runs" style={{ fontSize: 12, color: "var(--accent)", textDecoration: "none" }}>
                View all →
              </a>
            )}
          </div>
          <RunsTable runs={runs.slice(0, 6)} compact />
        </div>
      </div>
    </div>
  );
}
