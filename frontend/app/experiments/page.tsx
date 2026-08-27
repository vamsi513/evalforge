import { api } from "@/lib/api";
import { GitCompare, Trophy, ArrowUpRight, CheckCircle, XCircle } from "lucide-react";
import SeedButton from "@/components/SeedButton";

export const dynamic = "force-dynamic";

export default async function ExperimentsPage() {
  const leaderboard = await api.leaderboard().catch(() => ({ items: [] }));
  const items = leaderboard.items ?? [];

  const best = items[0];

  function scoreColor(s: number) {
    if (s >= 0.8) return "var(--green)";
    if (s >= 0.65) return "var(--yellow)";
    return "var(--red)";
  }
  function scoreDim(s: number) {
    if (s >= 0.8) return "var(--green-dim)";
    if (s >= 0.65) return "var(--yellow-dim)";
    return "var(--red-dim)";
  }

  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 28, fontWeight: 700, letterSpacing: "-0.7px", marginBottom: 5 }}>Experiments</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)" }}>
          Compare prompt versions and model configurations side by side — leaderboard ranked by average eval score
        </p>
      </div>

      {items.length === 0 ? (
        <div style={{
          background: "var(--surface)", border: "1px solid var(--border)",
          borderRadius: 14, padding: "60px 48px", textAlign: "center",
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: 12,
            background: "var(--accent-dim)", border: "1px solid rgba(99,102,241,0.2)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 16px",
          }}>
            <GitCompare size={22} style={{ color: "var(--accent)" }} />
          </div>
          <div style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>No experiments yet</div>
          <p style={{ fontSize: 13, color: "var(--muted)", maxWidth: 400, margin: "0 auto" }}>
            Run evals with an <span style={{ color: "var(--text)", fontWeight: 500 }}>experiment_name</span> field
            to track and compare different configurations here.
          </p>
          <div style={{ marginTop: 20, display: "flex", justifyContent: "center" }}>
            <SeedButton />
          </div>
          <p style={{ fontSize: 11.5, color: "var(--subtle)", marginTop: 10 }}>
            Seeds 3 heuristic demo experiments across General Knowledge, Customer Support, and Code &amp; Tech.
          </p>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          {/* Best performer highlight */}
          {best && (
            <div style={{
              background: "linear-gradient(135deg, rgba(99,102,241,0.08), rgba(139,92,246,0.04))",
              border: "1px solid rgba(99,102,241,0.25)",
              borderRadius: 14, padding: "18px 22px",
              display: "flex", alignItems: "center", gap: 16,
            }}>
              <div style={{
                width: 40, height: 40, borderRadius: 10, flexShrink: 0,
                background: "rgba(99,102,241,0.15)",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <Trophy size={18} style={{ color: "var(--accent)" }} />
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 11, color: "var(--accent)", fontWeight: 600, marginBottom: 3, letterSpacing: "0.05em" }}>
                  CURRENT LEADER
                </div>
                <div style={{ fontWeight: 700, fontSize: 14.5 }}>{best.experiment_name}</div>
                <div style={{ fontSize: 12, color: "var(--muted)", marginTop: 2 }}>
                  {best.dataset_name} · {best.run_count} run{best.run_count !== 1 ? "s" : ""}
                  {best.latest_gate_status && (
                    <span style={{
                      marginLeft: 8, fontSize: 11, fontWeight: 700,
                      color: best.latest_gate_status === "passed" ? "var(--green)" : "var(--red)",
                    }}>
                      Gate: {best.latest_gate_status.toUpperCase()}
                    </span>
                  )}
                </div>
              </div>
              <div className="mono" style={{
                fontSize: 28, fontWeight: 700, letterSpacing: "-1px",
                color: scoreColor(best.average_recent_score),
              }}>
                {Math.round(best.average_recent_score * 100)}%
              </div>
            </div>
          )}

          {/* Leaderboard table */}
          <div style={{
            background: "var(--surface)", border: "1px solid var(--border)",
            borderRadius: 14, overflow: "hidden",
          }}>
            <div style={{
              padding: "14px 20px", borderBottom: "1px solid var(--border)",
              fontSize: 12, fontWeight: 600, color: "var(--muted)",
            }}>
              Leaderboard · last 20 runs
            </div>
            <div style={{ overflowX: "auto" }}>
              <table className="data-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                <thead>
                  <tr>
                    {["Rank", "Experiment", "Dataset", "Avg Score", "Latest", "Runs", "Gate"].map(h => (
                      <th key={h} style={{
                        textAlign: "left", padding: "10px 16px",
                        fontSize: 10.5, fontWeight: 600, color: "var(--subtle)",
                        letterSpacing: "0.07em", textTransform: "uppercase",
                        borderBottom: "1px solid var(--border)",
                        background: "var(--bg)",
                      }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {items.map((item, i) => {
                    const score = item.average_recent_score ?? 0;
                    const latest = item.latest_score ?? 0;
                    const color = scoreColor(score);
                    const dim = scoreDim(score);
                    const gatePassed = item.latest_gate_status === "passed";
                    const gateFailed = item.latest_gate_status === "failed";
                    return (
                      <tr key={item.experiment_name}>
                        <td style={{ padding: "12px 16px", color: "var(--subtle)", fontWeight: 600, borderBottom: "1px solid var(--border)" }}>
                          {i === 0
                            ? <span style={{ color: "var(--accent)" }}>#{i + 1}</span>
                            : `#${i + 1}`}
                        </td>
                        <td style={{ padding: "12px 16px", fontWeight: 500, borderBottom: "1px solid var(--border)" }}>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {item.experiment_name}
                            {i === 0 && <ArrowUpRight size={13} style={{ color: "var(--accent)", opacity: 0.7 }} />}
                          </div>
                        </td>
                        <td style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                          <span className="mono" style={{ fontSize: 11.5, color: "var(--subtle)" }}>{item.dataset_name}</span>
                        </td>
                        <td style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                          <span className="mono" style={{
                            fontSize: 12.5, fontWeight: 700, color,
                            background: dim, padding: "2px 9px", borderRadius: 6,
                          }}>
                            {Math.round(score * 100)}%
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                          <span className="mono" style={{ fontSize: 12, color: scoreColor(latest) }}>
                            {Math.round(latest * 100)}%
                          </span>
                        </td>
                        <td style={{ padding: "12px 16px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                          {item.run_count}
                        </td>
                        <td style={{ padding: "12px 16px", borderBottom: "1px solid var(--border)" }}>
                          {gatePassed
                            ? <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--green)", fontSize: 11.5, fontWeight: 600 }}><CheckCircle size={12} /> PASS</span>
                            : gateFailed
                            ? <span style={{ display: "flex", alignItems: "center", gap: 4, color: "var(--red)", fontSize: 11.5, fontWeight: 600 }}><XCircle size={12} /> FAIL</span>
                            : <span style={{ color: "var(--subtle)", fontSize: 11.5 }}>—</span>}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
