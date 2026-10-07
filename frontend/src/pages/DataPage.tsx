import { useRef, useState } from "react";
import { DEFAULT_SESSION, api } from "../api";
import { progressOf, type DataCheck, type Page, type SessionDetail, type SessionSummary } from "../types";
import { Chip, Empty, ErrorNotice, Icon, NextStep, Notice, PageHead, Panel, fmt } from "../ui";

const SOURCES = [
  { table: "exams", label: "Exams", desc: "One row per exam paper.",
    cols: ["exam_id", "subject_code", "subject_name", "department", "semester", "duration_minutes", "student_count", "exam_type"],
    optional: ["priority"], example: "EXM001,CSE301,Data Structures,CSE,III,180,22,theory,0" },
  { table: "students", label: "Students", desc: "One row per student.",
    cols: ["student_id"], optional: ["department", "semester"], example: "ST001,CSE,III" },
  { table: "rooms", label: "Rooms", desc: "Every room that can host an exam. Room type is classroom, hall or lab.",
    cols: ["room_id", "room_code", "capacity"], optional: ["building", "room_type", "available"], example: "R01,C101,30,Main,classroom,true" },
  { table: "enrollments", label: "Enrollments", desc: "Which student takes which exam. Upload this after exams and students.",
    cols: ["student_id", "exam_id"], optional: [], example: "ST001,EXM001" },
] as const;

const template = (s: (typeof SOURCES)[number]) =>
  `data:text/csv;charset=utf-8,${encodeURIComponent([...s.cols, ...s.optional].join(",") + "\n" + s.example + "\n")}`;

export function DataPage({ session, go, quickStart, starting, onCreated, onChanged }: {
  session: SessionDetail | null; go: (page: Page) => void; quickStart: () => void; starting: boolean;
  onCreated: (s: SessionSummary) => void; onChanged: () => void;
}) {
  return (
    <>
      <PageHead step="Step 1 of 3" title={session ? "Add your data" : "Create an exam session"}>
        {session
          ? "The optimizer needs five things: exams, students, rooms, which student takes which exam, and the time slots exams can go in."
          : "A session is one exam period, for example the end-semester exams for 2026-27. All data and timetables belong to a session."}
      </PageHead>
      {session ? <Manage session={session} go={go} onChanged={onChanged} />
        : <CreateSession onCreated={onCreated} quickStart={quickStart} starting={starting} />}
    </>
  );
}

function CreateSession({ onCreated, quickStart, starting }: { onCreated: (s: SessionSummary) => void; quickStart: () => void; starting: boolean }) {
  const [form, setForm] = useState(DEFAULT_SESSION);
  const [error, setError] = useState<unknown>(null);
  const set = (k: string, v: string | number) => setForm({ ...form, [k]: v });
  const submit = async () => {
    try { onCreated(await api.createSession(form)); } catch (e) { setError(e); }
  };
  return (
    <>
      <Notice tone="info">
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span><strong>Just exploring?</strong> Skip this form and load a ready-made sample instead.</span>
          <button className="btn sm" onClick={quickStart} disabled={starting}>{starting ? "Setting up…" : "Use sample data"}</button>
        </div>
      </Notice>
      <Panel title="Session details">
        <div className="form-grid">
          <Field label="Session name" help="Anything that helps you recognise it"><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} /></Field>
          <Field label="Academic year"><input className="input" value={form.academic_year} onChange={(e) => set("academic_year", e.target.value)} /></Field>
          <Field label="Semester"><input className="input" value={form.semester} onChange={(e) => set("semester", e.target.value)} /></Field>
          <Field label="First exam day"><input className="input" type="date" value={form.start_date} onChange={(e) => set("start_date", e.target.value)} /></Field>
          <Field label="Last exam day"><input className="input" type="date" value={form.end_date} onChange={(e) => set("end_date", e.target.value)} /></Field>
          <Field label="Exam slots per day" help="For example 2 means morning and afternoon">
            <select className="input" value={form.slots_per_day} onChange={(e) => set("slots_per_day", Number(e.target.value))}>
              {[1, 2, 3].map((n) => <option key={n}>{n}</option>)}
            </select>
          </Field>
        </div>
        <div className="row" style={{ marginTop: 20 }}>
          <button className="btn primary" onClick={submit}>Create session</button>
        </div>
        <div style={{ marginTop: 12 }}><ErrorNotice error={error} title="Couldn't create the session" /></div>
      </Panel>
    </>
  );
}

function Field({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return <div className="field"><label>{label}</label>{children}{help && <span className="help">{help}</span>}</div>;
}

function Manage({ session, go, onChanged }: { session: SessionDetail; go: (page: Page) => void; onChanged: () => void }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [message, setMessage] = useState<{ text: string; warnings: string[] } | null>(null);
  const [check, setCheck] = useState<DataCheck | null>(null);
  const files = useRef<Record<string, HTMLInputElement | null>>({});
  const c = session.counts;
  const ready = progressOf(session).data;

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
    return { text: `${label}: ${fmt(r.imported)} rows imported${r.invalidated_timetables ? `. ${r.invalidated_timetables} old timetable(s) were removed because the data changed` : ""}.`, warnings: r.warnings };
  });

  const counts: Record<string, number> = { exams: c.exams, students: c.students, rooms: c.rooms, enrollments: c.enrollments };

  return (
    <>
      <div className="grid-even">
        <Panel title="Option A: Use sample data" note="Best for trying it out">
          <p className="muted" style={{ marginBottom: 14 }}>
            Made-up but realistic university data, ready to optimize. <b>Replaces everything in this session.</b>
          </p>
          <div className="choices">
            {[["small", "Small", "20 exams · 200 students"], ["medium", "Medium", "50 exams · 500 students"], ["large", "Large", "100 exams · 800 students"]].map(([name, label, note]) => (
              <button key={name} className="choice" disabled={!!busy} onClick={() => run(name, async () => {
                await api.loadSample(session.id, name);
                return { text: `Loaded the ${label.toLowerCase()} sample (${note}). You can go straight to Optimize.` };
              })}><b>{busy === name ? "Loading…" : label}</b><span>{note}</span></button>
            ))}
          </div>
        </Panel>
        <Panel title="Option B: Upload your own" note="CSV files">
          <ol className="muted" style={{ margin: 0, paddingLeft: 20, display: "grid", gap: 6 }}>
            <li>Download a template below to see the expected columns.</li>
            <li>Fill it in with a spreadsheet tool such as Excel and save it as CSV.</li>
            <li>Upload the files in order: exams, students, rooms, then enrollments.</li>
            <li>Generate time slots from the session dates.</li>
          </ol>
        </Panel>
      </div>

      {message && <Notice tone="ok" title={message.text} items={message.warnings} />}
      <ErrorNotice error={error} title="Import failed" />

      <Panel title="Your data" note={ready ? "Everything needed is loaded" : "Upload each file below"} flush>
        {SOURCES.map((s, i) => (
          <div className="source" key={s.table}>
            <span className={`dot ${counts[s.table] ? "done" : ""}`}>{counts[s.table] ? <Icon name="check" size={12} /> : i + 1}</span>
            <div>
              <div className="row" style={{ gap: 8 }}>
                <span className="name">{s.label}</span>
                {counts[s.table] ? <Chip tone="ok">{fmt(counts[s.table])} loaded</Chip> : <Chip>not loaded</Chip>}
              </div>
              <div className="desc">{s.desc}</div>
              <div className="cols">
                {s.cols.map((col) => <code key={col}>{col}</code>)}
                {s.optional.map((col) => <code key={col} className="muted" title="Optional">{col}?</code>)}
              </div>
            </div>
            <div className="actions">
              <a className="btn sm ghost" href={template(s)} download={`${s.table}_template.csv`}><Icon name="download" size={14} /> Template</a>
              <input ref={(el) => { files.current[s.table] = el; }} type="file" accept=".csv" hidden
                onChange={(e) => { upload(s.table, s.label)(e.target.files?.[0]); e.target.value = ""; }} />
              <button className="btn sm" disabled={!!busy} onClick={() => files.current[s.table]?.click()}>
                <Icon name="upload" size={14} /> {busy === s.table ? "Importing…" : counts[s.table] ? "Replace" : "Upload CSV"}
              </button>
            </div>
          </div>
        ))}
        <div className="source">
          <span className={`dot ${c.slots ? "done" : ""}`}>{c.slots ? <Icon name="check" size={12} /> : 5}</span>
          <div>
            <div className="row" style={{ gap: 8 }}>
              <span className="name">Time slots</span>
              {c.slots ? <Chip tone="ok">{fmt(c.slots)} slots</Chip> : <Chip>not created</Chip>}
            </div>
            <div className="desc">
              The times exams can be held. Built from your session: {session.start_date} to {session.end_date}, {session.slots_per_day} per weekday.
            </div>
          </div>
          <div className="actions">
            <button className="btn sm" disabled={!!busy} onClick={() => run("slots", async () => {
              const r = await api.generateSlots(session.id);
              return { text: `${fmt(r.imported)} time slots created from the session dates.` };
            })}>{busy === "slots" ? "Generating…" : c.slots ? "Regenerate" : "Generate slots"}</button>
          </div>
        </div>
      </Panel>

      <Panel title="Check your data" note="Optional, but recommended"
        actions={<button className="btn" disabled={!!busy || !ready} onClick={async () => {
          setBusy("validate"); setError(null);
          try { setCheck(await api.validateData(session.id)); } catch (e) { setError(e); } finally { setBusy(null); }
        }}>{busy === "validate" ? "Checking…" : "Run check"}</button>}>
        {!check ? (
          <p className="muted">
            Finds problems before you optimize, for example an exam with more students than any room holds, or too few
            exam days. Exams that share a student must be on different days.
          </p>
        ) : (
          <div className="stack">
            {check.errors.length > 0 && <Notice tone="bad" title="Fix these first. A clash-free timetable isn't possible yet." items={check.errors} />}
            {check.warnings.length > 0 && <Notice tone="bad" title="Worth a look" items={check.warnings} />}
            {check.ok && <Notice tone="ok" title="Looks good. Every exam fits at least one slot and one room." />}
            {Object.keys(check.stats).length > 0 && (
              <div className="row">
                <Chip>{fmt(check.stats.exams)} exams</Chip><Chip>{fmt(check.stats.students)} students</Chip>
                <Chip>{fmt(check.stats.rooms)} rooms</Chip><Chip>{fmt(check.stats.slots)} slots</Chip>
                <Chip>{fmt((check.stats.conflict_density ?? 0) * 100)}% of exam pairs share a student</Chip>
                <Chip tone="info">at least {fmt(check.stats.clique_lower_bound)} slots needed</Chip>
              </div>
            )}
          </div>
        )}
      </Panel>

      {ready ? <NextStep title="Your data is ready." label="Go to Optimize" onClick={() => go("optimize")}>
        Next, let the algorithm build a timetable.</NextStep>
        : c.exams === 0 && <Empty>Pick a sample above, or upload your files to get started.</Empty>}
    </>
  );
}
