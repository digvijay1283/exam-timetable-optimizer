# Architecture — Examination Timetable Optimization Using Genetic Algorithms

## 1. Architecture Objective

Use a **modular monolith** rather than microservices. The system should be easy to implement, run locally, test and explain during an academic viva.

The architecture separates:

```text
Data Management
      ↓
Preprocessing
      ↓
Optimization Context
      ↓
Genetic Algorithm
      ↓
Constraint Validation
      ↓
Analytics
      ↓
Timetable Presentation
```

## 2. High-Level Architecture

```text
┌──────────────────────────────────────────────┐
│              React + TypeScript              │
│ Dashboard | Import | Config | Timetable      │
│ Optimization | Experiments                  │
└──────────────────────┬───────────────────────┘
                       │ REST
                       ▼
┌──────────────────────────────────────────────┐
│                   FastAPI                    │
│ Sessions | Exams | Students | Rooms | Slots  │
│ Optimization | Timetables | Experiments      │
└───────────────┬──────────────┬───────────────┘
                │              │
                ▼              ▼
       ┌────────────────┐  ┌──────────────────┐
       │ Data / DB      │  │ Optimization     │
       │ SQLite/Postgres│  │ Engine           │
       └────────────────┘  │ GA               │
                            │ Selection        │
                            │ Crossover        │
                            │ Mutation         │
                            │ Repair           │
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │ Constraint       │
                            │ Validator        │
                            └────────┬─────────┘
                                     ▼
                            ┌──────────────────┐
                            │ Analytics        │
                            │ Metrics/Charts   │
                            └──────────────────┘
```

## 3. Repository Structure

```text
exam-timetable-optimizer/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── sessions.py
│   │   │   ├── exams.py
│   │   │   ├── students.py
│   │   │   ├── rooms.py
│   │   │   ├── slots.py
│   │   │   ├── optimization.py
│   │   │   ├── timetables.py
│   │   │   └── experiments.py
│   │   ├── models/
│   │   │   ├── session.py
│   │   │   ├── exam.py
│   │   │   ├── student.py
│   │   │   ├── enrollment.py
│   │   │   ├── room.py
│   │   │   ├── slot.py
│   │   │   ├── timetable.py
│   │   │   └── experiment.py
│   │   ├── schemas/
│   │   ├── services/
│   │   │   ├── import_service.py
│   │   │   ├── conflict_service.py
│   │   │   ├── slot_service.py
│   │   │   └── timetable_service.py
│   │   ├── optimization/
│   │   │   ├── chromosome.py
│   │   │   ├── population.py
│   │   │   ├── fitness.py
│   │   │   ├── selection.py
│   │   │   ├── crossover.py
│   │   │   ├── mutation.py
│   │   │   ├── repair.py
│   │   │   ├── validator.py
│   │   │   ├── genetic_algorithm.py
│   │   │   └── fuzzy_preferences.py
│   │   ├── analytics/
│   │   │   ├── metrics.py
│   │   │   ├── statistics.py
│   │   │   └── convergence.py
│   │   ├── database/
│   │   └── core/
│   └── tests/
│
├── frontend/
│   └── src/
│       ├── pages/
│       ├── components/
│       ├── services/
│       └── types/
│
├── data/
│   ├── exams.csv
│   ├── students.csv
│   ├── enrollments.csv
│   ├── rooms.csv
│   └── slots.csv
│
├── experiments/
│   ├── configs/
│   ├── results/
│   └── figures/
│
├── docs/
│   ├── PRD.md
│   └── ARCHITECTURE.md
└── README.md
```

## 4. Database Model

```text
SESSION
  │
  ├── EXAMS
  │     │
  │     └── ENROLLMENTS ── STUDENTS
  │
  ├── SLOTS
  │
  └── TIMETABLES
          │
          └── TIMETABLE_ENTRIES
                    ├── EXAM
                    ├── SLOT
                    └── ROOM

OPTIMIZATION_RUN
  └── generated TIMETABLE
```

### Tables

`session`

```text
id
name
academic_year
semester
start_date
end_date
created_at
```

`exam`

```text
id
session_id
subject_code
subject_name
department
semester
duration_minutes
student_count
priority
```

`student`

```text
id
student_code
department
semester
```

`enrollment`

```text
id
student_id
exam_id
```

`room`

```text
id
room_code
building
capacity
room_type
available
```

`slot`

```text
id
session_id
date
start_time
end_time
slot_number
```

`timetable`

```text
id
session_id
name
fitness
penalty
hard_violations
status
created_at
```

`timetable_entry`

```text
id
timetable_id
exam_id
slot_id
room_id
```

`optimization_run`

```text
id
session_id
population_size
generations
crossover_rate
mutation_rate
elite_count
seed
initial_penalty
best_penalty
best_fitness
runtime_seconds
created_at
```

## 5. Input Processing

```text
CSV / Form
    ↓
Schema Validation
    ↓
Normalization
    ↓
Database
    ↓
Conflict Matrix
    ↓
Optimization Context
```

Do not access the database repeatedly inside the GA loop.

Create an in-memory object:

```python
OptimizationContext(
    exams,
    students,
    rooms,
    slots,
    conflict_matrix,
    constraints,
    weights
)
```

The GA should operate on this object.

## 6. Conflict Matrix

For every pair of exams:

```text
conflict[i][j] =
number of students enrolled in both exams
```

Example:

```text
       E1   E2   E3
E1      0   20    0
E2     20    0    7
E3      0    7    0
```

This matrix is generated once before optimization.

Same-slot penalty:

```python
if slot[a] == slot[b]:
    penalty += conflict[a][b]
```

This is substantially faster than repeatedly scanning all students.

## 7. Chromosome

Recommended representation:

```python
class Gene:
    exam_id: int
    slot_id: int
    room_id: int

class Chromosome:
    genes: list[Gene]
    penalty: float
    fitness: float
```

Example:

```text
EXM01 → S03 → R01
EXM02 → S01 → R03
EXM03 → S05 → R02
```

One chromosome represents one complete timetable.

## 8. GA Pipeline

```text
Generate Initial Population
            ↓
        Evaluate
            ↓
       Keep Elites
            ↓
   Tournament Selection
            ↓
        Crossover
            ↓
         Mutation
            ↓
          Repair
            ↓
        Validation
            ↓
        Evaluation
            ↓
      New Population
            ↓
      Record Metrics
            ↓
      Stop Condition?
       /                No             Yes
     ↓               ↓
  Repeat       Best Timetable
```

## 9. Initialization

Use conflict-aware initialization:

```text
1. Calculate conflict degree for each exam.
2. Sort exams by descending conflict degree.
3. Select a random feasible slot.
4. Select a smallest sufficient room.
5. Continue.
```

This is better than completely random initialization while remaining easy to implement.

## 10. Selection

Use tournament selection:

```text
Randomly choose K chromosomes
        ↓
Compare penalties
        ↓
Choose lowest penalty
        ↓
Repeat
```

Recommended:

```text
K = 3
```

## 11. Crossover

Uniform crossover is straightforward:

```text
Parent A: A B C D E F
Parent B: X Y Z P Q R

Child:    A Y C P E R
```

Then run repair.

For a stronger implementation, preserve good exam assignments from elite parents.

## 12. Mutation

Implement three simple operators:

### Slot Mutation

```text
EXM01 → S03
       ↓
EXM01 → S06
```

### Room Mutation

```text
EXM01 → R01
       ↓
EXM01 → R04
```

### Swap Mutation

```text
EXM01 → S01
EXM02 → S05

       ↓

EXM01 → S05
EXM02 → S01
```

Choose the mutation operator randomly.

## 13. Repair

Repair must run after crossover and mutation.

```text
Candidate
   ↓
Room collision?
   ↓ yes
Move exam
   ↓
Capacity violation?
   ↓ yes
Choose larger room
   ↓
Student conflict?
   ↓ yes
Move exam to feasible slot
   ↓
Validate again
```

Maximum attempts:

```text
100
```

If a violation cannot be repaired, leave it as a penalty so the GA can still compare the chromosome.

## 14. Constraint Engine

Keep constraint checks modular:

```text
constraints/
├── student_conflict.py
├── room_conflict.py
├── room_capacity.py
├── valid_slot.py
├── consecutive_exam.py
├── short_gap.py
└── distribution.py
```

Or, for a smaller project, keep them as functions inside:

```text
optimization/fitness.py
```

The modular version is better for the research project.

## 15. Fitness Architecture

Implement:

```python
hard_penalty(schedule)
consecutive_penalty(schedule)
gap_penalty(schedule)
distribution_penalty(schedule)
slot_preference_penalty(schedule)
room_utilization_penalty(schedule)
```

Then:

```python
total_penalty = (
    hard_penalty(schedule)
    + consecutive_penalty(schedule)
    + gap_penalty(schedule)
    + distribution_penalty(schedule)
    + slot_preference_penalty(schedule)
    + room_utilization_penalty(schedule)
)
```

## 16. Room Assignment

For an exam with 80 students:

```text
R101 = 120
R102 = 90
R103 = 60
```

Choose `R102` because it is the smallest room with sufficient capacity.

This improves room utilization without complicating the GA.

## 17. Timetable Validation

Validator response:

```json
{
  "valid": true,
  "hard_violations": 0,
  "student_conflicts": 0,
  "room_conflicts": 0,
  "capacity_violations": 0
}
```

The validator should be independent from the optimizer.

That allows the same validator to check:

- GA schedules
- baseline schedules
- manually edited schedules
- final approved schedules

## 18. Optional Fuzzy Layer

```text
Gap
Slot Preference
Conflict Severity
Room Utilization
       ↓
  Fuzzy Inference
       ↓
Preference Score
       ↓
GA Soft Penalty
```

Fuzzy logic should never override hard constraints.

Example:

```text
IF gap = Large AND slot = Good
THEN preference = High
```

## 19. API Architecture

### Sessions

```http
POST /api/sessions
GET /api/sessions
GET /api/sessions/{id}
```

### Data

```http
POST /api/exams/import
POST /api/students/import
POST /api/rooms/import
POST /api/slots/generate
```

### Optimization

```http
POST /api/optimization/run
GET /api/optimization/{run_id}
GET /api/optimization/{run_id}/progress
```

### Timetable

```http
GET /api/timetables/{id}
POST /api/timetables/{id}/validate
POST /api/timetables/{id}/approve
```

### Experiments

```http
GET /api/experiments
POST /api/experiments/run
```

### Export

```http
GET /api/export/{timetable_id}/csv
GET /api/export/{timetable_id}/xlsx
```

## 20. Optimization Job

For small datasets:

```text
POST /optimization/run
       ↓
GA executes
       ↓
Return result
```

For larger datasets:

```text
POST /optimization/run
       ↓
Create optimization_run
       ↓
FastAPI background task
       ↓
GA executes
       ↓
Progress is saved
       ↓
Frontend polls status
```

Avoid Celery/Redis in the first version.

## 21. Frontend Architecture

```text
App
├── Dashboard
│   ├── KPI Cards
│   ├── Convergence Chart
│   └── Constraint Summary
├── Data Import
│   ├── Exams
│   ├── Students
│   ├── Enrollments
│   └── Rooms
├── Configuration
│   ├── Slots
│   ├── Constraints
│   └── GA Parameters
├── Optimization
│   ├── Start Run
│   ├── Progress
│   └── Results
├── Timetable
│   ├── Calendar/Table
│   ├── Filters
│   └── Validation
└── Experiments
    ├── Run Comparison
    ├── Statistics
    └── Graphs
```

## 22. Dashboard Layout

```text
┌────────────────────────────────────────────────────────────┐
│ Examination Timetable Optimizer                            │
├────────────────────────────────────────────────────────────┤
│ Exams │ Students │ Rooms │ Slots │ Penalty │ Hard Errors   │
├────────────────────────────────────────────────────────────┤
│                                                            │
│                 GA Convergence Chart                       │
│                                                            │
├────────────────────────────────────────────────────────────┤
│ Constraint Status                                          │
│ ✓ Student conflicts       0                                │
│ ✓ Room conflicts          0                                │
│ ✓ Capacity violations     0                                │
├────────────────────────────────────────────────────────────┤
│ Best Timetable                                             │
│ Date | Time | Subject | Department | Room | Students       │
└────────────────────────────────────────────────────────────┘
```

## 23. Experiment Architecture

Every run must store:

```text
seed
population size
generation count
mutation rate
crossover rate
elite count
initial penalty
final penalty
hard violations
runtime
```

Use seeds such as:

```text
42
43
44
45
...
51
```

This makes the research results reproducible.

## 24. Experimental Design

### Population Size

```text
50, 100, 150, 200
```

### Mutation

```text
0.05, 0.10, 0.20, 0.30
```

### Crossover

```text
0.60, 0.80, 0.90
```

### Generations

```text
100, 200, 300, 500
```

Do not test every possible combination. Use controlled experiments to keep runtime practical.

## 25. Evaluation

Report:

```text
Hard Constraint Violations
Final Penalty
Fitness
Runtime
Mean
Median
Standard Deviation
Minimum
Maximum
```

Compare:

```text
Greedy Baseline vs Genetic Algorithm
```

Recommended figures:

1. GA convergence curve.
2. Baseline vs GA bar chart.
3. Penalty boxplot across repeated runs.
4. Mutation/population sensitivity plot.

## 26. Testing

### Unit Tests

```text
test_conflict_matrix
test_student_constraint
test_room_capacity
test_room_collision
test_fitness
test_mutation
test_crossover
test_repair
test_validator
```

### Integration Test

```text
CSV
 ↓
Validation
 ↓
Conflict Matrix
 ↓
GA
 ↓
Validator
 ↓
Timetable
```

### Important Cases

1. Two exams sharing students cannot share a slot.
2. Room capacity cannot be exceeded.
3. One room cannot host two exams simultaneously.
4. Every exam must be assigned.
5. A manually modified invalid timetable must be rejected.

## 27. Deployment

For demonstration:

```text
Browser
   │
   ▼
React/Vite :5173
   │
   │ HTTP
   ▼
FastAPI :8000
   │
   ├── SQLite
   └── GA Engine
```

Everything can run on one laptop.

Docker is optional.

## 28. Recommended Implementation Sequence

### Phase 1
Database models and CSV import.

### Phase 2
Slot generation and validation.

### Phase 3
Conflict matrix.

### Phase 4
Chromosome and timetable representation.

### Phase 5
Constraint engine and fitness.

### Phase 6
Selection, crossover, mutation and repair.

### Phase 7
GA loop and convergence logging.

### Phase 8
Greedy baseline.

### Phase 9
Experiment runner and statistics.

### Phase 10
FastAPI endpoints.

### Phase 11
React dashboard.

### Phase 12
Paper figures, tables and final evaluation.

## 29. What Not to Build

Avoid:

- microservices
- Kubernetes
- Kafka
- distributed GA
- LLM integration
- complicated authentication
- real-time WebSocket infrastructure
- mobile application
- ERP integration

These are unnecessary for the FA objective.

## 30. Final Architecture

```text
                     ┌─────────────────┐
                     │   React UI      │
                     └────────┬────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │    FastAPI      │
                     │    REST API     │
                     └────────┬────────┘
                              │
             ┌────────────────┼────────────────┐
             ▼                ▼                ▼
       ┌──────────┐    ┌─────────────┐   ┌───────────┐
       │ Database │    │ Preprocessor│   │ Analytics │
       └──────────┘    └──────┬──────┘   └───────────┘
                              │
                              ▼
                     ┌─────────────────┐
                     │ Optimization    │
                     │ Context        │
                     └────────┬────────┘
                              ▼
                     ┌─────────────────┐
                     │ Genetic         │
                     │ Algorithm       │
                     │                 │
                     │ Selection       │
                     │ Crossover       │
                     │ Mutation        │
                     │ Repair          │
                     └────────┬────────┘
                              ▼
                     ┌─────────────────┐
                     │ Constraint      │
                     │ Validator       │
                     └────────┬────────┘
                              ▼
                     ┌─────────────────┐
                     │ Best Timetable  │
                     └─────────────────┘
```

## 31. Research Positioning

The project should not be presented as merely:

> “We used a Genetic Algorithm to make a timetable.”

A stronger description is:

> **A constraint-aware Genetic Algorithm framework for automated examination timetable generation using conflict-aware initialization, weighted fitness evaluation, constraint-based repair, and empirical comparison with a greedy baseline.**

This is feasible on a student laptop, sufficiently substantial for the FA research paper, and straightforward to demonstrate.
