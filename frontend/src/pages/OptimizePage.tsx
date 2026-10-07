import { useEffect, useState } from "react";
import { api } from "../api";
import { progressOf, type Page, type Progress, type Run, type SessionDetail } from "../types";
import { Chip, Convergence, Empty, ErrorNotice, Icon, PageHead, Panel, Verdict, fmt, useAsync } from "../ui";

const METHODS: [string, string, string][] = [
  ["ga", "Genetic algorithm", "Recommended. Evolves many timetables over many rounds and gives the best results."],
  ["greedy", "Greedy (first-fit)", "Places each exam in the first slot that works. Instant, but usually worse."],
  ["greedy_cost_aware", "Greedy (cost-aware)", "Like greedy, but picks the cheapest slot for each exam."],
  ["randomized_greedy", "Randomized greedy", "Greedy with some randomness. Useful as a comparison."],
  ["random_feasible", "Random", "A random valid timetable. Shows the worst case for comparison."],
];
const methodName = (m: string) => METHODS.find(([v]) => v === m)?.[1] ?? m;

const PRESETS = {
  quick: { label: "Quick", note: "Fastest", population_size: 50, generations: 100 },
  balanced: { label: "Balanced", note: "Good default", population_size: 100, generations: 300 },
  thorough: { label: "Thorough", note: "Slower, often better", population_size: 200, generations: 600 },
} as const;
type Preset = keyof typeof PRESETS;

const DEFAULTS = {
  population_size: 100, generations: 300, crossover_rate: 0.8, mutation_rate: 0.1,
  elite_count: 5, tournament_size: 3, seed: 42,
};

const ADVANCED: [keyof typeof DEFAULTS, string, string][] = [
  ["population_size", "Population size", "How many timetables are evolved at once."],
  ["generations", "Generations", "How many rounds of improvement to run."],
  ["crossover_rate", "Crossover rate", "How often two good timetables are combined (0 to 1)."],
  ["mutation_rate", "Mutation rate", "How often small random changes are made (0 to 1)."],
  ["elite_count", "Elites kept", "The best timetables copied unchanged into the next round."],
  ["tournament_size", "Tournament size", "Higher values favour strong timetables more when choosing parents."],
  ["seed", "Random seed", "Same seed with the same settings gives the same result."],
];

export function OptimizePage({ session, go, onOpenTimetable, onChanged }: {
  session: SessionDetail | null; go: (page: Page) => void; onOpenTimetable: (id: number) => void; onChanged: () => void;
}) {
  const [params, setParams] = useState({ ...DEFAULTS });
  const [preset, setPreset] = useState<Preset | null>("balanced");
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

  const head = (
    <PageHead step="Step 2 of 3" title="Build the timetable">
      Choose how hard the optimizer should work, then press start. You can watch it improve live.
    </PageHead>
  );
  if (!session || !progressOf(session).data) {
    return <>{head}<Empty action={<button className="btn primary" onClick={() => go("data")}>Go to step 1: Add data</button>}>
      There's no data to schedule yet. Add exams, students, rooms and time slots first, or load a sample.</Empty></>;
  }

  const set = (k: keyof typeof DEFAULTS, v: string) => { setParams({ ...params, [k]: Number(v) }); if (k === "population_size" || k === "generations") setPreset(null); };
  const choosePreset = (p: Preset) => {
    setPreset(p);
    setParams({ ...params, population_size: PRESETS[p].population_size, generations: PRESETS[p].generations });
  };
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
  const finishedRun = active?.status === "completed" ? runs.data?.find((r) => r.id === active.run_id) : undefined;

  return (
    <>
      {head}

      <Panel title="Settings">
        <div className="stack">
          {isGa && (
            <div className="field">
              <label>How hard should it work?</label>
              <div className="choices">
                {(Object.keys(PRESETS) as Preset[]).map((p) => (
                  <button key={p} className="choice" aria-pressed={preset === p} onClick={() => choosePreset(p)}>
                    <b>{PRESETS[p].label}</b><span>{PRESETS[p].note} · {PRESETS[p].generations} rounds</span>
                  </button>
                ))}
              </div>
              <span className="help">Bigger datasets need more rounds. If a result still has rule violations, try Thorough.</span>
            </div>
          )}
          <div className="row">
            <button className="btn primary lg" disabled={!!running} onClick={start}>
              <Icon name="play" size={16} /> {running ? "Running…" : "Start optimizing"}
            </button>
            {!isGa && <span className="muted">Using <b>{methodName(method)}</b>. Change it under advanced settings.</span>}
          </div>
          <ErrorNotice error={error} title="Couldn't start the run" />
        </div>

        <details className="advanced">
          <summary>Advanced settings</summary>
          <div className="inner stack">
            <div className="field" style={{ maxWidth: 520 }}>
              <label>Method</label>
              <select className="input" value={method} onChange={(e) => setMethod(e.target.value)}>
                {METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
              <span className="help">{METHODS.find(([v]) => v === method)?.[2]}</span>
            </div>
            <div className="form-grid">
              {ADVANCED.filter(([k]) => isGa || k === "seed").map(([k, l, help]) => (
                <div className="field" key={k}><label>{l}</label>
                  <input className="input" type="number" step={k.endsWith("rate") ? 0.05 : 1} value={params[k]} onChange={(e) => set(k, e.target.value)} />
                  <span className="help">{help}</span></div>
              ))}
            </div>
            {isGa && <label className="check">
              <input type="checkbox" checked={earlyStop} onChange={(e) => setEarlyStop(e.target.checked)} />
              Stop early if it stops improving</label>}
          </div>
        </details>
      </Panel>

      {active && (
        <Panel title={`Run #${active.run_id}`}
          note={active.status === "completed" ? "Finished" : active.status === "failed" ? "Failed"
            : active.total_generations ? `Round ${active.current_generation} of ${active.total_generations}` : "Starting…"}>
          <div className="stack">
            {running && active.total_generations > 0 && <div className="progress"><div style={{ width: `${pct}%` }} /></div>}
            {active.error && <ErrorNotice error={new Error(active.error)} title="The run failed" />}
            {finishedRun && active.timetable_id && (finishedRun.hard_violations === 0
              ? <Verdict ok title="Done. Your timetable is clash-free."
                  action={<button className="btn primary" onClick={() => onOpenTimetable(active.timetable_id!)}>View timetable <Icon name="arrow" size={16} /></button>}>
                  Penalty score went from {fmt(finishedRun.initial_penalty)} to {fmt(finishedRun.best_penalty)} in {fmt(finishedRun.runtime_seconds, 1)} s.
                </Verdict>
              : <Verdict ok={false} title={`Finished with ${finishedRun.hard_violations} rule violation${finishedRun.hard_violations === 1 ? "" : "s"}`}
                  action={<button className="btn" onClick={() => onOpenTimetable(active.timetable_id!)}>Inspect anyway</button>}>
                  Try the Thorough setting, or check your data. There may be too few rooms or slots.
                </Verdict>)}
            {last && (
              <div className="row">
                <Chip tone={last.best_hard === 0 ? "ok" : "bad"}>{last.best_hard === 0 ? "No rule violations" : `${last.best_hard} rule violations`}</Chip>
                <Chip tone="info">Penalty score {fmt(active.best_penalty ?? last.best_penalty)}</Chip>
                <Chip>{fmt(last.feasible_fraction * 100)}% of candidates are valid</Chip>
              </div>
            )}
            {isGa || active.history.length > 1 ? (
              <>
                <Convergence points={active.history.map((h) => ({ generation: h.generation, best: h.best_penalty, mean: h.mean_penalty }))} />
                <p className="muted small">The gold line is the best timetable found so far and the grey line is the average. Lower is better, and it should fall quickly, then level off.</p>
              </>
            ) : null}
          </div>
        </Panel>
      )}

      <Panel title="Past runs" flush>
        {!runs.data?.length ? <Empty>No runs yet. Press Start optimizing above.</Empty> : (
          <div className="scroll"><table className="table">
            <thead><tr><th>Run</th><th>Method</th><th>Status</th><th className="num">Rule violations</th><th className="num">Penalty score</th>
              <th className="num">Rounds</th><th className="num">Time</th><th /></tr></thead>
            <tbody>{runs.data.map((r) => (
              <tr key={r.id}>
                <td>#{r.id}</td><td>{methodName(r.method)}</td>
                <td><Chip tone={r.status === "completed" ? "ok" : r.status === "failed" ? "bad" : "info"}>{r.status}</Chip></td>
                <td className="num">{r.hard_violations == null ? "—" : <span className={r.hard_violations ? "bad-text" : "ok-text"}>{r.hard_violations}</span>}</td>
                <td className="num"><b>{fmt(r.best_penalty)}</b></td>
                <td className="num">{r.generations_run ?? "—"}</td>
                <td className="num">{r.runtime_seconds != null ? `${fmt(r.runtime_seconds, 1)} s` : "—"}</td>
                <td className="num">{r.timetable_id && <button className="btn sm" onClick={() => onOpenTimetable(r.timetable_id!)}>View</button>}</td>
              </tr>))}</tbody>
          </table></div>
        )}
      </Panel>
    </>
  );
}
