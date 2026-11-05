import { Loader2 } from "lucide-react";
import { STATUS, pct } from "../lib.js";

const TONES = {
  ok: "bg-ok-soft text-ok",
  warn: "bg-warn-soft text-warn",
  bad: "bg-bad-soft text-bad",
  brand: "bg-brand-soft text-brand",
  muted: "bg-sunk text-muted",
};

export function Badge({ tone = "muted", children, className = "" }) {
  return <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONES[tone]} ${className}`}>{children}</span>;
}

export function StatusBadge({ status }) {
  const s = STATUS[status] || { label: status, tone: "muted" };
  return <Badge tone={s.tone}>{s.label}</Badge>;
}

export function Spinner({ className = "" }) {
  return <Loader2 className={`animate-spin ${className}`} aria-hidden="true" />;
}

/** Thin bar showing extraction confidence (0 to 1). */
export function ConfidenceBar({ value }) {
  const tone = value >= 0.85 ? "bg-ok" : value >= 0.6 ? "bg-warn" : "bg-bad";
  return (
    <div className="flex items-center gap-2" title={`Confidence ${pct(value)}`}>
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-sunk" role="progressbar" aria-valuenow={Math.round(value * 100)} aria-valuemin="0" aria-valuemax="100">
        <div className={`h-full rounded-full ${tone}`} style={{ width: pct(value) }} />
      </div>
      <span className="num text-xs font-semibold text-muted">{pct(value)}</span>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="flex flex-col items-center px-6 py-14 text-center">
      <div className="mb-4 grid h-12 w-12 place-items-center rounded-full bg-sunk text-muted"><Icon className="h-6 w-6" /></div>
      <h3 className="text-base font-bold">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-muted">{children}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, subtitle, children }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      <div className="flex flex-wrap gap-2">{children}</div>
    </div>
  );
}

export function ErrorBox({ children }) {
  return <div role="alert" className="rounded-lg border border-bad/30 bg-bad-soft px-4 py-3 text-sm font-medium text-bad">{children}</div>;
}
