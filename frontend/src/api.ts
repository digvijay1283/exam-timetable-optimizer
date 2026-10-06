import type {
  DataCheck, ExperimentDetail, ExperimentSummary, ImportResult, Progress, Run,
  SessionDetail, SessionSummary, TimetableDetail, TimetableSummary, Validation,
} from "./types";

export class ApiError extends Error {
  constructor(public messages: string[], public status: number) {
    super(messages[0] ?? "Request failed");
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    let messages = [`${res.status} ${res.statusText}`];
    try {
      const body = await res.json();
      const d = body.detail;
      if (d?.errors) messages = d.errors;
      else if (typeof d === "string") messages = [d];
      else if (Array.isArray(d)) messages = d.map((e: { loc?: string[]; msg: string }) => `${(e.loc ?? []).slice(1).join(".")}: ${e.msg}`);
    } catch { /* keep status text */ }
    throw new ApiError(messages, res.status);
  }
  return res.json() as Promise<T>;
}

const json = (body: unknown): RequestInit => ({
  method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
});

export const api = {
  health: () => request<{ status: string }>("/api/health"),
  sessions: () => request<SessionSummary[]>("/api/sessions"),
  session: (id: number) => request<SessionDetail>(`/api/sessions/${id}`),
  createSession: (body: Record<string, unknown>) => request<SessionSummary>("/api/sessions", json(body)),
  loadSample: (id: number, name: string) => request<SessionDetail>(`/api/sessions/${id}/load-sample`, json({ name })),
  validateData: (id: number) => request<DataCheck>(`/api/sessions/${id}/validate`, { method: "POST" }),
  generateSlots: (id: number) => request<ImportResult>(`/api/sessions/${id}/slots/generate`, { method: "POST" }),
  upload: (id: number, table: string, file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<ImportResult>(`/api/sessions/${id}/${table}/import`, { method: "POST", body: form });
  },
  runs: (id: number) => request<Run[]>(`/api/sessions/${id}/runs`),
  startRun: (body: Record<string, unknown>) => request<Run>("/api/optimization/run", json(body)),
  progress: (runId: number) => request<Progress>(`/api/optimization/${runId}/progress`),
  timetables: (id: number) => request<TimetableSummary[]>(`/api/sessions/${id}/timetables`),
  timetable: (id: number, filters: Record<string, string> = {}) => {
    const q = new URLSearchParams(Object.entries(filters).filter(([, v]) => v));
    return request<TimetableDetail>(`/api/timetables/${id}?${q}`);
  },
  validateTimetable: (id: number) => request<Validation>(`/api/timetables/${id}/validate`, { method: "POST" }),
  approve: (id: number) => request<TimetableSummary>(`/api/timetables/${id}/approve`, { method: "POST" }),
  experiments: () => request<ExperimentSummary[]>("/api/experiments"),
  experiment: (name: string) => request<ExperimentDetail>(`/api/experiments/${name}`),
  runExperiment: (name: string, maxSeeds?: number) =>
    request<{ id: string; status: string; log_tail: string[] }>("/api/experiments/run", json({ name, max_seeds: maxSeeds })),
  experimentJob: (id: string) => request<{ id: string; status: string; log_tail: string[] }>(`/api/experiments/jobs/${id}`),
};
