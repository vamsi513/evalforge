export default function Loading() {
  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 160, height: 28, borderRadius: 6, background: "var(--surface2)", marginBottom: 8 }} className="sk" />
        <div style={{ width: 380, height: 14, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
      </div>
      <div style={{ height: 80, borderRadius: 14, background: "var(--surface)", border: "1px solid rgba(99,102,241,0.2)", marginBottom: 14 }} className="sk" />
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 14, overflow: "hidden" }}>
        <div style={{ height: 44, background: "var(--bg)", borderBottom: "1px solid var(--border)" }} />
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} style={{ height: 52, borderBottom: "1px solid var(--border)", padding: "0 16px", display: "flex", alignItems: "center", gap: 16 }}>
            {[40, 160, 140, 60, 60, 40, 60].map((w, j) => (
              <div key={j} style={{ width: w, height: 12, borderRadius: 4, background: "var(--surface2)", flexShrink: 0 }} className="sk" />
            ))}
          </div>
        ))}
      </div>
      <style>{`.sk{animation:sk 1.4s ease-in-out infinite}@keyframes sk{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </div>
  );
}
