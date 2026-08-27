import { api, EvalRun } from "@/lib/api";

export const dynamic = "force-dynamic";

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "var(--green)" : score >= 0.65 ? "var(--yellow)" : "var(--red)";
  return (
    <span style={{
      fontSize: 12, fontWeight: 700, color,
      background: `${color}18`, padding: "3px 9px", borderRadius: 6,
      fontVariantNumeric: "tabular-nums",
    }}>
      {pct}%
    </span>
  );
}

function PassRate({ results }: { results: EvalRun["results"] }) {
  if (!results?.length) return <span style={{ color: "var(--muted)", fontSize: 12 }}>—</span>;
  const passed = results.filter(r => r.passed).length;
  const rate = passed / results.length;
  const color = rate >= 0.8 ? "var(--green)" : rate >= 0.65 ? "var(--yellow)" : "var(--red)";
  return (
    <span style={{ fontSize: 12, color }}>
      {passed}/{results.length}
    </span>
  );
}

export default async function RunsPage() {
  const runs = await api.runs().catch(() => []);

  const totalCases = runs.reduce((s, r) => s + (r.results?.length ?? 0), 0);
  const totalPassed = runs.reduce((s, r) => s + (r.results?.filter(x => x.passed).length ?? 0), 0);

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Eval Runs</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Every batch of AI outputs scored against your test datasets
        </p>
      </div>

      {/* Summary strip */}
      {runs.length > 0 && (
        <div style={{
          display: "flex", gap: 24, marginBottom: 20, padding: "14px 20px",
          background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 10,
          fontSize: 13,
        }}>
          <span><b style={{ color: "var(--text)" }}>{runs.length}</b> <span style={{ color: "var(--muted)" }}>runs</span></span>
          <span><b style={{ color: "var(--text)" }}>{totalCases}</b> <span style={{ color: "var(--muted)" }}>test cases</span></span>
          <span>
            <b style={{ color: totalPassed / (totalCases || 1) >= 0.65 ? "var(--green)" : "var(--red)" }}>
              {totalCases > 0 ? Math.round(totalPassed / totalCases * 100) : 0}%
            </b>{" "}
            <span style={{ color: "var(--muted)" }}>pass rate</span>
          </span>
        </div>
      )}

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        {runs.length === 0 ? (
          <div style={{ padding: 48, textAlign: "center", color: "var(--muted)", fontSize: 14 }}>
            No eval runs yet. Click <b style={{ color: "var(--text)" }}>Run Demo Eval</b> on the Overview page to create the first one.
          </div>
        ) : (
          <div style={{ overflowX: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
              <thead>
                <tr style={{ background: "var(--bg)" }}>
                  {["Dataset", "Model", "Prompt Version", "Score", "Pass Rate", "Latency", "Date"].map(h => (
                    <th key={h} style={{
                      textAlign: "left", padding: "10px 16px",
                      fontSize: 11, fontWeight: 600, color: "var(--muted)",
                      letterSpacing: "0.05em", borderBottom: "1px solid var(--border)",
                    }}>
                      {h.toUpperCase()}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {runs.map((r) => {
                  const avgLatency = r.results?.length
                    ? Math.round(r.results.reduce((s, x) => s + (x.latency_ms ?? 0), 0) / r.results.length)
                    : 0;
                  return (
                    <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                      <td style={{ padding: "12px 16px", fontWeight: 500 }}>{r.dataset_name}</td>
                      <td style={{ padding: "12px 16px", color: "var(--muted)" }}>{r.model_name}</td>
                      <td style={{ padding: "12px 16px", color: "var(--muted)", fontFamily: "monospace", fontSize: 11.5 }}>
                        {r.prompt_version || "—"}
                      </td>
                      <td style={{ padding: "12px 16px" }}><ScoreBadge score={r.average_score} /></td>
                      <td style={{ padding: "12px 16px" }}><PassRate results={r.results} /></td>
                      <td style={{ padding: "12px 16px", color: "var(--muted)" }}>{avgLatency} ms</td>
                      <td style={{ padding: "12px 16px", color: "var(--muted)" }}>
                        {new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" })}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
