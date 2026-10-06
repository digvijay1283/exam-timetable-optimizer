export interface SessionSummary {
  id: number; name: string; academic_year: string; semester: string;
  start_date: string; end_date: string; working_days: number[]; slots_per_day: number;
}
export interface SessionDetail extends SessionSummary {
  counts: { exams: number; students: number; enrollments: number; rooms: number; slots: number; timetables: number };
}
export interface ImportResult { imported: number; warnings: string[]; invalidated_timetables: number }
export interface DataCheck { ok: boolean; errors: string[]; warnings: string[]; stats: Record<string, number | null> }

export interface HistoryPoint {
  generation: number; best_penalty: number; mean_penalty: number; worst_penalty: number;
  best_hard: number; feasible_fraction: number; best_fitness: number;
}
export interface Run {
  id: number; session_id: number; method: string; status: string; seed: number | null;
  params: Record<string, unknown>; current_generation: number; total_generations: number;
  initial_penalty: number | null; best_penalty: number | null; best_fitness: number | null;
  hard_violations: number | null; generations_run: number | null; stopped_by: string | null;
  runtime_seconds: number | null; timetable_id: number | null; error: string | null;
}
export interface Progress {
  run_id: number; status: string; current_generation: number; total_generations: number;
  best_penalty: number | null; best_fitness: number | null; timetable_id: number | null;
  error: string | null; history: HistoryPoint[];
}

export interface TimetableSummary {
  id: number; session_id: number; run_id: number | null; name: string; fitness: number;
  penalty: number; hard_violations: number; status: string; breakdown: Record<string, number>;
}
export interface Entry {
  exam_id: string; subject_code: string; subject_name: string; department: string; semester: string;
  exam_type: string; students: number; duration_minutes: number; slot_id: string; date: string;
  start_time: string; end_time: string; room_id: string; room_code: string; building: string; capacity: number;
}
export interface TimetableDetail extends TimetableSummary { entries: Entry[]; total_entries: number }
export interface Validation {
  valid: boolean; hard_violations: number; student_conflicts: number; room_conflicts: number;
  capacity_violations: number; unassigned: number; unavailable_rooms: number;
  room_type_mismatches: number; duration_violations: number; details: string[];
}

export interface ExperimentSummary {
  name: string; completed: boolean; description: string; created_utc: string | null;
  runs: number | null; wall_seconds: number | null;
}
export interface ExperimentDetail {
  meta: { name: string; description: string; runs: number; seeds: number[]; workers: number };
  tables: Record<string, Record<string, string | number | null>[]>;
  convergence: Record<string, Record<string, { mean: number[]; std: number[]; seeds: number }>>;
  figures: string[];
}
