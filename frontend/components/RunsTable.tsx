import { EvalRun } from "@/lib/api";

interface Props { runs: EvalRun[]; compact?: boolean }

function ScoreBadge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "var(--green)" : score >= 0.65 ? "var(--yellow)" : "var(--red)";
  const dimColor = score >= 0.8 ? "var(--green-dim)" : score >= 0.65 ? "var(--yellow-dim)" : "var(--red-dim)";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <div className="score-bar-track" style={{ width: 48 }}>
        <div
          className="score-bar-fill"
          style={{ width: `${pct}%`, background: color }}
        />
      </div>
      <span className="mono" style={{
        fontSize: 12, fontWeight: 600, color,
        background: dimColor, padding: "2px 7px", borderRadius: 5,
      }}>
        {pct}%
      </span>
    </div>
  );
}

export default function RunsTable({ runs, compact }: Props) {
  if (!runs.length) {
    return (
      <p style={{ fontSize: 13, color: "var(--muted)", textAlign: "center", padding: "28px 0" }}>
        No eval runs yet.
      </p>
    );
  }

  const headers = ["Dataset", "Model", "Score", ...(compact ? [] : ["Cases", "Cost", "Date"])];

  return (
    <div style={{ overflowX: "auto" }}>
      <table className="data-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr>
            {headers.map(h => (
              <th key={h} style={{
                textAlign: "left", padding: "7px 12px",
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
          {runs.map((r) => (
            <tr key={r.id}>
              <td style={{ padding: "11px 12px", fontWeight: 500, borderBottom: "1px solid var(--border)" }}>
                {r.dataset_name}
              </td>
              <td style={{ padding: "11px 12px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                <span className="mono" style={{ fontSize: 12 }}>{r.model_name}</span>
              </td>
              <td style={{ padding: "11px 12px", borderBottom: "1px solid var(--border)" }}>
                <ScoreBadge score={r.average_score} />
              </td>
              {!compact && <>
                <td style={{ padding: "11px 12px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                  {r.results?.length ?? 0}
                </td>
                <td style={{ padding: "11px 12px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                  <span className="mono">${(r.results?.reduce((s, x) => s + (x.cost_usd ?? 0), 0) ?? 0).toFixed(4)}</span>
                </td>
                <td style={{ padding: "11px 12px", color: "var(--muted)", borderBottom: "1px solid var(--border)" }}>
                  {new Date(r.created_at).toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                </td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
