from __future__ import annotations

import io
from typing import Iterator

import pandas as pd
from fastapi import HTTPException, Request, UploadFile
from sqlalchemy.orm import Session as DbSession

from app import models as orm
from app.core.validation import ValidationReport
from app.services.import_service import read_csv
from app.services.job_service import JobRunner


def get_db(request: Request) -> Iterator[DbSession]:
    with request.app.state.session_factory() as db:
        yield db


def get_jobs(request: Request) -> JobRunner:
    return request.app.state.jobs


def session_or_404(db: DbSession, session_id: int) -> orm.ExamSession:
    session = db.get(orm.ExamSession, session_id)
    if session is None:
        raise HTTPException(404, f"session {session_id} not found")
    return session


def fail(report: ValidationReport, status: int = 422) -> HTTPException:
    return HTTPException(
        status, detail={"errors": report.messages(), "warnings": [str(w) for w in report.warnings]}
    )


async def read_upload(file: UploadFile) -> pd.DataFrame:
    raw = await file.read()
    try:
        return read_csv(io.BytesIO(raw))
    except Exception as exc:  # malformed or empty CSV
        raise HTTPException(422, detail={"errors": [f"{file.filename}: could not read CSV ({exc})"], "warnings": []})
