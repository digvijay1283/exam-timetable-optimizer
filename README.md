# Examination Timetable Optimizer

A constraint-aware genetic algorithm that builds a clash-free university exam timetable, with a
greedy-baseline comparison, repeatable seeded experiments and a small web app.

Design documents: [PRD](docs/PRD.md), [Architecture](docs/ARCHITECTURE.md),
[Spec decisions](docs/SPEC_DECISIONS.md) (the definitions every number in the paper relies on).

## Setup (Windows, Python 3.12, Node 20+)

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
cd frontend; npm install
```

## Run the app

```powershell
# terminal 1: API on :8000
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:create_app --factory --port 8000
# terminal 2: UI on :5173
cd frontend; npm run dev
```

Open http://localhost:5173, then: **Data** → load a sample (or upload CSVs) → **Check data** →
**Optimize** → **Timetable** (validate, approve, export CSV/Excel).

## Reproduce the paper's results

```powershell
cd backend
..\.venv\Scripts\python -m app.analytics.run_all          # main, ablation, sensitivity, scaling
..\.venv\Scripts\python -m app.analytics.run_all --only main --max-seeds 2   # quick check
```

Tables (CSV + Markdown) land in `experiments/results/<name>/tables/`, figures (PNG + PDF) in
`experiments/figures/<name>/`. Seeds 42–51 are fixed in `experiments/configs/*.json`, so reruns give
identical penalties (only runtimes vary). The `scaling` experiment runs single-process so its
runtimes are not distorted by contention.

## Datasets

`python -m app.services.data_generator --preset medium --seed 42 --out ../data/medium`
(presets: small 20 exams, medium 50, large 100). CSV formats are in SPEC_DECISIONS.md section 1.

## Tests

```powershell
cd backend; ..\.venv\Scripts\python -m pytest
```

## Layout

`backend/app/optimization` GA, fitness, constraints, repair, baselines, independent validator ·
`backend/app/analytics` experiment runner, statistics, report · `backend/app/api` REST endpoints ·
`frontend/src` React UI · `data/` sample CSVs · `experiments/` configs, results, figures.
