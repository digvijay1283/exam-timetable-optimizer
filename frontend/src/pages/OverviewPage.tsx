import { api } from "../api";
import type { SessionDetail } from "../types";
import { Chip, Convergence, Empty, Panel, Stat, fmt, useAsync } from "../ui";

export function OverviewPage({ session, go, openTimetable }: {
  session: SessionDetail | null; go: (page: "data" | "optimize") => void; openTimetable: (id: number) => void;
}) {
  const runs = useAsync(() => (session ? api.runs(session.id) : Promise.resolve([])), [session?.id, session?.counts.timetables]);
  const latest = runs.data?.find((r) => r.method === "ga" && r.status === "completed");
  const progress = useAsync(() => (latest ? api.progress(latest.id) : Promise.resolve(null)), [latest?.id]);
  const timetable = useAsync(() => (latest?.timetable_id ? api.validateTimetable(latest.timetable_id) : Promise.resolve(null)), [latest?.timetable_id]);

  if (!session) {
    return <Empty action={<button className="btn primary" onClick={() => go("data")}>Create a session</button>}>
      Start by creating an examination session, then import or load sample data.</Empty>;
  }
  const c = session.counts;
  const v = timetable.data;

  return (
    <>
      <div className="page-head"><h1>{session.name}</h1>
        <span className="sub">{session.academic_year} · Semester {session.semester} · {session.start_date} to {session.end_date}</span></div>

      <div className="stats">
        <Stat label="Exams" value={fmt(c.exams)} />
        <Stat label="Students" value={fmt(c.students)} />
        <Stat label="Rooms" value={fmt(c.rooms)} />
        <Stat label="Slots" value={fmt(c.slots)} />
        <Stat label="Hard violations" value={latest ? latest.hard_violations : "—"} tone={latest ? (latest.hard_violations ? "bad" : "ok") : undefined} />
        <Stat label="Final penalty" value={fmt(latest?.best_penalty)} />
        <Stat label="Fitness" value={latest?.best_fitness != null ? latest.best_fitness.toExponential(2) : "—"} />
        <Stat label="Runtime" value={latest?.runtime_seconds != null ? `${fmt(latest.runtime_seconds, 1)} s` : "—"} />
      </div>

      {!latest ? (
        <Empty action={<button className="btn primary" onClick={() => go(c.exams ? "optimize" : "data")}>{c.exams ? "Run optimization" : "Add data"}</button>}>
          {c.exams ? "Data is loaded. Run the genetic algorithm to produce a timetable." : "No data in this session yet."}</Empty>
      ) : (
        <div className="grid-2">
          <Panel title="Convergence" note={`Run #${latest.id}, seed ${latest.seed}`}
            actions={latest.timetable_id ? <button className="btn sm" onClick={() => openTimetable(latest.timetable_id!)}>Open timetable</button> : undefined}>
            <Convergence points={(progress.data?.history ?? []).map((h) => ({ generation: h.generation, best: h.best_penalty, mean: h.mean_penalty }))} />
            <p className="muted" style={{ marginTop: 8 }}>
              Penalty fell from {fmt(latest.initial_penalty)} to {fmt(latest.best_penalty)} over {latest.generations_run} generations.</p>
          </Panel>
          <Panel title="Constraint status" note="Independent validator">
            {!v ? <p className="muted">Checking…</p> : (
              <table className="table" style={{ margin: "-6px -12px", width: "calc(100% + 24px)" }}><tbody>
                {([["Student clashes", v.student_conflicts], ["Room collisions", v.room_conflicts], ["Capacity violations", v.capacity_violations],
                  ["Unassigned exams", v.unassigned], ["Unavailable rooms", v.unavailable_rooms], ["Room type mismatches", v.room_type_mismatches],
                  ["Exam longer than slot", v.duration_violations]] as const).map(([l, n]) => (
                  <tr key={l}><td>{l}</td><td className="num"><Chip tone={n === 0 ? "ok" : "bad"}>{n}</Chip></td></tr>))}
              </tbody></table>
            )}
          </Panel>
        </div>
      )}
    </>
  );
}
