import { api } from "../api";
import { progressOf, type Page, type SessionDetail } from "../types";
import { Chip, Convergence, ErrorNotice, Icon, PageHead, Panel, Stat, Verdict, fmt, useAsync } from "../ui";

const HARD_RULES: [string, string][] = [
  ["No student clashes", "A student never has two exams in the same time slot."],
  ["One exam per day", "A student never sits more than one exam on the same day."],
  ["No double-booked rooms", "Each room holds at most one exam per slot."],
  ["Rooms are big enough", "Every exam gets a room with enough seats."],
  ["Right kind of room", "Practicals go to labs, written papers to classrooms or halls."],
  ["Exams fit their slot", "Every exam is scheduled, in an available room, within the slot's length."],
];
const SOFT_RULES: [string, string][] = [
  ["Leave rest days", "Avoid giving a student exams on consecutive days where possible."],
  ["Spread exams evenly", "No day is overloaded while others sit empty."],
  ["Prefer good slots", "Important exams avoid unpopular times."],
  ["Don't waste seats", "Use the smallest room that fits."],
];

export function OverviewPage({ session, go, openTimetable, quickStart, starting, startError }: {
  session: SessionDetail | null; go: (page: Page) => void; openTimetable: (id: number) => void;
  quickStart: () => void; starting: boolean; startError: unknown;
}) {
  const progress = progressOf(session);
  if (!session || session.counts.exams === 0) {
    return <Welcome go={go} quickStart={quickStart} starting={starting} startError={startError} />;
  }
  return <Dashboard session={session} progress={progress} go={go} openTimetable={openTimetable} />;
}

function Welcome({ go, quickStart, starting, startError }: {
  go: (page: Page) => void; quickStart: () => void; starting: boolean; startError: unknown;
}) {
  return (
    <>
      <section className="hero">
        <span className="eyebrow-pill"><Icon name="calendar" size={14} /> University exam scheduling</span>
        <h1>Build a clash-free exam timetable automatically</h1>
        <p className="lead">
          Tell it which exams you have, who is taking them, which rooms are free and which dates you can use.
          It searches through thousands of possible timetables and gives you the best one it finds: no student
          sits more than one exam a day, every exam gets a suitable room, and exams are spread out so students get rest between them.
        </p>
        <div className="row">
          <button className="btn primary lg" onClick={quickStart} disabled={starting}>
            <Icon name="play" size={16} /> {starting ? "Setting up…" : "Try it with sample data"}
          </button>
          <button className="btn lg" onClick={() => go("data")}>Use my own data</button>
        </div>
        <p className="fine">The sample has 20 exams, 200 students and 8 rooms. Running the optimizer on it takes a few seconds.</p>
        <ErrorNotice error={startError} title="Couldn't load the sample" />
      </section>

      <section>
        <h2 className="section-title">How it works</h2>
        <p className="section-sub">Three steps. Follow the numbered tabs at the top of the page.</p>
        <div className="steps">
          <StepCard n={1} title="Add your data">
            Upload CSV files of exams, students, rooms and enrollments, or load a sample. A quick check flags problems,
            such as an exam with no room big enough.
          </StepCard>
          <StepCard n={2} title="Optimize">
            Press start. A <b>genetic algorithm</b> begins with many random timetables. In each round
            (a "generation") it keeps the best ones, combines them and makes small changes, so the timetable gets better every round.
          </StepCard>
          <StepCard n={3} title="Review and export">
            See the timetable as a calendar grid or a list, filter by department or room, confirm it breaks no rules,
            approve it and download it as Excel or CSV.
          </StepCard>
        </div>
      </section>

      <RulesExplainer />
    </>
  );
}

function StepCard({ n, title, children, done, current, action }: {
  n: number; title: string; children: React.ReactNode; done?: boolean; current?: boolean; action?: React.ReactNode;
}) {
  return (
    <div className={`step-card ${current ? "current" : ""}`}>
      <span className={`step-badge ${done ? "done" : ""}`}>{done ? <Icon name="check" size={16} /> : n}</span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action && <div className="step-foot">{action}</div>}
    </div>
  );
}

function RulesExplainer() {
  return (
    <section>
      <h2 className="section-title">What makes a good timetable</h2>
      <p className="section-sub">
        Every timetable gets a <b>penalty score</b>, where lower is better. Breaking a must-have rule costs far more than
        missing a nice-to-have, so the optimizer fixes rule breaks first and then works on comfort.
      </p>
      <div className="rules">
        <Panel title="Must-have rules" note="Never broken in a valid timetable">
          <ul>{HARD_RULES.map(([t, d]) => (
            <li key={t}><span className="ok-text"><Icon name="check" /></span><div><b>{t}</b><span className="muted">{d}</span></div></li>
          ))}</ul>
        </Panel>
        <Panel title="Nice-to-haves" note="Improved as much as possible">
          <ul>{SOFT_RULES.map(([t, d]) => (
            <li key={t}><span style={{ color: "var(--gold)" }}><Icon name="arrow" /></span><div><b>{t}</b><span className="muted">{d}</span></div></li>
          ))}</ul>
        </Panel>
      </div>
    </section>
  );
}

function Dashboard({ session, progress, go, openTimetable }: {
  session: SessionDetail; progress: ReturnType<typeof progressOf>; go: (page: Page) => void; openTimetable: (id: number) => void;
}) {
  const runs = useAsync(() => api.runs(session.id), [session.id, session.counts.timetables]);
  const latest = runs.data?.find((r) => r.status === "completed" && r.timetable_id);
  const history = useAsync(() => (latest ? api.progress(latest.id) : Promise.resolve(null)), [latest?.id]);
  const check = useAsync(() => (latest?.timetable_id ? api.validateTimetable(latest.timetable_id) : Promise.resolve(null)), [latest?.timetable_id]);
  const c = session.counts;
  const v = check.data;

  return (
    <>
      <PageHead title={session.name}>
        {session.academic_year} · Semester {session.semester} · exams from {session.start_date} to {session.end_date}
      </PageHead>

      <div className="steps" style={{ marginTop: 0 }}>
        <StepCard n={1} title="Add data" done={progress.data} current={progress.next === "data"}
          action={<button className={`btn sm ${progress.next === "data" ? "primary" : ""}`} onClick={() => go("data")}>
            {progress.data ? "Review data" : "Add data"}</button>}>
          {progress.data
            ? `${fmt(c.exams)} exams, ${fmt(c.students)} students, ${fmt(c.rooms)} rooms and ${fmt(c.slots)} time slots loaded.`
            : "Some data is still missing. Add exams, students, enrollments, rooms and slots."}
        </StepCard>
        <StepCard n={2} title="Optimize" done={progress.optimized} current={progress.next === "optimize"}
          action={<button className={`btn sm ${progress.next === "optimize" ? "primary" : ""}`} onClick={() => go("optimize")} disabled={!progress.data}>
            {progress.optimized ? "Run again" : "Start optimizing"}</button>}>
          {progress.optimized ? `${c.timetables} timetable${c.timetables === 1 ? "" : "s"} generated so far.` : "Let the algorithm build a timetable from your data."}
        </StepCard>
        <StepCard n={3} title="Review and export" current={progress.next === "timetable"}
          action={<button className={`btn sm ${progress.next === "timetable" ? "primary" : ""}`} disabled={!progress.optimized}
            onClick={() => (latest?.timetable_id ? openTimetable(latest.timetable_id) : go("timetable"))}>Open timetable</button>}>
          Check the result, approve it and download it for students and staff.
        </StepCard>
      </div>

      {latest && (
        <>
          <section className="stack">
            <h2 className="section-title">Latest result</h2>
            {latest.hard_violations === 0
              ? <Verdict ok title="Clash-free timetable ready"
                  action={<button className="btn primary" onClick={() => openTimetable(latest.timetable_id!)}>View timetable <Icon name="arrow" size={16} /></button>}>
                  It breaks none of the must-have rules. The remaining penalty of {fmt(latest.best_penalty)} comes only from nice-to-haves.
                </Verdict>
              : <Verdict ok={false} title={`${latest.hard_violations} rule violation${latest.hard_violations === 1 ? "" : "s"} remain`}
                  action={<button className="btn" onClick={() => go("optimize")}>Try again</button>}>
                  Try a longer run, or go back to step 1 and check the data. There may not be enough rooms or time slots.
                </Verdict>}
            <div className="stats">
              <Stat label="Rule violations" hint="Must be 0" value={latest.hard_violations ?? "—"} tone={latest.hard_violations ? "bad" : "ok"} />
              <Stat label="Penalty score" hint="Lower is better" value={fmt(latest.best_penalty)} />
              <Stat label="Starting penalty" hint="Before optimizing" value={fmt(latest.initial_penalty)} />
              <Stat label="Time taken" value={latest.runtime_seconds != null ? `${fmt(latest.runtime_seconds, 1)} s` : "—"} />
            </div>
          </section>
          <div className={latest.method === "ga" ? "grid-2" : ""}>
            {latest.method === "ga" && <Panel title="How the timetable improved" note={`Run #${latest.id}`}>
              <Convergence points={(history.data?.history ?? []).map((h) => ({ generation: h.generation, best: h.best_penalty, mean: h.mean_penalty }))} />
              <p className="muted small" style={{ marginTop: 8 }}>
                Each point is one generation. The penalty fell from {fmt(latest.initial_penalty)} to {fmt(latest.best_penalty)} over {latest.generations_run} generations.
              </p>
            </Panel>}
            <Panel title="Rule check" note="Checked independently">
              {!v ? <p className="muted">Checking…</p> : (
                <ul className="checklist">
                  {([["Student clashes", v.student_conflicts], ["Two exams in one day", v.same_day_conflicts], ["Double-booked rooms", v.room_conflicts], ["Rooms too small", v.capacity_violations],
                    ["Unscheduled exams", v.unassigned], ["Unavailable rooms used", v.unavailable_rooms], ["Wrong room type", v.room_type_mismatches],
                    ["Exam longer than slot", v.duration_violations]] as const).map(([l, n]) => (
                    <li key={l}><span className={n === 0 ? "ok-text" : "bad-text"}><Icon name={n === 0 ? "check" : "alert"} /></span>
                      <span className="label">{l}</span><Chip tone={n === 0 ? "ok" : "bad"}>{n}</Chip></li>))}
                </ul>
              )}
            </Panel>
          </div>
        </>
      )}

      <RulesExplainer />
    </>
  );
}
