"""
Unit tests for Prisoner's Dilemma scoring, action parsing, system-message
construction, and single-match orchestration.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules.conversation_engine import ChatResult, GameAgent  # noqa: E402
from modules.negotiations_common import (  # noqa: E402
    DEFAULT_PD_PAYOFF_MATRIX,
    PD_ACTIONS,
    PD_DECISION_KEYWORD,
    compute_pd_scores,
    parse_pd_action,
)
import modules.negotiations_pd as pd_mod  # noqa: E402
from modules.negotiations_pd import (  # noqa: E402
    _build_decision_prompt,
    _build_pd_system_message,
    _format_chat_for_decision,
    create_pd_chat,
    create_pd_chats,
)
from modules.llm_provider import LLMConfig  # noqa: E402


# ---------------------------------------------------------------------------
# compute_pd_scores
# ---------------------------------------------------------------------------
class TestComputePdScores:
    MATRIX = DEFAULT_PD_PAYOFF_MATRIX

    @pytest.mark.unit
    def test_both_cooperate(self):
        assert compute_pd_scores("cooperate", "cooperate", self.MATRIX) == (3, 3)

    @pytest.mark.unit
    def test_both_defect(self):
        assert compute_pd_scores("defect", "defect", self.MATRIX) == (1, 1)

    @pytest.mark.unit
    def test_cooperate_defect(self):
        assert compute_pd_scores("cooperate", "defect", self.MATRIX) == (0, 5)

    @pytest.mark.unit
    def test_defect_cooperate(self):
        assert compute_pd_scores("defect", "cooperate", self.MATRIX) == (5, 0)

    @pytest.mark.unit
    def test_invalid_action_a(self):
        assert compute_pd_scores("invalid", "cooperate", self.MATRIX) == (0, 0)

    @pytest.mark.unit
    def test_invalid_action_b(self):
        assert compute_pd_scores("cooperate", "invalid", self.MATRIX) == (0, 0)

    @pytest.mark.unit
    def test_none_actions(self):
        assert compute_pd_scores(None, None, self.MATRIX) == (0, 0)

    @pytest.mark.unit
    def test_empty_string_actions(self):
        assert compute_pd_scores("", "", self.MATRIX) == (0, 0)

    @pytest.mark.unit
    def test_custom_matrix(self):
        custom = {
            "cooperate_cooperate": [4, 4],
            "cooperate_defect": [0, 6],
            "defect_cooperate": [6, 0],
            "defect_defect": [2, 2],
        }
        assert compute_pd_scores("cooperate", "cooperate", custom) == (4, 4)
        assert compute_pd_scores("defect", "defect", custom) == (2, 2)

    @pytest.mark.unit
    def test_missing_key_in_matrix(self):
        incomplete = {"cooperate_cooperate": [3, 3]}
        assert compute_pd_scores("defect", "defect", incomplete) == (0, 0)

    @pytest.mark.unit
    def test_asymmetric_matrix(self):
        asymmetric = {
            "cooperate_cooperate": [3, 4],
            "cooperate_defect": [0, 6],
            "defect_cooperate": [5, 0],
            "defect_defect": [1, 2],
        }
        assert compute_pd_scores("cooperate", "cooperate", asymmetric) == (3, 4)
        assert compute_pd_scores("cooperate", "defect", asymmetric) == (0, 6)


# ---------------------------------------------------------------------------
# parse_pd_action
# ---------------------------------------------------------------------------
class TestParsePdAction:
    @pytest.mark.unit
    def test_keyword_cooperate(self):
        assert parse_pd_action("FINAL_DECISION: cooperate") == "cooperate"

    @pytest.mark.unit
    def test_keyword_defect(self):
        assert parse_pd_action("FINAL_DECISION: defect") == "defect"

    @pytest.mark.unit
    def test_keyword_case_insensitive(self):
        assert parse_pd_action("final_decision: Cooperate") == "cooperate"
        assert parse_pd_action("Final_Decision: DEFECT") == "defect"

    @pytest.mark.unit
    def test_keyword_with_surrounding_text(self):
        text = "After careful consideration, FINAL_DECISION: cooperate. I hope this works."
        assert parse_pd_action(text) == "cooperate"

    @pytest.mark.unit
    def test_fallback_cooperate(self):
        assert parse_pd_action("I choose to cooperate.") == "cooperate"

    @pytest.mark.unit
    def test_fallback_defect(self):
        assert parse_pd_action("My choice is to defect.") == "defect"

    @pytest.mark.unit
    def test_fallback_last_occurrence_wins(self):
        # When both words appear, last occurrence wins
        text = "I thought about cooperate but I will defect."
        assert parse_pd_action(text) == "defect"

    @pytest.mark.unit
    def test_fallback_cooperate_last(self):
        text = "I could defect, but actually I cooperate."
        assert parse_pd_action(text) == "cooperate"

    @pytest.mark.unit
    def test_none_input(self):
        assert parse_pd_action(None) is None

    @pytest.mark.unit
    def test_empty_input(self):
        assert parse_pd_action("") is None

    @pytest.mark.unit
    def test_no_action_found(self):
        assert parse_pd_action("I have no idea what to do.") is None

    @pytest.mark.unit
    def test_keyword_takes_priority_over_fallback(self):
        # Keyword says cooperate even though "defect" appears later
        text = "FINAL_DECISION: cooperate but I almost chose to defect"
        assert parse_pd_action(text) == "cooperate"

    @pytest.mark.unit
    def test_multiline_keyword(self):
        text = "Here is my reasoning:\n\nFINAL_DECISION: defect\n"
        assert parse_pd_action(text) == "defect"


# ---------------------------------------------------------------------------
# PD constants
# ---------------------------------------------------------------------------
class TestPdConstants:
    @pytest.mark.unit
    def test_pd_actions_frozenset(self):
        assert PD_ACTIONS == {"cooperate", "defect"}

    @pytest.mark.unit
    def test_pd_decision_keyword(self):
        assert PD_DECISION_KEYWORD == "FINAL_DECISION:"

    @pytest.mark.unit
    def test_default_matrix_is_standard_pd(self):
        m = DEFAULT_PD_PAYOFF_MATRIX
        # Standard PD: T > R > P > S where T=5, R=3, P=1, S=0
        assert m["defect_cooperate"][0] > m["cooperate_cooperate"][0]  # T > R
        assert m["cooperate_cooperate"][0] > m["defect_defect"][0]  # R > P
        assert m["defect_defect"][0] > m["cooperate_defect"][0]  # P > S


# ---------------------------------------------------------------------------
# _build_pd_system_message
# ---------------------------------------------------------------------------
class TestBuildPdSystemMessage:
    @pytest.mark.unit
    def test_includes_student_prompt(self):
        msg = _build_pd_system_message("I am a tough negotiator", DEFAULT_PD_PAYOFF_MATRIX)
        assert "I am a tough negotiator" in msg

    @pytest.mark.unit
    def test_includes_payoff_values(self):
        msg = _build_pd_system_message("prompt", DEFAULT_PD_PAYOFF_MATRIX)
        assert "(3, 3)" in msg
        assert "(0, 5)" in msg
        assert "(5, 0)" in msg
        assert "(1, 1)" in msg

    @pytest.mark.unit
    def test_includes_private_value_when_provided(self):
        msg = _build_pd_system_message("prompt", DEFAULT_PD_PAYOFF_MATRIX, private_value=42)
        assert "42" in msg
        assert "PRIVATE INFORMATION" in msg

    @pytest.mark.unit
    def test_no_private_section_when_none(self):
        msg = _build_pd_system_message("prompt", DEFAULT_PD_PAYOFF_MATRIX, private_value=None)
        assert "PRIVATE INFORMATION" not in msg

    @pytest.mark.unit
    def test_includes_two_phases(self):
        msg = _build_pd_system_message("prompt", DEFAULT_PD_PAYOFF_MATRIX)
        assert "NEGOTIATION PHASE" in msg
        assert "DECISION PHASE" in msg

    @pytest.mark.unit
    def test_includes_termination_message(self):
        msg = _build_pd_system_message(
            "prompt", DEFAULT_PD_PAYOFF_MATRIX,
            negotiation_termination_message="GAME_OVER",
        )
        assert "GAME_OVER" in msg


# ---------------------------------------------------------------------------
# _format_chat_for_decision
# ---------------------------------------------------------------------------
class TestFormatChatForDecision:
    @pytest.mark.unit
    def test_basic_formatting(self):
        history = [
            {"name": "Alice", "content": "Hello"},
            {"name": "Bob", "content": "Hi Alice"},
        ]
        result = _format_chat_for_decision(history, "Alice", "Bob")
        assert "Alice: Hello" in result
        assert "Bob: Hi Alice" in result

    @pytest.mark.unit
    def test_cleans_agent_prefix(self):
        history = [
            {"name": "Alice", "content": "Alice: I propose we cooperate"},
        ]
        result = _format_chat_for_decision(history, "Alice", "Bob")
        assert "Alice: I propose we cooperate" in result
        assert "Alice: Alice:" not in result

    @pytest.mark.unit
    def test_empty_history(self):
        result = _format_chat_for_decision([], "A", "B")
        assert result == ""


# ---------------------------------------------------------------------------
# _build_decision_prompt
# ---------------------------------------------------------------------------
class TestBuildDecisionPrompt:
    @pytest.mark.unit
    def test_contains_keyword(self):
        prompt = _build_decision_prompt()
        assert PD_DECISION_KEYWORD in prompt

    @pytest.mark.unit
    def test_mentions_both_actions(self):
        prompt = _build_decision_prompt()
        assert "cooperate" in prompt
        assert "defect" in prompt

    @pytest.mark.unit
    def test_mentions_privacy(self):
        prompt = _build_decision_prompt()
        assert "NOT see your decision" in prompt


# ---------------------------------------------------------------------------
# create_pd_chat (mocked)
# ---------------------------------------------------------------------------
class TestCreatePdChat:
    @pytest.mark.unit
    def test_returns_actions_and_scores(self, monkeypatch):
        chat_history = [
            {"name": "Team1", "content": "Let's cooperate"},
            {"name": "Team2", "content": "Sounds good"},
        ]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "FINAL_DECISION: cooperate",
            "FINAL_DECISION: defect",
        ]

        team1 = {
            "Name": "ClassA_Group1",
            "Private Value": None,
            "Agent": GameAgent(name="Team1", system_message="prompt1"),
        }
        team2 = {
            "Name": "ClassB_Group2",
            "Private Value": None,
            "Agent": GameAgent(name="Team2", system_message="prompt2"),
        }

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        action1, action2, score1, score2 = create_pd_chat(
            game_id=1,
            team1=team1,
            team2=team2,
            num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX,
            round_num=1,
            engine=engine,
            negotiation_termination_message="DONE",
            store_in_db=True,
        )

        assert action1 == "cooperate"
        assert action2 == "defect"
        assert score1 == 0  # cooperate vs defect: sucker's payoff
        assert score2 == 5  # cooperate vs defect: temptation payoff

    @pytest.mark.unit
    def test_both_cooperate_scores(self, monkeypatch):
        chat_history = [{"name": "A", "content": "hi"}]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "FINAL_DECISION: cooperate",
            "FINAL_DECISION: cooperate",
        ]

        team1 = {"Name": "ClassA_Group1", "Private Value": None, "Agent": GameAgent(name="A", system_message="p")}
        team2 = {"Name": "ClassA_Group2", "Private Value": None, "Agent": GameAgent(name="B", system_message="p")}

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        _, _, score1, score2 = create_pd_chat(
            game_id=1, team1=team1, team2=team2, num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX, round_num=1,
            engine=engine, negotiation_termination_message="DONE",
        )

        assert score1 == 3
        assert score2 == 3

    @pytest.mark.unit
    def test_both_defect_scores(self, monkeypatch):
        chat_history = [{"name": "A", "content": "hi"}]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "FINAL_DECISION: defect",
            "FINAL_DECISION: defect",
        ]

        team1 = {"Name": "ClassA_Group1", "Private Value": None, "Agent": GameAgent(name="A", system_message="p")}
        team2 = {"Name": "ClassA_Group2", "Private Value": None, "Agent": GameAgent(name="B", system_message="p")}

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        _, _, score1, score2 = create_pd_chat(
            game_id=1, team1=team1, team2=team2, num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX, round_num=1,
            engine=engine, negotiation_termination_message="DONE",
        )

        assert score1 == 1
        assert score2 == 1

    @pytest.mark.unit
    def test_unclear_action_scores_zero(self, monkeypatch):
        chat_history = [{"name": "A", "content": "hi"}]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "I'm not sure what to do",  # no action parseable
            "FINAL_DECISION: cooperate",
        ]

        team1 = {"Name": "ClassA_Group1", "Private Value": None, "Agent": GameAgent(name="A", system_message="p")}
        team2 = {"Name": "ClassA_Group2", "Private Value": None, "Agent": GameAgent(name="B", system_message="p")}

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        action1, action2, score1, score2 = create_pd_chat(
            game_id=1, team1=team1, team2=team2, num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX, round_num=1,
            engine=engine, negotiation_termination_message="DONE",
        )

        assert action1 is None
        assert score1 == 0
        assert score2 == 0

    @pytest.mark.unit
    def test_timing_totals_populated(self, monkeypatch):
        chat_history = [{"name": "A", "content": "hi"}]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "FINAL_DECISION: cooperate",
            "FINAL_DECISION: cooperate",
        ]

        team1 = {"Name": "ClassA_Group1", "Private Value": None, "Agent": GameAgent(name="A", system_message="p")}
        team2 = {"Name": "ClassA_Group2", "Private Value": None, "Agent": GameAgent(name="B", system_message="p")}

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        timing = {"chat_seconds": 0.0, "summary_seconds": 0.0, "db_seconds": 0.0, "chats_measured": 0}
        diagnostics = {
            "attempts_total": 0, "attempts_failed": 0,
            "summary_calls": 0, "total_turns": 0, "successful_chats": 0,
        }

        create_pd_chat(
            game_id=1, team1=team1, team2=team2, num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX, round_num=1,
            engine=engine, negotiation_termination_message="DONE",
            timing_totals=timing, run_diagnostics=diagnostics,
        )

        assert timing["chats_measured"] == 1
        assert diagnostics["successful_chats"] == 1
        assert diagnostics["total_turns"] == 1  # 1 entry in chat_history

    @pytest.mark.unit
    def test_restores_system_messages(self, monkeypatch):
        """System messages should be restored after the chat."""
        chat_history = [{"name": "A", "content": "hi"}]
        engine = MagicMock()
        engine.run_bilateral.return_value = ChatResult(chat_history)
        engine.single_decision.side_effect = [
            "FINAL_DECISION: cooperate",
            "FINAL_DECISION: cooperate",
        ]

        agent1 = GameAgent(name="A", system_message="original1")
        agent2 = GameAgent(name="B", system_message="original2")
        team1 = {"Name": "ClassA_Group1", "Private Value": None, "Agent": agent1}
        team2 = {"Name": "ClassA_Group2", "Private Value": None, "Agent": agent2}

        monkeypatch.setattr(pd_mod, "get_game_by_id", lambda _: {"explanation": ""})
        monkeypatch.setattr(pd_mod, "insert_negotiation_chat", MagicMock())

        create_pd_chat(
            game_id=1, team1=team1, team2=team2, num_turns=5,
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX, round_num=1,
            engine=engine, negotiation_termination_message="DONE",
        )

        assert agent1.system_message == "original1"
        assert agent2.system_message == "original2"


# ---------------------------------------------------------------------------
# create_pd_chats (tournament, mocked)
# ---------------------------------------------------------------------------
class TestCreatePdChats:
    @pytest.mark.unit
    def test_tournament_success(self, monkeypatch):
        monkeypatch.setattr(
            pd_mod, "berger_schedule",
            lambda _teams, _rounds: [[("ClassT_Group1", "ClassT_Group2")]],
        )
        monkeypatch.setattr(pd_mod, "insert_round_data", lambda *a, **kw: True)
        monkeypatch.setattr(pd_mod, "update_round_data", lambda *a, **kw: True)

        team1 = {
            "Name": "ClassT_Group1",
            "Private Value": 10,
            "Agent": GameAgent(name="T1", system_message="p1"),
        }
        team2 = {
            "Name": "ClassT_Group2",
            "Private Value": 20,
            "Agent": GameAgent(name="T2", system_message="p2"),
        }
        monkeypatch.setattr(pd_mod, "create_pd_agents", lambda *a, **kw: [team1, team2])

        call_count = {"n": 0}

        def fake_create_pd_chat(*args, **kwargs):
            call_count["n"] += 1
            timing = kwargs.get("timing_totals")
            if timing:
                timing["chat_seconds"] += 3.0
                timing["summary_seconds"] += 1.0
                timing["db_seconds"] += 0.5
                timing["chats_measured"] += 1
            diag = kwargs.get("run_diagnostics")
            if diag:
                diag["total_turns"] += 4
                diag["successful_chats"] += 1
            return "cooperate", "cooperate", 3, 3

        monkeypatch.setattr(pd_mod, "create_pd_chat", fake_create_pd_chat)

        progress_events = []

        result = create_pd_chats(
            game_id=1,
            llm_config=LLMConfig(model="test", api_key="sk-test"),
            teams=[["T", 1], ["T", 2]],
            payoff_matrix=DEFAULT_PD_PAYOFF_MATRIX,
            private_values=[
                {"class": "T", "group_id": 1, "minimizer_value": 10},
                {"class": "T", "group_id": 2, "minimizer_value": 20},
            ],
            num_rounds=1,
            num_turns=5,
            negotiation_termination_message="DONE",
            progress_callback=lambda **kw: progress_events.append(kw),
        )

        assert result["status"] == "success"
        # PD plays each match once (not twice like zero-sum)
        assert result["total_matches"] == 1
        assert result["completed_matches"] == 1
        assert call_count["n"] == 1

    @pytest.mark.unit
    def test_tournament_uses_default_matrix_when_none(self, monkeypatch):
        monkeypatch.setattr(
            pd_mod, "berger_schedule",
            lambda _teams, _rounds: [[("ClassT_Group1", "ClassT_Group2")]],
        )
        monkeypatch.setattr(pd_mod, "insert_round_data", lambda *a, **kw: True)
        monkeypatch.setattr(pd_mod, "update_round_data", lambda *a, **kw: True)

        team1 = {"Name": "ClassT_Group1", "Private Value": None, "Agent": GameAgent(name="T1", system_message="p")}
        team2 = {"Name": "ClassT_Group2", "Private Value": None, "Agent": GameAgent(name="T2", system_message="p")}
        monkeypatch.setattr(pd_mod, "create_pd_agents", lambda *a, **kw: [team1, team2])

        captured_matrix = {}

        def fake_create_pd_chat(*args, **kwargs):
            # args: game_id, team1, team2, num_turns, payoff_matrix, ...
            captured_matrix["matrix"] = args[4]
            timing = kwargs.get("timing_totals")
            if timing:
                timing["chats_measured"] += 1
            diag = kwargs.get("run_diagnostics")
            if diag:
                diag["successful_chats"] += 1
            return "cooperate", "defect", 0, 5

        monkeypatch.setattr(pd_mod, "create_pd_chat", fake_create_pd_chat)

        result = create_pd_chats(
            game_id=1,
            llm_config=LLMConfig(model="test", api_key="sk-test"),
            teams=[["T", 1], ["T", 2]],
            payoff_matrix=None,  # should use default
            private_values=[],
            num_rounds=1,
            num_turns=5,
            negotiation_termination_message="DONE",
        )

        assert result["status"] == "success"
        assert captured_matrix["matrix"] == DEFAULT_PD_PAYOFF_MATRIX
