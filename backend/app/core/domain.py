"""Plain domain records shared by the importer, the optimizer and the validator.

These are independent of the database layer so the GA can run headless.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time
from typing import NamedTuple

from app.core.config import EXAM_ROOM_COMPAT


@dataclass(frozen=True)
class Exam:
    exam_id: str
    subject_code: str
    subject_name: str
    department: str
    semester: str
    duration_minutes: int
    student_count: int
    exam_type: str
    priority: int = 0


@dataclass(frozen=True)
class Student:
    student_id: str
    department: str = ""
    semester: str = ""


@dataclass(frozen=True)
class Room:
    room_id: str
    room_code: str
    capacity: int
    building: str = ""
    room_type: str = "classroom"
    available: bool = True


@dataclass(frozen=True)
class Slot:
    slot_id: str
    date: date
    start_time: time
    end_time: time
    slot_number: int = 0  # 0-based position within its day
    pref_penalty: int = 0  # 0 = most desirable

    @property
    def duration_minutes(self) -> int:
        return (self.end_time.hour * 60 + self.end_time.minute) - (
            self.start_time.hour * 60 + self.start_time.minute
        )


class Assignment(NamedTuple):
    """One timetable entry: the gene of PRD section 8 expressed with external ids."""

    exam_id: str
    slot_id: str
    room_id: str


@dataclass
class Dataset:
    exams: list[Exam] = field(default_factory=list)
    students: list[Student] = field(default_factory=list)
    enrollments: list[tuple[str, str]] = field(default_factory=list)  # (student_id, exam_id)
    rooms: list[Room] = field(default_factory=list)
    slots: list[Slot] = field(default_factory=list)  # chronological order


def room_allowed_for_exam(exam_type: str, room_type: str) -> bool:
    allowed = EXAM_ROOM_COMPAT.get(exam_type)
    return True if allowed is None else room_type in allowed
