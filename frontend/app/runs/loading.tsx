export default function Loading() {
  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 140, height: 26, borderRadius: 6, background: "var(--surface2)", marginBottom: 8 }} className="sk" />
        <div style={{ width: 300, height: 14, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
      </div>
      <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 12, overflow: "hidden" }}>
        <div style={{ height: 44, background: "var(--bg)", borderBottom: "1px solid var(--border)" }} />
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} style={{ height: 52, borderBottom: "1px solid var(--border)", padding: "0 16px", display: "flex", alignItems: "center", gap: 16 }}>
            {[160, 100, 90, 60, 50, 70, 80].map((w, j) => (
              <div key={j} style={{ width: w, height: 12, borderRadius: 4, background: "var(--surface2)", flexShrink: 0 }} className="sk" />
            ))}
          </div>
        ))}
      </div>
      <style>{`.sk{animation:sk 1.4s ease-in-out infinite}@keyframes sk{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </div>
  );
}
