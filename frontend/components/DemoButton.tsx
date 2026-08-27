"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";

interface CaseResult {
  prompt: string;
  score: number;
  passed: boolean;
  feedback: string;
}

interface RunResult {
  average_score: number;
  results: CaseResult[];
}

export default function DemoButton() {
  const [state, setState] = useState<"idle" | "running" | "done" | "error">("idle");
  const [result, setResult] = useState<RunResult | null>(null);
  const router = useRouter();

  async function runDemo() {
    setState("running");
    setResult(null);
    try {
      const res = await fetch("/api/demo", { method: "POST" });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error ?? "Failed");
      setResult(data as RunResult);
      setState("done");
      router.refresh(); // re-run server components so metrics update
    } catch {
      setState("error");
    }
  }

  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{
        background: "var(--surface)",
        border: "1px solid var(--border)",
        borderRadius: 12,
        padding: "20px 24px",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexWrap: "wrap",
        gap: 16,
      }}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 3 }}>Try a live eval run</div>
          <div style={{ fontSize: 12.5, color: "var(--muted)" }}>
            Scores 3 real AI answers instantly — no setup needed
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
            transition: "opacity 0.15s",
          }}
        >
          {state === "running" ? (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"
                style={{ animation: "spin 1s linear infinite" }}>
                <path d="M21 12a9 9 0 1 1-6.219-8.56"/>
              </svg>
              Running…
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <polygon points="5 3 19 12 5 21 5 3"/>
              </svg>
              Run Demo Eval
            </>
          )}
        </button>
      </div>

      {state === "done" && result && (
        <div style={{
          marginTop: 10, background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 12, overflow: "hidden",
        }}>
          <div style={{
            padding: "14px 20px", borderBottom: "1px solid var(--border)",
            display: "flex", alignItems: "center", justifyContent: "space-between",
          }}>
            <span style={{ fontSize: 13, fontWeight: 600 }}>Demo run complete</span>
            <span style={{
              fontFamily: "var(--mono)", fontSize: 13, fontWeight: 700,
              color: result.average_score >= 0.8 ? "var(--green)" : result.average_score >= 0.5 ? "var(--yellow)" : "var(--red)",
            }}>
              {Math.round(result.average_score * 100)}% avg score
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
                background: r.passed ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                color: r.passed ? "var(--green)" : "var(--red)", fontSize: 11, fontWeight: 700,
              }}>
                {r.passed ? "✓" : "✗"}
              </span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 12.5, fontWeight: 500, marginBottom: 2 }}>{r.prompt}</div>
                <div style={{ fontSize: 11.5, color: "var(--muted)" }}>{r.feedback}</div>
              </div>
              <span style={{
                fontFamily: "var(--mono)", fontSize: 12, fontWeight: 700, flexShrink: 0,
                color: r.score >= 0.8 ? "var(--green)" : r.score >= 0.5 ? "var(--yellow)" : "var(--red)",
              }}>
                {Math.round(r.score * 100)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {state === "error" && (
        <div style={{
          marginTop: 10, padding: "12px 16px", borderRadius: 8,
          background: "rgba(239,68,68,0.08)", border: "1px solid rgba(239,68,68,0.2)",
          fontSize: 12.5, color: "var(--red)",
        }}>
          Demo run failed — check that the API server is running.
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}
