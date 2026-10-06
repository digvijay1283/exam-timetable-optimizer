from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import fail, get_db, read_upload, session_or_404
from app.core.validation import ValidationReport
from app.schemas.session import ImportResult
from app.services import dataset_service
from app.services.import_service import parse_exams

router = APIRouter(prefix="/api/sessions/{session_id}/exams", tags=["exams"])


@router.post("/import", response_model=ImportResult)
async def import_exams(session_id: int, file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    """Replace the session's exams from an exams.csv. Enrollments of replaced exams are dropped."""
    session_or_404(db, session_id)
    report = ValidationReport()
    parsed = parse_exams(await read_upload(file), report)
    if not report.ok or parsed is None:
        raise fail(report)
    exams, _ = parsed
    invalidated = dataset_service.replace_exams(db, session_id, exams)
    db.commit()
    return ImportResult(imported=len(exams), warnings=[str(w) for w in report.warnings], invalidated_timetables=invalidated)


@router.get("")
def list_exams(session_id: int, db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    rows = db.scalars(select(orm.Exam).where(orm.Exam.session_id == session_id).order_by(orm.Exam.id)).all()
    return [
        {
            "exam_id": e.external_id, "subject_code": e.subject_code, "subject_name": e.subject_name,
            "department": e.department, "semester": e.semester, "duration_minutes": e.duration_minutes,
            "student_count": e.student_count, "exam_type": e.exam_type, "priority": e.priority,
        }
        for e in rows
    ]
