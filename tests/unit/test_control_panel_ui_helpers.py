import os
import sys

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules.control_panel_ui_helpers import (  # noqa: E402
    build_year_class_options,
    calculate_planned_chats,
    format_progress_caption,
    format_progress_status_line,
    parse_year_class,
)


class TestYearClassHelpers:
    @pytest.mark.unit
    def test_build_year_class_options(self):
        combos = {"2025": ["A", "B"], "2024": ["C"]}
        result = build_year_class_options(combos)
        assert result == ["2025", "2025 - A", "2025 - B", "2024", "2024 - C"]

    @pytest.mark.unit
    def test_parse_year_class_with_class(self):
        year, cls = parse_year_class("2025 - A")
        assert year == "2025"
        assert cls == "A"

    @pytest.mark.unit
    def test_parse_year_class_without_class(self):
        year, cls = parse_year_class("2025")
        assert year == "2025"
        assert cls == "_"


class TestSimulationProgressHelpers:
    @pytest.mark.unit
    def test_calculate_planned_chats_even_teams(self):
        # 4 teams -> 2 matches/round -> *2 chats per match
        assert calculate_planned_chats(4, 3) == 12

    @pytest.mark.unit
    def test_calculate_planned_chats_odd_teams(self):
        # 3 teams -> 1 match/round (one bye) -> *2 chats per match
        assert calculate_planned_chats(3, 3) == 6

    @pytest.mark.unit
    def test_format_progress_status_line(self):
        text = format_progress_status_line(
            round_num=1,
            team1_name="ClassT_Group1",
            team2_name="ClassT_Group2",
            role1_name="Buyer",
            role2_name="Seller",
            phase="running",
            attempt=2,
            elapsed_seconds=12.3,
        )
        assert "Round 1:" in text
        assert "ClassT_Group1 (Buyer) vs ClassT_Group2 (Seller)" in text
        assert "Running (attempt 2)" in text
        assert "elapsed 12.3s" in text

    @pytest.mark.unit
    def test_format_progress_caption_running(self):
        text = format_progress_caption(completed_matches=3, total_matches=10, phase="running")
        assert text == "Processing chat 4 of 10 (completed 3)"

    @pytest.mark.unit
    def test_format_progress_caption_completed(self):
        text = format_progress_caption(completed_matches=4, total_matches=10, phase="completed")
        assert text == "Processed 4 of 10 chats"
