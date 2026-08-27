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

const EVALUATORS = [
  { name: "Keyword Match",      desc: "Checks for required terms"           },
  { name: "Reference Overlap",  desc: "ROUGE-style token similarity"        },
  { name: "Rubric Coverage",    desc: "Criterion-by-criterion scoring"      },
  { name: "JSON Structure",     desc: "Schema validation for structured output" },
  { name: "Groundedness",       desc: "Source attribution & factual support" },
];

const FEATURES = [
  { icon: "🧪", label: "Experiment tracking",   desc: "Compare prompt versions and model configs side by side" },
  { icon: "🚦", label: "Release gates",         desc: "PASS/FAIL CI signal that blocks regressions before deploy" },
  { icon: "⚡", label: "Async job worker",       desc: "Background eval jobs via queue — decoupled from the API layer" },
  { icon: "📊", label: "MLflow integration",    desc: "Optional run logging to hosted MLflow tracking server" },
  { icon: "🔌", label: "LLM judge adapters",    desc: "OpenAI · Anthropic · Mistral adapters — with deterministic heuristic fallback" },
];

const STACK = ["FastAPI", "SQLAlchemy", "SQLite", "Next.js 16", "Docker", "GitHub Actions"];

export default async function DashboardPage() {
  const [health, telemetry, runs] = await Promise.all([
    api.health().catch(() => ({ status: "error" })),
    api.telemetry().catch(() => ({ total_runs: 0, average_score: 0, total_cost_usd: 0, average_latency_ms: 0 })),
    api.runs().catch(() => []),
  ]);

  const online = health.status === "ok";

  const allResults = runs.flatMap(r => r.results ?? []);
  const totalPassed = allResults.filter(r => r.passed).length;
  const passRate = allResults.length > 0 ? totalPassed / allResults.length : 0;

  // Prefer runs-derived score (always available) over telemetry (may be scoped differently)
  const runsAvgScore = runs.length > 0
    ? runs.reduce((sum, r) => sum + (r.average_score ?? 0), 0) / runs.length
    : 0;
  const score = runsAvgScore > 0 ? runsAvgScore : (telemetry.average_score ?? 0);
  const runsAvgLatency = allResults.length > 0
    ? allResults.reduce((sum, r) => sum + (r.latency_ms ?? 0), 0) / allResults.length
    : 0;
  const avgLatency = runsAvgLatency > 0 ? runsAvgLatency : (telemetry.average_latency_ms ?? 0);

  const now = new Date().toLocaleString("en-US", {
    month: "short", day: "numeric", hour: "numeric", minute: "2-digit", hour12: true,
  });

  const hasData = runs.length > 0;

  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>

      {/* Page header */}
      <div style={{ marginBottom: 28 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 12 }}>
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 11.5, fontWeight: 600, padding: "4px 11px", borderRadius: 20,
            background: online ? "var(--green-dim)" : "var(--red-dim)",
            color: online ? "var(--green)" : "var(--red)",
            border: `1px solid ${online ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.2)"}`,
          }}>
            <span className={online ? "pulse" : ""} style={{
              width: 6, height: 6, borderRadius: "50%",
              background: online ? "var(--green)" : "var(--red)",
              display: "inline-block",
            }} />
            {online ? "All systems operational" : "API unreachable"}
          </span>
          <span style={{ fontSize: 11.5, color: "var(--subtle)" }}>Updated {now}</span>
        </div>

        <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.7px", marginBottom: 5 }}>Overview</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)" }}>
          Production-inspired LLM evaluation platform — deterministic scoring, experiment tracking, and release gates
        </p>
      </div>

      {/* Demo widget */}
      <DemoButton />

      {/* Metric cards */}
      <div className="metrics-grid" style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 28 }}>
        <MetricCard
          label="Avg Quality Score"
          value={hasData ? `${Math.round(score * 100)}%` : "—"}
          sub={hasData ? (score >= 0.8 ? "Above threshold" : score >= 0.65 ? "Near threshold" : "Below threshold") : "Run demo to populate"}
          icon={CheckCircle}
          color={hasData ? scoreColor(score) : "var(--muted)"}
        />
        <MetricCard
          label="Pass Rate"
          value={allResults.length > 0 ? `${Math.round(passRate * 100)}%` : "—"}
          sub={allResults.length > 0 ? `${totalPassed} of ${allResults.length} cases` : "Run demo to populate"}
          icon={TrendingUp}
          color={allResults.length > 0 ? (passRate >= 0.8 ? "var(--green)" : passRate >= 0.65 ? "var(--yellow)" : "var(--red)") : "var(--muted)"}
        />
        <MetricCard
          label="Total Eval Runs"
          value={String(telemetry.total_runs > 0 ? telemetry.total_runs : runs.length)}
          sub={(telemetry.total_runs > 0 || runs.length > 0) ? "Demo workspace" : "Run demo to populate"}
          icon={FlaskConical}
        />
        <MetricCard
          label="Avg Latency"
          value={hasData ? `${Math.round(avgLatency)} ms` : "—"}
          sub="Per test case"
          icon={Zap}
          color={hasData ? "var(--yellow)" : "var(--muted)"}
        />
        <MetricCard
          label="Compute Cost"
          value={`$${(telemetry.total_cost_usd ?? 0).toFixed(4)}`}
          sub={(telemetry.total_cost_usd ?? 0) < 0.001 ? "Heuristic scoring" : "Judge API spend"}
          icon={DollarSign}
          color="var(--green)"
        />
      </div>

      {/* Charts row */}
      <div className="chart-grid" style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 14, marginBottom: 28 }}>
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
              <div style={{ fontSize: 11.5, color: "var(--muted)", marginTop: 2 }}>{runs.length} total</div>
            </div>
            {runs.length > 0 && (
              <a href="/runs" style={{ fontSize: 12, color: "var(--accent)", fontWeight: 500 }}>View all →</a>
            )}
          </div>
          <RunsTable runs={runs.slice(0, 7)} compact />
        </div>
      </div>

      {/* ── Evaluator profiles ── */}
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 14, padding: "22px 24px", marginBottom: 16,
      }}>
        <div style={{ marginBottom: 16 }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 4 }}>Evaluator profiles</div>
          <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
            Five deterministic signals — no external API required. LLM judge adapters layer on top for deeper semantic scoring.
          </div>
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 10 }}>
          {EVALUATORS.map(e => (
            <div key={e.name} style={{
              background: "var(--bg)", border: "1px solid var(--border)",
              borderRadius: 10, padding: "12px 14px",
            }}>
              <div style={{
                display: "inline-block", width: 6, height: 6, borderRadius: "50%",
                background: "var(--accent)", marginBottom: 8,
              }} />
              <div style={{ fontSize: 12.5, fontWeight: 600, color: "var(--text)", marginBottom: 4 }}>{e.name}</div>
              <div style={{ fontSize: 11, color: "var(--subtle)", lineHeight: 1.5 }}>{e.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* ── Feature cards ── */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 16 }}>
        {FEATURES.slice(0, 3).map(f => (
          <div key={f.label} style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "16px 18px",
          }}>
            <div style={{ fontSize: 20, marginBottom: 10 }}>{f.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 5 }}>{f.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.55 }}>{f.desc}</div>
          </div>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: 12, marginBottom: 24 }}>
        {FEATURES.slice(3).map(f => (
          <div key={f.label} style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "16px 18px",
          }}>
            <div style={{ fontSize: 20, marginBottom: 10 }}>{f.icon}</div>
            <div style={{ fontSize: 13, fontWeight: 700, marginBottom: 5 }}>{f.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--muted)", lineHeight: 1.55 }}>{f.desc}</div>
          </div>
        ))}
      </div>

      {/* ── Tech stack strip ── */}
      <div style={{
        display: "flex", alignItems: "center", gap: 10,
        padding: "14px 20px",
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 10, flexWrap: "wrap",
      }}>
        <span style={{ fontSize: 11, fontWeight: 600, color: "var(--subtle)", letterSpacing: "0.06em", textTransform: "uppercase", marginRight: 4 }}>
          Stack
        </span>
        {STACK.map(t => (
          <span key={t} style={{
            fontSize: 12, padding: "3px 10px", borderRadius: 6,
            background: "var(--surface2)", border: "1px solid var(--border2)",
            color: "var(--muted)", fontFamily: "monospace",
          }}>
            {t}
          </span>
        ))}
        <span style={{ marginLeft: "auto", fontSize: 11.5, color: "var(--subtle)" }}>
          <a href="https://github.com/vamsi513/evalforge" target="_blank" rel="noopener noreferrer"
            style={{ color: "var(--accent)", fontWeight: 500 }}>
            View source →
          </a>
        </span>
      </div>

    </div>
  );
}
