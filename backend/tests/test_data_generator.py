from dataclasses import replace

import pytest

from app.optimization.context import build_context
from app.services.data_generator import PRESETS, generate_dataset
from app.services.feasibility_service import check_feasibility


@pytest.mark.parametrize("preset", ["small", "medium", "large"])
def test_presets_are_feasible_and_sized(preset):
    cfg = PRESETS[preset]
    ds = generate_dataset(cfg)
    assert len(ds.exams) == cfg.n_exams
    assert len(ds.students) == cfg.n_students
    assert check_feasibility(build_context(ds)).ok


def test_same_seed_gives_identical_dataset():
    a = generate_dataset(PRESETS["small"])
    b = generate_dataset(PRESETS["small"])
    assert a == b


def test_different_seeds_differ():
    a = generate_dataset(PRESETS["small"])
    b = generate_dataset(replace(PRESETS["small"], seed=43))
    assert a.enrollments != b.enrollments


def test_every_exam_and_student_has_enrollments():
    ds = generate_dataset(PRESETS["medium"])
    counts = {e.exam_id: 0 for e in ds.exams}
    taken = {s.student_id: 0 for s in ds.students}
    for sid, eid in ds.enrollments:
        counts[eid] += 1
        taken[sid] += 1
    assert min(counts.values()) > 0 and min(taken.values()) > 0
    assert [counts[e.exam_id] for e in ds.exams] == [e.student_count for e in ds.exams]


def test_practical_exams_have_labs_and_fit():
    ds = generate_dataset(PRESETS["medium"])
    assert any(e.exam_type == "practical" for e in ds.exams)
    assert any(r.room_type == "lab" for r in ds.rooms)
    ctx = build_context(ds)
    assert ctx.room_ok.any(axis=1).all()
    assert ctx.slot_ok.any(axis=1).all()
