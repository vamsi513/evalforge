import { EvalRun } from "@/lib/api";

interface Props { runs: EvalRun[]; compact?: boolean }

function Badge({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const color = score >= 0.8 ? "var(--green)" : score >= 0.5 ? "var(--yellow)" : "var(--red)";
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color, background: `${color}18`, padding: "2px 8px", borderRadius: 6 }}>
      {pct}%
    </span>
  );
}

export default function RunsTable({ runs, compact }: Props) {
  if (!runs.length) return (
    <p style={{ fontSize: 13, color: "var(--muted)", textAlign: "center", padding: "24px 0" }}>No eval runs yet.</p>
  );

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
        <thead>
          <tr style={{ borderBottom: "1px solid var(--border)" }}>
            {["Dataset", "Model", "Score", ...(compact ? [] : ["Cases", "Cost", "Date"])].map(h => (
              <th key={h} style={{ textAlign: "left", padding: "6px 8px", fontSize: 11.5, fontWeight: 600, color: "var(--muted)", letterSpacing: "0.04em" }}>
                {h.toUpperCase()}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
              <td style={{ padding: "10px 8px", color: "var(--text)", fontWeight: 500 }}>{r.dataset_name}</td>
              <td style={{ padding: "10px 8px", color: "var(--muted)" }}>{r.model_name}</td>
              <td style={{ padding: "10px 8px" }}><Badge score={r.average_score} /></td>
              {!compact && <>
                <td style={{ padding: "10px 8px", color: "var(--muted)" }}>{r.results?.length ?? 0}</td>
                <td style={{ padding: "10px 8px", color: "var(--muted)" }}>
                  ${(r.results?.reduce((s, x) => s + (x.cost_usd ?? 0), 0) ?? 0).toFixed(4)}
                </td>
                <td style={{ padding: "10px 8px", color: "var(--muted)" }}>
                  {new Date(r.created_at).toLocaleDateString()}
                </td>
              </>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
