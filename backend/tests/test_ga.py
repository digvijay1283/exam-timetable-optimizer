from dataclasses import replace

import pytest

from app.optimization.context import build_context
from app.optimization.genetic_algorithm import run_ga
from app.optimization.params import GAParams
from app.optimization.validator import validate_timetable
from app.services.data_generator import PRESETS, generate_dataset

DATASET = generate_dataset(PRESETS["small"])
CTX = build_context(DATASET)
FAST = GAParams(population_size=30, generations=25, early_stopping=False)


def test_ga_returns_a_valid_timetable_confirmed_by_the_independent_validator():
    res = run_ga(CTX, FAST)
    assert res.valid and res.evaluation.hard_violations == 0
    assert validate_timetable(DATASET, res.best.assignments(CTX)).valid
    assert len(res.best.assignments(CTX)) == len(DATASET.exams)  # every exam assigned


def test_ga_improves_on_its_initial_population():
    res = run_ga(CTX, FAST)
    assert res.evaluation.penalty < res.initial_penalty


def test_same_seed_is_reproducible():
    a, b = run_ga(CTX, FAST), run_ga(CTX, FAST)
    assert [h.best_penalty for h in a.history] == [h.best_penalty for h in b.history]
    assert (a.best.slot == b.best.slot).all() and (a.best.room == b.best.room).all()


def test_different_seeds_differ():
    a, b = run_ga(CTX, FAST), run_ga(CTX, replace(FAST, seed=43))
    assert [h.best_penalty for h in a.history] != [h.best_penalty for h in b.history]


def test_elitism_makes_best_penalty_monotone():
    res = run_ga(CTX, FAST)
    best = [h.best_penalty for h in res.history]
    assert all(later <= earlier + 1e-9 for earlier, later in zip(best, best[1:]))
    assert len(res.history) == FAST.generations + 1 and res.generations_run == FAST.generations


def test_fixed_generation_run_has_no_early_stop():
    res = run_ga(CTX, replace(FAST, patience=1, early_stopping=False))
    assert res.generations_run == FAST.generations and res.stopped_by == "max_generations"


def test_early_stopping_on_no_improvement():
    res = run_ga(CTX, replace(FAST, generations=300, early_stopping=True, patience=5))
    assert res.stopped_by == "no_improvement" and res.generations_run < 300


def test_early_stopping_on_target():
    res = run_ga(CTX, replace(FAST, generations=300, early_stopping=True, target_penalty=1e9))
    assert res.stopped_by == "target_reached" and res.generations_run == 1


def test_progress_callback_sees_every_generation():
    seen = []
    run_ga(CTX, replace(FAST, generations=5), progress=seen.append)
    assert [s.generation for s in seen] == [0, 1, 2, 3, 4, 5]


def test_history_dicts_include_fitness():
    res = run_ga(CTX, replace(FAST, generations=2))
    row = res.history_dicts()[0]
    assert row["best_fitness"] == pytest.approx(1 / (1 + row["best_penalty"]))


def test_two_point_crossover_and_no_repair_options_run():
    assert run_ga(CTX, replace(FAST, generations=3, crossover_type="two_point")).generations_run == 3
    no_repair = run_ga(CTX, replace(FAST, generations=3, repair=False))
    assert no_repair.generations_run == 3  # may be infeasible, but must not crash


def test_invalid_parameters_rejected():
    for bad in (
        GAParams(population_size=1),
        GAParams(elite_count=100, population_size=50),
        GAParams(mutation_rate=1.5),
        GAParams(tournament_size=0),
    ):
        with pytest.raises(ValueError):
            run_ga(CTX, bad)
