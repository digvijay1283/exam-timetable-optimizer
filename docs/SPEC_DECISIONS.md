# Spec Decisions

Resolves ambiguities in [PRD.md](PRD.md) and [ARCHITECTURE.md](ARCHITECTURE.md). Where a decision here differs from those documents, **this file wins**. Items marked *(tunable until M4)* may change while the GA is being tuned; after the first experiment batch they are frozen so every reported number comes from one definition.

## 0. Scope and priorities

- Deliverable: FA research paper + demo. The application exists to produce reproducible evidence.
- Critical path: data → conflict matrix → fitness/validator → GA → baselines → experiments (M0–M4). API and UI (M5–M6) are kept minimal. Fuzzy extension is out of scope unless time remains.
- Data: synthetic only, from a seeded generator.

## 1. Entities and CSV contracts

Date format `YYYY-MM-DD`, time format `HH:MM`. Header names are exact. Values are trimmed.

| File | Required columns | Optional columns (default) |
|---|---|---|
| `exams.csv` | exam_id, subject_code, subject_name, department, semester, duration_minutes, student_count, exam_type | priority (0) |
| `students.csv` | student_id | department, semester |
| `enrollments.csv` | student_id, exam_id | — |
| `rooms.csv` | room_id, room_code, capacity | building, room_type (`classroom`), available (`true`) |
| `slots.csv` | slot_id, date, start_time, end_time | slot_number (derived), pref_penalty (derived) |

- `priority`: integer 0–2. 0 normal, 1 high, 2 critical. Higher priority amplifies the slot-preference penalty (§4).
- `exam_type`: `theory` or `practical`. `room_type`: `classroom`, `hall` or `lab`.
- Exam/room compatibility (hard, H6): `theory` → `classroom`/`hall`; `practical` → `lab`. Any other exam type may use any room.
- Slots are sorted chronologically on load; `slot_number` is the 0-based position within its day.
- **Enrollments are authoritative for `student_count`.** If the CSV value differs from the enrollment count, the enrollment count is used and a warning is raised. If an exam has no enrollments, the CSV value is kept, with a warning.
- All import problems are collected (not fail-fast) and reported with file and row. Errors block the run; warnings do not.

## 2. Hard constraints and the violation unit

`HardViolations` is an integer sum of the following counts. A timetable is **valid** iff it is 0.

| Id | Meaning | Counted as |
|---|---|---|
| H1 | Student clash: two exams sharing students in the same slot | Σ over same-slot exam pairs of C[i][j] (student-clash incidents). Per student with k exams in a slot this equals C(k,2). |
| H2 | Capacity: `student_count > room.capacity` | 1 per exam |
| H3 | Room collision: two exams in the same room and slot | 1 per colliding pair, i.e. C(k,2) for k exams in one (room, slot) |
| H4 | Not assigned / invalid slot or room reference / assigned more than once | 1 per exam (an entry for an unknown exam counts 1). Such an exam counts only here and is skipped by every other check. |
| H5 | Room not available | 1 per exam |
| H6 | Exam type not allowed in room type | 1 per exam |
| H7 | Exam duration longer than the slot | 1 per exam |

The validator reports each category separately, so the dashboard and the paper can show the breakdown.

## 3. Conflict matrix

`C[i][j]` = number of students enrolled in both exams, `C[i][i] = 0`, symmetric, `int32`. Built once per session as `BᵀB` where `B` is the student × exam 0/1 enrollment matrix.

Conflict degree of an exam = number of other exams it conflicts with (ties broken by weighted degree `ΣC[i][·]`).

## 4. Soft constraints (all pairwise terms use the matrix)

Slots are ordered chronologically. For a slot `s`: `date(s)`, `pos(s)` (position within the day), `day_index(s)` (index among distinct exam dates).
For a pair of slots `a ≠ b` let `dd = |date(a) − date(b)|` in **calendar days** (so a weekend counts as a gap).

For every exam pair `i < j` with `C[i][j] > 0`, `a = slot(i)`, `b = slot(j)`:

- **Consecutive** (back-to-back on the same day): `dd = 0` and `|pos(a) − pos(b)| = 1`.
- **Short gap**: not consecutive, and either (`dd = 0`, non-adjacent) or (`1 ≤ dd ≤ short_gap_days`). Default `short_gap_days = 1`.

```
ConsecutiveConflicts = Σ_{i<j} C[i][j] · consecutive(slot_i, slot_j)
ShortGaps            = Σ_{i<j} C[i][j] · short_gap(slot_i, slot_j)
```

This is exactly the per-student sum of pair costs, evaluated in O(conflicting pairs) instead of scanning students.

- **Distribution**: how unevenly exams are spread over exam days. With `E` exams and `D` exam days, `fair = ⌈E / D⌉`:
  `DistributionPenalty = Σ_d max(0, exams_on_day(d) − fair)`.
- **Slot preference**: each slot has `pref_penalty` (0 = most desirable; default = position within the day, so morning = 0).
  `SlotPreferencePenalty = Σ_i pref_penalty(slot_i) · (1 + priority_i)`.
- **Room utilization**: wasted seat fraction. `RoomUtilizationPenalty = Σ_i (capacity(room_i) − student_count_i) / capacity(room_i)`, summed over exams with a valid room.

## 5. Fitness

```
TotalPenalty = WH·HardViolations + WC·Consecutive + WG·ShortGaps + WD·Distribution + WS·SlotPref + WR·RoomUtil
Fitness      = 1 / (1 + TotalPenalty)          (display only; selection uses TotalPenalty directly)
```

Defaults: WH = 10000, WC = 100, WG = 40, WD = 20, WS = 10, WR = 5. Weights are configurable and stored with every run. The weighted form (PRD §7) is used; the unweighted sum in Architecture §15 is superseded.

## 6. Representation

A chromosome is two NumPy int arrays `slot[n_exams]` and `room[n_exams]`, indexed by exam position. `(exam, slot, room)` genes are materialised only at the API/DB boundary. Crossover inherits `(slot, room)` as a unit per exam.

## 7. Genetic algorithm *(tunable until M4)*

- Parameters (all configurable): population 100, generations 300, crossover rate 0.80, mutation rate 0.10, elite count 5, tournament size 3.
- **Mutation rate is per chromosome**: with probability `mutation_rate` a child is mutated, receiving `mutation_ops` operations (default `max(1, ⌈5 % of exams⌉)`), each chosen uniformly from slot / room / swap mutation.
- Initialization: conflict-aware randomized greedy (exams in descending conflict degree, a random feasible slot, smallest sufficient room).
- Repair: at most 100 attempts per chromosome; an irreparable violation stays in the penalty.
- Stopping: `MAX_GENERATIONS`, or hard violations = 0 and penalty ≤ target, or no improvement for 50 generations. **Comparative experiments run a fixed number of generations** (no early stopping) so convergence curves have equal length. Early stopping is a UI convenience only.

## 8. Baselines and statistics

Three reference schedulers, all validated by the same validator:

1. **Greedy** — deterministic conflict-aware scheduler (PRD §12).
2. **Randomized greedy** — same, with seeded random slot choice; run once per seed to give a distribution.
3. **Random feasible** — random slot/room within per-exam feasibility masks.

Statistics per configuration over ≥ 10 seeds (42–51): mean, median, standard deviation, min, max. `Improvement % = (Baseline − GA) / Baseline × 100`, reported only when `Baseline > 0`. Significance of GA vs randomized greedy: Mann–Whitney U.

## 9. Infeasible results

If the best timetable has `HardViolations > 0` it is stored but flagged `infeasible`, cannot be approved or exported as final, and is counted as a failure in experiment summaries. A baseline with hard violations is reported separately and excluded from Improvement %.

## 10. Reproducibility

- Every random choice uses a `numpy.random.Generator` created from the run seed and passed explicitly. No global RNG.
- A run stores: seed, GA parameters, weights, constraint parameters, dataset identifier and a hash of the input data.
- Runtime is the only non-reproducible output field.

## 11. Pre-run feasibility check ("Validate Data" step)

Errors (run blocked):
- an exam fits in no slot (duration);
- an exam has no compatible, available room with enough capacity;
- fewer slots than the size of a clique of mutually conflicting exams;
- more exams than `slots × available rooms`.

Warning: a greedy (DSATUR) colouring needs more slots than are defined, so a clash-free timetable may not exist.

## 12. Background execution

The GA is CPU-bound and runs in a separate process (`ProcessPoolExecutor`), not a FastAPI background thread. Progress is written to SQLite (WAL mode) every N generations and polled by the UI. The same process pool runs seeds in parallel for experiments.

## 13. API additions to the PRD list

`POST /api/enrollments/import`, `POST /api/baseline/run`, `POST /api/timetables/validate` (validate an arbitrary or manually edited timetable), `POST /api/experiments/run`. Dataset endpoints are scoped under `/api/sessions/{id}/…`. There is no authentication; "Viewer" is a read-only route.

## 14. Implementation notes (deviations from the original documents)

- All input tables (students, rooms as well as exams and slots) are scoped to a session, so replacing one session's data never affects another. Changing any input table deletes that session's timetables; optimization runs are kept as history.
- Experiments are file-based (`experiments/results/<name>/`) rather than database tables; `GET /api/experiments` reads them. `POST /api/experiments/run` starts a subprocess.
- `POST /api/baseline/run` and `POST /api/optimization/run` (with a `method`) share one code path.
- The UI uses plain CSS with design tokens instead of Tailwind.
- A fourth, stronger baseline (`greedy_cost_aware`) was added so the GA is compared with more than a first-fit strawman.
