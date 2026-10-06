import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { ApiError } from "./api";

export const fmt = (n: number | null | undefined, digits = 0) =>
  n == null || Number.isNaN(n) ? "—" : n.toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });

export function Stat({ label, value, tone }: { label: string; value: ReactNode; tone?: "ok" | "bad" }) {
  return (
    <div className={`stat ${tone ?? ""}`}>
      <div className="v">{value}</div>
      <div className="l">{label}</div>
    </div>
  );
}

export function Chip({ tone, children }: { tone?: "ok" | "bad" | "info"; children: ReactNode }) {
  return <span className={`chip ${tone ?? ""}`}>{children}</span>;
}

export function Notice({ tone, title, items }: { tone: "bad" | "ok"; title?: string; items?: string[] }) {
  return (
    <div className={`notice ${tone}`} role={tone === "bad" ? "alert" : "status"}>
      {title && <strong>{title}</strong>}
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

export function Convergence({ points, height = 230 }: {
  points: { generation: number; best: number; mean?: number }[]; height?: number;
}) {
  if (points.length < 2) return <Empty>The curve appears once a run has started.</Empty>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={points} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid stroke="#e9ecf0" vertical={false} />
        <XAxis dataKey="generation" tick={{ fontSize: 11, fill: "#667085" }} tickLine={false} axisLine={{ stroke: "#cfd4dc" }} />
        <YAxis scale="log" domain={["auto", "auto"]} allowDataOverflow tick={{ fontSize: 11, fill: "#667085" }}
          tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => fmt(v)} />
        <Tooltip formatter={(v) => fmt(Number(v))} labelFormatter={(g) => `Generation ${g}`}
          contentStyle={{ fontSize: 12, borderRadius: 6, border: "1px solid #e3e6eb", boxShadow: "none" }} />
        <Line type="monotone" dataKey="best" name="Best penalty" stroke="#0072b2" strokeWidth={2} dot={false} isAnimationActive={false} />
        {points.some((p) => p.mean != null) && (
          <Line type="monotone" dataKey="mean" name="Population mean" stroke="#9aa4b2" strokeWidth={1.2} dot={false} isAnimationActive={false} />
        )}
      </LineChart>
    </ResponsiveContainer>
  );
}

export function SimpleTable({ rows, highlight }: { rows: Record<string, string | number | null>[]; highlight?: (r: Record<string, string | number | null>) => boolean }) {
  if (!rows.length) return <Empty>No rows.</Empty>;
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
