"""Seeded synthetic dataset generator.

Models a university: departments x semesters form cohorts that share core exams; students also
take electives and occasionally a carry-over (backlog) exam from another cohort, which creates
the cross-cohort conflicts that make the problem hard. The generator guarantees the result
passes the feasibility check (a clash-free timetable with enough rooms exists).

CLI:  python -m app.services.data_generator --preset medium --seed 42 --out ../data/medium
"""
from __future__ import annotations

import argparse
import math
from dataclasses import dataclass, replace
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.core.domain import Dataset, Exam, Room, Student
from app.optimization.context import build_context
from app.services.conflict_service import build_conflict_matrix, dsatur_colors, greedy_clique_size
from app.services.feasibility_service import check_feasibility
from app.services.slot_service import generate_slots

DEPARTMENTS = ["CSE", "ECE", "MECH", "CIVIL", "IT", "EEE"]
ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6, "VII": 7, "VIII": 8}
BUILDINGS = ["Main", "Annex", "Science"]


@dataclass(frozen=True)
class GeneratorConfig:
    n_exams: int = 50
    n_students: int = 500
    seed: int = 42
    n_departments: int = 4
    semesters: tuple[str, ...] = ("III", "V")
    slots_per_day: int = 2
    start_date: date = date(2026, 11, 20)
    slack: float = 1.4  # slots = ceil(slack x greedy-colouring slots)
    core_fraction: float = 0.7
    practical_fraction: float = 0.1
    backlog_prob: float = 0.10
    attendance_prob: float = 0.97  # chance a student sits each core exam of their cohort
    max_electives: int = 2


PRESETS: dict[str, GeneratorConfig] = {
    "small": GeneratorConfig(n_exams=20, n_students=200),
    "medium": GeneratorConfig(n_exams=50, n_students=500),
    "large": GeneratorConfig(n_exams=100, n_students=800, n_departments=5),
}


def _round_up(value: float, step: int = 10) -> int:
    return int(math.ceil(value / step) * step)


def _width(n: int) -> int:
    return max(3, len(str(n)))


def _classes_fit(classes: list[list[int]], sizes: np.ndarray, caps: list[int]) -> bool:
    """Best-fit matching check: the i-th largest exam of a class must fit the i-th largest room."""
    caps_sorted = sorted(caps, reverse=True)
    for members in classes:
        need = sorted((int(sizes[i]) for i in members), reverse=True)
        if len(need) > len(caps_sorted) or any(n > c for n, c in zip(need, caps_sorted)):
            return False
    return True


def _make_rooms(
    sizes: np.ndarray,
    is_practical: np.ndarray,
    color_classes: list[list[int]],
) -> list[Room]:
    theory_sizes = sizes[~is_practical]
    practical_sizes = sizes[is_practical]
    theory_classes = [[i for i in c if not is_practical[i]] for c in color_classes]
    practical_classes = [[i for i in c if is_practical[i]] for c in color_classes]

    rooms: list[Room] = []

    def add(kind: str, capacity: int) -> None:
        n = len(rooms) + 1
        rooms.append(
            Room(
                room_id=f"R{n:02d}",
                room_code=f"{kind[0].upper()}{100 + n}",
                capacity=capacity,
                building=BUILDINGS[n % len(BUILDINGS)],
                room_type=kind,
                available=True,
            )
        )

    if len(theory_sizes):
        peak = max(len(c) for c in theory_classes)
        n_rooms = max(6, math.ceil(1.5 * peak))
        quantiles = (np.arange(n_rooms) + 1) / n_rooms
        caps = [_round_up(float(np.quantile(theory_sizes, q)) * 1.25) for q in quantiles]
        top = _round_up(float(theory_sizes.max()) * 1.25)
        while not _classes_fit(theory_classes, sizes, caps):
            caps.append(top)
        for cap in sorted(caps):
            add("hall" if cap >= 120 else "classroom", cap)

    if len(practical_sizes):
        peak = max(len(c) for c in practical_classes)
        cap = _round_up(float(practical_sizes.max()) * 1.2)
        caps = [cap] * max(2, math.ceil(1.5 * peak))
        while not _classes_fit(practical_classes, sizes, caps):
            caps.append(cap)
        for c in caps:
            add("lab", c)
    return rooms


def generate_dataset(cfg: GeneratorConfig) -> Dataset:
    rng = np.random.default_rng(cfg.seed)
    depts = DEPARTMENTS[: cfg.n_departments]
    n_exams = cfg.n_exams
    n_core = max(1, round(cfg.core_fraction * n_exams))
    n_elec = n_exams - n_core

    # Cohorts interleaved by semester so truncation keeps departments balanced.
    cohorts = [(d, s) for s in cfg.semesters for d in depts][: max(1, n_core)]
    n_cohorts = len(cohorts)

    # --- exam skeleton: (department, semester, code, name, is_core) ---------------------------
    meta: list[tuple[str, str, str, str, bool]] = []
    per_cohort_count = [0] * n_cohorts
    for k in range(n_core):
        c = k % n_cohorts
        per_cohort_count[c] += 1
        dept, sem = cohorts[c]
        code = f"{dept}{ROMAN.get(sem, sem)}{per_cohort_count[c]:02d}"
        meta.append((dept, sem, code, f"{dept} Core {per_cohort_count[c]} (Sem {sem})", True))
    for j in range(n_elec):
        dept = depts[j % len(depts)]
        sem = cfg.semesters[j % len(cfg.semesters)]
        meta.append((dept, sem, f"{dept}E{j + 1:02d}", f"{dept} Elective {j + 1}", False))

    core_of_cohort = [[k for k in range(n_core) if k % n_cohorts == c] for c in range(n_cohorts)]
    elective_ids = list(range(n_core, n_exams))

    # --- students and enrollments -------------------------------------------------------------
    cohort_p = rng.dirichlet(np.full(n_cohorts, 8.0))
    elective_p = rng.dirichlet(np.full(n_elec, 2.0)) if n_elec else None
    sw = _width(cfg.n_students)
    students: list[Student] = []
    enrolled: list[set[int]] = []
    for i in range(cfg.n_students):
        c = int(rng.choice(n_cohorts, p=cohort_p))
        dept, sem = cohorts[c]
        students.append(Student(f"ST{i + 1:0{sw}d}", dept, sem))
        exams_taken = {k for k in core_of_cohort[c] if rng.random() < cfg.attendance_prob}
        if n_elec:
            take = int(rng.integers(1, cfg.max_electives + 1))
            picks = rng.choice(n_elec, size=min(take, n_elec), replace=False, p=elective_p)
            exams_taken.update(elective_ids[int(p)] for p in picks)
        if rng.random() < cfg.backlog_prob:
            others = [k for k in range(n_core) if k not in core_of_cohort[c] and k not in exams_taken]
            if others:
                exams_taken.add(int(rng.choice(others)))
        if not exams_taken:
            exams_taken.add(int(rng.integers(0, n_exams)))
        enrolled.append(exams_taken)

    # Make sure every exam has students (an unpopular elective could end up empty).
    counts = np.zeros(n_exams, dtype=int)
    for taken in enrolled:
        for k in taken:
            counts[k] += 1
    for k in np.flatnonzero(counts == 0):
        for s in rng.choice(cfg.n_students, size=min(5, cfg.n_students), replace=False):
            enrolled[int(s)].add(int(k))
            counts[k] += 1

    ew = _width(n_exams)
    exam_ids = [f"EXM{k + 1:0{ew}d}" for k in range(n_exams)]
    enrollments = [
        (students[s].student_id, exam_ids[k]) for s, taken in enumerate(enrolled) for k in sorted(taken)
    ]
    sizes = np.zeros(n_exams, dtype=int)
    for taken in enrolled:
        for k in taken:
            sizes[k] += 1

    # --- conflict structure drives the calendar and the room mix -------------------------------
    skeleton = Dataset(
        exams=[
            Exam(exam_ids[k], meta[k][2], meta[k][3], meta[k][0], meta[k][1], 180, int(sizes[k]), "theory")
            for k in range(n_exams)
        ],
        students=students,
        enrollments=enrollments,
    )
    conflict = build_conflict_matrix(skeleton)
    colors = dsatur_colors(conflict)
    n_colors = int(colors.max()) + 1
    clique = greedy_clique_size(conflict)
    classes = [[int(i) for i in np.flatnonzero(colors == c)] for c in range(n_colors)]

    min_slots = max(math.ceil(cfg.slack * n_colors), clique + 1, 2 * cfg.slots_per_day)
    slots = generate_slots(cfg.start_date, slots_per_day=cfg.slots_per_day, min_slots=min_slots)
    slot_len = min(s.duration_minutes for s in slots)

    # --- exam attributes ----------------------------------------------------------------------
    core_idx = np.arange(n_core)
    n_prac = min(n_core, round(cfg.practical_fraction * n_exams))
    practical = set(int(k) for k in rng.choice(core_idx, size=n_prac, replace=False)) if n_prac else set()
    durations = [d for d in (120, 180) if d <= slot_len] or [slot_len]
    exams: list[Exam] = []
    for k in range(n_exams):
        is_prac = k in practical
        duration = int(rng.choice(durations, p=[0.3, 0.7] if len(durations) == 2 else None))
        exams.append(
            Exam(
                exam_id=exam_ids[k],
                subject_code=meta[k][2],
                subject_name=meta[k][3],
                department=meta[k][0],
                semester=meta[k][1],
                duration_minutes=min(180, slot_len) if is_prac else duration,
                student_count=int(sizes[k]),
                exam_type="practical" if is_prac else "theory",
                priority=int(rng.choice([0, 1, 2], p=[0.8, 0.15, 0.05])),
            )
        )

    is_practical = np.array([e.exam_type == "practical" for e in exams], dtype=bool)
    rooms = _make_rooms(sizes, is_practical, classes)

    dataset = Dataset(exams=exams, students=students, enrollments=enrollments, rooms=rooms, slots=slots)
    report = check_feasibility(build_context(dataset))
    if not report.ok:  # a generator bug, never a user error
        raise RuntimeError("generated an infeasible dataset: " + "; ".join(report.messages()))
    return dataset


def write_dataset(dataset: Dataset, out_dir: str | Path) -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "exam_id": e.exam_id, "subject_code": e.subject_code, "subject_name": e.subject_name,
                "department": e.department, "semester": e.semester,
                "duration_minutes": e.duration_minutes, "student_count": e.student_count,
                "exam_type": e.exam_type, "priority": e.priority,
            }
            for e in dataset.exams
        ]
    ).to_csv(out / "exams.csv", index=False)
    pd.DataFrame(
        [{"student_id": s.student_id, "department": s.department, "semester": s.semester} for s in dataset.students]
    ).to_csv(out / "students.csv", index=False)
    pd.DataFrame(dataset.enrollments, columns=["student_id", "exam_id"]).to_csv(out / "enrollments.csv", index=False)
    pd.DataFrame(
        [
            {
                "room_id": r.room_id, "room_code": r.room_code, "building": r.building,
                "capacity": r.capacity, "room_type": r.room_type, "available": str(r.available).lower(),
            }
            for r in dataset.rooms
        ]
    ).to_csv(out / "rooms.csv", index=False)
    pd.DataFrame(
        [
            {
                "slot_id": s.slot_id, "date": s.date.isoformat(),
                "start_time": s.start_time.strftime("%H:%M"), "end_time": s.end_time.strftime("%H:%M"),
                "slot_number": s.slot_number, "pref_penalty": s.pref_penalty,
            }
            for s in dataset.slots
        ]
    ).to_csv(out / "slots.csv", index=False)


def describe(dataset: Dataset) -> str:
    conflict = build_conflict_matrix(dataset)
    n = len(dataset.exams)
    density = float((conflict > 0).sum() / max(1, n * (n - 1)))
    per_student = len(dataset.enrollments) / max(1, len(dataset.students))
    return (
        f"{n} exams, {len(dataset.students)} students, {len(dataset.rooms)} rooms, {len(dataset.slots)} slots | "
        f"{per_student:.1f} exams/student | conflict density {density:.0%} | "
        f"clique>={greedy_clique_size(conflict)} | DSATUR slots={int(dsatur_colors(conflict).max()) + 1}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a synthetic examination dataset.")
    parser.add_argument("--preset", choices=sorted(PRESETS), default="medium")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--exams", type=int, help="override the preset's number of exams")
    parser.add_argument("--students", type=int, help="override the preset's number of students")
    parser.add_argument("--slots-per-day", type=int)
    parser.add_argument("--out", required=True, help="output directory for the CSV files")
    args = parser.parse_args()

    cfg = replace(PRESETS[args.preset], seed=args.seed)
    if args.exams:
        cfg = replace(cfg, n_exams=args.exams)
    if args.students:
        cfg = replace(cfg, n_students=args.students)
    if args.slots_per_day:
        cfg = replace(cfg, slots_per_day=args.slots_per_day)
    dataset = generate_dataset(cfg)
    write_dataset(dataset, args.out)
    print(f"wrote {args.out}: {describe(dataset)}")


if __name__ == "__main__":
    main()
