"""The real execution path: the GA runs in a separate process and the API polls its progress
from SQLite (WAL) while it is still running."""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

SESSION = {
    "name": "Process mode", "academic_year": "2026-27", "semester": "VII",
    "start_date": "2026-11-20", "end_date": "2026-12-31", "slots_per_day": 2,
}


@pytest.fixture
def client(tmp_path):
    app = create_app(f"sqlite:///{(tmp_path / 'proc.db').as_posix()}", job_mode="process")
    with TestClient(app) as c:
        yield c


def wait_for(client, run_id, timeout=120):
    deadline = time.time() + timeout
    seen = []
    while time.time() < deadline:
        p = client.get(f"/api/optimization/{run_id}/progress").json()
        seen.append(p)
        if p["status"] in ("completed", "failed"):
            return p, seen
        time.sleep(0.2)
    raise AssertionError(f"run did not finish: {seen[-1]}")


def test_background_run_completes_and_reports_progress(client):
    sid = client.post("/api/sessions", json=SESSION).json()["id"]
    client.post(f"/api/sessions/{sid}/load-sample", json={"name": "small"})
    r = client.post(
        "/api/optimization/run",
        json={"session_id": sid, "params": {"population_size": 30, "generations": 40, "early_stopping": False}},
    )
    assert r.status_code == 202
    final, seen = wait_for(client, r.json()["id"])

    assert final["status"] == "completed", final["error"]
    assert final["current_generation"] == 40 and len(final["history"]) == 41
    assert final["timetable_id"] is not None
    assert {p["status"] for p in seen} <= {"queued", "running", "completed"}
    tt = client.get(f"/api/timetables/{final['timetable_id']}").json()
    assert tt["hard_violations"] == 0 and tt["total_entries"] == 20
    assert client.post(f"/api/timetables/{tt['id']}/validate").json()["valid"]


def test_failed_run_is_recorded_not_lost(client):
    sid = client.post("/api/sessions", json=SESSION).json()["id"]
    client.post(f"/api/sessions/{sid}/load-sample", json={"name": "small"})
    run_id = client.post(
        "/api/optimization/run",
        json={"session_id": sid, "params": {"population_size": 10, "generations": 2, "early_stopping": False}},
    ).json()["id"]
    wait_for(client, run_id)
    # Corrupt the stored parameters of a second run so the worker raises.
    from sqlalchemy import update

    from app import models as orm

    with client.app.state.session_factory() as db:
        run = orm.OptimizationRun(session_id=sid, method="ga", params={"population_size": 1}, weights={})
        db.add(run)
        db.commit()
        bad_id = run.id
    client.app.state.jobs.submit(bad_id)
    final, _ = wait_for(client, bad_id)
    assert final["status"] == "failed" and "population_size" in final["error"]
