from datetime import date, time

import pandas as pd
import pytest

from app.core.domain import Dataset, Exam, Room, Slot, Student


def _slot(n: int, day: int, pos: int) -> Slot:
    starts = [time(9, 30), time(14, 0)]
    ends = [time(12, 30), time(17, 0)]
    return Slot(f"S{n:02d}", date(2026, 11, day), starts[pos], ends[pos], slot_number=pos, pref_penalty=pos)


@pytest.fixture
def tiny_dataset() -> Dataset:
    """Architecture section 6 example: E1-E2 share 20 students, E2-E3 share 7.

    Plus 5 students only in E1 and 3 only in E3. Mon 23 and Tue 24 Nov 2026, 2 slots/day.
    """
    exams = [
        Exam("E1", "C1", "Course 1", "CSE", "V", 180, 25, "theory"),
        Exam("E2", "C2", "Course 2", "CSE", "V", 180, 27, "theory"),
        Exam("E3", "C3", "Course 3", "ECE", "V", 120, 10, "theory"),
    ]
    students: list[Student] = []
    enrollments: list[tuple[str, str]] = []

    def add(count: int, exam_ids: list[str]) -> None:
        for _ in range(count):
            sid = f"ST{len(students) + 1:03d}"
            students.append(Student(sid))
            enrollments.extend((sid, e) for e in exam_ids)

    add(20, ["E1", "E2"])
    add(7, ["E2", "E3"])
    add(5, ["E1"])
    add(3, ["E3"])
    rooms = [
        Room("R1", "A101", 30, "Main", "classroom", True),
        Room("R2", "A102", 40, "Main", "classroom", True),
        Room("R3", "B201", 120, "Annex", "hall", True),
    ]
    slots = [_slot(1, 23, 0), _slot(2, 23, 1), _slot(3, 24, 0), _slot(4, 24, 1)]
    return Dataset(exams, students, enrollments, rooms, slots)


def frames_from(dataset: Dataset) -> dict[str, pd.DataFrame]:
    """Raw string tables, as read_csv would return them, for importer tests."""
    return {
        "exams": pd.DataFrame(
            [
                {
                    "exam_id": e.exam_id, "subject_code": e.subject_code, "subject_name": e.subject_name,
                    "department": e.department, "semester": e.semester,
                    "duration_minutes": str(e.duration_minutes), "student_count": str(e.student_count),
                    "exam_type": e.exam_type,
                }
                for e in dataset.exams
            ]
        ),
        "students": pd.DataFrame([{"student_id": s.student_id} for s in dataset.students]),
        "enrollments": pd.DataFrame(dataset.enrollments, columns=["student_id", "exam_id"]),
        "rooms": pd.DataFrame(
            [
                {
                    "room_id": r.room_id, "room_code": r.room_code, "building": r.building,
                    "capacity": str(r.capacity), "room_type": r.room_type, "available": "true",
                }
                for r in dataset.rooms
            ]
        ),
        "slots": pd.DataFrame(
            [
                {
                    "slot_id": s.slot_id, "date": s.date.isoformat(),
                    "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
                }
                for s in dataset.slots
            ]
        ),
    }


@pytest.fixture
def tiny_frames(tiny_dataset: Dataset) -> dict[str, pd.DataFrame]:
    return frames_from(tiny_dataset)
