"use client";
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import { EvalRun } from "@/lib/api";

interface Props { runs: EvalRun[] }

export default function ScoreChart({ runs }: Props) {
  const data = [...runs].reverse().slice(-20).map((r, i) => ({
    name: `Run ${i + 1}`,
    score: Math.round((r.average_score ?? 0) * 100),
  }));

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
      <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 4 }}>Quality Score Trend</h2>
      <p style={{ fontSize: 12, color: "var(--muted)", marginBottom: 20 }}>Last {data.length} eval runs</p>
      {data.length === 0 ? (
        <div style={{ height: 180, display: "flex", alignItems: "center", justifyContent: "center", color: "var(--muted)", fontSize: 13 }}>
          No runs yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#27272a" vertical={false} />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} />
            <YAxis domain={[0, 100]} tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} tickFormatter={v => `${v}%`} />
            <Tooltip
              contentStyle={{ background: "#18181b", border: "1px solid #27272a", borderRadius: 8, fontSize: 12 }}
              labelStyle={{ color: "#a1a1aa" }}
              formatter={(v) => [`${v}%`, "Score"]}
            />
            <Area type="monotone" dataKey="score" stroke="#6366f1" strokeWidth={2} fill="url(#scoreGrad)" dot={false} activeDot={{ r: 4, fill: "#6366f1" }} />
          </AreaChart>
        </ResponsiveContainer>
      )}
    </div>
  );
}
