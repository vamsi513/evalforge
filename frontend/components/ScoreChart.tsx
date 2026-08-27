"use client";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";
import { EvalRun } from "@/lib/api";

interface Props { runs: EvalRun[] }

export default function ScoreChart({ runs }: Props) {
  const data = [...runs].reverse().slice(-20).map((r, i) => ({
    name: `#${i + 1}`,
    score: Math.round((r.average_score ?? 0) * 100),
    dataset: r.dataset_name,
    model: r.model_name,
  }));

  const avg = data.length
    ? Math.round(data.reduce((s, d) => s + d.score, 0) / data.length)
    : 0;
  const latest = data.at(-1)?.score ?? 0;
  const latestColor = latest >= 80 ? "#22c55e" : latest >= 65 ? "#f59e0b" : "#ef4444";

  return (
    <div style={{
      background: "var(--surface)", border: "1px solid var(--border)",
      borderRadius: 14, padding: "20px 22px", overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 22 }}>
        <div>
          <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 3 }}>Quality Score Trend</div>
          <div style={{ fontSize: 11.5, color: "var(--muted)" }}>Last {data.length} eval runs</div>
        </div>
        {data.length > 0 && (
          <div style={{ textAlign: "right" }}>
            <div className="mono" style={{
              fontSize: 26, fontWeight: 700, letterSpacing: "-1px",
              color: latestColor, lineHeight: 1,
            }}>
              {latest}%
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 3 }}>
              latest &nbsp;·&nbsp; {avg}% avg
            </div>
          </div>
        )}
      </div>

      {data.length === 0 ? (
        <div style={{
          height: 190, display: "flex", alignItems: "center", justifyContent: "center",
          color: "var(--muted)", fontSize: 13, flexDirection: "column", gap: 8,
        }}>
          <div style={{ fontSize: 28, opacity: 0.3 }}>📈</div>
          <span>Run an eval to see your trend</span>
        </div>
      ) : (
        <>
        {/* Visually hidden data table for screen readers */}
        <table style={{ position: "absolute", width: 1, height: 1, overflow: "hidden", clip: "rect(0,0,0,0)", whiteSpace: "nowrap" }}
          aria-label="Quality score trend data">
          <thead><tr><th>Run</th><th>Dataset</th><th>Score</th></tr></thead>
          <tbody>
            {data.map(d => (
              <tr key={d.name}><td>{d.name}</td><td>{d.dataset}</td><td>{d.score}%</td></tr>
            ))}
          </tbody>
        </table>
        <ResponsiveContainer width="100%" height={190}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: -16, bottom: 0 }}>
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%"  stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="2 4" stroke="#1e1e2e" vertical={false} />
            <ReferenceLine
              y={65} stroke="#f59e0b" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: "65% threshold", fill: "#f59e0b", fontSize: 9.5, position: "insideTopRight", dx: -4, dy: 4 }}
            />
            <XAxis
              dataKey="name"
              tick={{ fontSize: 10.5, fill: "#52526e" }}
              axisLine={false} tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fontSize: 10.5, fill: "#52526e" }}
              axisLine={false} tickLine={false}
              tickFormatter={v => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                background: "#16161f", border: "1px solid #2a2a3e",
                borderRadius: 8, fontSize: 12, boxShadow: "0 8px 24px rgba(0,0,0,0.5)",
              }}
              labelStyle={{ color: "#8b8ba7", marginBottom: 4, fontSize: 11 }}
              formatter={(v, _name, props) => [
                <span key="v" className="mono" style={{ fontWeight: 600 }}>{v}%</span>,
                props.payload?.dataset ?? "Score",
              ]}
            />
            <Area
              type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2}
              fill="url(#scoreGrad)" dot={false}
              activeDot={{ r: 4, fill: "#6366f1", strokeWidth: 0 }}
            />
          </AreaChart>
        </ResponsiveContainer>
        </>
      )}
    </div>
  );
}
