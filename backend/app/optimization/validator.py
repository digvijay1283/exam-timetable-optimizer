"""Independent timetable validator (Architecture section 17).

Deliberately does NOT share code with the optimizer's fitness: it works from the raw dataset and
scans student by student instead of using the conflict matrix. It can therefore check GA output,
baseline output, manually edited timetables and approved timetables, and it serves as an oracle
for the fitness function in tests.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass
from itertools import combinations
from typing import Iterable

from app.core.domain import Assignment, Dataset, Room, Slot, room_allowed_for_exam

MAX_DETAILS = 200


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    hard_violations: int
    student_conflicts: int
    room_conflicts: int
    capacity_violations: int
    unassigned: int
    unavailable_rooms: int
    room_type_mismatches: int
    duration_violations: int
    same_day_conflicts: int = 0
    details: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def validate_timetable(
    dataset: Dataset, assignments: Iterable[tuple[str, str, str]], one_exam_per_day: bool = True
) -> ValidationResult:
    """Check every hard constraint. `one_exam_per_day` enables H8 (see ConstraintParams)."""
    exams = {e.exam_id: e for e in dataset.exams}
    rooms = {r.room_id: r for r in dataset.rooms}
    slots = {s.slot_id: s for s in dataset.slots}
    details: list[str] = []
    unassigned = 0

    entries: dict[str, list[Assignment]] = defaultdict(list)
    for entry in assignments:
        a = Assignment(*entry)
        if a.exam_id not in exams:
            unassigned += 1
            details.append(f"entry for unknown exam {a.exam_id}")
        else:
            entries[a.exam_id].append(a)

    placed: dict[str, tuple[Slot, Room]] = {}
    for exam in dataset.exams:
        mine = entries.get(exam.exam_id, [])
        if not mine:
            unassigned += 1
            details.append(f"{exam.exam_id} is not assigned")
        elif len(mine) > 1:
            unassigned += 1
            details.append(f"{exam.exam_id} is assigned {len(mine)} times")
        elif mine[0].slot_id not in slots:
            unassigned += 1
            details.append(f"{exam.exam_id} references unknown slot {mine[0].slot_id}")
        elif mine[0].room_id not in rooms:
            unassigned += 1
            details.append(f"{exam.exam_id} references unknown room {mine[0].room_id}")
        else:
            placed[exam.exam_id] = (slots[mine[0].slot_id], rooms[mine[0].room_id])

    capacity = unavailable = mismatch = too_long = 0
    for exam_id, (slot, room) in placed.items():
        exam = exams[exam_id]
        if exam.student_count > room.capacity:
            capacity += 1
            details.append(f"{exam_id} has {exam.student_count} students but room {room.room_id} seats {room.capacity}")
        if not room.available:
            unavailable += 1
            details.append(f"{exam_id} uses unavailable room {room.room_id}")
        if not room_allowed_for_exam(exam.exam_type, room.room_type):
            mismatch += 1
            details.append(f"{exam_id} ({exam.exam_type}) cannot use {room.room_type} room {room.room_id}")
        if slot.duration_minutes < exam.duration_minutes:
            too_long += 1
            details.append(
                f"{exam_id} needs {exam.duration_minutes} min but slot {slot.slot_id} lasts {slot.duration_minutes}"
            )

    by_cell: dict[tuple[str, str], list[str]] = defaultdict(list)
    for exam_id, (slot, room) in placed.items():
        by_cell[(slot.slot_id, room.room_id)].append(exam_id)
    room_conflicts = 0
    for (slot_id, room_id), members in by_cell.items():
        k = len(members)
        if k > 1:
            room_conflicts += k * (k - 1) // 2
            details.append(f"room {room_id} hosts {', '.join(sorted(members))} in slot {slot_id}")

    exams_of_student: dict[str, list[str]] = defaultdict(list)
    for student_id, exam_id in dataset.enrollments:
        if exam_id in placed:
            exams_of_student[student_id].append(exam_id)
    shared: dict[tuple[str, str, str], int] = defaultdict(int)
    shared_day: dict[tuple[str, str, str], int] = defaultdict(int)
    for student_exams in exams_of_student.values():
        for a, b in combinations(sorted(student_exams), 2):
            slot_a, slot_b = placed[a][0], placed[b][0]
            if slot_a.slot_id == slot_b.slot_id:
                shared[(a, b, slot_a.slot_id)] += 1
            elif one_exam_per_day and slot_a.date == slot_b.date:
                shared_day[(a, b, slot_a.date.isoformat())] += 1
    student_conflicts = sum(shared.values())
    same_day = sum(shared_day.values())
    for (a, b, slot_id), n in sorted(shared.items()):
        details.append(f"{a} and {b} share {n} student(s) in slot {slot_id}")
    for (a, b, day), n in sorted(shared_day.items()):
        details.append(f"{a} and {b} share {n} student(s) on the same day ({day})")

    hard = student_conflicts + room_conflicts + capacity + unassigned + unavailable + mismatch + too_long + same_day
    if len(details) > MAX_DETAILS:
        extra = len(details) - MAX_DETAILS
        details = details[:MAX_DETAILS] + [f"... and {extra} more"]
    return ValidationResult(
        valid=hard == 0,
        hard_violations=hard,
        student_conflicts=student_conflicts,
        room_conflicts=room_conflicts,
        capacity_violations=capacity,
        unassigned=unassigned,
        unavailable_rooms=unavailable,
        room_type_mismatches=mismatch,
        duration_violations=too_long,
        same_day_conflicts=same_day,
        details=tuple(details),
    )
