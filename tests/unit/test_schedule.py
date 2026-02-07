"""
Unit tests for schedule module.

Tests the Berger round-robin scheduling algorithm.
"""

import os
import sys

import pytest

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from streamlit.modules.schedule import berger_schedule


class TestBergerSchedule:
    """Tests for the Berger round-robin scheduling algorithm."""

    @pytest.mark.unit
    def test_even_number_of_teams(self):
        """Test schedule generation with even number of teams."""
        teams = ["A", "B", "C", "D"]
        schedule = berger_schedule(teams, num_rounds=3)

        assert len(schedule) == 3  # 3 rounds
        for round_matches in schedule:
            assert len(round_matches) == 2  # 2 matches per round with 4 teams

    @pytest.mark.unit
    def test_odd_number_of_teams(self):
        """Test schedule generation with odd number of teams (one bye per round)."""
        teams = ["A", "B", "C"]
        schedule = berger_schedule(teams, num_rounds=3)

        assert len(schedule) == 3
        # With odd teams, some rounds may have fewer matches (bye)
        for round_matches in schedule:
            # Each round should have at most 1 match (3 teams, 1 bye)
            assert len(round_matches) <= 1

    @pytest.mark.unit
    def test_single_round(self):
        """Test schedule generation for single round."""
        teams = ["A", "B", "C", "D"]
        schedule = berger_schedule(teams, num_rounds=1)

        assert len(schedule) == 1
        assert len(schedule[0]) == 2

    @pytest.mark.unit
    def test_all_teams_play(self):
        """Test that all teams appear in the schedule over full rotation."""
        teams = ["A", "B", "C", "D"]
        num_rounds = len(teams) - 1  # Full round-robin
        schedule = berger_schedule(teams, num_rounds=num_rounds)

        # Collect all teams that appear in matches
        teams_in_schedule = set()
        for round_matches in schedule:
            for team1, team2 in round_matches:
                teams_in_schedule.add(team1)
                teams_in_schedule.add(team2)

        # All original teams should appear
        for team in teams:
            assert team in teams_in_schedule

    @pytest.mark.unit
    def test_no_team_plays_itself(self):
        """Test that no team is matched against itself."""
        teams = ["A", "B", "C", "D", "E", "F"]
        schedule = berger_schedule(teams, num_rounds=5)

        for round_matches in schedule:
            for team1, team2 in round_matches:
                assert team1 != team2, f"Team {team1} matched against itself"

    @pytest.mark.unit
    def test_no_duplicate_matchups_per_round(self):
        """Test that a team doesn't play twice in the same round."""
        teams = ["A", "B", "C", "D", "E", "F"]
        schedule = berger_schedule(teams, num_rounds=5)

        for round_num, round_matches in enumerate(schedule):
            teams_in_round = []
            for team1, team2 in round_matches:
                assert team1 not in teams_in_round, f"Team {team1} plays twice in round {round_num}"
                assert team2 not in teams_in_round, f"Team {team2} plays twice in round {round_num}"
                teams_in_round.extend([team1, team2])

    @pytest.mark.unit
    def test_dummy_team_excluded(self):
        """Test that dummy team (for odd count) is excluded from matches."""
        teams = ["A", "B", "C", "D", "E"]  # Odd number
        schedule = berger_schedule(teams, num_rounds=4)

        for round_matches in schedule:
            for team1, team2 in round_matches:
                assert team1 != "Dummy", "Dummy team should not appear in matches"
                assert team2 != "Dummy", "Dummy team should not appear in matches"

    @pytest.mark.unit
    def test_two_teams(self):
        """Test schedule with minimum team count."""
        teams = ["A", "B"]
        schedule = berger_schedule(teams, num_rounds=1)

        assert len(schedule) == 1
        assert len(schedule[0]) == 1
        match = schedule[0][0]
        assert set(match) == {"A", "B"}

    @pytest.mark.unit
    def test_schedule_returns_tuples(self):
        """Test that matches are returned as tuples."""
        teams = ["A", "B", "C", "D"]
        schedule = berger_schedule(teams, num_rounds=1)

        for round_matches in schedule:
            for match in round_matches:
                assert isinstance(match, tuple)
                assert len(match) == 2

    @pytest.mark.unit
    def test_large_team_count(self):
        """Test schedule with larger team count."""
        teams = [f"Team{i}" for i in range(10)]
        schedule = berger_schedule(teams, num_rounds=9)

        assert len(schedule) == 9
        # With 10 teams, each round should have 5 matches
        for round_matches in schedule:
            assert len(round_matches) == 5

    @pytest.mark.unit
    def test_does_not_mutate_input_teams(self):
        """Ensure schedule generation does not mutate the input team list."""
        teams = ["A", "B", "C"]
        original = teams.copy()
        _ = berger_schedule(teams, num_rounds=3)

        assert teams == original

    @pytest.mark.unit
    def test_zero_rounds_returns_empty_schedule(self):
        """Zero or negative rounds should return an empty schedule."""
        teams = ["A", "B", "C", "D"]
        assert berger_schedule(teams, num_rounds=0) == []
