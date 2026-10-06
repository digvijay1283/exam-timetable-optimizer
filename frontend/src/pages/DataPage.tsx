import { useRef, useState } from "react";
import { api } from "../api";
import type { DataCheck, SessionDetail, SessionSummary } from "../types";
import { Chip, Empty, ErrorNotice, Notice, Panel, fmt } from "../ui";

const SOURCES = [
  { table: "exams", label: "Exams", hint: "exam_id, subject_code, subject_name, department, semester, duration_minutes, student_count, exam_type" },
  { table: "students", label: "Students", hint: "student_id" },
  { table: "rooms", label: "Rooms", hint: "room_id, room_code, capacity (+ building, room_type, available)" },
  { table: "enrollments", label: "Enrollments", hint: "student_id, exam_id. Import after exams and students." },
] as const;

export function DataPage({ session, onCreated, onChanged }: {
  session: SessionDetail | null; onCreated: (s: SessionSummary) => void; onChanged: () => void;
}) {
  return (
    <>
      <div className="page-head"><h1>Data</h1><span className="sub">Bring in exams, students, rooms and slots, then check they can be scheduled.</span></div>
      {session ? <Manage session={session} onChanged={onChanged} /> : <CreateSession onCreated={onCreated} />}
    </>
  );
}

function CreateSession({ onCreated }: { onCreated: (s: SessionSummary) => void }) {
  const [form, setForm] = useState({
    name: "End Semester Examination", academic_year: "2026-27", semester: "VII",
    start_date: "2026-11-20", end_date: "2026-12-31", slots_per_day: 2,
  });
  const [error, setError] = useState<unknown>(null);
  const set = (k: string, v: string | number) => setForm({ ...form, [k]: v });
  const submit = async () => {
    try { onCreated(await api.createSession(form)); } catch (e) { setError(e); }
  };
  return (
    <Panel title="New examination session" actions={<button className="btn primary" onClick={submit}>Create session</button>}>
      <div className="form-grid" style={{ gridTemplateColumns: "2fr 1fr 1fr" }}>
        <Field label="Session name"><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
        <Field label="Academic year"><input className="input" value={form.academic_year} onChange={(e) => set("academic_year", e.target.value)} /></Field>
        <Field label="Semester"><input className="input" value={form.semester} onChange={(e) => set("semester", e.target.value)} /></Field>
        <Field label="First day"><input className="input" type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
        <Field label="Last day"><input className="input" type="date" value={form.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
        <Field label="Slots per day">
          <select className="input" value={form.slots_per_day} onChange={(e) => set("slots_per_day", Number(e.target.value))}>
            {[1, 2, 3].map((n) => <option key={n}>{n}</option>)}
          </select>
        </Field>
      </div>
      <div style={{ marginTop: 12 }}><ErrorNotice error={error} title="Couldn't create the session" /></div>
    </Panel>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div className="field"><label>{label}</label>{children}</div>;
}

function Manage({ session, onChanged }: { session: SessionDetail; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<{ text: string; warnings: string[] } | null>(null);
  const [check, setCheck] = useState<DataCheck | null>(null);
  const files = useRef<Record<string, HTMLInputElement | null>>({});
  const c = session.counts;

  const run = async (key: string, job: () => Promise<{ text: string; warnings?: string[] } | void>) => {
    setBusy(key); setError(null); setMessage(null);
    try {
      const out = await job();
      if (out) setMessage({ text: out.text, warnings: out.warnings ?? [] });
      setCheck(null);
      onChanged();
    } catch (e) { setError(e); } finally { setBusy(null); }
  };

  const upload = (table: string, label: string) => (file?: File) => file && run(table, async () => {
    const r = await api.upload(session.id, table, file);
    return { text: `${label}: ${fmt(r.imported)} imported${r.invalidated_timetables ? `, ${r.invalidated_timetables} timetable(s) cleared because the data changed` : ""}.`, warnings: r.warnings };
  });

  const counts: Record<string, number> = { exams: c.exams, students: c.students, rooms: c.rooms, enrollments: c.enrollments };

  return (
    <>
      <div className="grid-2">
        <Panel title="Files" note="CSV, one table at a time" flush>
          {SOURCES.map((s) => (
            <div className="source" key={s.table}>
              <span className="name">{s.label}</span>
              <span className="meta" title={s.hint}>
                {counts[s.table] ? `${fmt(counts[s.table])} loaded` : "Nothing loaded"}
                <span style={{ marginLeft: 10 }}>{s.hint.length > 70 ? s.hint.slice(0, 68) + "…" : s.hint}</span>
              </span>
              <span>
                <input ref={(el) => { files.current[s.table] = el; }} type="file" accept=".csv" hidden
                  onChange={(e) => { upload(s.table, s.label)(e.target.files?.[0]); e.target.value = ""; }} />
                <button className="btn sm" disabled={!!busy} onClick={() => files.current[s.table]?.click()}>
                  {busy === s.table ? "Importing…" : "Choose CSV"}
                </button>
              </span>
            </div>
          ))}
          <div className="source">
            <span className="name">Slots</span>
            <span className="meta">{c.slots ? `${fmt(c.slots)} loaded` : "Nothing loaded"}
              <span style={{ marginLeft: 10 }}>{session.start_date} to {session.end_date}, {session.slots_per_day} per day</span></span>
            <button className="btn sm" disabled={!!busy} onClick={() => run("slots", async () => {
              const r = await api.generateSlots(session.id);
              return { text: `Slots: ${fmt(r.imported)} generated from the session dates.` };
            })}>{busy === "slots" ? "Generating…" : "Generate slots"}</button>
          </div>
        </Panel>

        <Panel title="Sample data" note="Synthetic, seeded">
          <p className="muted" style={{ marginBottom: 10 }}>Replaces everything in this session.</p>
          <div className="row">
            {[["small", "20 exams"], ["medium", "50 exams"], ["large", "100 exams"]].map(([name, note]) => (
              <button key={name} className="btn" disabled={!!busy} onClick={() => run(name, async () => {
                await api.loadSample(session.id, name);
                return { text: `Loaded the ${name} sample (${note}).` };
              })}>{busy === name ? "Loading…" : `${name[0].toUpperCase()}${name.slice(1)} · ${note}`}</button>
            ))}
          </div>
        </Panel>
      </div>

      {message && <Notice tone="ok" title={message.text} items={message.warnings} />}
      <ErrorNotice error={error} title="Import failed" />

      <Panel title="Check before optimizing"
        note={check ? (check.ok ? "Ready to schedule" : "Needs attention") : undefined}
        actions={<button className="btn primary" disabled={!!busy} onClick={async () => {
          setBusy("validate"); setError(null);
          try { setCheck(await api.validateData(session.id)); } catch (e) { setError(e); } finally { setBusy(null); }
        }}>{busy === "validate" ? "Checking…" : "Check data"}</button>}>
        {!check ? <Empty>Run the check to find missing data and problems that make a clash-free timetable impossible.</Empty> : (
          <div style={{ display: "grid", gap: 12 }}>
            {check.errors.length > 0 && <Notice tone="bad" title="Fix these before optimizing" items={check.errors} />}
            {check.warnings.length > 0 && <Notice tone="bad" title="Worth a look" items={check.warnings} />}
            {check.ok && <Notice tone="ok" title="Every exam fits a slot and a room." />}
            {Object.keys(check.stats).length > 0 && (
              <div className="row">
                <Chip>{fmt(check.stats.exams)} exams</Chip><Chip>{fmt(check.stats.students)} students</Chip>
                <Chip>{fmt(check.stats.rooms)} rooms</Chip><Chip>{fmt(check.stats.slots)} slots</Chip>
                <Chip>{fmt((check.stats.conflict_density ?? 0) * 100)}% of exam pairs share students</Chip>
                <Chip tone="info">needs at least {fmt(check.stats.clique_lower_bound)} slots</Chip>
              </div>
            )}
          </div>
        )}
      </Panel>
    </>
  );
}
