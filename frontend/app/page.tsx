import { api } from "@/lib/api";
import MetricCard from "@/components/MetricCard";
import RunsTable from "@/components/RunsTable";
import ScoreChart from "@/components/ScoreChart";
import DemoButton from "@/components/DemoButton";
import { CheckCircle, FlaskConical, Zap, TrendingUp, DollarSign } from "lucide-react";

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
  const totalPassed = allResults.filter(r => r.passed).length;
  const passRate = allResults.length > 0 ? totalPassed / allResults.length : 0;

  const now = new Date().toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true,
  });

  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      {/* Page header */}
      <div style={{ marginBottom: 32 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              fontSize: 11.5, fontWeight: 600, padding: "4px 11px", borderRadius: 20,
              background: online ? "var(--green-dim)" : "var(--red-dim)",
              color: online ? "var(--green)" : "var(--red)",
              border: `1px solid ${online ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
            }}>
              <span
                className={online ? "pulse" : ""}
                style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: online ? "var(--green)" : "var(--red)",
                  display: "inline-block",
                }}
              />
              {online ? "All systems operational" : "API unreachable"}
            </span>
          </div>
          <span style={{ fontSize: 11.5, color: "var(--subtle)" }}>Updated {now}</span>
        </div>

        <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.7px", marginBottom: 5 }}>
          Overview
        </h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)" }}>
          Quality metrics across your AI evaluation runs
        </p>
      </div>

      {/* Demo widget */}
      <DemoButton />

      {/* Metric cards */}
      <div className="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 28 }}>
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
          sub={allResults.length > 0
            ? `${totalPassed} of ${allResults.length} cases`
            : "No cases yet"}
          icon={TrendingUp}
          color={passRate >= 0.8 ? "var(--green)" : passRate >= 0.65 ? "var(--yellow)" : "var(--red)"}
        />
        <MetricCard
          label="Total Eval Runs"
          value={String(telemetry.total_runs)}
          sub="Demo workspace"
          icon={FlaskConical}
        />
        <MetricCard
          label="Avg Latency"
          value={`${Math.round(telemetry.average_latency_ms)} ms`}
          sub="Per test case"
          icon={Zap}
          color="var(--yellow)"
        />
        <MetricCard
          label="Compute Cost"
          value={`$${(telemetry.total_cost_usd ?? 0).toFixed(4)}`}
          sub="Total OpenAI spend"
          icon={DollarSign}
          color="var(--green)"
        />
      </div>

      {/* Charts row */}
      <div className="chart-grid" style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 14 }}>
        <ScoreChart runs={runs} />
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 14, overflow: "hidden",
        }}>
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "16px 20px", borderBottom: "1px solid var(--border)",
          }}>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600 }}>Recent Runs</div>
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>
                {runs.length} total
              </div>
            </div>
            {runs.length > 0 && (
              <a href="/runs" style={{ fontSize: 12, color: "var(--accent)", fontWeight: 500 }}>
                View all →
              </a>
            )}
          </div>
          <RunsTable runs={runs.slice(0, 7)} compact />
        </div>
      </div>
    </div>
  );
}
