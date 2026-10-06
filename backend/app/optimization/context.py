"""In-memory optimization context (Architecture section 5).

Built once per run; the GA never touches the database. All arrays are indexed by position in
`dataset.exams`, `dataset.rooms` and `dataset.slots`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from app.core.config import ConstraintParams, Weights
from app.core.domain import Dataset, room_allowed_for_exam
from app.services.conflict_service import build_conflict_matrix, conflict_degree, weighted_conflict_degree


@dataclass
class OptimizationContext:
    dataset: Dataset
    weights: Weights
    params: ConstraintParams

    exam_ids: list[str]
    room_ids: list[str]
    slot_ids: list[str]

    student_count: np.ndarray  # (n_exams,)
    exam_minutes: np.ndarray  # (n_exams,)
    priority: np.ndarray  # (n_exams,)
    room_capacity: np.ndarray  # (n_rooms,)
    room_available: np.ndarray  # (n_rooms,) bool
    slot_minutes: np.ndarray  # (n_slots,)
    slot_pref: np.ndarray  # (n_slots,) 0 = most desirable
    slot_day_index: np.ndarray  # (n_slots,) index among distinct exam dates
    n_days: int

    conflict: np.ndarray  # (n_exams, n_exams) int32
    degree: np.ndarray  # (n_exams,) number of conflicting exams
    weighted_degree: np.ndarray  # (n_exams,) total shared students
    # Sparse view of the conflict matrix: every pair i < j with C[i][j] > 0.
    pair_i: np.ndarray
    pair_j: np.ndarray
    pair_c: np.ndarray

    room_type_ok: np.ndarray  # (n_exams, n_rooms) bool
    room_ok: np.ndarray  # (n_exams, n_rooms) bool: capacity, availability and type all fine
    slot_ok: np.ndarray  # (n_exams, n_slots) bool: exam duration fits the slot

    pair_consecutive: np.ndarray  # (n_slots, n_slots) int8
    pair_gap: np.ndarray  # (n_slots, n_slots) int8

    @property
    def n_exams(self) -> int:
        return len(self.exam_ids)

    @property
    def n_rooms(self) -> int:
        return len(self.room_ids)

    @property
    def n_slots(self) -> int:
        return len(self.slot_ids)

    @property
    def fair_exams_per_day(self) -> int:
        return int(-(-self.n_exams // max(1, self.n_days)))  # ceil

    def exam_index(self) -> dict[str, int]:
        return {e: i for i, e in enumerate(self.exam_ids)}

    def room_index(self) -> dict[str, int]:
        return {r: i for i, r in enumerate(self.room_ids)}

    def slot_index(self) -> dict[str, int]:
        return {s: i for i, s in enumerate(self.slot_ids)}


def build_context(
    dataset: Dataset,
    weights: Weights | None = None,
    params: ConstraintParams | None = None,
) -> OptimizationContext:
    weights = weights or Weights()
    params = params or ConstraintParams()
    exams, rooms, slots = dataset.exams, dataset.rooms, dataset.slots

    student_count = np.array([e.student_count for e in exams], dtype=np.int32)
    exam_minutes = np.array([e.duration_minutes for e in exams], dtype=np.int32)
    priority = np.array([e.priority for e in exams], dtype=np.int32)
    room_capacity = np.array([r.capacity for r in rooms], dtype=np.int32)
    room_available = np.array([r.available for r in rooms], dtype=bool)
    slot_minutes = np.array([s.duration_minutes for s in slots], dtype=np.int32)
    slot_pref = np.array([s.pref_penalty for s in slots], dtype=np.int32)
    slot_pos = np.array([s.slot_number for s in slots], dtype=np.int32)
    ordinals = np.array([s.date.toordinal() for s in slots], dtype=np.int64)

    unique_days = np.unique(ordinals)
    slot_day_index = np.searchsorted(unique_days, ordinals).astype(np.int32)

    conflict = build_conflict_matrix(dataset)
    iu, ju = np.triu_indices(len(exams), 1)
    has_conflict = conflict[iu, ju] > 0
    pair_i, pair_j = iu[has_conflict], ju[has_conflict]
    pair_c = conflict[pair_i, pair_j].astype(np.int64)

    room_type_ok = np.array(
        [[room_allowed_for_exam(e.exam_type, r.room_type) for r in rooms] for e in exams], dtype=bool
    ).reshape(len(exams), len(rooms))
    room_ok = (
        (room_capacity[None, :] >= student_count[:, None]) & room_available[None, :] & room_type_ok
    )
    slot_ok = slot_minutes[None, :] >= exam_minutes[:, None]

    # Slot-pair relations used by the pairwise soft penalties (docs/SPEC_DECISIONS.md section 4).
    day_diff = np.abs(ordinals[:, None] - ordinals[None, :])
    same_day = (day_diff == 0) & ~np.eye(len(slots), dtype=bool)
    consecutive = same_day & (np.abs(slot_pos[:, None] - slot_pos[None, :]) == 1)
    gap = (same_day & ~consecutive) | ((day_diff >= 1) & (day_diff <= params.short_gap_days))

    return OptimizationContext(
        dataset=dataset,
        weights=weights,
        params=params,
        exam_ids=[e.exam_id for e in exams],
        room_ids=[r.room_id for r in rooms],
        slot_ids=[s.slot_id for s in slots],
        student_count=student_count,
        exam_minutes=exam_minutes,
        priority=priority,
        room_capacity=room_capacity,
        room_available=room_available,
        slot_minutes=slot_minutes,
        slot_pref=slot_pref,
        slot_day_index=slot_day_index,
        n_days=len(unique_days),
        conflict=conflict,
        degree=conflict_degree(conflict),
        weighted_degree=weighted_conflict_degree(conflict),
        pair_i=pair_i,
        pair_j=pair_j,
        pair_c=pair_c,
        room_type_ok=room_type_ok,
        room_ok=room_ok,
        slot_ok=slot_ok,
        pair_consecutive=consecutive.astype(np.int8),
        pair_gap=gap.astype(np.int8),
    )
