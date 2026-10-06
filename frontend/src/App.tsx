import { useCallback, useEffect, useState } from "react";
import { api } from "./api";
import { DataPage } from "./pages/DataPage";
import { ExperimentsPage } from "./pages/ExperimentsPage";
import { OptimizePage } from "./pages/OptimizePage";
import { OverviewPage } from "./pages/OverviewPage";
import { TimetablePage } from "./pages/TimetablePage";
import type { SessionDetail, SessionSummary } from "./types";
import { ErrorNotice, useAsync } from "./ui";

type Page = "overview" | "data" | "optimize" | "timetable" | "experiments";
const TABS: [Page, string][] = [
  ["overview", "Overview"], ["data", "Data"], ["optimize", "Optimize"], ["timetable", "Timetable"], ["experiments", "Experiments"],
];

const stored = () => {
  try { return Number(localStorage.getItem("session")) || null; } catch { return null; }
};

export default function App() {
  const [page, setPage] = useState<Page>(() => (location.hash.slice(1) as Page) || "overview");
  const [sessionId, setSessionId] = useState<number | null>(stored);
  const [timetableId, setTimetableId] = useState<number | null>(null);
  const [creating, setCreating] = useState(false);
  const sessions = useAsync(() => api.sessions(), []);
  const id = sessionId ?? sessions.data?.[0]?.id ?? null;
  const detail = useAsync<SessionDetail | null>(() => (id ? api.session(id) : Promise.resolve(null)), [id]);

  useEffect(() => { location.hash = page; }, [page]);
  useEffect(() => {
    const onHash = () => { const h = location.hash.slice(1) as Page; if (TABS.some(([p]) => p === h)) setPage(h); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  const refresh = useCallback(() => { void detail.reload(); }, [detail.reload]); // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (value: number) => {
    setSessionId(value);
    try { localStorage.setItem("session", String(value)); } catch { /* storage unavailable */ }
  };
  const openTimetable = (tid: number) => { setTimetableId(tid); setPage("timetable"); };
  const session = detail.data;

  return (
    <>
      <div className="topbar"><div className="topbar-inner">
        <span className="brand">Exam Timetable Optimizer</span>
        <nav className="tabs" aria-label="Sections">
          {TABS.map(([p, label]) => (
            <button key={p} className="tab" aria-current={page === p ? "page" : undefined} onClick={() => setPage(p)}>{label}</button>
          ))}
        </nav>
        <span className="spacer" />
        {sessions.data && sessions.data.length > 0 && (
          <select className="input" style={{ width: "auto", maxWidth: 240 }} value={id ?? ""} aria-label="Session"
            onChange={(e) => pick(Number(e.target.value))}>
            {sessions.data.map((s) => <option key={s.id} value={s.id}>{s.name} · {s.academic_year}</option>)}
          </select>
        )}
        <button className="btn sm" onClick={() => { setCreating(true); setPage("data"); }}>New session</button>
      </div></div>
      <main>
        {sessions.error ? <ErrorNotice error={sessions.error} title="Can't reach the server. Is the API running on port 8000?" /> : (
          <>
            {page === "overview" && <OverviewPage session={session} go={setPage} openTimetable={openTimetable} />}
            {page === "data" && (
              <DataPage session={creating || (!sessions.loading && !sessions.data?.length) ? null : session}
                onCreated={(s: SessionSummary) => { pick(s.id); setCreating(false); void sessions.reload(); }} onChanged={refresh} />)}
            {page === "optimize" && <OptimizePage session={session} onOpenTimetable={openTimetable} onChanged={refresh} />}
            {page === "timetable" && <TimetablePage session={session} selectedId={timetableId} onSelect={setTimetableId} onChanged={refresh} />}
            {page === "experiments" && <ExperimentsPage />}
          </>
        )}
      </main>
    </>
  );
}
