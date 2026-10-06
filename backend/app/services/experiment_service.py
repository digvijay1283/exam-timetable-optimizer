"""Read finished experiments from experiments/results and launch new ones as subprocesses."""
from __future__ import annotations

import json
import subprocess
import sys
import uuid
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.convergence import mean_std_band, stack_histories
from app.analytics.experiment_runner import PROJECT_ROOT, RESULTS_DIR

BACKEND_DIR = PROJECT_ROOT / "backend"
CONFIG_DIR = PROJECT_ROOT / "experiments" / "configs"
FIGURES_DIR = PROJECT_ROOT / "experiments" / "figures"
JOBS_DIR = BACKEND_DIR / "var" / "jobs"

_jobs: dict[str, dict] = {}


def available_configs() -> list[str]:
    return sorted(p.stem for p in CONFIG_DIR.glob("*.json"))


def _meta(name: str) -> dict | None:
    path = RESULTS_DIR / name / "meta.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def list_experiments() -> list[dict]:
    out = []
    for name in available_configs():
        meta = _meta(name)
        out.append({
            "name": name,
            "completed": meta is not None,
            "description": meta["description"] if meta else _config_description(name),
            "created_utc": meta["created_utc"] if meta else None,
            "runs": meta["runs"] if meta else None,
            "wall_seconds": meta["wall_seconds"] if meta else None,
        })
    return out


def _config_description(name: str) -> str:
    return json.loads((CONFIG_DIR / f"{name}.json").read_text(encoding="utf-8")).get("description", "")


def _clean(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.replace({np.nan: None}).to_json(orient="records"))


def experiment_detail(name: str) -> dict | None:
    meta = _meta(name)
    if meta is None:
        return None
    root = RESULTS_DIR / name
    runs = pd.read_csv(root / "runs.csv")
    histories = json.loads((root / "histories.json").read_text(encoding="utf-8"))

    tables = {p.stem: _clean(pd.read_csv(p)) for p in sorted((root / "tables").glob("*.csv"))}
    convergence: dict = {}
    for dataset, configs in histories.items():
        for config, per_seed in configs.items():
            best = stack_histories(per_seed, "best")
            mean, std = mean_std_band(best)
            convergence.setdefault(dataset, {})[config] = {
                "mean": [round(float(v), 3) for v in mean],
                "std": [round(float(v), 3) for v in std],
                "seeds": int(best.shape[0]),
            }
    figures = sorted(p.name for p in (FIGURES_DIR / name).glob("*.png")) if (FIGURES_DIR / name).is_dir() else []
    slim = runs[["dataset", "method", "config", "seed", "initial_penalty", "final_penalty", "hard_violations",
                 "valid", "runtime_seconds"]]
    return {
        "meta": meta,
        "tables": tables,
        "convergence": convergence,
        "runs": _clean(slim),
        "figures": [f"/api/experiments/figures/{name}/{f}" for f in figures],
    }


def launch(name: str, max_seeds: int | None = None) -> dict:
    if name not in available_configs():
        raise KeyError(name)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    job_id = uuid.uuid4().hex[:10]
    log_path = JOBS_DIR / f"{job_id}.log"
    cmd = [sys.executable, "-m", "app.analytics.run_all", "--only", name]
    if max_seeds:
        cmd += ["--max-seeds", str(max_seeds)]
    log = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=BACKEND_DIR, stdout=log, stderr=subprocess.STDOUT)
    _jobs[job_id] = {"id": job_id, "experiment": name, "proc": proc, "log": log_path, "file": log}
    return job_status(job_id)


def job_status(job_id: str) -> dict | None:
    job = _jobs.get(job_id)
    if job is None:
        return None
    code = job["proc"].poll()
    if code is not None and not job["file"].closed:
        job["file"].close()
    lines = Path(job["log"]).read_text(encoding="utf-8", errors="replace").splitlines()
    status = "running" if code is None else ("completed" if code == 0 else "failed")
    return {"id": job_id, "experiment": job["experiment"], "status": status, "log_tail": lines[-8:]}
