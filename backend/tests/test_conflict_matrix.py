import numpy as np

from app.core.domain import Dataset, Exam, Student
from app.services.conflict_service import (
    build_conflict_matrix,
    conflict_degree,
    dsatur_colors,
    greedy_clique_size,
    weighted_conflict_degree,
)


def test_conflict_matrix_matches_architecture_example(tiny_dataset):
    c = build_conflict_matrix(tiny_dataset)
    expected = np.array([[0, 20, 0], [20, 0, 7], [0, 7, 0]])
    assert (c == expected).all()
    assert c.dtype == np.int32


def test_matrix_is_symmetric_with_zero_diagonal(tiny_dataset):
    c = build_conflict_matrix(tiny_dataset)
    assert (c == c.T).all()
    assert (np.diag(c) == 0).all()


def test_degrees(tiny_dataset):
    c = build_conflict_matrix(tiny_dataset)
    assert conflict_degree(c).tolist() == [1, 2, 1]
    assert weighted_conflict_degree(c).tolist() == [20, 27, 7]


def test_matrix_matches_bruteforce_on_random_enrollments():
    rng = np.random.default_rng(0)
    n_exams, n_students = 12, 60
    exams = [Exam(f"E{i}", "c", "n", "d", "s", 60, 1, "theory") for i in range(n_exams)]
    students = [Student(f"S{i}") for i in range(n_students)]
    taken = {s.student_id: set(rng.choice(n_exams, size=rng.integers(1, 6), replace=False)) for s in students}
    enrollments = [(sid, f"E{k}") for sid, ks in taken.items() for k in ks]
    c = build_conflict_matrix(Dataset(exams, students, enrollments))
    for i in range(n_exams):
        for j in range(n_exams):
            expected = 0 if i == j else sum(1 for ks in taken.values() if i in ks and j in ks)
            assert c[i, j] == expected


def test_clique_and_dsatur_on_chain(tiny_dataset):
    c = build_conflict_matrix(tiny_dataset)  # E1-E2, E2-E3 (a path)
    assert greedy_clique_size(c) == 2
    colors = dsatur_colors(c)
    assert colors.max() + 1 == 2
    assert colors[0] == colors[2] != colors[1]


def test_dsatur_is_a_proper_colouring_and_clique_is_lower_bound():
    rng = np.random.default_rng(1)
    n = 30
    upper = np.triu(rng.integers(0, 3, size=(n, n)), 1)
    c = (upper + upper.T).astype(np.int32)
    colors = dsatur_colors(c)
    for i in range(n):
        for j in range(n):
            if c[i, j] > 0:
                assert colors[i] != colors[j]
    assert greedy_clique_size(c) <= colors.max() + 1


def test_empty_graph():
    c = np.zeros((0, 0), dtype=np.int32)
    assert greedy_clique_size(c) == 0
    assert len(dsatur_colors(c)) == 0
