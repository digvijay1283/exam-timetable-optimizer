import { useCallback, useEffect, useState } from "react";
import { DEFAULT_SESSION, api } from "./api";
import { DataPage } from "./pages/DataPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { OptimizePage } from "./pages/OptimizePage";
import { OverviewPage } from "./pages/OverviewPage";
import { TimetablePage } from "./pages/TimetablePage";
import { progressOf, type Page, type SessionDetail, type SessionSummary } from "./types";
import { Icon, Notice, useAsync } from "./ui";

const NAV: { page: Page; label: string; step?: number }[] = [
  { page: "overview", label: "Home" },
  { page: "data", label: "Add data", step: 1 },
  { page: "optimize", label: "Optimize", step: 2 },
  { page: "timetable", label: "Timetable", step: 3 },
];

const stored = () => {
  try { return Number(localStorage.getItem("session")) || null; } catch { return null; }
};
const fromHash = (): Page | null => {
  const h = location.hash.slice(1);
  return [...NAV.map((n) => n.page), "experiments"].includes(h) ? (h as Page) : null;
};

export default function App() {
  const [page, setPage] = useState<Page>(() => fromHash() ?? "overview");
  const [sessionId, setSessionId] = useState<number | null>(stored);
  const [timetableId, setTimetableId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [startError, setStartError] = useState<unknown>(null);
  const sessions = useAsync(() => api.sessions(), []);
  const known = sessions.data?.some((s) => s.id === sessionId);
  const id = (known ? sessionId : null) ?? sessions.data?.[0]?.id ?? null;
  const detail = useAsync<SessionDetail | null>(() => (id ? api.session(id) : Promise.resolve(null)), [id]);

  useEffect(() => { location.hash = page; window.scrollTo(0, 0); }, [page]);
  useEffect(() => {
    const onHash = () => { const h = fromHash(); if (h) setPage(h); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const refresh = useCallback(() => { void detail.reload(); }, [detail.reload]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (value: number) => {
    setSessionId(value);
    try { localStorage.setItem("session", String(value)); } catch { /* storage unavailable */ }
  };
  const openTimetable = (tid: number) => { setTimetableId(tid); setPage("timetable"); };
  const go = (p: Page) => { if (p !== "data") setCreating(false); setPage(p); };

  /** One click from an empty app to a session holding the small sample, ready to optimize. */
  const quickStart = async () => {
    setStarting(true); setStartError(null);
    try {
      let sid = id;
      if (!sid) { sid = (await api.createSession(DEFAULT_SESSION)).id; pick(sid); }
      await api.loadSample(sid, "small");
      await sessions.reload();
      if (sid === id) await detail.reload();
      setCreating(false);
      setPage("optimize");
    } catch (e) { setStartError(e); } finally { setStarting(false); }
  };

  const session = detail.data;
  const progress = progressOf(session);
  const done: Partial<Record<Page, boolean>> = { data: progress.data, optimize: progress.optimized };

  return (
    <>
      <header className="topbar"><div className="topbar-inner">
        <button className="brand" onClick={() => go("overview")}>
          <span className="brand-mark"><Icon name="calendar" size={17} /></span>
          <span className="brand-name">Exam Timetable Optimizer</span>
        </button>
        <nav className="nav" aria-label="Steps">
          {NAV.map(({ page: p, label, step }) => (
            <button key={p} className="nav-item" aria-current={page === p ? "page" : undefined} onClick={() => go(p)}>
              {step && <span className={`nav-num ${done[p] ? "done" : ""}`}>{done[p] ? <Icon name="check" size={12} /> : step}</span>}
              {label}
            </button>
          ))}
          <span className="nav-sep" />
          <button className="nav-item" aria-current={page === "experiments" ? "page" : undefined} onClick={() => go("experiments")}>Research</button>
        </nav>
        <span className="spacer" />
        {sessions.data && sessions.data.length > 0 && (
          <label className="session-pick">
            <span>Session</span>
            <select className="input" value={id ?? ""} onChange={(e) => { pick(Number(e.target.value)); setCreating(false); }}>
              {sessions.data.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.academic_year}</option>)}
            </select>
            <button className="btn sm" title="Start a new exam session" onClick={() => { setCreating(true); setPage("data"); }}>+ New</button>
          </label>
        )}
      </div></header>
      <main>
        {sessions.error ? <ServerDown onRetry={() => void sessions.reload()} /> : sessions.loading && !sessions.data ? (
          <p className="muted">Loading…</p>
        ) : (
          <>
            {page === "overview" && <OverviewPage session={session} go={go} openTimetable={openTimetable}
              quickStart={quickStart} starting={starting} startError={startError} />}
            {page === "data" && (
              <DataPage session={creating || !sessions.data?.length ? null : session} go={go}
                quickStart={quickStart} starting={starting}
                onCreated={(s: SessionSummary) => { pick(s.id); setCreating(false); void sessions.reload(); }} onChanged={refresh} />)}
            {page === "optimize" && <OptimizePage session={session} go={go} onOpenTimetable={openTimetable} onChanged={refresh} />}
            {page === "timetable" && <TimetablePage session={session} go={go} selectedId={timetableId} onSelect={setTimetableId} onChanged={refresh} />}
            {page === "experiments" && <ExperimentsPage />}
          </>
        )}
      </main>
    </>
  );
}

function ServerDown({ onRetry }: { onRetry: () => void }) {
  return (
    <Notice tone="bad" title="Can't reach the backend server">
      <p style={{ marginTop: 4 }}>The web page loaded, but the API it talks to (port 8000) isn't answering. Start it in a terminal, then retry:</p>
      <pre><code>cd backend{"\n"}..\.venv\Scripts\python -m uvicorn app.main:create_app --factory --port 8000</code></pre>
      <button className="btn" style={{ marginTop: 10 }} onClick={onRetry}>Retry</button>
    </Notice>
  );
}
