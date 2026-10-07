import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ApiError } from "./api";

export const fmt = (n: number | null | undefined, digits = 0) =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function Stat({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: "ok" | "bad"; hint?: string }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <div className="v">{value}</div>
      <div className="l">{label}</div>
      {hint && <div className="h">{hint}</div>}
    </div>
  );
}

const PATHS = {
  check: "M5 12.5l4.2 4.2L19 7",
  alert: "M12 8v5m0 3.5v.01M10.3 3.9L2.6 17.5A2 2 0 004.3 20.5h15.4a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z",
  arrow: "M5 12h14m-6-6l6 6-6 6",
  calendar: "M7 3v3m10-3v3M4 9h16M5 5h14a1 1 0 011 1v13a1 1 0 01-1 1H5a1 1 0 01-1-1V6a1 1 0 011-1z",
  info: "M12 11v5m0-8.5v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  download: "M12 4v11m-5-5l5 5 5-5M5 20h14",
  upload: "M12 20V9m-5 5l5-5 5 5M5 4h14",
  play: "M8 5.5v13l10.5-6.5L8 5.5z",
};

export function Icon({ name, size = 18 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg className="icon" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={name === "check" ? 2.4 : 2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d={PATHS[name]} />
    </svg>
  );
}

/** Page title block: which workflow step this is, what the page does. */
export function PageHead({ step, title, children, actions }: {
  step?: string; title: ReactNode; children?: ReactNode; actions?: ReactNode;
}) {
  return (
    <div className="page-head-row">
      <div className="page-head" style={{ flex: 1, minWidth: 260 }}>
        {step && <span className="eyebrow">{step}</span>}
        <h1>{title}</h1>
        {children && <p className="sub">{children}</p>}
      </div>
      {actions}
    </div>
  );
}

/** Tells the user what to do after finishing this page. */
export function NextStep({ title, children, label, onClick }: {
  title: string; children?: ReactNode; label: string; onClick: () => void;
}) {
  return (
    <div className="next">
      <div className="body"><b>{title}</b>{children && <p>{children}</p>}</div>
      <button className="btn primary" onClick={onClick}>{label} <Icon name="arrow" size={16} /></button>
    </div>
  );
}

export function Verdict({ ok, title, children, action }: { ok: boolean; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className={`verdict ${ok ? "ok" : "bad"}`} role="status">
      <span className="v-icon"><Icon name={ok ? "check" : "alert"} size={26} /></span>
      <div className="body"><h2>{title}</h2>{children && <p>{children}</p>}</div>
      {action}
    </div>
  );
}

export function Chip({ tone, children }: { tone?: "ok" | "bad" | "info"; children: ReactNode }) {
  return <span className={`chip ${tone ?? ""}`}>{children}</span>;
}

export function Notice({ tone, title, items, children }: { tone: "bad" | "ok" | "info"; title?: string; items?: string[]; children?: ReactNode }) {
  return (
    <div className={`notice ${tone}`} role={tone === "bad" ? "alert" : "status"}>
      {title && <strong>{title}</strong>}
      {children}
      {items && items.length > 0 && (
        <ul>{items.slice(0, 12).map((m, i) => <li key={i}>{m}</li>)}{items.length > 12 && <li>and {items.length - 12} more</li>}</ul>
      )}
    </div>
  );
}

export function ErrorNotice({ error, title }: { error: unknown; title?: string }) {
  if (!error) return null;
  const messages = error instanceof ApiError ? error.messages : [String((error as Error).message ?? error)];
  return <Notice tone="bad" title={title ?? "That didn't work"} items={messages} />;
}

export function Empty({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return <div className="empty"><p>{children}</p>{action}</div>;
}

export function Panel({ title, note, actions, children, flush }: {
  title: string; note?: ReactNode; actions?: ReactNode; children: ReactNode; flush?: boolean;
}) {
  return (
    <section className="panel">
      <header>
        <h2>{title}</h2>
        {note && <span className="note">{note}</span>}
        <span className="spacer" />
        {actions}
      </header>
      <div className={flush ? "" : "panel-body"}>{children}</div>
    </section>
  );
}

/** Load data on mount and whenever `deps` change; `reload` refetches. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const reload = useCallback(() => {
    setLoading(true);
    return fnRef.current().then(
      (d) => { setData(d); setError(null); setLoading(false); },
      (e) => { setError(e); setLoading(false); },
    );
  }, []);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { void reload(); }, deps);
  return { data, error, loading, reload };
}

export const TOOLTIP = { fontSize: 13, borderRadius: 8, border: "1px solid var(--rule)", background: "var(--surface)", color: "var(--ink)", boxShadow: "none" };

export function Convergence({ points, height = 230 }: {
  points: { generation: number; best: number; mean?: number }[]; height?: number;
}) {
  if (points.length < 2) return <Empty>The progress chart appears once the run has started.</Empty>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="var(--grid)" vertical={false} />
        <XAxis dataKey="generation" tick={{ fontSize: 12, fill: "var(--muted)" }} tickLine={false} axisLine={{ stroke: "var(--rule-strong)" }}
          label={{ value: "Generation", position: "insideBottom", offset: -2, fontSize: 12, fill: "var(--muted)" }} height={36} />
        <YAxis scale="log" domain={["auto", "auto"]} allowDataOverflow tick={{ fontSize: 12, fill: "var(--muted)" }}
          tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => fmt(v)} />
        <Tooltip formatter={(v) => fmt(Number(v))} labelFormatter={(g) => `Generation ${g}`}
          contentStyle={TOOLTIP} />
        <Line type="monotone" dataKey="best" name="Best schedule" stroke="var(--gold)" strokeWidth={2.4} dot={false} isAnimationActive={false} />
        {points.some((p) => p.mean != null) && (
          <Line type="monotone" dataKey="mean" name="Average schedule" stroke="var(--muted)" strokeWidth={1.2} dot={false} isAnimationActive={false} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SimpleTable({ rows, highlight }: { rows: Record<string, string | number | null>[]; highlight?: (r: Record<string, string | number | null>) => boolean }) {
  if (!rows.length) return <Empty>Nothing to show.</Empty>;
  const cols = Object.keys(rows[0]);
  return (
    <div className="scroll">
      <table className="table">
        <thead><tr>{cols.map((c, i) => <th key={c} className={i ? "num" : ""}>{c}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className={highlight?.(r) ? "is-best" : ""}>
              {cols.map((c, j) => <td key={c} className={j ? "num" : ""}>{String(r[c] ?? "—")}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
