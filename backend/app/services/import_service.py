"""CSV loading, schema validation and normalization (PRD FR-06).

All problems are collected into a ValidationReport instead of failing on the first one.
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, time
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from app.core.config import DEFAULT_ROOM_TYPE
from app.core.domain import Dataset, Exam, Room, Slot, Student
from app.core.validation import DataValidationError, ValidationReport

EXAMS, STUDENTS, ENROLLMENTS, ROOMS, SLOTS = "exams", "students", "enrollments", "rooms", "slots"
ALL_TABLES = (EXAMS, STUDENTS, ENROLLMENTS, ROOMS, SLOTS)

REQUIRED_COLUMNS: dict[str, list[str]] = {
    EXAMS: [
        "exam_id", "subject_code", "subject_name", "department",
        "semester", "duration_minutes", "student_count", "exam_type",
    ],
    STUDENTS: ["student_id"],
    ENROLLMENTS: ["student_id", "exam_id"],
    ROOMS: ["room_id", "room_code", "capacity"],
    SLOTS: ["slot_id", "date", "start_time", "end_time"],
}

_TRUE = {"true", "1", "yes", "y", "t"}
_FALSE = {"false", "0", "no", "n", "f"}


def read_csv(path) -> pd.DataFrame:
    """Read a CSV (path or file-like) as trimmed strings; tolerates the BOM Excel adds."""
    df = pd.read_csv(path, dtype=str, keep_default_na=False, encoding="utf-8-sig")
    df.columns = [str(c).strip() for c in df.columns]
    return df.apply(lambda col: col.str.strip())


class _Row:
    """Typed access to one CSV row that records problems against the report."""

    def __init__(self, rec: Mapping[str, Any], file: str, line: int, report: ValidationReport):
        self.rec, self.file, self.line, self.report = rec, file, line, report
        self.ok = True

    def _fail(self, message: str) -> None:
        self.ok = False
        self.report.error(self.file, message, self.line)

    def text(self, col: str) -> str:
        value = str(self.rec.get(col, "")).strip()
        if not value:
            self._fail(f"'{col}' is required")
        return value

    def opt(self, col: str, default: str = "") -> str:
        return str(self.rec.get(col, "")).strip() or default

    def integer(self, col: str, minimum: int | None = None, maximum: int | None = None) -> int:
        raw = self.text(col)
        if not raw:
            return 0
        try:
            value = int(raw)
        except ValueError:
            self._fail(f"'{col}' must be an integer, got '{raw}'")
            return 0
        if minimum is not None and value < minimum:
            self._fail(f"'{col}' must be >= {minimum}, got {value}")
        if maximum is not None and value > maximum:
            self._fail(f"'{col}' must be <= {maximum}, got {value}")
        return value

    def opt_integer(self, col: str, default: int, minimum: int | None = None, maximum: int | None = None) -> int:
        if not str(self.rec.get(col, "")).strip():
            return default
        return self.integer(col, minimum, maximum)

    def boolean(self, col: str, default: bool = True) -> bool:
        raw = str(self.rec.get(col, "")).strip().lower()
        if not raw:
            return default
        if raw in _TRUE:
            return True
        if raw in _FALSE:
            return False
        self._fail(f"'{col}' must be true/false, got '{raw}'")
        return default

    def date_(self, col: str) -> date:
        raw = self.text(col)
        try:
            return date.fromisoformat(raw)
        except ValueError:
            if raw:
                self._fail(f"'{col}' must be a date like 2026-11-20, got '{raw}'")
            return date.min

    def time_(self, col: str) -> time:
        raw = self.text(col)
        try:
            return time.fromisoformat(raw)
        except ValueError:
            if raw:
                self._fail(f"'{col}' must be a time like 09:30, got '{raw}'")
            return time.min


def _rows(df: pd.DataFrame, file: str, report: ValidationReport) -> Iterable[_Row]:
    for line, rec in enumerate(df.to_dict("records"), start=2):
        yield _Row(rec, file, line, report)


def _has_columns(df: pd.DataFrame, table: str, report: ValidationReport) -> bool:
    missing = [c for c in REQUIRED_COLUMNS[table] if c not in df.columns]
    if missing:
        report.error(f"{table}.csv", f"missing required column(s): {', '.join(missing)}")
        return False
    return True


def _parse_exams(df: pd.DataFrame, report: ValidationReport) -> tuple[list[Exam], dict[str, int]] | None:
    file = "exams.csv"
    if not _has_columns(df, EXAMS, report):
        return None
    exams: list[Exam] = []
    first_line: dict[str, int] = {}
    for row in _rows(df, file, report):
        exam_id = row.text("exam_id")
        exam = Exam(
            exam_id=exam_id,
            subject_code=row.text("subject_code"),
            subject_name=row.text("subject_name"),
            department=row.text("department"),
            semester=row.text("semester"),
            duration_minutes=row.integer("duration_minutes", minimum=1),
            student_count=row.integer("student_count", minimum=1),
            exam_type=row.text("exam_type").lower(),
            priority=row.opt_integer("priority", 0, minimum=0, maximum=2),
        )
        if exam_id and exam_id in first_line:
            row._fail(f"duplicate exam_id '{exam_id}' (first seen on row {first_line[exam_id]})")
        elif exam_id:
            first_line[exam_id] = row.line
        if row.ok:
            exams.append(exam)
    if not len(df):
        report.error(file, "no exams defined")
    return exams, first_line


def _parse_students(df: pd.DataFrame, report: ValidationReport) -> list[Student] | None:
    file = "students.csv"
    if not _has_columns(df, STUDENTS, report):
        return None
    students: list[Student] = []
    seen: dict[str, int] = {}
    for row in _rows(df, file, report):
        student_id = row.text("student_id")
        if student_id and student_id in seen:
            row._fail(f"duplicate student_id '{student_id}' (first seen on row {seen[student_id]})")
        elif student_id:
            seen[student_id] = row.line
        if row.ok:
            students.append(Student(student_id, row.opt("department"), row.opt("semester")))
    if not len(df):
        report.error(file, "no students defined")
    return students


def _parse_rooms(df: pd.DataFrame, report: ValidationReport) -> list[Room] | None:
    file = "rooms.csv"
    if not _has_columns(df, ROOMS, report):
        return None
    rooms: list[Room] = []
    seen: dict[str, int] = {}
    for row in _rows(df, file, report):
        room_id = row.text("room_id")
        room_code = row.text("room_code")
        capacity = row.integer("capacity")
        if row.ok and capacity <= 0:
            row._fail(f"room {room_id} has non-positive capacity ({capacity}).")
        if room_id and room_id in seen:
            row._fail(f"duplicate room_id '{room_id}' (first seen on row {seen[room_id]})")
        elif room_id:
            seen[room_id] = row.line
        room = Room(
            room_id=room_id,
            room_code=room_code,
            capacity=capacity,
            building=row.opt("building"),
            room_type=row.opt("room_type", DEFAULT_ROOM_TYPE).lower(),
            available=row.boolean("available", True),
        )
        if row.ok:
            rooms.append(room)
    if not len(df):
        report.error(file, "no rooms defined")
    return rooms


def _parse_slots(df: pd.DataFrame, report: ValidationReport) -> list[Slot] | None:
    file = "slots.csv"
    if not _has_columns(df, SLOTS, report):
        return None
    parsed: list[tuple[Slot, bool]] = []  # (slot, slot_number given?)
    seen: dict[str, int] = {}
    for row in _rows(df, file, report):
        slot_id = row.text("slot_id")
        day, start, end = row.date_("date"), row.time_("start_time"), row.time_("end_time")
        if row.ok and end <= start:
            row._fail(f"end_time {end:%H:%M} must be after start_time {start:%H:%M}")
        if slot_id and slot_id in seen:
            row._fail(f"duplicate slot_id '{slot_id}' (first seen on row {seen[slot_id]})")
        elif slot_id:
            seen[slot_id] = row.line
        has_number = bool(row.opt("slot_number"))
        number = row.opt_integer("slot_number", 0, minimum=0)
        pref = row.opt_integer("pref_penalty", -1, minimum=0)
        if row.ok:
            parsed.append((Slot(slot_id, day, start, end, number, pref), has_number))
    if not parsed:
        if not len(df):
            report.error(file, "no slots defined.")
        return []

    parsed.sort(key=lambda p: (p[0].date, p[0].start_time))
    slots: list[Slot] = []
    position: dict[date, int] = {}
    for slot, has_number in parsed:
        pos = position.get(slot.date, 0)
        position[slot.date] = pos + 1
        number = slot.slot_number if has_number else pos
        pref = slot.pref_penalty if slot.pref_penalty >= 0 else number
        slots.append(replace(slot, slot_number=number, pref_penalty=pref))
    for prev, nxt in zip(slots, slots[1:]):
        if prev.date == nxt.date and nxt.start_time < prev.end_time:
            report.warn(file, f"slots {prev.slot_id} and {nxt.slot_id} overlap on {prev.date}")
    return slots


def _parse_enrollments(
    df: pd.DataFrame,
    exam_ids: set[str] | None,
    student_ids: set[str] | None,
    report: ValidationReport,
) -> list[tuple[str, str]] | None:
    file = "enrollments.csv"
    if not _has_columns(df, ENROLLMENTS, report):
        return None
    pairs: list[tuple[str, str]] = []
    seen: dict[tuple[str, str], int] = {}
    for row in _rows(df, file, report):
        student_id, exam_id = row.text("student_id"), row.text("exam_id")
        if not row.ok:
            continue
        if student_ids is not None and student_id not in student_ids:
            row._fail(f"{exam_id} references student {student_id}, but {student_id} does not exist.")
        if exam_ids is not None and exam_id not in exam_ids:
            row._fail(f"{student_id} is enrolled in {exam_id}, but {exam_id} does not exist.")
        pair = (student_id, exam_id)
        if pair in seen:
            row._fail(
                f"duplicate enrollment: {student_id} is enrolled in {exam_id} more than once "
                f"(first seen on row {seen[pair]})."
            )
        else:
            seen[pair] = row.line
        if row.ok:
            pairs.append(pair)
    return pairs


def _reconcile_student_counts(
    exams: list[Exam],
    first_line: dict[str, int],
    enrollments: list[tuple[str, str]],
    report: ValidationReport,
) -> list[Exam]:
    """Enrollments are authoritative for student_count (docs/SPEC_DECISIONS.md section 1)."""
    counts: dict[str, int] = {}
    for _, exam_id in enrollments:
        counts[exam_id] = counts.get(exam_id, 0) + 1
    out: list[Exam] = []
    for exam in exams:
        n = counts.get(exam.exam_id, 0)
        line = first_line.get(exam.exam_id)
        if n == 0:
            report.warn("exams.csv", f"{exam.exam_id} has no enrollments; keeping student_count={exam.student_count}.", line)
            out.append(exam)
        elif n != exam.student_count:
            report.warn(
                "exams.csv",
                f"{exam.exam_id} lists student_count={exam.student_count} but has {n} enrollments; using {n}.",
                line,
            )
            out.append(replace(exam, student_count=n))
        else:
            out.append(exam)
    return out


# Single-table parsers for the API, which imports one CSV at a time.
parse_exams = _parse_exams
parse_students = _parse_students
parse_rooms = _parse_rooms
parse_slots = _parse_slots
parse_enrollments = _parse_enrollments
reconcile_student_counts = _reconcile_student_counts


def parse_dataset(
    frames: Mapping[str, pd.DataFrame],
    require: Iterable[str] = ALL_TABLES,
) -> tuple[Dataset | None, ValidationReport]:
    """Validate raw tables and build a Dataset. Returns (None, report) if there are errors."""
    report = ValidationReport()
    for table in require:
        if frames.get(table) is None:
            report.error(f"{table}.csv", "not provided")

    exams_res = _parse_exams(frames[EXAMS], report) if frames.get(EXAMS) is not None else None
    students = _parse_students(frames[STUDENTS], report) if frames.get(STUDENTS) is not None else None
    rooms = _parse_rooms(frames[ROOMS], report) if frames.get(ROOMS) is not None else None
    slots = _parse_slots(frames[SLOTS], report) if frames.get(SLOTS) is not None else None

    exams, first_line = exams_res if exams_res is not None else (None, {})
    enrollments: list[tuple[str, str]] | None = None
    if frames.get(ENROLLMENTS) is not None:
        enrollments = _parse_enrollments(
            frames[ENROLLMENTS],
            {e.exam_id for e in exams} if exams is not None else None,
            {s.student_id for s in students} if students is not None else None,
            report,
        )

    if not report.ok:
        return None, report
    exams = exams or []
    if enrollments is not None:
        exams = _reconcile_student_counts(exams, first_line, enrollments, report)
    dataset = Dataset(
        exams=exams,
        students=students or [],
        enrollments=enrollments or [],
        rooms=rooms or [],
        slots=slots or [],
    )
    return dataset, report


def load_dataset_with_report(data_dir: str | Path) -> tuple[Dataset | None, ValidationReport]:
    data_dir = Path(data_dir)
    frames: dict[str, pd.DataFrame] = {}
    missing = ValidationReport()
    for table in ALL_TABLES:
        path = data_dir / f"{table}.csv"
        if path.is_file():
            frames[table] = read_csv(path)
        else:
            missing.error(f"{table}.csv", f"file not found in {data_dir}")
    if not missing.ok:
        return None, missing
    return parse_dataset(frames)


def load_dataset(data_dir: str | Path) -> Dataset:
    """Load and validate a data directory; raises DataValidationError listing every problem."""
    dataset, report = load_dataset_with_report(data_dir)
    if dataset is None:
        raise DataValidationError(report)
    return dataset
