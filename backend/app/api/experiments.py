from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services import experiment_service as svc

router = APIRouter(prefix="/api/experiments", tags=["experiments"])


class ExperimentRunRequest(BaseModel):
    name: str
    max_seeds: int | None = Field(default=None, ge=1, description="use only the first N seeds (quick run)")


@router.get("")
def list_experiments():
    return svc.list_experiments()


@router.post("/run", status_code=202)
def run_experiment(body: ExperimentRunRequest):
    """Start a configured experiment as a background process; poll /api/experiments/jobs/{id}."""
    try:
        return svc.launch(body.name, body.max_seeds)
    except KeyError:
        raise HTTPException(404, f"unknown experiment '{body.name}'; available: {svc.available_configs()}")


@router.get("/jobs/{job_id}")
def job_status(job_id: str):
    status = svc.job_status(job_id)
    if status is None:
        raise HTTPException(404, "job not found")
    return status


@router.get("/{name}")
def get_experiment(name: str):
    if name not in svc.available_configs():
        raise HTTPException(404, f"unknown experiment '{name}'")
    detail = svc.experiment_detail(name)
    if detail is None:
        raise HTTPException(404, f"experiment '{name}' has not been run yet")
    return detail
