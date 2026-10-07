"""The matrix-based fitness must agree with the independent per-student validator and with a
naive per-student computation of the soft penalties, on arbitrary (even invalid) timetables."""
import math
from collections import Counter
from itertools import combinations

import numpy as np
from hypothesis import HealthCheck, given, settings, strategies as st

from app.core.domain import Dataset
from app.optimization.context import OptimizationContext, build_context
from app.optimization.fitness import evaluate
from app.optimization.validator import validate_timetable
from app.services.data_generator import PRESETS, generate_dataset

DATASET = generate_dataset(PRESETS["small"])
CTX = build_context(DATASET)
N, S, R = CTX.n_exams, CTX.n_slots, CTX.n_rooms

# -1 means "no entry at all"; S / R mean "entry referencing a slot / room that does not exist".
slots_st = st.lists(st.integers(-1, S), min_size=N, max_size=N)
rooms_st = st.lists(st.integers(-1, R), min_size=N, max_size=N)
valid_slots_st = st.lists(st.integers(0, S - 1), min_size=N, max_size=N)
valid_rooms_st = st.lists(st.integers(0, R - 1), min_size=N, max_size=N)
HYP = dict(max_examples=150, deadline=None, suppress_health_check=[HealthCheck.too_slow])


def to_entries(ctx: OptimizationContext, slot, room):
    entries = []
    for i in range(ctx.n_exams):
        if slot[i] == -1 or room[i] == -1:
            continue  # exam left out of the timetable entirely
        slot_id = ctx.slot_ids[slot[i]] if slot[i] < ctx.n_slots else "NO_SUCH_SLOT"
        room_id = ctx.room_ids[room[i]] if room[i] < ctx.n_rooms else "NO_SUCH_ROOM"
        entries.append((ctx.exam_ids[i], slot_id, room_id))
    return entries


@settings(**HYP)
@given(slots_st, rooms_st)
def test_hard_breakdown_matches_validator(slot, room):
    ev = evaluate(CTX, np.array(slot), np.array(room))
    res = validate_timetable(DATASET, to_entries(CTX, slot, room))
    assert ev.student_clashes == res.student_conflicts
    assert ev.room_collisions == res.room_conflicts
    assert ev.capacity_violations == res.capacity_violations
    assert ev.unassigned == res.unassigned
    assert ev.unavailable_rooms == res.unavailable_rooms
    assert ev.room_type_mismatches == res.room_type_mismatches
    assert ev.duration_violations == res.duration_violations
    assert ev.same_day_conflicts == res.same_day_conflicts
    assert ev.hard_violations == res.hard_violations
    assert ev.valid == res.valid


def naive_soft(dataset: Dataset, ctx: OptimizationContext, slot, room):
    """Soft penalties computed by scanning students, straight from the definitions."""
    slots = {s.slot_id: s for s in dataset.slots}
    placed = {ctx.exam_ids[i]: slots[ctx.slot_ids[slot[i]]] for i in range(ctx.n_exams)}
    taken: dict[str, list[str]] = {}
    for sid, eid in dataset.enrollments:
        taken.setdefault(sid, []).append(eid)
    consecutive = gap = 0
    for exams in taken.values():
        for a, b in combinations(exams, 2):
            sa, sb = placed[a], placed[b]
            if sa.slot_id == sb.slot_id:
                continue
            days = abs((sa.date - sb.date).days)
            if days == 0 and abs(sa.slot_number - sb.slot_number) == 1:
                consecutive += 1
            elif days == 0 or 1 <= days <= ctx.params.short_gap_days:
                gap += 1
    per_day = Counter(placed[e].date for e in placed)
    n_days = len({s.date for s in dataset.slots})
    fair = math.ceil(len(dataset.exams) / n_days)
    distribution = sum(max(0, c - fair) for c in per_day.values())
    pref = sum(placed[e.exam_id].pref_penalty * (1 + e.priority) for e in dataset.exams)
    rooms = {r.room_id: r for r in dataset.rooms}
    util = sum(
        max(0, rooms[ctx.room_ids[room[i]]].capacity - e.student_count) / rooms[ctx.room_ids[room[i]]].capacity
        for i, e in enumerate(dataset.exams)
    )
    return consecutive, gap, distribution, pref, util


@settings(**HYP)
@given(valid_slots_st, valid_rooms_st)
def test_soft_components_match_naive_per_student_computation(slot, room):
    ev = evaluate(CTX, np.array(slot), np.array(room))
    consecutive, gap, distribution, pref, util = naive_soft(DATASET, CTX, slot, room)
    assert ev.consecutive == consecutive
    assert ev.short_gaps == gap
    assert ev.distribution == distribution
    assert ev.slot_preference == pref
    assert math.isclose(ev.room_utilization, util, rel_tol=1e-9, abs_tol=1e-9)
    w = CTX.weights
    expected = (
        w.hard * ev.hard_violations + w.consecutive * consecutive + w.gap * gap
        + w.distribution * distribution + w.slot_pref * pref + w.room_util * util
    )
    assert math.isclose(ev.penalty, expected, rel_tol=1e-9)


def test_perfect_hand_built_schedule_is_valid_on_generated_data():
    """Sanity: a DSATUR colouring with best-fit rooms has zero hard violations in both.

    Colour k goes to the first slot of day k, so exams sharing students are on different days."""
    from app.services.conflict_service import dsatur_colors

    colors = dsatur_colors(CTX.conflict)
    assert colors.max() < CTX.n_days  # the generator sizes the calendar for this
    first_slot_of_day = np.array([np.flatnonzero(CTX.slot_day_index == d)[0] for d in range(CTX.n_days)])
    slot = first_slot_of_day[colors].astype(np.int64)
    room = np.zeros(N, dtype=np.int64)
    for c in np.unique(slot):
        members = sorted(np.flatnonzero(slot == c), key=lambda i: -CTX.student_count[i])
        free = list(np.argsort(CTX.room_capacity))  # smallest first
        for i in members:
            pick = next(r for r in free if CTX.room_ok[i, r])
            room[i] = pick
            free.remove(pick)
    ev = evaluate(CTX, slot, room)
    res = validate_timetable(DATASET, to_entries(CTX, slot.tolist(), room.tolist()))
    assert ev.hard_violations == 0 and res.valid
