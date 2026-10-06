from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.api.deps import get_db, session_or_404
from app.optimization.validator import validate_timetable
from app.schemas.timetable import TimetableDetail, TimetableOut, ValidateRequest, ValidationOut
from app.services import timetable_service as svc
from app.services.dataset_service import load_dataset_from_db

router = APIRouter(tags=["timetables"])


def _timetable_or_404(db: DbSession, timetable_id: int) -> orm.Timetable:
    timetable = db.get(orm.Timetable, timetable_id)
    if timetable is None:
        raise HTTPException(404, f"timetable {timetable_id} not found")
    return timetable


@router.get("/api/sessions/{session_id}/timetables", response_model=list[TimetableOut])
def list_timetables(session_id: int, db: DbSession = Depends(get_db)):
    session_or_404(db, session_id)
    return db.scalars(
        select(orm.Timetable).where(orm.Timetable.session_id == session_id).order_by(orm.Timetable.id.desc())
    ).all()


@router.get("/api/timetables/{timetable_id}", response_model=TimetableDetail)
def get_timetable(
    timetable_id: int,
    department: str | None = None,
    semester: str | None = None,
    date: date | None = None,
    room: str | None = None,
    subject: str | None = None,
    db: DbSession = Depends(get_db),
):
    """Timetable with its entries; optional filters per PRD section 10."""
    timetable = _timetable_or_404(db, timetable_id)
    rows = svc.entry_rows(db, timetable_id)
    shown = svc.filter_rows(rows, department, semester, date, room, subject)
    return TimetableDetail(**TimetableOut.model_validate(timetable).model_dump(), entries=shown, total_entries=len(rows))


@router.post("/api/timetables/validate", response_model=ValidationOut)
def validate_entries(body: ValidateRequest, db: DbSession = Depends(get_db)):
    """Validate any proposed timetable, e.g. a manually edited one, against the session's data."""
    session_or_404(db, body.session_id)
    dataset = load_dataset_from_db(db, body.session_id).dataset
    result = validate_timetable(dataset, [(e.exam_id, e.slot_id, e.room_id) for e in body.entries])
    return ValidationOut(**result.to_dict() | {"details": list(result.details)})


@router.post("/api/timetables/{timetable_id}/validate", response_model=ValidationOut)
def validate_stored(timetable_id: int, db: DbSession = Depends(get_db)):
    result = svc.validate_stored(db, _timetable_or_404(db, timetable_id))
    return ValidationOut(**result.to_dict() | {"details": list(result.details)})


@router.post("/api/timetables/{timetable_id}/approve", response_model=TimetableOut)
def approve_timetable(timetable_id: int, db: DbSession = Depends(get_db)):
    timetable = _timetable_or_404(db, timetable_id)
    result = svc.approve(db, timetable)
    if not result.valid:
        raise HTTPException(
            409,
            detail={"errors": [f"cannot approve: {result.hard_violations} hard violation(s)", *result.details[:20]],
                    "warnings": []},
        )
    db.commit()
    return timetable


def _exportable(db: DbSession, timetable_id: int) -> tuple[orm.Timetable, list[dict]]:
    timetable = _timetable_or_404(db, timetable_id)
    if timetable.hard_violations > 0 or timetable.status == "infeasible":
        raise HTTPException(409, detail={"errors": ["an infeasible timetable cannot be exported"], "warnings": []})
    return timetable, svc.entry_rows(db, timetable_id)


@router.get("/api/export/{timetable_id}/csv")
def export_csv(timetable_id: int, db: DbSession = Depends(get_db)):
    _, rows = _exportable(db, timetable_id)
    return Response(
        svc.export_csv(rows), media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="timetable_{timetable_id}.csv"'},
    )


@router.get("/api/export/{timetable_id}/xlsx")
def export_xlsx(timetable_id: int, db: DbSession = Depends(get_db)):
    timetable, rows = _exportable(db, timetable_id)
    return Response(
        svc.export_xlsx(rows, timetable.name),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="timetable_{timetable_id}.xlsx"'},
    )
