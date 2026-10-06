import { useMemo, useState } from "react";
import { api } from "../api";
import type { Entry, SessionDetail, Validation } from "../types";
import { Chip, Empty, ErrorNotice, Notice, Panel, Stat, fmt, useAsync } from "../ui";

const hue = (index: number) => (index * 47 + 200) % 360;
const deptStyle = (i: number) =>
  ({ "--c": `hsl(${hue(i)} 48% 36%)`, "--bg": `hsl(${hue(i)} 55% 95%)` }) as React.CSSProperties;

const dayLabel = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  return { weekday: d.toLocaleDateString("en-GB", { weekday: "short" }), date: d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) };
};

export function TimetablePage({ session, selectedId, onSelect, onChanged }: {
  session: SessionDetail | null; selectedId: number | null; onSelect: (id: number) => void; onChanged: () => void;
}) {
  const [filters, setFilters] = useState({ department: "", semester: "", date: "", room: "", subject: "" });
  const [view, setView] = useState<"grid" | "list">("grid");
  const [validation, setValidation] = useState<Validation | null>(null);
  const [error, setError] = useState<unknown>(null);
  const list = useAsync(() => (session ? api.timetables(session.id) : Promise.resolve([])), [session?.id, session?.counts.timetables]);
  const id = selectedId ?? list.data?.[0]?.id ?? null;
  const detail = useAsync(() => (id ? api.timetable(id, filters) : Promise.resolve(null)), [id, JSON.stringify(filters)]);
  const all = useAsync(() => (id ? api.timetable(id) : Promise.resolve(null)), [id]);

  const options = useMemo(() => {
    const e = all.data?.entries ?? [];
    const uniq = (f: (x: Entry) => string) => [...new Set(e.map(f))].sort();
    return { dept: uniq((x) => x.department), sem: uniq((x) => x.semester), date: uniq((x) => x.date), room: uniq((x) => x.room_code) };
  }, [all.data]);
  const deptIndex = (d: string) => options.dept.indexOf(d);

  if (!session) return <Empty>Create a session on the Data tab first.</Empty>;
  if (!list.data?.length) return <Empty>No timetables yet. Run an optimization to generate one.</Empty>;

  const t = detail.data;
  const act = async (job: () => Promise<unknown>) => {
    setError(null);
    try { await job(); } catch (e) { setError(e); }
  };

  return (
    <>
      <div className="page-head">
        <h1>Timetable</h1>
        <select className="input" style={{ width: "auto" }} value={id ?? ""} onChange={(e) => { onSelect(Number(e.target.value)); setValidation(null); }}>
          {list.data.map((x) => <option key={x.id} value={x.id}>#{x.id} · {x.name}</option>)}
        </select>
        {t && <Chip tone={t.status === "approved" ? "ok" : t.status === "infeasible" ? "bad" : "info"}>{t.status}</Chip>}
        <span className="spacer" />
        {t && (
          <div className="row">
            <button className="btn" onClick={() => act(async () => setValidation(await api.validateTimetable(t.id)))}>Validate</button>
            <button className="btn primary" disabled={t.hard_violations > 0 || t.status === "approved"}
              onClick={() => act(async () => { await api.approve(t.id); await detail.reload(); await list.reload(); onChanged(); })}>
              {t.status === "approved" ? "Approved" : "Approve"}</button>
            <a className={`btn ${t.hard_violations > 0 ? "disabled" : ""}`} href={`/api/export/${t.id}/csv`} aria-disabled={t.hard_violations > 0}>CSV</a>
            <a className="btn" href={`/api/export/${t.id}/xlsx`} aria-disabled={t.hard_violations > 0}>Excel</a>
          </div>
        )}
      </div>

      {t && (
        <div className="stats">
          <Stat label="Exams" value={t.total_entries} />
          <Stat label="Hard violations" value={t.hard_violations} tone={t.hard_violations ? "bad" : "ok"} />
          <Stat label="Penalty" value={fmt(t.penalty)} />
          <Stat label="Fitness" value={t.fitness.toExponential(2)} />
          <Stat label="Back-to-back" value={fmt(t.breakdown.consecutive)} />
          <Stat label="Short gaps" value={fmt(t.breakdown.short_gaps)} />
        </div>
      )}

      <ErrorNotice error={error} />
      {validation && (validation.valid
        ? <Notice tone="ok" title="Valid: no student clashes, room collisions or capacity problems." />
        : <Notice tone="bad" title={`${validation.hard_violations} hard violation(s)`} items={validation.details} />)}

      <Panel flush title="Schedule" note={t ? `${t.entries.length} of ${t.total_entries} exams shown` : undefined}
        actions={<div className="seg" role="group" aria-label="View">
          <button aria-pressed={view === "grid"} onClick={() => setView("grid")}>Grid</button>
          <button aria-pressed={view === "list"} onClick={() => setView("list")}>List</button></div>}>
        <div className="row" style={{ padding: "10px 14px", borderBottom: "1px solid var(--rule)" }}>
          <Filter label="Department" value={filters.department} options={options.dept} onChange={(v) => setFilters({ ...filters, department: v })} />
          <Filter label="Semester" value={filters.semester} options={options.sem} onChange={(v) => setFilters({ ...filters, semester: v })} />
          <Filter label="Date" value={filters.date} options={options.date} onChange={(v) => setFilters({ ...filters, date: v })} />
          <Filter label="Room" value={filters.room} options={options.room} onChange={(v) => setFilters({ ...filters, room: v })} />
          <input className="input" style={{ width: 150 }} placeholder="Search subject" value={filters.subject}
            onChange={(e) => setFilters({ ...filters, subject: e.target.value })} aria-label="Search subject" />
          {Object.values(filters).some(Boolean) && <button className="btn sm" onClick={() => setFilters({ department: "", semester: "", date: "", room: "", subject: "" })}>Clear</button>}
        </div>
        {!t ? null : t.entries.length === 0 ? <Empty>No exams match these filters.</Empty>
          : view === "grid" ? <Grid entries={t.entries} deptIndex={deptIndex} /> : <List entries={t.entries} />}
        <div className="legend" style={{ padding: "10px 14px", borderTop: "1px solid var(--rule)" }}>
          {options.dept.map((d, i) => <span key={d} style={deptStyle(i)}><i />{d}</span>)}
        </div>
      </Panel>
    </>
  );
}

function Filter({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <select className="input" style={{ width: "auto" }} value={value} onChange={(e) => onChange(e.target.value)} aria-label={label}>
      <option value="">{label}: all</option>
      {options.map((o) => <option key={o} value={o}>{o}</option>)}
    </select>
  );
}

function Grid({ entries, deptIndex }: { entries: Entry[]; deptIndex: (d: string) => number }) {
  const days = [...new Set(entries.map((e) => e.date))].sort();
  const slots = [...new Map(entries.map((e) => [e.start_time, `${e.start_time.slice(0, 5)}–${e.end_time.slice(0, 5)}`])).entries()].sort();
  const cols = { "--cols": slots.length } as React.CSSProperties;
  return (
    <div className="scroll"><div className="tt" style={{ minWidth: 560 }}>
      <div className="tt-row tt-head" style={cols}><div />{slots.map(([k, label]) => <div key={k}>{label}</div>)}</div>
      {days.map((day) => {
        const { weekday, date } = dayLabel(day);
        return (
          <div className="tt-row" style={cols} key={day}>
            <div className="tt-day"><b>{date}</b><span>{weekday}</span></div>
            {slots.map(([start]) => (
              <div className="tt-cell" key={start}>
                {entries.filter((e) => e.date === day && e.start_time === start).map((e) => (
                  <div className="exam" style={deptStyle(deptIndex(e.department))} key={e.exam_id}
                    title={`${e.subject_name}\n${e.department} · semester ${e.semester}\n${e.students} students · ${e.room_code}, ${e.building}`}>
                    <b>{e.subject_code}</b><span>{e.room_code} · {e.students}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        );
      })}
    </div></div>
  );
}

function List({ entries }: { entries: Entry[] }) {
  return (
    <div className="scroll"><table className="table">
      <thead><tr><th>Date</th><th>Time</th><th>Subject</th><th>Department</th><th>Sem</th><th>Room</th><th className="num">Students</th></tr></thead>
      <tbody>{entries.map((e) => {
        const { weekday, date } = dayLabel(e.date);
        return (
          <tr key={e.exam_id}>
            <td>{weekday} {date}</td><td>{e.start_time.slice(0, 5)}–{e.end_time.slice(0, 5)}</td>
            <td><b>{e.subject_code}</b> <span className="muted">{e.subject_name}</span></td>
            <td>{e.department}</td><td>{e.semester}</td><td>{e.room_code}</td><td className="num">{e.students}</td>
          </tr>);
      })}</tbody>
    </table></div>
  );
}
