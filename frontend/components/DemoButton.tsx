"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

interface CaseResult {
  prompt: string;
  score: number;
  passed: boolean;
  feedback: string;
  criterion_scores?: Record<string, number>;
  matched_terms?: string[];
  missing_terms?: string[];
}

interface RunResult {
  average_score: number;
  results: CaseResult[];
}

const SCENARIOS = [
  { key: "general", label: "General Knowledge", desc: "Geography, math, literature" },
  { key: "support", label: "Customer Support", desc: "Refunds, shipping, accounts" },
  { key: "code",    label: "Code & Tech",       desc: "Algorithms, JS, databases" },
];

function buildFeedback(r: CaseResult): string {
  const scores = r.criterion_scores ?? {};
  const parts: string[] = [];

  if (scores.keyword !== undefined) {
    parts.push(scores.keyword >= 0.9
      ? "Keyword matched"
      : scores.keyword >= 0.5 ? "Partial keyword match" : "Keyword missing");
  }
  if (scores.reference_overlap !== undefined) {
    parts.push(scores.reference_overlap >= 0.7
      ? "Strong reference overlap"
      : scores.reference_overlap >= 0.4 ? "Moderate overlap with reference" : "Low reference overlap");
  }
  if (scores.groundedness !== undefined) {
    parts.push(scores.groundedness >= 0.8
      ? "Well-grounded in source"
      : scores.groundedness >= 0.5 ? "Mostly grounded" : "Some unsupported claims");
  }
  if (r.missing_terms?.length) {
    parts.push(`Missing: ${r.missing_terms.slice(0, 2).join(", ")}`);
  }

  return parts.length > 0 ? parts.join(" · ") : r.feedback;
}

export default function DemoButton() {
  const [activeScenario, setActiveScenario] = useState("general");
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<RunResult | null>(null);
  const [errorMsg, setErrorMsg] = useState<string>("");
  const router = useRouter();

  async function runDemo() {
    setState("running");
    setResult(null);
    setErrorMsg("");
    try {
      const res = await fetch("/api/demo", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: activeScenario }),
      });
      const data = await res.json();
      if (!res.ok) {
        const msg = (data as { error?: string; detail?: string }).error
          ?? (data as { detail?: string }).detail
          ?? `HTTP ${res.status}`;
        setErrorMsg(msg);
        setState("error");
        return;
      }
      setResult(data as RunResult);
      setState("done");
      router.refresh();
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Network error");
      setState("error");
    }
  }

  const scenarioLabel = SCENARIOS.find(s => s.key === activeScenario)?.label ?? "Demo";

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{
        background: "var(--surface)", border: "1px solid var(--border)",
        borderRadius: 12, overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{
          padding: "16px 20px", borderBottom: "1px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          flexWrap: "wrap", gap: 12,
        }}>
          <div>
            <div style={{ fontSize: 13.5, fontWeight: 700, marginBottom: 2 }}>Try a live eval run</div>
            <div style={{ fontSize: 12, color: "var(--muted)" }}>
              Scores 3 curated sample answers with 5 deterministic heuristic evaluators — no setup needed
            </div>
          </div>
          <button
            onClick={runDemo}
            disabled={state === "running"}
            style={{
              display: "inline-flex", alignItems: "center", gap: 8,
              padding: "9px 20px", borderRadius: 8,
              background: state === "running" ? "var(--surface2)" : "var(--accent)",
              color: "#fff", border: "none", cursor: state === "running" ? "not-allowed" : "pointer",
              fontSize: 13, fontWeight: 600, fontFamily: "inherit",
              opacity: state === "running" ? 0.7 : 1,
              transition: "opacity 0.15s",
            }}
          >
            {state === "running" ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                  style={{ animation: "spin 1s linear infinite" }}>
                  <path d="M21 12a9 9 0 1 1-6.219-8.56" />
                </svg>
                Scoring…
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polygon points="5 3 19 12 5 21 5 3" />
                </svg>
                Run {scenarioLabel}
              </>
            )}
          </button>
        </div>

        {/* Scenario tabs */}
        <div style={{ display: "flex", background: "var(--bg)", borderBottom: "1px solid var(--border)" }}>
          {SCENARIOS.map(s => {
            const active = s.key === activeScenario;
            return (
              <button
                key={s.key}
                onClick={() => { setActiveScenario(s.key); setState("idle"); setResult(null); }}
                disabled={state === "running"}
                style={{
                  flex: 1, padding: "10px 12px", border: "none", cursor: "pointer",
                  background: active ? "var(--surface)" : "transparent",
                  borderBottom: active ? "2px solid var(--accent)" : "2px solid transparent",
                  fontFamily: "inherit", textAlign: "left", transition: "all 0.15s",
                }}
              >
                <div style={{ fontSize: 12.5, fontWeight: active ? 600 : 400, color: active ? "var(--text)" : "var(--muted)" }}>
                  {s.label}
                </div>
                <div style={{ fontSize: 11, color: "var(--subtle)", marginTop: 1 }}>{s.desc}</div>
              </button>
            );
          })}
        </div>

        {/* Results */}
        {state === "done" && result && (
          <>
            <div style={{
              padding: "11px 20px", borderBottom: "1px solid var(--border)",
              display: "flex", alignItems: "center", justifyContent: "space-between",
              background: "rgba(99,102,241,0.04)",
            }}>
              <span style={{ fontSize: 12, fontWeight: 600, color: "var(--muted)" }}>
                {scenarioLabel} · 3 cases scored
              </span>
              <span className="mono" style={{
                fontSize: 13.5, fontWeight: 700,
                color: result.average_score >= 0.8 ? "var(--green)"
                  : result.average_score >= 0.65 ? "var(--yellow)" : "var(--red)",
              }}>
                {Math.round(result.average_score * 100)}% avg
              </span>
            </div>
            {result.results?.map((r, i) => (
              <div key={i} style={{
                padding: "12px 20px",
                borderBottom: i < result.results.length - 1 ? "1px solid var(--border)" : "none",
                display: "flex", alignItems: "flex-start", gap: 12,
              }}>
                <span style={{
                  width: 20, height: 20, borderRadius: "50%", flexShrink: 0, marginTop: 1,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  background: r.passed ? "var(--green-dim)" : "var(--red-dim)",
                  color: r.passed ? "var(--green)" : "var(--red)", fontSize: 11, fontWeight: 700,
                }}>
                  {r.passed ? "✓" : "✗"}
                </span>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 12.5, fontWeight: 500, marginBottom: 3 }}>{r.prompt}</div>
                  <div style={{ fontSize: 11, color: "var(--subtle)" }}>{buildFeedback(r)}</div>
                </div>
                <span className="mono" style={{
                  fontSize: 12, fontWeight: 700, flexShrink: 0,
                  color: r.score >= 0.8 ? "var(--green)" : r.score >= 0.65 ? "var(--yellow)" : "var(--red)",
                }}>
                  {Math.round(r.score * 100)}%
                </span>
              </div>
            ))}
          </>
        )}

        {state === "error" && (
          <div style={{
            padding: "12px 20px", fontSize: 12.5, color: "var(--red)",
            background: "rgba(239,68,68,0.06)",
          }}>
            {errorMsg ? `Error: ${errorMsg}` : "Demo run failed — check that the API server is running."}
          </div>
        )}

        {state === "idle" && (
          <div style={{ padding: "13px 20px", fontSize: 12, color: "var(--subtle)" }}>
            Pick a scenario and click <strong style={{ color: "var(--muted)" }}>Run</strong> — scored by deterministic keyword, overlap, and groundedness evaluators.
          </div>
        )}
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
