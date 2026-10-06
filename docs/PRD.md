# PRD — Examination Timetable Optimization Using Genetic Algorithms

## 1. Product Overview

A local-first examination timetable optimization system that automatically generates a valid, high-quality university examination schedule using a Genetic Algorithm (GA).

The system solves a constrained scheduling problem:

- Assign every examination to exactly one time slot.
- Assign a suitable room.
- Prevent student clashes.
- Prevent room clashes.
- Respect room capacity.
- Minimize consecutive examinations and short gaps.
- Improve room utilization and timetable distribution.
- Provide measurable results for the research paper.

**Core technique:** Genetic Algorithm  
**Optional extension:** Fuzzy Logic preference scoring  
**Recommended stack:** React + TypeScript, FastAPI + Python, SQLite/PostgreSQL.

## 2. Goals

1. Generate a complete timetable automatically.
2. Achieve zero hard-constraint violations in accepted solutions.
3. Minimize soft-constraint penalty.
4. Show GA convergence and fitness.
5. Compare GA against a greedy/random baseline.
6. Support repeatable experiments with stored random seeds.
7. Allow CSV import and timetable export.
8. Provide an understandable dashboard suitable for an FA demonstration.
9. Keep the entire project feasible on a laptop with no paid cloud services.

## 3. Users

### Examination Coordinator / Admin
- Create examination session.
- Import exams, students, enrollments and rooms.
- Generate slots.
- Configure GA parameters and constraint weights.
- Run optimization.
- Review and validate timetable.
- Approve and export timetable.
- Compare experimental runs.

### Viewer
- View the approved timetable.
- Filter by department, semester, subject, date and room.
- Export the timetable.

## 4. Core User Flow

```text
Create Session
   ↓
Import Exam Data
   ↓
Import Student Enrollments
   ↓
Configure Rooms
   ↓
Generate Exam Slots
   ↓
Validate Data
   ↓
Build Exam Conflict Matrix
   ↓
Configure GA
   ↓
Generate Population
   ↓
Evaluate Fitness
   ↓
Selection → Crossover → Mutation → Repair
   ↓
Repeat Generations
   ↓
Best Timetable
   ↓
Validate
   ↓
Human Review
   ↓
Approve / Export
```

## 5. Functional Requirements

### FR-01 Session Management

Fields:

- session name
- academic year
- semester
- start date
- end date
- working days
- slots per day

Example:

```text
End Semester Examination
2026-27
Semester VII
20-Nov-2026 to 30-Nov-2026
2 slots/day
```

### FR-02 Exam Management

Each exam contains:

| Field | Required |
|---|---|
| exam_id | Yes |
| subject_code | Yes |
| subject_name | Yes |
| department | Yes |
| semester | Yes |
| duration_minutes | Yes |
| student_count | Yes |
| exam_type | Yes |
| priority | No |

### FR-03 Student Enrollment

Use a simple many-to-many table:

```text
student_id, exam_id
ST001, EXM001
ST001, EXM005
ST002, EXM001
```

The system precomputes an exam conflict matrix:

```text
C[i][j] = number of students enrolled in both exams
```

### FR-04 Room Management

```text
room_id
room_code
building
capacity
room_type
available
```

MVP rule:

> One exam uses one room.

Room splitting can be a future extension.

### FR-05 Slot Management

A slot contains:

```text
slot_id
date
start_time
end_time
```

### FR-06 Input Validation

Reject:

- duplicate exam IDs
- missing required fields
- invalid student references
- invalid exam references
- rooms with non-positive capacity
- empty slot sets
- duplicate enrollments

Example error:

```text
EXM017 references student ST999, but ST999 does not exist.
```

## 6. Constraint Model

### Hard Constraints

These must be satisfied.

**H1 — No student same-slot conflict**

```text
slot(exam_i) != slot(exam_j)
```

for exams sharing students.

**H2 — Room capacity**

```text
exam.student_count <= room.capacity
```

**H3 — Room collision**

At most one exam per room per slot.

**H4 — Every exam is assigned**

Every exam has exactly one valid slot and room.

**H5 — Room availability**

Only available rooms may be assigned.

### Soft Constraints

These are optimized.

- Consecutive examinations for a student.
- Very short gaps between examinations.
- Poorly distributed examinations.
- Undesirable time slots.
- Poor room utilization.

## 7. Fitness Function

Use a minimization penalty:

```text
TotalPenalty =
    WH × HardViolations
  + WC × ConsecutiveConflicts
  + WG × ShortGaps
  + WD × DistributionPenalty
  + WS × SlotPreferencePenalty
  + WR × RoomUtilizationPenalty
```

Example:

```text
WH = 10000
WC = 100
WG = 40
WD = 20
WS = 10
WR = 5
```

Fitness:

```text
Fitness = 1 / (1 + TotalPenalty)
```

Hard constraints therefore dominate all soft preferences.

## 8. Genetic Algorithm

### Chromosome

```text
Gene = (exam_id, slot_id, room_id)
```

Example:

```text
EXM01 → S03 → R01
EXM02 → S01 → R03
EXM03 → S05 → R02
```

### Recommended Initial Parameters

```text
Population = 100
Generations = 300
Crossover rate = 0.80
Mutation rate = 0.10
Elite count = 5
Tournament size = 3
```

All parameters must be configurable.

### Initialization

Use conflict-aware initialization:

1. Sort exams by conflict degree.
2. Pick a feasible slot.
3. Pick a suitable room.
4. Repeat until all exams are assigned.

### Selection

Use tournament selection because it is simple, fast and robust.

### Crossover

Use uniform or two-point crossover followed by repair.

### Mutation

Implement:

- slot mutation
- room mutation
- exam swap mutation

### Repair

After crossover/mutation:

```text
Detect room conflicts
      ↓
Detect capacity violations
      ↓
Detect student conflicts
      ↓
Move conflicting exam
      ↓
Select feasible room
      ↓
Revalidate
```

Set a maximum repair attempt count to avoid infinite loops.

### Stopping

Stop when:

```text
generation >= MAX_GENERATIONS
```

or

```text
hard violations = 0 and penalty <= target
```

or

```text
no improvement for 50 generations
```

## 9. Output

Final timetable:

| Date | Time | Subject | Department | Room | Students |
|---|---|---|---|---|---|

Optimization result:

```json
{
  "fitness": 0.0083,
  "penalty": 119,
  "hard_violations": 0,
  "generations": 300,
  "runtime_seconds": 8.7
}
```

## 10. Dashboard

KPI cards:

- Total exams
- Students
- Rooms
- Slots
- Hard violations
- Final penalty
- Fitness
- Runtime

Charts:

1. Fitness vs generation.
2. Penalty vs generation.
3. GA vs baseline.
4. Penalty distribution across runs.

Timetable filters:

```text
Department
Semester
Date
Room
Subject
```

## 11. Research Experiment Module

Each run records:

```text
run_id
seed
population_size
generations
mutation_rate
crossover_rate
elite_count
initial_penalty
final_penalty
hard_violations
runtime
```

Run the GA at least 10 times for statistical reporting.

Calculate:

```text
Mean
Median
Standard deviation
Minimum
Maximum
Improvement %
```

Improvement:

```text
((BaselinePenalty - GAPenalty) / BaselinePenalty) × 100
```

## 12. Baseline

Use a simple conflict-aware greedy scheduler:

```text
Sort exams by conflict degree
        ↓
For each exam
        ↓
Choose feasible slot
        ↓
Choose smallest sufficient room
        ↓
Validate
        ↓
Calculate penalty
```

Compare its result against GA.

## 13. Optional Fuzzy Logic Extension

Keep fuzzy logic separate from hard constraints.

Inputs:

```text
Exam gap
Slot desirability
Conflict severity
Room utilization
```

Fuzzy labels:

```text
Gap: Small / Medium / Large
Slot: Poor / Average / Good
Conflict: Low / Medium / High
```

Output:

```text
Preference: Poor / Average / Good
```

Example:

```text
IF gap is Large AND slot is Good
THEN preference is High
```

The fuzzy score can become an additional soft component of the GA fitness.

## 14. Technology

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS
- Recharts

### Backend
- Python
- FastAPI
- Pydantic
- SQLAlchemy

### Optimization
- Python
- NumPy
- Pandas
- Custom GA

### Database
- SQLite for MVP
- PostgreSQL for deployment

### Deployment
- Localhost
- Optional Docker

## 15. API

```text
POST /api/sessions
GET  /api/sessions/{id}

POST /api/exams/import
GET  /api/exams

POST /api/students/import
POST /api/rooms/import

POST /api/slots/generate

POST /api/optimization/run
GET  /api/optimization/{run_id}
GET  /api/optimization/{run_id}/progress

GET  /api/timetables/{id}
POST /api/timetables/{id}/validate
POST /api/timetables/{id}/approve

GET  /api/experiments

GET  /api/export/{timetable_id}/csv
GET  /api/export/{timetable_id}/xlsx
```

## 16. MVP

The minimum strong implementation is:

- CSV import
- Exam/student/room/slot management
- Conflict matrix
- GA optimizer
- Fitness function
- Repair operator
- Validator
- Greedy baseline
- Timetable dashboard
- Convergence graph
- Multiple-run experiment logging
- CSV export

## 17. Performance Targets

Approximate academic-prototype targets:

| Dataset | Target |
|---|---:|
| 50 exams | < 15 sec |
| 100 exams | < 60 sec |
| 500 students | < 30 sec |

Actual runtime depends on hardware and GA parameters.

## 18. Success Criteria

The project is successful when:

- every exam is scheduled;
- accepted schedules have zero hard violations;
- GA improves the baseline penalty;
- results are reproducible;
- convergence is visualized;
- multiple runs have statistical results;
- the implementation can generate the tables/graphs used in the research paper.

## 19. Future Scope

- NSGA-II multi-objective optimization
- GA + Fuzzy Logic
- GA + Simulated Annealing
- PSO/ACO comparison
- invigilator assignment
- multi-room exams
- student preference learning
- ERP integration
- historical timetable analysis
