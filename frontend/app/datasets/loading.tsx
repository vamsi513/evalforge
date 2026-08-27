export default function Loading() {
  return (
    <div style={{ padding: "36px 44px", maxWidth: 1220 }}>
      <div style={{ marginBottom: 28 }}>
        <div style={{ width: 130, height: 28, borderRadius: 6, background: "var(--surface2)", marginBottom: 8 }} className="sk" />
        <div style={{ width: 300, height: 14, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 14 }}>
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} style={{ height: 130, borderRadius: 14, background: "var(--surface)", border: "1px solid var(--border)", padding: 20 }}>
            <div style={{ display: "flex", gap: 12, marginBottom: 16 }}>
              <div style={{ width: 36, height: 36, borderRadius: 9, background: "var(--surface2)" }} className="sk" />
              <div style={{ flex: 1 }}>
                <div style={{ width: "80%", height: 14, borderRadius: 4, background: "var(--surface2)", marginBottom: 6 }} className="sk" />
                <div style={{ width: "50%", height: 11, borderRadius: 4, background: "var(--surface2)" }} className="sk" />
              </div>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              <div style={{ flex: 1, height: 36, borderRadius: 8, background: "var(--surface2)" }} className="sk" />
              <div style={{ flex: 1, height: 36, borderRadius: 8, background: "var(--surface2)" }} className="sk" />
            </div>
          </div>
        ))}
      </div>
      <style>{`.sk{animation:sk 1.4s ease-in-out infinite}@keyframes sk{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </div>
  );
}
