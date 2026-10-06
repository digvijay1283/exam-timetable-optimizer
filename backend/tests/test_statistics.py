import math

import numpy as np
import pytest

from app.analytics.convergence import generations_to_reach, mean_std_band, stack_histories
from app.analytics.statistics import cliffs_delta, improvement_percent, mann_whitney_less, summarize


def test_summarize_matches_numpy():
    values = [5, 1, 9, 3, 7]
    s = summarize(values)
    assert s == {"n": 5, "mean": 5.0, "median": 5.0, "std": pytest.approx(np.std(values, ddof=1)), "min": 1.0, "max": 9.0}


def test_summarize_edge_cases():
    assert summarize([4.0])["std"] == 0.0
    assert math.isnan(summarize([])["mean"])


def test_improvement_percent_formula_from_prd():
    assert improvement_percent(200, 50) == pytest.approx(75.0)
    assert improvement_percent(100, 100) == 0.0
    assert improvement_percent(100, 150) == pytest.approx(-50.0)  # worse than baseline


def test_improvement_undefined_for_non_positive_baseline():
    assert improvement_percent(0, 5) is None
    assert improvement_percent(-1, 5) is None


def test_mann_whitney_detects_clear_difference_and_needs_two_samples():
    good = [10, 11, 12, 13, 14, 15]
    bad = [100, 101, 102, 103, 104, 105]
    assert mann_whitney_less(good, bad)["p"] < 0.01
    assert mann_whitney_less(bad, good)["p"] > 0.9
    assert mann_whitney_less([1], bad) is None


def test_cliffs_delta_extremes():
    assert cliffs_delta([1, 2], [10, 20]) == -1.0
    assert cliffs_delta([10, 20], [1, 2]) == 1.0
    assert cliffs_delta([1, 2], [1, 2]) == 0.0


def test_convergence_helpers():
    per_seed = {"43": {"best": [10, 6, 4]}, "42": {"best": [8, 4, 2]}}
    curves = stack_histories(per_seed)
    assert curves.tolist() == [[8, 4, 2], [10, 6, 4]]  # numeric seed order
    mean, std = mean_std_band(curves)
    assert mean.tolist() == [9, 5, 3] and std[0] == pytest.approx(math.sqrt(2))
    assert generations_to_reach(np.array([100.0, 40.0, 11.0, 10.0, 10.0]), 0.95) == 2
