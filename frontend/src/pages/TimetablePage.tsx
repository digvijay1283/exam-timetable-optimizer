import { useMemo, useState } from "react";
import { api } from "../api";
import type { Entry, Page, SessionDetail, Validation } from "../types";
import { Chip, Empty, ErrorNotice, Icon, Notice, PageHead, Panel, Stat, fmt, useAsync } from "../ui";

const hue = (index: number) => (index * 47 + 200) % 360;
const deptStyle = (i: number) =>
  ({ "--c": `hsl(${hue(i)} 55% 42%)`, "--bg-c": `hsl(${hue(i)} 60% 50% / 0.1)` }) as React.CSSProperties;

const dayLabel = (iso: string) => {
  const d = new Date(iso + "T00:00:00");
  return { weekday: d.toLocaleDateString("en-GB", { weekday: "short" }), date: d.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) };
};

export function TimetablePage({ session, go, selectedId, onSelect, onChanged }: {
  session: SessionDetail | null; go: (page: Page) => void; selectedId: number | null; onSelect: (id: number) => void; onChanged: () => void;
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

  const head = (
    <PageHead step="Step 3 of 3" title="Review and export">
      Check the timetable, approve the version you want to publish, and download it as Excel or CSV.
    </PageHead>
  );
  if (!session || (!list.loading && !list.data?.length)) {
    return <>{head}<Empty action={<button className="btn primary" onClick={() => go("optimize")}>Go to step 2: Optimize</button>}>
      No timetable yet. Run the optimizer to create one.</Empty></>;
  }
  if (!list.data) return head;

  const t = detail.data;
  const act = async (job: () => Promise<unknown>) => {
    setError(null);
    try { await job(); } catch (e) { setError(e); }
  };

  return (
    <>
      {head}
      <div className="row">
        <label className="muted" htmlFor="tt-pick">Version</label>
        <select id="tt-pick" className="input" style={{ width: "auto", maxWidth: "100%" }} value={id ?? ""} onChange={(e) => { onSelect(Number(e.target.value)); setValidation(null); }}>
          {list.data.map((x) => <option key={x.id} value={x.id}>#{x.id} · {x.name}</option>)}
        </select>
        {t && <Chip tone={t.status === "approved" ? "ok" : t.status === "infeasible" ? "bad" : "info"}>{t.status === "approved" ? "Approved" : t.status === "infeasible" ? "Has rule violations" : "Draft"}</Chip>}
        <span className="spacer" />
        {t && (
          <div className="row">
            <button className="btn" title="Re-check every must-have rule from scratch" onClick={() => act(async () => setValidation(await api.validateTimetable(t.id)))}>Check rules</button>
            <button className="btn primary" title="Mark this as the final version" disabled={t.hard_violations > 0 || t.status === "approved"}
              onClick={() => act(async () => { await api.approve(t.id); await detail.reload(); await list.reload(); onChanged(); })}>
              {t.status === "approved" ? <><Icon name="check" size={16} /> Approved</> : "Approve"}</button>
            <a className="btn" href={`/api/export/${t.id}/xlsx`} aria-disabled={t.hard_violations > 0}><Icon name="download" size={16} /> Excel</a>
            <a className="btn" href={`/api/export/${t.id}/csv`} aria-disabled={t.hard_violations > 0}><Icon name="download" size={16} /> CSV</a>
          </div>
        )}
      </div>

      {t && (
        <div className="stats">
          <Stat label="Exams scheduled" value={t.total_entries} />
          <Stat label="Rule violations" hint="Must be 0" value={t.hard_violations} tone={t.hard_violations ? "bad" : "ok"} />
          <Stat label="Penalty score" hint="Lower is better" value={fmt(t.penalty)} />
          <Stat label="Exams on consecutive days" hint="Fewer is better" value={fmt(t.breakdown.short_gaps)} />
        </div>
      )}

      <ErrorNotice error={error} />
      {t && t.hard_violations > 0 && <Notice tone="bad" title="This timetable breaks some must-have rules, so it can't be approved or exported. Run the optimizer again with more rounds." />}
      {validation && (validation.valid
        ? <Notice tone="ok" title="All rules pass: no student has two exams at once or two exams in one day, no room is double-booked, and every room is big enough." />
        : <Notice tone="bad" title={`${validation.hard_violations} rule violation(s) found`} items={validation.details} />)}

      <Panel flush title="Schedule" note={t ? `Showing ${t.entries.length} of ${t.total_entries} exams · hover an exam for details` : undefined}
        actions={<div className="seg" role="group" aria-label="View">
          <button aria-pressed={view === "grid"} onClick={() => setView("grid")}>Grid</button>
          <button aria-pressed={view === "list"} onClick={() => setView("list")}>List</button></div>}>
        <div className="row" style={{ padding: "12px 20px", borderBottom: "1px solid var(--rule)" }}>
          <span className="muted small">Filter:</span>
          <Filter label="Department" value={filters.department} options={options.dept} onChange={(v) => setFilters({ ...filters, department: v })} />
          <Filter label="Semester" value={filters.semester} options={options.sem} onChange={(v) => setFilters({ ...filters, semester: v })} />
          <Filter label="Date" value={filters.date} options={options.date} onChange={(v) => setFilters({ ...filters, date: v })} />
          <Filter label="Room" value={filters.room} options={options.room} onChange={(v) => setFilters({ ...filters, room: v })} />
          <input className="input" style={{ width: 180 }} placeholder="Search subject…" value={filters.subject}
            onChange={(e) => setFilters({ ...filters, subject: e.target.value })} aria-label="Search subject" />
          {Object.values(filters).some(Boolean) && <button className="btn sm" onClick={() => setFilters({ department: "", semester: "", date: "", room: "", subject: "" })}>Clear filters</button>}
        </div>
        {!t ? null : t.entries.length === 0 ? <Empty>No exams match these filters.</Empty>
          : view === "grid" ? <Grid entries={t.entries} deptIndex={deptIndex} /> : <List entries={t.entries} />}
        <div className="legend" style={{ padding: "12px 20px", borderTop: "1px solid var(--rule)" }}>
          <span>Departments:</span>
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
                    title={`${e.subject_name} (${e.subject_code})\n${e.department} · semester ${e.semester}\n${e.students} students · room ${e.room_code}, ${e.building}`}>
                    <b>{e.subject_name}</b>
                    <span>{e.subject_code} · Room {e.room_code} · {e.students} students</span>
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
            <td><b>{e.subject_name}</b> <span className="muted">{e.subject_code}</span></td>
            <td>{e.department}</td><td>{e.semester}</td><td>{e.room_code}</td><td className="num">{e.students}</td>
          </tr>);
      })}</tbody>
    </table></div>
  );
}
