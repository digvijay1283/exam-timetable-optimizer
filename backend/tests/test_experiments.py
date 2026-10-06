import json

import pandas as pd
import pytest

from app.analytics.experiment_runner import ExperimentConfig, build_tasks, run_experiment
from app.analytics.metrics import RunRecord, dataset_fingerprint
from app.analytics.report import build_report
from app.services.data_generator import PRESETS, generate_dataset, write_dataset


@pytest.fixture(scope="module")
def small_dir(tmp_path_factory):
    path = tmp_path_factory.mktemp("data") / "small"
    write_dataset(generate_dataset(PRESETS["small"]), path)
    return path


def make_config(small_dir, **overrides) -> ExperimentConfig:
    raw = dict(
        name="t", datasets=[str(small_dir)], seeds=[42, 43, 44],
        ga_defaults={"population_size": 12, "generations": 6},
        configs={"default": {}, "mut30": {"mutation_rate": 0.3}},
        baselines=["greedy", "randomized_greedy"],
    )
    raw.update(overrides)
    return ExperimentConfig(**raw)


def test_task_grid_covers_configs_seeds_and_baselines(small_dir):
    cfg = make_config(small_dir)
    tasks = build_tasks(cfg)
    ga = [t for t in tasks if t["kind"] == "ga"]
    assert len(ga) == 2 * 3
    assert all(t["params"]["early_stopping"] is False for t in ga)  # fixed-length runs
    assert {t["params"]["seed"] for t in ga} == {42, 43, 44}
    base = [t for t in tasks if t["kind"] == "baseline"]
    assert len([t for t in base if t["method"] == "greedy"]) == 1  # deterministic: once
    assert len([t for t in base if t["method"] == "randomized_greedy"]) == 3
    assert len(build_tasks(cfg, max_seeds=1)) == 2 + 1 + 1


def test_sweep_expands_and_reuses_the_default(small_dir):
    cfg = make_config(small_dir, configs={}, sweep={"population_size": [12, 20], "mutation_rate": [0.1, 0.3]})
    names = set(cfg.expanded_configs())
    assert names == {"default", "population_size=20", "mutation_rate=0.3"}
    assert cfg.expanded_configs()["population_size=20"] == {"population_size": 20}


def test_run_experiment_writes_records_and_histories(small_dir, tmp_path):
    out = run_experiment(make_config(small_dir), workers=1, out_dir=tmp_path / "res", quiet=True)
    runs = pd.read_csv(out / "runs.csv")
    assert list(runs.columns) == RunRecord.columns()
    assert len(runs) == 6 + 1 + 3
    ga = runs[runs["method"] == "ga"]
    assert ga["valid"].all() and (ga["generations_run"] == 6).all() and ga["population_size"].eq(12).all()
    assert (ga["final_penalty"] <= ga["initial_penalty"]).all()
    assert (runs["dataset_hash"] == dataset_fingerprint(small_dir)).all()

    histories = json.loads((out / "histories.json").read_text())
    assert len(histories["small"]["default"]["42"]["best"]) == 7  # generations + 1
    meta = json.loads((out / "meta.json").read_text())
    assert meta["runs"] == len(runs) and meta["seeds"] == [42, 43, 44]


def test_results_are_identical_across_worker_counts(small_dir, tmp_path):
    cfg = make_config(small_dir, configs={"default": {}}, baselines=["randomized_greedy"], seeds=[42, 43])
    serial = pd.read_csv(run_experiment(cfg, workers=1, out_dir=tmp_path / "a", quiet=True) / "runs.csv")
    parallel = pd.read_csv(run_experiment(cfg, workers=2, out_dir=tmp_path / "b", quiet=True) / "runs.csv")
    cols = [c for c in serial.columns if c != "runtime_seconds"]
    pd.testing.assert_frame_equal(serial[cols], parallel[cols])


def test_report_builds_tables_and_figures(small_dir, tmp_path):
    out = run_experiment(make_config(small_dir), workers=1, out_dir=tmp_path / "res", quiet=True)
    made = build_report(out, figures_dir=tmp_path / "figs")
    assert "comparison_small" in made["tables"] and "convergence_small" in made["figures"]
    table = pd.read_csv(out / "tables" / "comparison_small.csv")
    assert list(table["Method"])[0] == "Genetic algorithm"
    assert {"Greedy (first-fit)", "Randomized greedy"} <= set(table["Method"])
    for name in ("convergence_small", "baseline_vs_ga_small", "penalty_boxplot_small"):
        assert (tmp_path / "figs" / f"{name}.png").stat().st_size > 5_000
        assert (tmp_path / "figs" / f"{name}.pdf").exists()


def test_report_handles_ablation_and_sweep_shapes(small_dir, tmp_path):
    ablation = make_config(small_dir, baselines=[], configs={"default": {}, "no_repair": {"repair": False}}, seeds=[42, 43])
    out = run_experiment(ablation, workers=1, out_dir=tmp_path / "abl", quiet=True)
    assert "ablation_small" in build_report(out, figures_dir=tmp_path / "f1")["figures"]

    sweep = make_config(small_dir, baselines=[], configs={}, seeds=[42, 43], sweep={"mutation_rate": [0.1, 0.3]})
    out = run_experiment(sweep, workers=1, out_dir=tmp_path / "swp", quiet=True)
    made = build_report(out, figures_dir=tmp_path / "f2")
    assert "sensitivity_small" in made["tables"]
    table = pd.read_csv(out / "tables" / "sensitivity_small.csv")
    assert list(table["Value"]) == [0.1, 0.3]
