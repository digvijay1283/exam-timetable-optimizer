"""Reproducible experiment batches (PRD section 11, Architecture sections 23-24).

An experiment config lists datasets, seeds, GA parameter sets (and optional one-factor-at-a-time
sweeps) and baselines. Every (dataset, parameter set, seed) is one run, executed in a process
pool; every run is recorded with its seed, parameters and a fingerprint of the input data.

    python -m app.analytics.experiment_runner experiments/configs/main.json --workers 10
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from app.analytics.metrics import RunRecord, baseline_record, dataset_fingerprint, ga_record
from app.optimization.baseline import BASELINES, DETERMINISTIC, run_baseline
from app.optimization.context import OptimizationContext, build_context
from app.optimization.genetic_algorithm import run_ga
from app.optimization.mutation import default_mutation_ops
from app.optimization.params import GAParams
from app.services.import_service import load_dataset

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RESULTS_DIR = PROJECT_ROOT / "experiments" / "results"

# Fixed-length runs so convergence curves are comparable (docs/SPEC_DECISIONS.md section 7).
GA_BASE_DEFAULTS = {"early_stopping": False}


@dataclass
class ExperimentConfig:
    name: str
    datasets: list[str]
    seeds: list[int]
    description: str = ""
    ga_defaults: dict = field(default_factory=dict)
    configs: dict[str, dict] = field(default_factory=dict)  # name -> GA parameter overrides
    sweep: dict[str, list] = field(default_factory=dict)  # one-factor-at-a-time around the defaults
    baselines: list[str] = field(default_factory=list)
    baseline_seeds: list[int] | None = None
    workers: int | None = None  # preferred process count; 1 gives uncontended runtimes

    @classmethod
    def load(cls, path: str | Path) -> "ExperimentConfig":
        raw = json.loads(_resolve(path).read_text(encoding="utf-8"))
        datasets = raw.get("datasets") or [raw["dataset"]]
        return cls(
            name=raw["name"],
            datasets=list(datasets),
            seeds=list(raw["seeds"]),
            description=raw.get("description", ""),
            ga_defaults=raw.get("ga_defaults", {}),
            configs=raw.get("configs", {"default": {}}),
            sweep=raw.get("sweep", {}),
            baselines=raw.get("baselines", []),
            baseline_seeds=raw.get("baseline_seeds"),
            workers=raw.get("workers"),
        )

    def base_params(self) -> dict:
        return {**GAParams().as_dict(), **GA_BASE_DEFAULTS, **self.ga_defaults}

    def expanded_configs(self) -> dict[str, dict]:
        """Named parameter overrides: explicit configs plus one config per non-default sweep value."""
        out = dict(self.configs)
        if self.sweep:
            out.setdefault("default", {})
        base = self.base_params()
        for param, values in self.sweep.items():
            for value in values:
                if value != base.get(param):
                    out[sweep_config_name(param, value)] = {param: value}
        return out


def sweep_config_name(param: str, value) -> str:
    return f"{param}={value}"


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    if p.is_absolute() or p.exists():
        return p
    return PROJECT_ROOT / p


# --- worker side -------------------------------------------------------------------------------
_CONTEXTS: dict[str, tuple[OptimizationContext, str]] = {}


def _context(dataset_dir: str) -> tuple[OptimizationContext, str]:
    if dataset_dir not in _CONTEXTS:
        _CONTEXTS[dataset_dir] = (build_context(load_dataset(dataset_dir)), dataset_fingerprint(dataset_dir))
    return _CONTEXTS[dataset_dir]


def _run_task(task: dict) -> dict:
    ctx, fingerprint = _context(task["dataset_dir"])
    if task["kind"] == "ga":
        params = GAParams(**task["params"])
        res = run_ga(ctx, params)
        ops = params.mutation_ops if params.mutation_ops is not None else default_mutation_ops(ctx)
        record = ga_record(
            res, run_id=task["run_id"], experiment=task["experiment"], config=task["config"],
            dataset=task["dataset"], dataset_hash=fingerprint, mutation_ops=ops,
        )
        history = {
            "best": [round(h.best_penalty, 3) for h in res.history],
            "mean": [round(h.mean_penalty, 3) for h in res.history],
            "feasible": [round(h.feasible_fraction, 4) for h in res.history],
        }
        return {"record": record.as_dict(), "history": history, "task": task}
    res = run_baseline(ctx, task["method"], task["seed"])
    record = baseline_record(
        res, run_id=task["run_id"], experiment=task["experiment"], dataset=task["dataset"], dataset_hash=fingerprint
    )
    return {"record": record.as_dict(), "history": None, "task": task}


# --- orchestration -----------------------------------------------------------------------------
def build_tasks(cfg: ExperimentConfig, max_seeds: int | None = None) -> list[dict]:
    seeds = cfg.seeds[:max_seeds] if max_seeds else cfg.seeds
    baseline_seeds = (cfg.baseline_seeds or cfg.seeds)
    baseline_seeds = baseline_seeds[:max_seeds] if max_seeds else baseline_seeds
    tasks: list[dict] = []
    for dataset in cfg.datasets:
        dataset_dir = str(_resolve(dataset))
        dataset_name = Path(dataset).name
        for config_name, overrides in cfg.expanded_configs().items():
            for seed in seeds:
                params = {**cfg.base_params(), **overrides, "seed": seed}
                tasks.append({
                    "kind": "ga", "experiment": cfg.name, "dataset": dataset_name, "dataset_dir": dataset_dir,
                    "config": config_name, "seed": seed, "params": params,
                    "run_id": f"{dataset_name}:{config_name}:{seed}",
                })
        for method in cfg.baselines:
            if method not in BASELINES:
                raise ValueError(f"unknown baseline '{method}'")
            for seed in ([None] if method in DETERMINISTIC else baseline_seeds):
                tasks.append({
                    "kind": "baseline", "experiment": cfg.name, "dataset": dataset_name,
                    "dataset_dir": dataset_dir, "config": method, "method": method, "seed": seed,
                    "run_id": f"{dataset_name}:{method}:{seed}",
                })
    return tasks


def _cost(task: dict) -> float:
    """Rough relative cost, used to start the slowest runs first."""
    if task["kind"] != "ga":
        return 0.0
    p = task["params"]
    size = {"large": 5.0, "medium": 1.0, "small": 0.2}.get(task["dataset"], 1.0)
    return size * p["population_size"] * p["generations"]


def run_experiment(
    cfg: ExperimentConfig,
    workers: int | None = None,
    max_seeds: int | None = None,
    out_dir: str | Path | None = None,
    quiet: bool = False,
) -> Path:
    tasks = sorted(build_tasks(cfg, max_seeds), key=_cost, reverse=True)
    workers = workers or cfg.workers or max(1, (os.cpu_count() or 2) - 2)
    out = Path(out_dir) if out_dir else RESULTS_DIR / cfg.name
    out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    results: list[dict] = []
    if workers == 1:
        for n, task in enumerate(tasks, 1):
            results.append(_run_task(task))
            _progress(n, len(tasks), results[-1], quiet)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run_task, t) for t in tasks]
            for n, future in enumerate(as_completed(futures), 1):
                results.append(future.result())
                _progress(n, len(tasks), results[-1], quiet)

    results.sort(
        key=lambda r: (
            r["record"]["dataset"], r["record"]["method"], r["record"]["config"],
            -1 if r["record"]["seed"] is None else r["record"]["seed"],
        )
    )
    pd.DataFrame([r["record"] for r in results], columns=RunRecord.columns()).to_csv(out / "runs.csv", index=False)

    histories: dict = {}
    for r in results:
        if r["history"] is not None:
            rec = r["record"]
            histories.setdefault(rec["dataset"], {}).setdefault(rec["config"], {})[str(rec["seed"])] = r["history"]
    (out / "histories.json").write_text(json.dumps(histories), encoding="utf-8")

    wall = time.perf_counter() - started
    meta = {
        "name": cfg.name,
        "description": cfg.description,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "wall_seconds": round(wall, 1),
        "workers": workers,
        "runs": len(results),
        "python": sys.version.split()[0],
        "numpy": np.__version__,
        "platform": platform.platform(),
        "cpu_count": os.cpu_count(),
        "dataset_hashes": {Path(d).name: dataset_fingerprint(_resolve(d)) for d in cfg.datasets},
        "base_params": cfg.base_params(),
        "configs": cfg.expanded_configs(),
        "sweep": cfg.sweep,
        "baselines": cfg.baselines,
        "seeds": cfg.seeds[:max_seeds] if max_seeds else cfg.seeds,
    }
    (out / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    if not quiet:
        print(f"wrote {len(results)} runs to {out} in {wall:.1f}s")
    return out


def _progress(n: int, total: int, result: dict, quiet: bool) -> None:
    if quiet:
        return
    r = result["record"]
    print(
        f"[{n}/{total}] {r['dataset']} {r['config']} seed={r['seed']} "
        f"penalty={r['final_penalty']:.0f} hard={r['hard_violations']} {r['runtime_seconds']:.1f}s",
        flush=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a configured batch of GA/baseline experiments.")
    parser.add_argument("config", help="path to an experiment JSON config")
    parser.add_argument("--workers", type=int, help="processes (default: CPUs - 2)")
    parser.add_argument("--max-seeds", type=int, help="use only the first N seeds (smoke test)")
    parser.add_argument("--out", help="output directory (default experiments/results/<name>)")
    args = parser.parse_args()
    run_experiment(ExperimentConfig.load(args.config), args.workers, args.max_seeds, args.out)


if __name__ == "__main__":
    main()
