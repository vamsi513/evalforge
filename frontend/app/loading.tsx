export default function Loading() {
  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 180, height: 28, borderRadius: 6, background: "var(--surface2)", marginBottom: 8 }} className="skeleton" />
        <div style={{ width: 340, height: 14, borderRadius: 4, background: "var(--surface2)" }} className="skeleton" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5,1fr)", gap: 14, marginBottom: 28 }}>
        {Array.from({ length: 5 }).map((_, i) => (
          <div key={i} style={{ height: 90, borderRadius: 12, background: "var(--surface)", border: "1px solid var(--border)" }} className="skeleton" />
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1.35fr 1fr", gap: 14 }}>
        <div style={{ height: 220, borderRadius: 14, background: "var(--surface)", border: "1px solid var(--border)" }} className="skeleton" />
        <div style={{ height: 220, borderRadius: 14, background: "var(--surface)", border: "1px solid var(--border)" }} className="skeleton" />
      </div>
      <style>{`
        .skeleton { animation: shimmer 1.4s ease-in-out infinite; }
        @keyframes shimmer {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  );
}
