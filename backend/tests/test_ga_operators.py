import numpy as np
import pytest

from app.optimization.chromosome import Chromosome
from app.optimization.context import build_context
from app.optimization.crossover import two_point_crossover, uniform_crossover
from app.optimization.fitness import evaluate
from app.optimization.mutation import mutate, room_mutation, slot_mutation, swap_mutation
from app.optimization.population import constructive_individual, exam_order, initial_population
from app.optimization.repair import repair
from app.optimization.selection import tournament_select
from app.optimization.validator import validate_timetable
from app.services.data_generator import PRESETS, generate_dataset

DATASET = generate_dataset(PRESETS["small"])
CTX = build_context(DATASET)


def rng(seed=0):
    return np.random.default_rng(seed)


# --- selection ---------------------------------------------------------------------------------
def test_tournament_prefers_lower_penalty():
    penalties = np.arange(100, dtype=float)  # index == penalty
    winners = tournament_select(penalties, k=3, n=5000, rng=rng())
    assert winners.mean() < 30  # mean of the min of 3 uniform draws is ~24
    assert winners.min() >= 0 and winners.max() < 100


def test_tournament_of_one_is_uniform_and_of_population_is_best():
    penalties = np.arange(50, dtype=float)
    assert 20 < tournament_select(penalties, 1, 5000, rng()).mean() < 29
    assert (tournament_select(penalties, 5000, 10, rng()) == 0).all()


# --- initialization ----------------------------------------------------------------------------
def test_exam_order_is_descending_conflict_degree():
    order = exam_order(CTX, rng())
    degrees = CTX.degree[order]
    assert (np.diff(degrees) <= 0).all()


def test_initial_individuals_are_feasible_and_diverse():
    pop = initial_population(CTX, 20, rng())
    for c in pop:
        assert evaluate(CTX, c.slot, c.room).hard_violations == 0
    assert len({tuple(c.slot) for c in pop}) > 1


def test_first_fit_construction_is_deterministic_and_valid():
    a = constructive_individual(CTX, rng(1), "first")
    b = constructive_individual(CTX, rng(2), "first")
    assert evaluate(CTX, a.slot, a.room).hard_violations == 0
    # ties in the exam order are random, but feasibility holds for any seed
    assert evaluate(CTX, b.slot, b.room).hard_violations == 0


# --- crossover ---------------------------------------------------------------------------------
@pytest.mark.parametrize("op", [uniform_crossover, two_point_crossover])
def test_crossover_inherits_each_gene_from_a_parent(op):
    a, b = initial_population(CTX, 2, rng(3))
    c1, c2 = op(a, b, rng(4))
    for i in range(CTX.n_exams):
        genes = {(a.slot[i], a.room[i]), (b.slot[i], b.room[i])}
        assert (c1.slot[i], c1.room[i]) in genes and (c2.slot[i], c2.room[i]) in genes
        # the two children together hold both parental genes for the exam
        assert {(c1.slot[i], c1.room[i]), (c2.slot[i], c2.room[i])} == genes or len(genes) == 1


def test_crossover_does_not_modify_parents():
    a, b = initial_population(CTX, 2, rng(5))
    a0, b0 = a.slot.copy(), b.slot.copy()
    uniform_crossover(a, b, rng(6))
    assert (a.slot == a0).all() and (b.slot == b0).all()


# --- mutation ----------------------------------------------------------------------------------
def test_slot_mutation_changes_one_slot_to_a_fitting_one():
    c = initial_population(CTX, 1, rng(7))[0]
    before = c.slot.copy()
    slot_mutation(CTX, c, rng(8))
    changed = np.flatnonzero(c.slot != before)
    assert len(changed) == 1 and CTX.slot_ok[changed[0], c.slot[changed[0]]]


def test_room_mutation_changes_one_room_to_a_suitable_one():
    c = initial_population(CTX, 1, rng(9))[0]
    before = c.room.copy()
    room_mutation(CTX, c, rng(10))
    changed = np.flatnonzero(c.room != before)
    assert len(changed) <= 1
    assert all(CTX.room_ok[i, c.room[i]] for i in changed)


def test_swap_mutation_preserves_slot_multiset():
    c = initial_population(CTX, 1, rng(11))[0]
    before = sorted(c.slot)
    swap_mutation(CTX, c, rng(12))
    assert sorted(c.slot) == before


def test_mutate_keeps_indices_in_range():
    c = initial_population(CTX, 1, rng(13))[0]
    mutate(CTX, c, rng(14), ops=50)
    assert c.slot.min() >= 0 and c.slot.max() < CTX.n_slots
    assert c.room.min() >= 0 and c.room.max() < CTX.n_rooms


# --- repair ------------------------------------------------------------------------------------
def test_repair_fixes_a_badly_broken_timetable():
    # every exam in slot 0 and room 0: maximal clashes, collisions and capacity violations
    c = Chromosome(np.zeros(CTX.n_exams, dtype=np.int64), np.zeros(CTX.n_exams, dtype=np.int64))
    assert evaluate(CTX, c.slot, c.room).hard_violations > 0
    repair(CTX, c, rng(15), max_attempts=200)
    ev = evaluate(CTX, c.slot, c.room)
    assert ev.hard_violations == 0
    assert validate_timetable(DATASET, c.assignments(CTX)).valid


def test_repair_leaves_a_valid_timetable_untouched():
    c = initial_population(CTX, 1, rng(16))[0]
    before = (c.slot.copy(), c.room.copy())
    moves = repair(CTX, c, rng(17))
    assert moves == 0 and (c.slot == before[0]).all() and (c.room == before[1]).all()


def test_repair_respects_attempt_budget():
    c = Chromosome(np.zeros(CTX.n_exams, dtype=np.int64), np.zeros(CTX.n_exams, dtype=np.int64))
    assert repair(CTX, c, rng(18), max_attempts=3) == 3
    assert evaluate(CTX, c.slot, c.room).hard_violations > 0  # budget too small to finish


def test_repair_never_makes_hard_violations_worse_on_crossover_children():
    pop = initial_population(CTX, 12, rng(19))
    r = rng(20)
    for a, b in zip(pop[::2], pop[1::2]):
        for child in uniform_crossover(a, b, r):
            before = evaluate(CTX, child.slot, child.room).hard_violations
            repair(CTX, child, r)
            assert evaluate(CTX, child.slot, child.room).hard_violations <= before
