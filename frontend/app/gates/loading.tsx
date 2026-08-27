export default function Loading() {
  return (
    <div style={{ padding: "32px 40px", maxWidth: 1200 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 160, height: 26, borderRadius: 6, background: "var(--surface2)", marginBottom: 8 }} className="sk" />
        <div style={{ width: 320, height: 14, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} style={{
            height: 80, borderRadius: 12,
            background: "var(--surface)", border: "1px solid var(--border)",
            padding: "16px 20px", display: "flex", alignItems: "center", gap: 16,
          }}>
            <div style={{ width: 20, height: 20, borderRadius: "50%", background: "var(--surface2)", flexShrink: 0 }} className="sk" />
            <div style={{ flex: 1 }}>
              <div style={{ width: 160, height: 14, borderRadius: 4, background: "var(--surface2)", marginBottom: 8 }} className="sk" />
              <div style={{ width: 120, height: 11, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
            </div>
            <div style={{ width: 48, height: 28, borderRadius: 6, background: "var(--surface2)", flexShrink: 0 }} className="sk" />
            <div style={{ width: 70, height: 26, borderRadius: 6, background: "var(--surface2)", flexShrink: 0 }} className="sk" />
          </div>
        ))}
      </div>
      <style>{`.sk{animation:sk 1.4s ease-in-out infinite}@keyframes sk{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </div>
  );
}
