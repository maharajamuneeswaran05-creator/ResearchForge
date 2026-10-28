"use client";

export function CodeBlock({ code, label }: { code: string; label?: string }) {
  return (
    <div className="stack tight">
      {label ? (
        <span className="field-label" style={{ marginBottom: 0 }}>
          {label}
        </span>
      ) : null}
      <pre className="code-block">{code}</pre>
    </div>
  );
}

export function LogBlock({ text, tone }: { text: string; tone?: "stderr" }) {
  if (!text) return null;
  return (
    <pre className={`log-block${tone === "stderr" ? " stderr" : ""}`}>{text}</pre>
  );
}
