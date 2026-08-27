import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "EvalForge — LLM Evaluation Platform";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OGImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          background: "#0a0a0f",
          padding: "72px 80px",
          justifyContent: "space-between",
        }}
      >
        {/* Top: logo + wordmark */}
        <div style={{ display: "flex", alignItems: "center", gap: 20 }}>
          <div
            style={{
              width: 56, height: 56, borderRadius: 14,
              background: "linear-gradient(135deg, #6366f1, #8b5cf6)",
              display: "flex", alignItems: "center", justifyContent: "center",
              boxShadow: "0 0 32px rgba(99,102,241,0.6)",
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
            </svg>
          </div>
          <div style={{ display: "flex", flexDirection: "column" }}>
            <span style={{ fontSize: 32, fontWeight: 800, color: "#f0f0f8", letterSpacing: "-1px" }}>
              EvalForge
            </span>
            <span style={{ fontSize: 16, color: "#52526e", letterSpacing: "0.04em" }}>
              LLM Evaluation Platform
            </span>
          </div>
        </div>

        {/* Center: headline */}
        <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          <div style={{ fontSize: 64, fontWeight: 800, color: "#f0f0f8", letterSpacing: "-2px", lineHeight: 1.1 }}>
            Deterministic{" "}
            <span style={{ color: "#6366f1" }}>LLM evaluation</span>
            {" "}at scale
          </div>
          <div style={{ fontSize: 24, color: "#8b8ba7", maxWidth: 720, lineHeight: 1.5 }}>
            Multi-signal evaluators · Experiment tracking · Release gates · OpenAI, Anthropic & Mistral judge adapters
          </div>
        </div>

        {/* Bottom: stats row */}
        <div style={{ display: "flex", gap: 32 }}>
          {[
            { label: "Evaluators", value: "5" },
            { label: "Judge adapters", value: "3" },
            { label: "Stack", value: "FastAPI + Next.js" },
            { label: "CI gate", value: "PASS / FAIL" },
          ].map(({ label, value }) => (
            <div
              key={label}
              style={{
                display: "flex", flexDirection: "column", gap: 4,
                padding: "14px 22px", borderRadius: 12,
                background: "rgba(99,102,241,0.08)",
                border: "1px solid rgba(99,102,241,0.2)",
              }}
            >
              <span style={{ fontSize: 28, fontWeight: 700, color: "#f0f0f8", letterSpacing: "-0.5px" }}>{value}</span>
              <span style={{ fontSize: 14, color: "#8b8ba7" }}>{label}</span>
            </div>
          ))}
        </div>
      </div>
    ),
    { ...size }
  );
}
