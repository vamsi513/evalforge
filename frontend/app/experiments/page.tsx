import { api } from "@/lib/api";
import { GitCompare } from "lucide-react";

export const dynamic = "force-dynamic";

export default async function ExperimentsPage() {
  const leaderboard = await api.leaderboard().catch(() => ({ items: [] }));
  const items = leaderboard.items ?? [];

  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.5px" }}>Experiments</h1>
        <p style={{ fontSize: 13.5, color: "var(--muted)", marginTop: 4 }}>
          Compare prompt versions and model configurations side by side
        </p>
      </div>

      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 24 }}>
        {items.length === 0 ? (
          <div style={{ textAlign: "center", padding: "32px 0" }}>
            <GitCompare size={32} style={{ color: "var(--muted)", margin: "0 auto 12px" }} />
            <p style={{ color: "var(--muted)", fontSize: 14 }}>No experiments yet.</p>
          </div>
        ) : (
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--border)" }}>
                {["Rank", "Experiment", "Model", "Score", "Runs", "Avg Latency"].map(h => (
                  <th key={h} style={{ textAlign: "left", padding: "6px 10px", fontSize: 11.5, fontWeight: 600, color: "var(--muted)", letterSpacing: "0.04em" }}>
                    {h.toUpperCase()}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((item, i) => {
                const score = item.average_score ?? 0;
                const color = score >= 0.8 ? "var(--green)" : score >= 0.5 ? "var(--yellow)" : "var(--red)";
                return (
                  <tr key={item.experiment_name} style={{ borderBottom: "1px solid var(--border)" }}>
                    <td style={{ padding: "10px", color: "var(--muted)", fontWeight: 600 }}>#{i + 1}</td>
                    <td style={{ padding: "10px", fontWeight: 500 }}>{item.experiment_name || "—"}</td>
                    <td style={{ padding: "10px", color: "var(--muted)" }}>{item.model_name || "—"}</td>
                    <td style={{ padding: "10px" }}>
                      <span style={{ fontSize: 12, fontWeight: 600, color, background: `${color}18`, padding: "2px 8px", borderRadius: 6 }}>
                        {Math.round(score * 100)}%
                      </span>
                    </td>
                    <td style={{ padding: "10px", color: "var(--muted)" }}>{item.run_count}</td>
                    <td style={{ padding: "10px", color: "var(--muted)" }}>{Math.round(item.average_latency_ms ?? 0)} ms</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
