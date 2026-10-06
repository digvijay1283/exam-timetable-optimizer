from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import fail, get_db, read_upload, session_or_404
from app.core.validation import ValidationReport
from app.schemas.session import ImportResult, SlotGenerateRequest
from app.services import dataset_service
from app.services.import_service import parse_slots
from app.services.slot_service import generate_slots

router = APIRouter(prefix="/api/sessions/{session_id}/slots", tags=["slots"])


@router.post("/generate", response_model=ImportResult)
def generate(session_id: int, body: SlotGenerateRequest | None = None, db: DbSession = Depends(get_db)):
    """Generate slots from the session's date range, working days and slots per day."""
    session = session_or_404(db, session_id)
    body = body or SlotGenerateRequest()
    try:
        slots = generate_slots(
            session.start_date, session.end_date,
            slots_per_day=session.slots_per_day, working_days=session.working_days,
            slot_times=body.slot_times, holidays=body.holidays,
        )
    except ValueError as exc:
        raise HTTPException(422, detail={"errors": [str(exc)], "warnings": []})
    if not slots:
        raise HTTPException(422, detail={"errors": ["the date range contains no working days"], "warnings": []})
    invalidated = dataset_service.replace_slots(db, session_id, slots)
    db.commit()
    return ImportResult(imported=len(slots), invalidated_timetables=invalidated)


@router.post("/import", response_model=ImportResult)
async def import_slots(session_id: int, file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    report = ValidationReport()
    slots = parse_slots(await read_upload(file), report)
    if not report.ok or slots is None:
        raise fail(report)
    invalidated = dataset_service.replace_slots(db, session_id, slots)
    db.commit()
    return ImportResult(imported=len(slots), warnings=[str(w) for w in report.warnings], invalidated_timetables=invalidated)


@router.get("")
def list_slots(session_id: int, db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    rows = db.scalars(
        select(orm.Slot).where(orm.Slot.session_id == session_id).order_by(orm.Slot.date, orm.Slot.start_time)
    ).all()
    return [
        {"slot_id": s.external_id, "date": s.date, "start_time": s.start_time, "end_time": s.end_time,
         "slot_number": s.slot_number, "pref_penalty": s.pref_penalty}
        for s in rows
    ]
