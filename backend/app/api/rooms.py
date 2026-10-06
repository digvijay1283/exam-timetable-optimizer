from __future__ import annotations

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import fail, get_db, read_upload, session_or_404
from app.core.validation import ValidationReport
from app.schemas.session import ImportResult
from app.services import dataset_service
from app.services.import_service import parse_rooms

router = APIRouter(prefix="/api/sessions/{session_id}/rooms", tags=["rooms"])


@router.post("/import", response_model=ImportResult)
async def import_rooms(session_id: int, file: UploadFile = File(...), db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    report = ValidationReport()
    rooms = parse_rooms(await read_upload(file), report)
    if not report.ok or rooms is None:
        raise fail(report)
    invalidated = dataset_service.replace_rooms(db, session_id, rooms)
    db.commit()
    return ImportResult(imported=len(rooms), warnings=[str(w) for w in report.warnings], invalidated_timetables=invalidated)


@router.get("")
def list_rooms(session_id: int, db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    rows = db.scalars(select(orm.Room).where(orm.Room.session_id == session_id).order_by(orm.Room.id)).all()
    return [
        {"room_id": r.external_id, "room_code": r.room_code, "building": r.building,
         "capacity": r.capacity, "room_type": r.room_type, "available": r.available}
        for r in rows
    ]
