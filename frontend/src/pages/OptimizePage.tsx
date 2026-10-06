import { useEffect, useState } from "react";
import { api } from "../api";
import type { Progress, Run, SessionDetail } from "../types";
import { Chip, Convergence, Empty, ErrorNotice, Panel, fmt, useAsync } from "../ui";

const METHODS = [
  ["ga", "Genetic algorithm"], ["greedy", "Greedy (first-fit)"], ["greedy_cost_aware", "Greedy (cost-aware)"],
  ["randomized_greedy", "Randomized greedy"], ["random_feasible", "Random"],
];

const DEFAULTS = {
  population_size: 100, generations: 300, crossover_rate: 0.8, mutation_rate: 0.1,
  elite_count: 5, tournament_size: 3, seed: 42,
};

export function OptimizePage({ session, onOpenTimetable, onChanged }: {
  session: SessionDetail | null; onOpenTimetable: (id: number) => void; onChanged: () => void;
}) {
  const [params, setParams] = useState({ ...DEFAULTS });
  const [method, setMethod] = useState("ga");
  const [earlyStop, setEarlyStop] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [active, setActive] = useState<Progress | null>(null);
  const runs = useAsync(() => (session ? api.runs(session.id) : Promise.resolve([] as Run[])), [session?.id]);

  // Poll the active run until it finishes.
  const activeId = active?.run_id;
  const running = active && (active.status === "queued" || active.status === "running");
  useEffect(() => {
    if (!activeId || !running) return;
    const timer = setInterval(async () => {
      try {
        const p = await api.progress(activeId);
        setActive(p);
        if (p.status === "completed" || p.status === "failed") { void runs.reload(); onChanged(); }
      } catch (e) { setError(e); }
    }, 700);
    return () => clearInterval(timer);
  }, [activeId, running]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!session) return <Empty>Create a session on the Data tab first.</Empty>;

  const set = (k: keyof typeof DEFAULTS, v: string) => setParams({ ...params, [k]: Number(v) });
  const start = async () => {
    setError(null);
    try {
      const run = await api.startRun({ session_id: session.id, method, params: { ...params, early_stopping: earlyStop } });
      setActive({ run_id: run.id, status: run.status, current_generation: 0, total_generations: run.total_generations,
        best_penalty: null, best_fitness: null, timetable_id: null, error: null, history: [] });
      void runs.reload();
    } catch (e) { setError(e); }
  };

  const pct = active && active.total_generations ? (active.current_generation / active.total_generations) * 100 : 0;
  const last = active?.history.at(-1);
  const isGa = method === "ga";

  return (
    <>
      <div className="page-head"><h1>Optimize</h1><span className="sub">Run the genetic algorithm or a baseline on {session.name}.</span></div>

      <Panel title="Settings" actions={<button className="btn primary" disabled={!!running} onClick={start}>{running ? "Running…" : "Start run"}</button>}>
        <div className="form-grid">
          <div className="field"><label>Method</label>
            <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select></div>
          {isGa && (
            <>
              {([["population_size", "Population"], ["generations", "Generations"], ["crossover_rate", "Crossover rate"],
                ["mutation_rate", "Mutation rate"], ["elite_count", "Elites"], ["tournament_size", "Tournament size"]] as const).map(([k, l]) => (
                <div className="field" key={k}><label>{l}</label>
                  <input className="input" type="number" step={k.endsWith("rate") ? 0.05 : 1} value={params[k]} onChange={(e) => set(k, e.target.value)} /></div>
              ))}
            </>
          )}
          <div className="field"><label>Seed</label><input className="input" type="number" value={params.seed} onChange={(e) => set("seed", e.target.value)} /></div>
          {isGa && <label className="check" style={{ alignSelf: "end", paddingBottom: 6 }}>
            <input type="checkbox" checked={earlyStop} onChange={(e) => setEarlyStop(e.target.checked)} /> Stop early when stalled</label>}
        </div>
        <div style={{ marginTop: 12 }}><ErrorNotice error={error} title="Couldn't start the run" /></div>
      </Panel>

      {active && (
        <Panel title={`Run #${active.run_id}`}
          note={active.status === "completed" ? "Completed" : active.status === "failed" ? "Failed" : `Generation ${active.current_generation} of ${active.total_generations}`}
          actions={active.timetable_id ? <button className="btn sm primary" onClick={() => onOpenTimetable(active.timetable_id!)}>Open timetable</button> : undefined}>
          {active.total_generations > 0 && <div className="progress" style={{ marginBottom: 12 }}><div style={{ width: `${pct}%` }} /></div>}
          {active.error && <ErrorNotice error={new Error(active.error)} title="The run failed" />}
          <div className="row" style={{ marginBottom: 8 }}>
            <Chip tone="info">best penalty {fmt(active.best_penalty ?? last?.best_penalty)}</Chip>
            {last && <Chip tone={last.best_hard === 0 ? "ok" : "bad"}>{last.best_hard} hard violations</Chip>}
            {last && <Chip>{fmt(last.feasible_fraction * 100)}% of population feasible</Chip>}
          </div>
          <Convergence points={active.history.map((h) => ({ generation: h.generation, best: h.best_penalty, mean: h.mean_penalty }))} />
        </Panel>
      )}

      <Panel title="Run history" flush>
        {!runs.data?.length ? <Empty>No runs yet. Start one above.</Empty> : (
          <div className="scroll"><table className="table">
            <thead><tr><th>Run</th><th>Method</th><th>Status</th><th className="num">Seed</th><th className="num">Initial</th><th className="num">Final penalty</th>
              <th className="num">Hard</th><th className="num">Generations</th><th className="num">Time (s)</th><th /></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td><td>{METHODS.find(([v]) => v === r.method)?.[1] ?? r.method}</td>
                <td><Chip tone={r.status === "completed" ? "ok" : r.status === "failed" ? "bad" : "info"}>{r.status}</Chip></td>
                <td className="num">{r.seed ?? "—"}</td><td className="num">{fmt(r.initial_penalty)}</td>
                <td className="num"><b>{fmt(r.best_penalty)}</b></td>
                <td className="num">{r.hard_violations ?? "—"}</td><td className="num">{r.generations_run ?? "—"}</td>
                <td className="num">{fmt(r.runtime_seconds, 1)}</td>
                <td>{r.timetable_id && <button className="btn sm" onClick={() => onOpenTimetable(r.timetable_id!)}>Open</button>}</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Panel>
    </>
  );
}
