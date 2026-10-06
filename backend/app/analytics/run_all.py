"""Run every configured experiment and build its tables and figures.

    python -m app.analytics.run_all                  # main, ablation, sensitivity, scaling
    python -m app.analytics.run_all --only main      # a subset
    python -m app.analytics.run_all --max-seeds 2    # quick smoke test

Experiments use the seeds in their JSON config, so reruns reproduce the same penalties.
"""
from __future__ import annotations

import argparse
import time

from app.analytics.experiment_runner import PROJECT_ROOT, ExperimentConfig, run_experiment
from app.analytics.report import build_report

DEFAULT_ORDER = ["main", "ablation", "sensitivity", "scaling"]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run all experiments and build their reports.")
    parser.add_argument("--only", help="comma-separated experiment names (default: all)")
    parser.add_argument("--workers", type=int, help="override every experiment's process count")
    parser.add_argument("--max-seeds", type=int, help="use only the first N seeds")
    args = parser.parse_args()

    names = args.only.split(",") if args.only else DEFAULT_ORDER
    started = time.perf_counter()
    for name in names:
        print(f"\n=== {name} ===", flush=True)
        cfg = ExperimentConfig.load(PROJECT_ROOT / "experiments" / "configs" / f"{name}.json")
        out = run_experiment(cfg, workers=args.workers, max_seeds=args.max_seeds)
        made = build_report(out)
        print(f"tables : {', '.join(made['tables']) or '-'}")
        print(f"figures: {', '.join(made['figures']) or '-'}", flush=True)
    print(f"\nall done in {(time.perf_counter() - started) / 60:.1f} min")


if __name__ == "__main__":
    main()
