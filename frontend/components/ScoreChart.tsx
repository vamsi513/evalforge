"use client";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  CartesianGrid, ReferenceLine,
} from "recharts";
import { EvalRun } from "@/lib/api";

interface Props { runs: EvalRun[] }

export default function ScoreChart({ runs }: Props) {
  const data = [...runs].reverse().slice(-20).map((r, i) => ({
    name: `Run ${i + 1}`,
    score: Math.round((r.average_score ?? 0) * 100),
    dataset: r.dataset_name,
  }));

  const avg = data.length
    ? Math.round(data.reduce((s, d) => s + d.score, 0) / data.length)
    : 0;
  const latest = data.at(-1)?.score ?? 0;

  return (
    <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, padding: 20 }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 20 }}>
        <div>
          <h2 style={{ fontSize: 14, fontWeight: 600, marginBottom: 3 }}>Quality Score Trend</h2>
          <p style={{ fontSize: 12, color: "var(--muted)" }}>Last {data.length} eval runs</p>
        </div>
        {data.length > 0 && (
          <div style={{ textAlign: "right" }}>
            <div style={{
              fontSize: 22, fontWeight: 700, letterSpacing: "-0.5px",
              color: latest >= 80 ? "var(--green)" : latest >= 65 ? "var(--yellow)" : "var(--red)",
            }}>
              {latest}%
            </div>
            <div style={{ fontSize: 11, color: "var(--muted)" }}>latest · {avg}% avg</div>
          </div>
        )}
      </div>

      {data.length === 0 ? (
        <div style={{
          height: 180, display: "flex", alignItems: "center", justifyContent: "center",
          color: "var(--muted)", fontSize: 13,
        }}>
          No runs yet
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={data} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id="scoreGrad" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#6366f1" stopOpacity={0.25} />
                <stop offset="95%" stopColor="#6366f1" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" vertical={false} />
            <ReferenceLine
              y={65} stroke="#eab308" strokeDasharray="4 3" strokeWidth={1.5}
              label={{ value: "Pass threshold", fill: "#eab308", fontSize: 10, position: "insideTopRight" }}
            />
            <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#71717a" }} axisLine={false} tickLine={false} />
            <YAxis
              domain={[0, 100]} tick={{ fontSize: 11, fill: "#71717a" }}
              axisLine={false} tickLine={false} tickFormatter={v => `${v}%`}
            />
            <Tooltip
              contentStyle={{
                background: "#18181b", border: "1px solid #27272a",
                borderRadius: 8, fontSize: 12,
              }}
              labelStyle={{ color: "#a1a1aa", marginBottom: 4 }}
              formatter={(v, _name, props) => [
                `${v}%`,
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
      )}
    </div>
  );
}
