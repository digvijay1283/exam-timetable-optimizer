"""Persist imported data and rebuild the engine's in-memory Dataset from the database.

All data is scoped to an examination session. Changing any input table invalidates the session's
timetables (they were computed from the old data); optimization runs are kept as history.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.core import domain
from app.core.validation import ValidationReport
from app.services.import_service import reconcile_student_counts


@dataclass
class LoadedDataset:
    """A Dataset plus the database primary keys needed to store results against it."""

    dataset: domain.Dataset
    exam_pk: dict[str, int]
    room_pk: dict[str, int]
    slot_pk: dict[str, int]


def load_dataset_from_db(db: DbSession, session_id: int) -> LoadedDataset:
    exams = db.scalars(select(orm.Exam).where(orm.Exam.session_id == session_id).order_by(orm.Exam.id)).all()
    students = db.scalars(select(orm.Student).where(orm.Student.session_id == session_id).order_by(orm.Student.id)).all()
    rooms = db.scalars(select(orm.Room).where(orm.Room.session_id == session_id).order_by(orm.Room.id)).all()
    slots = db.scalars(
        select(orm.Slot).where(orm.Slot.session_id == session_id).order_by(orm.Slot.date, orm.Slot.start_time)
    ).all()
    exam_code = {e.id: e.external_id for e in exams}
    student_code = {s.id: s.external_id for s in students}
    pairs = db.execute(
        select(orm.Enrollment.student_id, orm.Enrollment.exam_id)
        .where(orm.Enrollment.session_id == session_id)
        .order_by(orm.Enrollment.id)
    ).all()
    dataset = domain.Dataset(
        exams=[
            domain.Exam(e.external_id, e.subject_code, e.subject_name, e.department, e.semester,
                        e.duration_minutes, e.student_count, e.exam_type, e.priority)
            for e in exams
        ],
        students=[domain.Student(s.external_id, s.department, s.semester) for s in students],
        enrollments=[(student_code[s], exam_code[e]) for s, e in pairs],
        rooms=[
            domain.Room(r.external_id, r.room_code, r.capacity, r.building, r.room_type, r.available)
            for r in rooms
        ],
        slots=[
            domain.Slot(s.external_id, s.date, s.start_time, s.end_time, s.slot_number, s.pref_penalty)
            for s in slots
        ],
    )
    return LoadedDataset(
        dataset,
        {e.external_id: e.id for e in exams},
        {r.external_id: r.id for r in rooms},
        {s.external_id: s.id for s in slots},
    )


def counts(db: DbSession, session_id: int) -> dict[str, int]:
    def n(model) -> int:
        return db.scalar(select(func.count()).select_from(model).where(model.session_id == session_id)) or 0

    return {
        "exams": n(orm.Exam), "students": n(orm.Student), "enrollments": n(orm.Enrollment),
        "rooms": n(orm.Room), "slots": n(orm.Slot), "timetables": n(orm.Timetable),
    }


def existing_codes(db: DbSession, session_id: int, model) -> set[str]:
    return set(db.scalars(select(model.external_id).where(model.session_id == session_id)).all())


def invalidate_results(db: DbSession, session_id: int) -> int:
    """Delete the session's timetables after its input data changed; returns how many."""
    ids = db.scalars(select(orm.Timetable.id).where(orm.Timetable.session_id == session_id)).all()
    if ids:
        db.execute(update(orm.OptimizationRun).where(orm.OptimizationRun.timetable_id.in_(ids)).values(timetable_id=None))
        db.execute(delete(orm.TimetableEntry).where(orm.TimetableEntry.timetable_id.in_(ids)))
        db.execute(delete(orm.Timetable).where(orm.Timetable.id.in_(ids)))
    return len(ids)


def _replace(db: DbSession, session_id: int, model, rows: list[dict]) -> int:
    invalid = invalidate_results(db, session_id)
    db.execute(delete(model).where(model.session_id == session_id))
    if rows:
        db.execute(insert(model), [{"session_id": session_id, **r} for r in rows])
    return invalid


def replace_exams(db: DbSession, session_id: int, exams: list[domain.Exam]) -> int:
    """Replace the session's exams (and, by cascade, their enrollments)."""
    rows = [
        {"external_id": e.exam_id, "subject_code": e.subject_code, "subject_name": e.subject_name,
         "department": e.department, "semester": e.semester, "duration_minutes": e.duration_minutes,
         "student_count": e.student_count, "exam_type": e.exam_type, "priority": e.priority}
        for e in exams
    ]
    return _replace(db, session_id, orm.Exam, rows)


def replace_students(db: DbSession, session_id: int, students: list[domain.Student]) -> int:
    rows = [{"external_id": s.student_id, "department": s.department, "semester": s.semester} for s in students]
    return _replace(db, session_id, orm.Student, rows)


def replace_rooms(db: DbSession, session_id: int, rooms: list[domain.Room]) -> int:
    rows = [
        {"external_id": r.room_id, "room_code": r.room_code, "building": r.building,
         "capacity": r.capacity, "room_type": r.room_type, "available": r.available}
        for r in rooms
    ]
    return _replace(db, session_id, orm.Room, rows)


def replace_slots(db: DbSession, session_id: int, slots: list[domain.Slot]) -> int:
    rows = [
        {"external_id": s.slot_id, "date": s.date, "start_time": s.start_time, "end_time": s.end_time,
         "slot_number": s.slot_number, "pref_penalty": s.pref_penalty}
        for s in slots
    ]
    return _replace(db, session_id, orm.Slot, rows)


def replace_enrollments(db: DbSession, session_id: int, pairs: list[tuple[str, str]]) -> tuple[int, ValidationReport]:
    """Replace enrollments and set each exam's student_count from them; returns (invalidated, report)."""
    invalid = invalidate_results(db, session_id)
    student_pk = dict(db.execute(select(orm.Student.external_id, orm.Student.id).where(orm.Student.session_id == session_id)).all())
    exam_rows = db.scalars(select(orm.Exam).where(orm.Exam.session_id == session_id).order_by(orm.Exam.id)).all()
    exam_pk = {e.external_id: e.id for e in exam_rows}
    db.execute(delete(orm.Enrollment).where(orm.Enrollment.session_id == session_id))
    if pairs:
        db.execute(
            insert(orm.Enrollment),
            [{"session_id": session_id, "student_id": student_pk[s], "exam_id": exam_pk[e]} for s, e in pairs],
        )
    exams = [
        domain.Exam(e.external_id, e.subject_code, e.subject_name, e.department, e.semester,
                    e.duration_minutes, e.student_count, e.exam_type, e.priority)
        for e in exam_rows
    ]
    report = ValidationReport()
    for fixed in reconcile_student_counts(exams, {}, pairs, report):
        db.execute(
            update(orm.Exam)
            .where(orm.Exam.id == exam_pk[fixed.exam_id])
            .values(student_count=fixed.student_count)
        )
    return invalid, report


def apply_dataset(db: DbSession, session_id: int, dataset: domain.Dataset) -> None:
    """Replace every input table of a session with `dataset` (used to load sample data)."""
    replace_exams(db, session_id, dataset.exams)
    replace_students(db, session_id, dataset.students)
    replace_rooms(db, session_id, dataset.rooms)
    replace_slots(db, session_id, dataset.slots)
    replace_enrollments(db, session_id, dataset.enrollments)
