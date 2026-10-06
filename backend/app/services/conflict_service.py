"""Exam conflict matrix and graph helpers (PRD FR-03, Architecture section 6)."""
from __future__ import annotations

import numpy as np

from app.core.domain import Dataset


def build_conflict_matrix(dataset: Dataset) -> np.ndarray:
    """C[i][j] = number of students enrolled in both exams; symmetric, zero diagonal, int32."""
    exam_idx = {e.exam_id: i for i, e in enumerate(dataset.exams)}
    student_idx = {s.student_id: i for i, s in enumerate(dataset.students)}
    enrolled = np.zeros((len(student_idx), len(exam_idx)), dtype=np.int32)
    for student_id, exam_id in dataset.enrollments:
        enrolled[student_idx[student_id], exam_idx[exam_id]] = 1
    conflict = enrolled.T @ enrolled
    np.fill_diagonal(conflict, 0)
    return conflict.astype(np.int32)


def conflict_degree(conflict: np.ndarray) -> np.ndarray:
    """Number of other exams each exam conflicts with."""
    return (conflict > 0).sum(axis=1)


def weighted_conflict_degree(conflict: np.ndarray) -> np.ndarray:
    """Total number of shared students across all conflicting exams (tie-breaker)."""
    return conflict.sum(axis=1)


def greedy_clique_size(conflict: np.ndarray) -> int:
    """Size of a clique of mutually conflicting exams found greedily.

    Every exam in a clique needs its own slot, so this is a valid lower bound on slots needed.
    """
    n = len(conflict)
    if n == 0:
        return 0
    adj = conflict > 0
    degree = adj.sum(axis=1)
    best = 1
    for start in range(n):
        size = 1
        candidates = adj[start].copy()
        while candidates.any():
            idx = np.flatnonzero(candidates)
            pick = idx[np.argmax(degree[idx])]
            size += 1
            candidates &= adj[pick]
        best = max(best, size)
    return best


def dsatur_colors(conflict: np.ndarray) -> np.ndarray:
    """DSATUR colouring: colors[i] is the (0-based) slot class of exam i with no student clashes.

    The number of colours used is an upper bound on the slots a clash-free timetable needs.
    """
    n = len(conflict)
    colors = np.full(n, -1, dtype=np.int64)
    if n == 0:
        return colors
    adj = conflict > 0
    degree = adj.sum(axis=1)
    neighbour_colors: list[set[int]] = [set() for _ in range(n)]
    for _ in range(n):
        uncolored = np.flatnonzero(colors < 0)
        pick = max(uncolored, key=lambda v: (len(neighbour_colors[v]), degree[v], -v))
        color = 0
        while color in neighbour_colors[pick]:
            color += 1
        colors[pick] = color
        for u in np.flatnonzero(adj[pick]):
            neighbour_colors[u].add(color)
    return colors
