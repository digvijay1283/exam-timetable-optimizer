from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import fail, get_db, read_upload, session_or_404
from app.core.validation import ValidationReport
from app.schemas.session import ImportResult
from app.services import dataset_service
from app.services.import_service import parse_enrollments, parse_students

router = APIRouter(prefix="/api/sessions/{session_id}", tags=["students"])


@router.post("/students/import", response_model=ImportResult)
async def import_students(session_id: int, file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    """Replace the session's students. Their enrollments are dropped."""
    session_or_404(db, session_id)
    report = ValidationReport()
    students = parse_students(await read_upload(file), report)
    if not report.ok or students is None:
        raise fail(report)
    invalidated = dataset_service.replace_students(db, session_id, students)
    db.commit()
    return ImportResult(imported=len(students), warnings=[str(w) for w in report.warnings], invalidated_timetables=invalidated)


@router.post("/enrollments/import", response_model=ImportResult)
async def import_enrollments(session_id: int, file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    """Replace the session's enrollments. Import exams and students first: references are checked
    against them, and each exam's student_count is set from the enrollments."""
    session_or_404(db, session_id)
    report = ValidationReport()
    pairs = parse_enrollments(
        await read_upload(file),
        dataset_service.existing_codes(db, session_id, orm.Exam),
        dataset_service.existing_codes(db, session_id, orm.Student),
        report,
    )
    if not report.ok or pairs is None:
        raise fail(report)
    invalidated, reconcile = dataset_service.replace_enrollments(db, session_id, pairs)
    db.commit()
    warnings = [str(w) for w in report.warnings] + [str(w) for w in reconcile.warnings]
    return ImportResult(imported=len(pairs), warnings=warnings, invalidated_timetables=invalidated)
