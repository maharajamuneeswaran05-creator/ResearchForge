export function LoadingState({ label = "Working…" }: { label?: string }) {
  return (
    <div aria-busy="true" aria-live="polite">
      <div className="btn-row" style={{ marginBottom: 14 }}>
        <span className="spinner" style={{ color: "var(--accent)" }} />
        <span style={{ color: "var(--text-muted)", fontSize: 13 }}>{label}</span>
      </div>
      <div className="skeleton skeleton-line" style={{ width: "92%" }} />
      <div className="skeleton skeleton-line" style={{ width: "74%" }} />
      <div className="skeleton skeleton-line" style={{ width: "84%", marginBottom: 0 }} />
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorBox({ title = "Request failed", children }: { title?: string; children: React.ReactNode }) {
  return (
    <div className="error-box">
      <strong>{title}</strong>
      {children}
    </div>
  );
}
