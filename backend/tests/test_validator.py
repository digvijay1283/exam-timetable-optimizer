from dataclasses import replace

from app.optimization.validator import validate_timetable

GOOD = [("E1", "S01", "R1"), ("E2", "S03", "R2"), ("E3", "S02", "R1")]


def test_valid_timetable_accepted(tiny_dataset):
    result = validate_timetable(tiny_dataset, GOOD)
    assert result.valid and result.hard_violations == 0
    assert result.to_dict()["student_conflicts"] == 0


def test_student_conflict_rejected_with_detail(tiny_dataset):
    bad = [("E1", "S01", "R1"), ("E2", "S01", "R2"), ("E3", "S04", "R1")]
    result = validate_timetable(tiny_dataset, bad)
    assert not result.valid
    assert result.student_conflicts == 20
    assert "E1 and E2 share 20 student(s) in slot S01" in result.details


def test_room_collision_rejected(tiny_dataset):
    bad = [("E1", "S01", "R1"), ("E2", "S03", "R2"), ("E3", "S01", "R1")]
    result = validate_timetable(tiny_dataset, bad)
    assert result.room_conflicts == 1
    assert result.student_conflicts == 0  # E1 and E3 share no students


def test_capacity_violation_rejected(tiny_dataset):
    rooms = [replace(tiny_dataset.rooms[0], capacity=20), *tiny_dataset.rooms[1:]]
    result = validate_timetable(replace(tiny_dataset, rooms=rooms), GOOD)
    assert result.capacity_violations == 1


def test_missing_exam_rejected(tiny_dataset):
    result = validate_timetable(tiny_dataset, GOOD[:2])
    assert result.unassigned == 1 and not result.valid
    assert "E3 is not assigned" in result.details


def test_duplicate_assignment_rejected(tiny_dataset):
    result = validate_timetable(tiny_dataset, GOOD + [("E1", "S02", "R3")])
    assert result.unassigned == 1
    assert "E1 is assigned 2 times" in result.details


def test_unknown_references_rejected(tiny_dataset):
    bad = [("E1", "S99", "R1"), ("E2", "S03", "R9"), ("E3", "S04", "R1"), ("E7", "S01", "R1")]
    result = validate_timetable(tiny_dataset, bad)
    assert result.unassigned == 3  # E1 bad slot, E2 bad room, entry for unknown exam E7


def test_manually_edited_invalid_timetable_is_rejected(tiny_dataset):
    """A coordinator moves E3 into E2's slot: they share 7 students."""
    edited = [("E1", "S01", "R1"), ("E2", "S03", "R2"), ("E3", "S03", "R3")]
    result = validate_timetable(tiny_dataset, edited)
    assert not result.valid and result.student_conflicts == 7


def test_unavailable_room_type_and_duration(tiny_dataset):
    rooms = [replace(tiny_dataset.rooms[0], available=False), *tiny_dataset.rooms[1:]]
    exams = list(tiny_dataset.exams)
    exams[2] = replace(exams[2], exam_type="practical")
    exams[1] = replace(exams[1], duration_minutes=240)
    result = validate_timetable(replace(tiny_dataset, rooms=rooms, exams=exams), GOOD)
    assert (result.unavailable_rooms, result.room_type_mismatches, result.duration_violations) == (2, 1, 1)
    assert result.hard_violations == 4


def test_two_exams_on_one_day_rejected_with_detail(tiny_dataset):
    """E2 and E3 share 7 students and sit on the same day in different slots."""
    same_day = [("E1", "S01", "R1"), ("E2", "S03", "R2"), ("E3", "S04", "R1")]
    result = validate_timetable(tiny_dataset, same_day)
    assert not result.valid and result.same_day_conflicts == 7 and result.student_conflicts == 0
    assert any("same day (2026-11-24)" in d for d in result.details)
    assert validate_timetable(tiny_dataset, same_day, one_exam_per_day=False).valid
