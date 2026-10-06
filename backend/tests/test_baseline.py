import numpy as np
import pytest

from app.optimization.baseline import BASELINES, DETERMINISTIC, run_baseline
from app.optimization.context import build_context
from app.optimization.genetic_algorithm import run_ga
from app.optimization.params import GAParams
from app.optimization.validator import validate_timetable
from app.services.data_generator import PRESETS, generate_dataset

DATASET = generate_dataset(PRESETS["small"])
CTX = build_context(DATASET)


@pytest.mark.parametrize("name", ["greedy", "greedy_cost_aware", "randomized_greedy"])
def test_conflict_aware_baselines_are_valid_per_independent_validator(name):
    res = run_baseline(CTX, name, seed=7)
    assert res.valid
    assert validate_timetable(DATASET, res.chromosome.assignments(CTX)).valid
    assert res.evaluation.penalty == pytest.approx(res.chromosome.penalty)


def test_deterministic_baselines_ignore_the_seed():
    for name in DETERMINISTIC:
        a, b = run_baseline(CTX, name, seed=1), run_baseline(CTX, name, seed=2)
        assert (a.chromosome.slot == b.chromosome.slot).all() and a.seed is None


def test_seeded_baselines_reproduce_and_vary():
    a, b, c = (run_baseline(CTX, "randomized_greedy", seed=s) for s in (1, 1, 2))
    assert (a.chromosome.slot == b.chromosome.slot).all()
    assert not (a.chromosome.slot == c.chromosome.slot).all()


def test_random_feasible_respects_masks_but_ignores_clashes():
    res = run_baseline(CTX, "random_feasible", seed=3)
    ch = res.chromosome
    assert CTX.slot_ok[np.arange(CTX.n_exams), ch.slot].all()
    assert CTX.room_ok[np.arange(CTX.n_exams), ch.room].all()
    assert res.evaluation.hard_violations > 0  # clashes and room collisions are not avoided


def test_cost_aware_greedy_beats_first_fit_and_ga_beats_both():
    first_fit = run_baseline(CTX, "greedy").evaluation.penalty
    cost_aware = run_baseline(CTX, "greedy_cost_aware").evaluation.penalty
    assert cost_aware < first_fit
    ga = run_ga(CTX, GAParams(population_size=40, generations=40, early_stopping=False))
    assert ga.valid and ga.evaluation.penalty < cost_aware


def test_unknown_baseline_rejected():
    with pytest.raises(ValueError):
        run_baseline(CTX, "nope")
    assert set(BASELINES) == {"greedy", "greedy_cost_aware", "randomized_greedy", "random_feasible"}
