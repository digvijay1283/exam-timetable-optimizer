"""Hand-computed fitness cases on the tiny dataset (see conftest).

Exams E1(25) E2(27) E3(10); rooms R1(30) R2(40) R3(120); slots S01,S02 on Mon 23 Nov and
S03,S04 on Tue 24 Nov (positions 0,1 within each day). C = [[0,20,0],[20,0,7],[0,7,0]].
"""
from dataclasses import replace

import numpy as np
import pytest

from app.core.config import Weights
from app.optimization.chromosome import Chromosome
from app.optimization.context import build_context
from app.optimization.fitness import evaluate


def arrays(slot, room):
    return np.array(slot, dtype=np.int64), np.array(room, dtype=np.int64)


def test_valid_timetable_penalty_is_hand_computed(tiny_dataset):
    ctx = build_context(tiny_dataset)
    # E1->S01/R1, E2->S03/R2, E3->S04/R1
    ev = evaluate(ctx, *arrays([0, 2, 3], [0, 1, 0]))
    assert ev.hard_violations == 0 and ev.valid
    assert ev.short_gaps == 20  # E1-E2 on adjacent days
    assert ev.consecutive == 7  # E2-E3 back-to-back on Tue
    assert ev.distribution == 0
    assert ev.slot_preference == 1  # only S04 is a second-position slot
    assert ev.room_utilization == pytest.approx(5 / 30 + 13 / 40 + 20 / 30)
    expected = 100 * 7 + 40 * 20 + 20 * 0 + 10 * 1 + 5 * (5 / 30 + 13 / 40 + 20 / 30)
    assert ev.penalty == pytest.approx(expected)
    assert ev.fitness == pytest.approx(1 / (1 + expected))


def test_hard_violations_dominate(tiny_dataset):
    ctx = build_context(tiny_dataset)
    # everything in S01; E1 and E3 also share R1
    ev = evaluate(ctx, *arrays([0, 0, 0], [0, 1, 0]))
    assert ev.student_clashes == 27  # 20 + 7
    assert ev.room_collisions == 1
    assert ev.hard_violations == 28
    assert ev.distribution == 1  # 3 exams on one of two days, fair share is 2
    assert ev.penalty > 10_000 * 28
    valid = evaluate(ctx, *arrays([0, 2, 3], [0, 1, 0]))
    assert ev.penalty > valid.penalty


def test_unassigned_exam_counts_once_and_is_skipped_elsewhere(tiny_dataset):
    ctx = build_context(tiny_dataset)
    ev = evaluate(ctx, *arrays([0, -1, 3], [0, -1, 0]))
    assert ev.unassigned == 1 and ev.hard_violations == 1
    assert ev.consecutive == 0 and ev.short_gaps == 0  # pairs with E2 ignored
    assert ev.slot_preference == 1
    assert ev.room_utilization == pytest.approx(5 / 30 + 20 / 30)


def test_out_of_range_indices_are_unassigned(tiny_dataset):
    ctx = build_context(tiny_dataset)
    ev = evaluate(ctx, *arrays([0, 99, 3], [0, 1, 42]))
    assert ev.unassigned == 2


def test_capacity_violation(tiny_dataset):
    rooms = [replace(tiny_dataset.rooms[0], capacity=20), *tiny_dataset.rooms[1:]]
    ctx = build_context(replace(tiny_dataset, rooms=rooms))
    ev = evaluate(ctx, *arrays([0, 2, 3], [0, 1, 0]))
    assert ev.capacity_violations == 1  # E1 (25) in a 20-seat room; E3 (10) is fine
    assert ev.hard_violations == 1
    assert ev.room_utilization == pytest.approx(0 + 13 / 40 + 10 / 20)  # overflow wastes nothing


def test_unavailable_room_type_and_duration(tiny_dataset):
    rooms = [replace(tiny_dataset.rooms[0], available=False), *tiny_dataset.rooms[1:]]
    exams = list(tiny_dataset.exams)
    exams[2] = replace(exams[2], exam_type="practical")  # needs a lab, rooms are classrooms/hall
    exams[1] = replace(exams[1], duration_minutes=240)  # longer than any 180-min slot
    ctx = build_context(replace(tiny_dataset, rooms=rooms, exams=exams))
    ev = evaluate(ctx, *arrays([0, 2, 3], [0, 1, 0]))
    assert ev.unavailable_rooms == 2  # E1 and E3 use R1
    assert ev.room_type_mismatches == 1  # only practical E3 is in a non-lab room
    assert ev.duration_violations == 1  # E2 (240 min) in a 180-min slot
    assert ev.hard_violations == 4


def test_weights_scale_each_component(tiny_dataset):
    slot, room = arrays([0, 2, 3], [0, 1, 0])
    base = evaluate(build_context(tiny_dataset), slot, room)
    only_consecutive = Weights(hard=0, consecutive=1, gap=0, distribution=0, slot_pref=0, room_util=0)
    ev = evaluate(build_context(tiny_dataset, weights=only_consecutive), slot, room)
    assert ev.penalty == pytest.approx(base.consecutive)
    only_hard = Weights(hard=1, consecutive=0, gap=0, distribution=0, slot_pref=0, room_util=0)
    clash = evaluate(build_context(tiny_dataset, weights=only_hard), *arrays([0, 0, 0], [0, 1, 2]))
    assert clash.penalty == 27


def test_short_gap_days_parameter(tiny_dataset):
    from app.core.config import ConstraintParams

    ctx = build_context(tiny_dataset, params=ConstraintParams(short_gap_days=0))
    ev = evaluate(ctx, *arrays([0, 2, 3], [0, 1, 0]))
    assert ev.short_gaps == 0  # adjacent days no longer count


def test_chromosome_round_trip_and_evaluate(tiny_dataset):
    ctx = build_context(tiny_dataset)
    chrom = Chromosome(*arrays([0, 2, 3], [0, 1, 0]))
    ev = chrom.evaluate(ctx)
    assert chrom.penalty == ev.penalty and chrom.hard_violations == 0
    again = Chromosome.from_assignments(ctx, chrom.assignments(ctx))
    assert (again.slot == chrom.slot).all() and (again.room == chrom.room).all()
    assert chrom.assignments(ctx)[0] == ("E1", "S01", "R1")
