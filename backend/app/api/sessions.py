from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.analytics.experiment_runner import PROJECT_ROOT
from app.api.deps import get_db, session_or_404
from app.core.validation import DataValidationError
from app.optimization.context import build_context
from app.schemas.session import DataCheck, SampleRequest, SessionCreate, SessionDetail, SessionOut
from app.services import dataset_service
from app.services.conflict_service import dsatur_colors, greedy_clique_size
from app.services.feasibility_service import check_feasibility
from app.services.import_service import load_dataset

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=SessionOut, status_code=201)
def create_session(body: SessionCreate, db: DbSession = Depends(get_db)):
    session = orm.ExamSession(**body.model_dump())
    db.add(session)
    db.commit()
    return session


@router.get("", response_model=list[SessionOut])
def list_sessions(db: DbSession = Depends(get_db)):
    return db.scalars(select(orm.ExamSession).order_by(orm.ExamSession.id.desc())).all()


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: int, db: DbSession = Depends(get_db)):
    session = session_or_404(db, session_id)
    return SessionDetail(**SessionOut.model_validate(session).model_dump(), counts=dataset_service.counts(db, session_id))


@router.post("/{session_id}/load-sample", response_model=SessionDetail)
def load_sample(session_id: int, body: SampleRequest, db: DbSession = Depends(get_db)):
    """Replace the session's data with one of the bundled synthetic datasets (small / medium / large)."""
    session = session_or_404(db, session_id)
    try:
        dataset = load_dataset(PROJECT_ROOT / "data" / body.name)
    except DataValidationError as exc:
        raise HTTPException(500, f"bundled sample '{body.name}' is invalid: {exc}")
    dataset_service.apply_dataset(db, session_id, dataset)
    dates = [s.date for s in dataset.slots]
    session.start_date, session.end_date = min(dates), max(dates)
    session.slots_per_day = max(s.slot_number for s in dataset.slots) + 1
    db.commit()
    return SessionDetail(**SessionOut.model_validate(session).model_dump(), counts=dataset_service.counts(db, session_id))


@router.post("/{session_id}/validate", response_model=DataCheck)
def validate_data(session_id: int, db: DbSession = Depends(get_db)):
    """The "Validate Data" step: completeness, feasibility and problem statistics."""
    session_or_404(db, session_id)
    dataset = dataset_service.load_dataset_from_db(db, session_id).dataset
    missing = [
        f"no {name} imported yet"
        for name, rows in (("exams", dataset.exams), ("students", dataset.students),
                           ("enrollments", dataset.enrollments), ("rooms", dataset.rooms),
                           ("slots", dataset.slots))
        if not rows
    ]
    if missing:
        return DataCheck(ok=False, errors=missing, warnings=[], stats={})
    ctx = build_context(dataset)
    report = check_feasibility(ctx)
    n = ctx.n_exams
    stats = {
        "exams": n, "students": len(dataset.students), "rooms": ctx.n_rooms, "slots": ctx.n_slots,
        "enrollments": len(dataset.enrollments),
        "conflict_density": float((ctx.conflict > 0).sum() / max(1, n * (n - 1))),
        "clique_lower_bound": greedy_clique_size(ctx.conflict),
        "greedy_slots_needed": int(dsatur_colors(ctx.conflict).max()) + 1,
        "largest_exam": int(ctx.student_count.max()),
        "largest_room": int(ctx.room_capacity.max()),
    }
    return DataCheck(ok=report.ok, errors=report.messages(), warnings=[str(w) for w in report.warnings], stats=stats)
