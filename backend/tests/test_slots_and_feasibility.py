from dataclasses import replace
from datetime import date

import pytest

from app.core.config import ConstraintParams
from app.optimization.context import build_context
from app.services.feasibility_service import check_feasibility
from app.services.slot_service import generate_slots


# --- slot generation ---------------------------------------------------------------------------
def test_prd_example_session_two_slots_per_day():
    # 20-Nov-2026 (Fri) to 30-Nov-2026 (Mon), Mon-Fri: 20, 23-27, 30 = 7 days.
    slots = generate_slots(date(2026, 11, 20), date(2026, 11, 30), slots_per_day=2)
    assert len(slots) == 14
    assert slots[0].slot_id == "S01" and slots[-1].slot_id == "S14"
    assert slots[0].date == date(2026, 11, 20) and slots[2].date == date(2026, 11, 23)
    assert [s.slot_number for s in slots[:4]] == [0, 1, 0, 1]
    assert all(s.duration_minutes == 180 for s in slots)


def test_min_slots_extends_to_whole_days():
    slots = generate_slots(date(2026, 11, 20), slots_per_day=2, min_slots=5)
    assert len(slots) == 6


def test_holidays_and_custom_working_days():
    slots = generate_slots(
        date(2026, 11, 23), date(2026, 11, 28), slots_per_day=1,
        working_days=(0, 1, 2, 3, 4, 5), holidays=[date(2026, 11, 25)],
    )
    assert [s.date.day for s in slots] == [23, 24, 26, 27, 28]


def test_bad_slot_arguments():
    with pytest.raises(ValueError):
        generate_slots(date(2026, 11, 20))
    with pytest.raises(ValueError):
        generate_slots(date(2026, 11, 20), date(2026, 11, 30), slots_per_day=5)
    with pytest.raises(ValueError):
        generate_slots(date(2026, 11, 20), date(2026, 11, 30), slots_per_day=2, slot_times=[("09:00", "10:00")])


# --- feasibility precheck ----------------------------------------------------------------------
def test_tiny_dataset_is_feasible(tiny_dataset):
    report = check_feasibility(build_context(tiny_dataset))
    assert report.ok and not report.warnings


def test_exam_larger_than_every_room(tiny_dataset):
    exams = list(tiny_dataset.exams)
    exams[0] = replace(exams[0], student_count=150)
    ds = replace(tiny_dataset, exams=exams)
    msgs = check_feasibility(build_context(ds)).messages()
    assert any("E1 needs 150 seats but the largest compatible available room has 120" in m for m in msgs)


def test_practical_exam_without_lab(tiny_dataset):
    exams = list(tiny_dataset.exams)
    exams[2] = replace(exams[2], exam_type="practical")
    msgs = check_feasibility(build_context(replace(tiny_dataset, exams=exams))).messages()
    assert any("E3 has no available room compatible with exam type 'practical'" in m for m in msgs)


def test_unavailable_rooms_are_ignored(tiny_dataset):
    rooms = [replace(r, available=(r.room_id != "R3")) for r in tiny_dataset.rooms]
    exams = list(tiny_dataset.exams)
    exams[0] = replace(exams[0], student_count=100)
    msgs = check_feasibility(build_context(replace(tiny_dataset, rooms=rooms, exams=exams))).messages()
    assert any("E1 needs 100 seats but the largest compatible available room has 40" in m for m in msgs)


def test_exam_longer_than_any_slot(tiny_dataset):
    exams = list(tiny_dataset.exams)
    exams[0] = replace(exams[0], duration_minutes=240)
    msgs = check_feasibility(build_context(replace(tiny_dataset, exams=exams))).messages()
    assert any("E1 lasts 240 min but the longest slot is 180 min" in m for m in msgs)


def test_clique_larger_than_slot_count(tiny_dataset):
    # ST001 already takes E1 and E2; adding E3 makes all three exams pairwise conflicting.
    no_h8 = ConstraintParams(one_exam_per_day=False)
    enrollments = tiny_dataset.enrollments + [("ST001", "E3")]
    three_slots = replace(tiny_dataset, enrollments=enrollments, slots=tiny_dataset.slots[:3])
    assert check_feasibility(build_context(three_slots, params=no_h8)).ok

    two_slots = replace(three_slots, slots=tiny_dataset.slots[:2])
    msgs = check_feasibility(build_context(two_slots, params=no_h8)).messages()
    assert any("At least 3 slots are needed" in m for m in msgs)


def test_clique_larger_than_day_count(tiny_dataset):
    # Three pairwise-conflicting exams need three days when a student sits one exam per day.
    enrollments = tiny_dataset.enrollments + [("ST001", "E3")]
    ds = replace(tiny_dataset, enrollments=enrollments)  # 4 slots but only 2 days
    msgs = check_feasibility(build_context(ds)).messages()
    assert any("At least 3 exam days are needed" in m for m in msgs)
    assert check_feasibility(build_context(ds, params=ConstraintParams(one_exam_per_day=False))).ok


def test_more_exams_than_cells(tiny_dataset):
    ds = replace(tiny_dataset, rooms=tiny_dataset.rooms[2:], slots=tiny_dataset.slots[:2])
    msgs = check_feasibility(build_context(ds)).messages()
    assert any("3 exams cannot fit into 2 slots x 1 available rooms = 2" in m for m in msgs)
