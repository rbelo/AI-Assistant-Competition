import os
import sys

import pytest

# Add streamlit directory to path for imports
STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules.negotiations import compute_deal_scores


def test_compute_deal_scores_invalid_deal():
    assert compute_deal_scores(-1, 20, 10) == (-1, -1)
    assert compute_deal_scores(None, 20, 10) == (0, 0)


def test_compute_deal_scores_out_of_range_gap():
    assert compute_deal_scores(25, 20, 10) == (1, 0)
    assert compute_deal_scores(5, 20, 10) == (0, 1)


def test_compute_deal_scores_zero_width_range():
    assert compute_deal_scores(10, 10, 10) == (0, 0)


def test_compute_deal_scores_within_range_gap():
    assert compute_deal_scores(10, 20, 10) == (0, 0)
    assert compute_deal_scores(20, 20, 10) == (0, 0)
    assert compute_deal_scores(15, 20, 10) == (0, 0)


def test_compute_deal_scores_inverted_bounds_low():
    assert compute_deal_scores(5, 10, 20) == (0, 1)


def test_compute_deal_scores_inverted_bounds_mid():
    assert compute_deal_scores(15, 10, 20) == (0.5, 0.5)


def test_compute_deal_scores_inverted_bounds_high():
    assert compute_deal_scores(25, 10, 20) == (1, 0)


def test_compute_deal_scores_ratio_minimizer_high():
    assert compute_deal_scores(12, 10, 20) == (0.2, 0.8)


def test_compute_deal_scores_ratio_maximizer_high():
    score_max, score_min = compute_deal_scores(18, 10, 20)
    assert score_max == pytest.approx(0.8)
    assert score_min == pytest.approx(0.2)
