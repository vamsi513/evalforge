import { api } from "@/lib/api";
import { Shield, CheckCircle, XCircle, Lock, GitMerge, AlertTriangle } from "lucide-react";
import SeedButton from "@/components/SeedButton";

export const dynamic = "force-dynamic";

const HOW_IT_WORKS = [
  {
    icon: GitMerge,
    title: "Define a gate",
    desc: "Attach a minimum quality threshold (e.g. 75%) to an experiment and dataset.",
  },
  {
    icon: AlertTriangle,
    title: "Evaluate before deploy",
    desc: "Every eval run is scored against the gate. If average score drops below the threshold, the gate fails.",
  },
  {
    icon: Lock,
    title: "Block bad releases",
    desc: "CI/CD pipelines call the gate API to get a PASS/FAIL signal before promoting the model to production.",
  },
];

export default async function GatesPage() {
  const gates = await api.releaseGates().catch(() => []);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Release Gates</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Automated quality gates that block regressions from reaching production
        </p>
      </div>

      {gates.length === 0 ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {/* Explainer */}
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "28px 32px",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 20 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: "var(--accent-dim)", display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Shield size={18} style={{ color: "var(--accent)" }} />
              </div>
              <div>
                <div style={{ fontWeight: 700, fontSize: 14 }}>How release gates work</div>
                <div style={{ fontSize: 12, color: "var(--muted)" }}>
                  No gates configured yet — here&apos;s what they do
                </div>
              </div>
            </div>

            <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 16 }}>
              {HOW_IT_WORKS.map(({ icon: Icon, title, desc }) => (
                <div key={title} style={{
                  background: "var(--bg)", borderRadius: 10, padding: "16px 18px",
                  border: "1px solid var(--border)",
                }}>
                  <div style={{
                    width: 30, height: 30, borderRadius: 8, background: "var(--accent-dim)",
                    display: "flex", alignItems: "center", justifyContent: "center", marginBottom: 10,
                  }}>
                    <Icon size={14} style={{ color: "var(--accent)" }} />
                  </div>
                  <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 4 }}>{title}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)", lineHeight: 1.5 }}>{desc}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Seed demo */}
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "18px 24px",
            display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
          }}>
            <div>
              <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 3 }}>See a live gate decision</div>
              <div style={{ fontSize: 12, color: "var(--muted)" }}>
                Seeds 3 demo experiments and creates release gates — takes ~3 seconds
              </div>
            </div>
            <SeedButton />
          </div>

          {/* API example */}
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 12, padding: "20px 24px",
          }}>
            <div style={{ fontWeight: 600, fontSize: 13, marginBottom: 12 }}>Create a gate via the API</div>
            <pre style={{
              background: "var(--bg)", borderRadius: 8, padding: "14px 16px",
              fontSize: 12, fontFamily: "monospace", color: "var(--muted)",
              border: "1px solid var(--border)", overflowX: "auto",
              lineHeight: 1.7,
            }}>{`POST /api/v1/release-gates
{
  "experiment_name": "gpt4o-chat-v3",
  "dataset_name":    "production-qa",
  "min_score":       0.75,
  "evaluator_profile": "strict"
}`}</pre>
          </div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {gates.map((g: Record<string, unknown>, i: number) => {
            const passed = g.status === "passed";
            const metrics = (g.metrics ?? {}) as Record<string, unknown>;
            const candidateScore = typeof metrics.candidate_score === "number" ? metrics.candidate_score : null;
            const scoreDelta = typeof metrics.score_delta === "number" ? metrics.score_delta : null;
            return (
              <div key={i} style={{
                background: "var(--surface)", border: `1px solid ${passed ? "rgba(34,197,94,0.2)" : "rgba(239,68,68,0.15)"}`,
                borderRadius: 12, padding: "16px 20px",
                display: "flex", alignItems: "center", gap: 16,
              }}>
                {passed
                  ? <CheckCircle size={20} style={{ color: "var(--green)", flexShrink: 0 }} />
                  : <XCircle size={20} style={{ color: "var(--red)", flexShrink: 0 }} />}
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 600, fontSize: 13.5 }}>{String(g.experiment_name || "—")}</div>
                  <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                    {String(g.dataset_name || "—")}
                    {scoreDelta !== null && (
                      <span style={{ marginLeft: 8, color: scoreDelta >= 0 ? "var(--green)" : "var(--red)" }}>
                        Δ {scoreDelta >= 0 ? "+" : ""}{(scoreDelta * 100).toFixed(1)}%
                      </span>
                    )}
                  </div>
                  {typeof g.summary === "string" && g.summary && (
                    <div style={{ fontSize: 11.5, color: "var(--subtle)", marginTop: 4, lineHeight: 1.4 }}>
                      {passed ? "No threshold regressions detected — candidate meets all quality criteria." : g.summary}
                    </div>
                  )}
                </div>
                {candidateScore !== null && (
                  <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: passed ? "var(--green)" : "var(--red)", flexShrink: 0 }}>
                    {Math.round(candidateScore * 100)}%
                  </span>
                )}
                <span style={{
                  fontSize: 11.5, fontWeight: 700, padding: "3px 10px", borderRadius: 6, flexShrink: 0,
                  background: passed ? "rgba(34,197,94,0.12)" : "rgba(239,68,68,0.12)",
                  color: passed ? "var(--green)" : "var(--red)",
                  letterSpacing: "0.04em",
                }}>
                  {passed ? "PASSED" : "FAILED"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
