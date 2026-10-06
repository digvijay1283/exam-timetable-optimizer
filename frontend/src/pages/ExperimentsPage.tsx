import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "../api";
import { Chip, Empty, ErrorNotice, Panel, SimpleTable, fmt, useAsync } from "../ui";

const PALETTE = ["#0072b2", "#e69f00", "#009e73", "#d55e00", "#7f7f7f", "#cc79a7"];

export function ExperimentsPage() {
  const list = useAsync(() => api.experiments(), []);
  const [name, setName] = useState<string | null>(null);
  const [job, setJob] = useState<{ id: string; status: string; log_tail: string[] } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const selected = name ?? list.data?.find((e) => e.completed)?.name ?? list.data?.[0]?.name ?? null;
  const detail = useAsync(async () => {
    const ex = list.data?.find((e) => e.name === selected);
    return selected && ex?.completed ? api.experiment(selected) : null;
  }, [selected, list.data]);

  useEffect(() => {
    if (!job || job.status !== "running") return;
    const t = setInterval(async () => {
      const j = await api.experimentJob(job.id);
      setJob(j);
      if (j.status !== "running") { void list.reload(); }
    }, 2000);
    return () => clearInterval(t);
  }, [job?.id, job?.status]); // eslint-disable-line react-hooks/exhaustive-deps

  if (list.loading && !list.data) return <p className="muted">Loading experiments…</p>;
  const d = detail.data;
  const conv = d ? Object.entries(d.convergence) : [];

  return (
    <>
      <div className="page-head"><h1>Experiments</h1><span className="sub">Repeated seeded runs, compared against baselines.</span></div>
      <ErrorNotice error={error ?? list.error} />
      <Panel title="Available" flush>
        <table className="table"><tbody>
          {list.data?.map((e) => (
            <tr key={e.name} className={e.name === selected ? "is-best" : ""}>
              <td style={{ width: 120 }}><b>{e.name}</b></td>
              <td className="muted">{e.description}</td>
              <td style={{ width: 130 }}>{e.completed ? <Chip tone="ok">{e.runs} runs</Chip> : <Chip>not run yet</Chip>}</td>
              <td style={{ width: 170 }}><div className="row">
                {e.completed && <button className="btn sm" onClick={() => setName(e.name)}>View</button>}
                <button className="btn sm" disabled={job?.status === "running"} title="Runs only the first 2 seeds"
                  onClick={async () => { try { setError(null); setJob(await api.runExperiment(e.name, 2)); } catch (err) { setError(err); } }}>Quick run</button>
              </div></td>
            </tr>))}
        </tbody></table>
      </Panel>
      {job && <p className="muted">{job.status === "running" ? "Running… " : `Job ${job.status}. `}{job.log_tail.at(-1)}</p>}

      {!d ? <Empty>Select a finished experiment to see its tables and figures.</Empty> : (
        <>
          {Object.entries(d.tables).map(([title, rows]) => (
            <Panel key={title} title={title.replace(/_/g, " ")} flush>
              <SimpleTable rows={rows} highlight={(r) => r.Method === "Genetic algorithm" || r.Setting === "default"} />
            </Panel>))}
          {conv.map(([dataset, configs]) => {
            const names = Object.keys(configs);
            const len = configs[names[0]].mean.length;
            const rows = Array.from({ length: len }, (_, g) => ({ generation: g, ...Object.fromEntries(names.map((n) => [n, configs[n].mean[g]])) }));
            return (
              <Panel key={dataset} title={`Convergence on ${dataset}`} note="Mean best penalty across seeds">
                <ResponsiveContainer width="100%" height={240}>
                  <LineChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
                    <CartesianGrid stroke="#e9ecf0" vertical={false} />
                    <XAxis dataKey="generation" tick={{ fontSize: 11, fill: "#667085" }} tickLine={false} />
                    <YAxis scale="log" domain={["auto", "auto"]} tick={{ fontSize: 11, fill: "#667085" }} tickLine={false} axisLine={false} width={52} tickFormatter={(v: number) => fmt(v)} />
                    <Tooltip formatter={(v) => fmt(Number(v))} contentStyle={{ fontSize: 12, borderRadius: 6, boxShadow: "none" }} />
                    {names.length > 1 && <Legend wrapperStyle={{ fontSize: 12 }} />}
                    {names.map((n, i) => <Line key={n} dataKey={n} stroke={PALETTE[i % PALETTE.length]} strokeWidth={n === "default" ? 2.2 : 1.4} dot={false} isAnimationActive={false} />)}
                  </LineChart>
                </ResponsiveContainer>
              </Panel>);
          })}
          {d.figures.length > 0 && (
            <Panel title="Figures" note="Generated for the paper (PNG and PDF in experiments/figures)">
              <div className="figs">{d.figures.map((f) => <img key={f} src={f} alt={f.split("/").pop()} loading="lazy" />)}</div>
            </Panel>)}
        </>
      )}
    </>
  );
}
