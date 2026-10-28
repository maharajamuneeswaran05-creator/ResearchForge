"use client";

type Tone = "accent" | "violet" | "success" | "warning";

const TONE_CLASS: Record<Tone, string> = {
  accent: "",
  violet: "violet",
  success: "success",
  warning: "warning",
};

export function ConfidenceMeter({
  label,
  value,
  tone = "accent",
  caption,
}: {
  label: string;
  value: number;
  tone?: Tone;
  caption?: string;
}) {
  const percent = Math.max(0, Math.min(1, value || 0)) * 100;

  return (
    <div className="stack tight">
      <div className="meter-row">
        <span>{label}</span>
        <span className="value">{percent.toFixed(0)}%</span>
      </div>
      <div className={`meter ${TONE_CLASS[tone]}`}>
        <span style={{ width: `${percent}%` }} />
      </div>
      {caption ? (
        <span style={{ color: "var(--text-faint)", fontSize: 12 }}>{caption}</span>
      ) : null}
    </div>
  );
}
