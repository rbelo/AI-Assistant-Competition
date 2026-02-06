"""
Unit tests for pure/near-pure functions in the negotiations module.

Covers: clean_agent_message, _build_summary_context, _extract_summary_text,
parse_deal_value, extract_summary_from_transcript, resolve_initiator_role_index,
get_role_agent, get_minimizer_reservation, get_maximizer_reservation,
get_minimizer_maximizer, is_valid_termination, build_llm_config,
is_invalid_api_key_error.
"""

import os
import sys
from unittest.mock import MagicMock

import pytest

STREAMLIT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../streamlit"))
if STREAMLIT_PATH not in sys.path:
    sys.path.insert(0, STREAMLIT_PATH)

from modules.negotiations import (  # noqa: E402
    _build_summary_context,
    _extract_summary_text,
    build_llm_config,
    clean_agent_message,
    extract_summary_from_transcript,
    get_maximizer_reservation,
    get_minimizer_maximizer,
    get_minimizer_reservation,
    get_role_agent,
    is_invalid_api_key_error,
    is_valid_termination,
    parse_deal_value,
    resolve_initiator_role_index,
)


# ---------------------------------------------------------------------------
# clean_agent_message
# ---------------------------------------------------------------------------
class TestCleanAgentMessage:
    @pytest.mark.unit
    def test_removes_agent1_prefix(self):
        result = clean_agent_message("Alice", "Bob", "Alice: Hello there")
        assert result == "Hello there"

    @pytest.mark.unit
    def test_removes_agent2_prefix(self):
        result = clean_agent_message("Alice", "Bob", "Bob: Hi Alice")
        assert result == "Hi Alice"

    @pytest.mark.unit
    def test_case_insensitive(self):
        result = clean_agent_message("Alice", "Bob", "alice: hello")
        assert result == "hello"

    @pytest.mark.unit
    def test_no_prefix_unchanged(self):
        result = clean_agent_message("Alice", "Bob", "Hello there")
        assert result == "Hello there"

    @pytest.mark.unit
    def test_empty_message(self):
        assert clean_agent_message("Alice", "Bob", "") == ""

    @pytest.mark.unit
    def test_none_message(self):
        assert clean_agent_message("Alice", "Bob", None) == ""

    @pytest.mark.unit
    def test_leading_whitespace_before_prefix(self):
        result = clean_agent_message("Alice", "Bob", "  Alice: hi")
        assert result == "hi"

    @pytest.mark.unit
    def test_special_regex_chars_in_name(self):
        result = clean_agent_message("Agent (1)", "Agent [2]", "Agent (1): msg")
        assert result == "msg"

    @pytest.mark.unit
    def test_prefix_only_at_start(self):
        """Agent name appearing mid-message should not be stripped."""
        result = clean_agent_message("Alice", "Bob", "I told Alice: sure")
        assert result == "I told Alice: sure"

    @pytest.mark.unit
    def test_colon_with_extra_spaces(self):
        # The \s* after colon consumes all whitespace
        result = clean_agent_message("Alice", "Bob", "Alice:   spaced out")
        assert result == "spaced out"


# ---------------------------------------------------------------------------
# _build_summary_context
# ---------------------------------------------------------------------------
class TestBuildSummaryContext:
    @pytest.mark.unit
    def test_empty_history(self):
        assert _build_summary_context([]) == ""
        assert _build_summary_context(None) == ""

    @pytest.mark.unit
    def test_basic_history(self):
        history = [
            {"name": "Buyer", "content": "I offer 10"},
            {"name": "Seller", "content": "I accept"},
        ]
        result = _build_summary_context(history)
        assert "Buyer: I offer 10" in result
        assert "Seller: I accept" in result

    @pytest.mark.unit
    def test_history_size_limits_entries(self):
        history = [
            {"name": "A", "content": "msg1"},
            {"name": "B", "content": "msg2"},
            {"name": "A", "content": "msg3"},
            {"name": "B", "content": "msg4"},
            {"name": "A", "content": "msg5"},
        ]
        result = _build_summary_context(history, history_size=2)
        assert "msg5" in result
        assert "msg4" in result
        assert "msg1" not in result

    @pytest.mark.unit
    def test_history_size_none_uses_all(self):
        history = [{"name": "A", "content": f"msg{i}"} for i in range(10)]
        result = _build_summary_context(history, history_size=None)
        for i in range(10):
            assert f"msg{i}" in result

    @pytest.mark.unit
    def test_history_size_zero_returns_empty(self):
        history = [{"name": "A", "content": "msg"}]
        result = _build_summary_context(history, history_size=0)
        assert result == ""

    @pytest.mark.unit
    def test_cleans_agent_names_when_provided(self):
        history = [{"name": "Buyer", "content": "Buyer: I offer 10"}]
        result = _build_summary_context(history, role1_name="Buyer", role2_name="Seller")
        assert "Buyer: I offer 10" in result
        # The agent prefix "Buyer: " inside content should be cleaned
        # so it becomes "I offer 10", then wrapped as "Buyer: I offer 10"
        assert "Buyer: Buyer:" not in result

    @pytest.mark.unit
    def test_no_cleaning_without_role_names(self):
        history = [{"name": "Buyer", "content": "Buyer: I offer 10"}]
        result = _build_summary_context(history)
        assert "Buyer: Buyer: I offer 10" in result

    @pytest.mark.unit
    def test_missing_keys_handled(self):
        history = [{"content": "no name"}, {"name": "A"}]
        result = _build_summary_context(history)
        assert ": no name" in result
        assert "A: " in result


# ---------------------------------------------------------------------------
# _extract_summary_text
# ---------------------------------------------------------------------------
class TestExtractSummaryText:
    @pytest.mark.unit
    def test_none_eval(self):
        assert _extract_summary_text(None, "Agent") == ""

    @pytest.mark.unit
    def test_no_chat_history_attr(self):
        eval_obj = MagicMock(spec=[])  # no chat_history attribute
        assert _extract_summary_text(eval_obj, "Agent") == ""

    @pytest.mark.unit
    def test_empty_chat_history(self):
        eval_obj = MagicMock()
        eval_obj.chat_history = []
        assert _extract_summary_text(eval_obj, "Agent") == ""

    @pytest.mark.unit
    def test_finds_matching_agent_entry(self):
        eval_obj = MagicMock()
        eval_obj.chat_history = [
            {"name": "User", "content": "prompt text"},
            {"name": "Summary_Agent", "content": "Deal value: 15"},
        ]
        assert _extract_summary_text(eval_obj, "Summary_Agent") == "Deal value: 15"

    @pytest.mark.unit
    def test_returns_last_matching_entry(self):
        eval_obj = MagicMock()
        eval_obj.chat_history = [
            {"name": "Summary_Agent", "content": "first"},
            {"name": "User", "content": "middle"},
            {"name": "Summary_Agent", "content": "last"},
        ]
        # reversed iteration finds "last" first
        assert _extract_summary_text(eval_obj, "Summary_Agent") == "last"

    @pytest.mark.unit
    def test_falls_back_to_last_entry(self):
        eval_obj = MagicMock()
        eval_obj.chat_history = [
            {"name": "Other", "content": "fallback text"},
        ]
        assert _extract_summary_text(eval_obj, "Summary_Agent") == "fallback text"

    @pytest.mark.unit
    def test_skips_matching_entry_with_empty_content(self):
        eval_obj = MagicMock()
        eval_obj.chat_history = [
            {"name": "Summary_Agent", "content": "good"},
            {"name": "Summary_Agent", "content": ""},
        ]
        # reversed: first sees empty content (skips), then finds "good"
        assert _extract_summary_text(eval_obj, "Summary_Agent") == "good"


# ---------------------------------------------------------------------------
# parse_deal_value
# ---------------------------------------------------------------------------
class TestParseDealValue:
    @pytest.mark.unit
    def test_empty_inputs(self):
        assert parse_deal_value("", "DEAL:") == -1
        assert parse_deal_value(None, "DEAL:") == -1
        assert parse_deal_value("DEAL: 15", "") == -1
        assert parse_deal_value("DEAL: 15", None) == -1

    @pytest.mark.unit
    def test_simple_integer(self):
        assert parse_deal_value("DEAL: 15", "DEAL:") == 15.0

    @pytest.mark.unit
    def test_float_value(self):
        assert parse_deal_value("DEAL: 15.5", "DEAL:") == 15.5

    @pytest.mark.unit
    def test_dollar_sign_stripped(self):
        assert parse_deal_value("DEAL: $15", "DEAL:") == 15.0

    @pytest.mark.unit
    def test_comma_in_number(self):
        assert parse_deal_value("DEAL: $1,500", "DEAL:") == 1500.0

    @pytest.mark.unit
    def test_negative_value(self):
        assert parse_deal_value("DEAL: -1", "DEAL:") == -1.0

    @pytest.mark.unit
    def test_no_number_after_termination(self):
        assert parse_deal_value("DEAL: no number", "DEAL:") == -1

    @pytest.mark.unit
    def test_multiline_finds_correct_line(self):
        text = "Some preamble\nDEAL: 42\nSome epilogue"
        assert parse_deal_value(text, "DEAL:") == 42.0

    @pytest.mark.unit
    def test_termination_not_present(self):
        assert parse_deal_value("No deal here", "DEAL:") == -1

    @pytest.mark.unit
    def test_comma_stripped_before_parsing(self):
        # Commas are stripped as thousands separators before regex matching,
        # so "15,5" becomes "155", not "15.5"
        assert parse_deal_value("DEAL: 15,5", "DEAL:") == 155.0

    @pytest.mark.unit
    def test_uses_first_number_found(self):
        assert parse_deal_value("DEAL: 10 and 20", "DEAL:") == 10.0


# ---------------------------------------------------------------------------
# extract_summary_from_transcript
# ---------------------------------------------------------------------------
class TestExtractSummaryFromTranscript:
    @pytest.mark.unit
    def test_empty_transcript(self):
        assert extract_summary_from_transcript("", "DEAL:") == ("", -1)
        assert extract_summary_from_transcript(None, "DEAL:") == ("", -1)

    @pytest.mark.unit
    def test_whitespace_only_transcript(self):
        assert extract_summary_from_transcript("   \n\n\n   ", "DEAL:") == ("", -1)

    @pytest.mark.unit
    def test_extracts_last_part(self):
        transcript = "Buyer: Hello\n\n\nSeller: Hi\n\n\nDEAL: 25"
        summary, value = extract_summary_from_transcript(transcript, "DEAL:")
        assert summary == "DEAL: 25"
        assert value == 25.0

    @pytest.mark.unit
    def test_no_termination_message_in_summary(self):
        transcript = "Buyer: Hello\n\n\nSeller: Goodbye"
        summary, value = extract_summary_from_transcript(transcript, "DEAL:")
        assert summary == ""
        assert value == -1

    @pytest.mark.unit
    def test_none_termination_message(self):
        # When summary_termination_message is None, the `and` short-circuits
        transcript = "Part1\n\n\nPart2"
        summary, value = extract_summary_from_transcript(transcript, None)
        assert summary == "Part2"
        # parse_deal_value with None termination_message returns -1
        assert value == -1

    @pytest.mark.unit
    def test_single_part_with_termination(self):
        transcript = "DEAL: 50"
        summary, value = extract_summary_from_transcript(transcript, "DEAL:")
        assert summary == "DEAL: 50"
        assert value == 50.0


# ---------------------------------------------------------------------------
# resolve_initiator_role_index
# ---------------------------------------------------------------------------
class TestResolveInitiatorRoleIndex:
    @pytest.mark.unit
    def test_none_conversation_order(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], None) == 1

    @pytest.mark.unit
    def test_empty_conversation_order(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "") == 1

    @pytest.mark.unit
    def test_same_returns_1(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "same") == 1

    @pytest.mark.unit
    def test_opposite_returns_2(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "opposite") == 2

    @pytest.mark.unit
    def test_matches_first_role_name(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "Buyer") == 1

    @pytest.mark.unit
    def test_matches_second_role_name(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "Seller") == 2

    @pytest.mark.unit
    def test_unrecognized_defaults_to_1(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "unknown") == 1

    @pytest.mark.unit
    def test_whitespace_stripped(self):
        assert resolve_initiator_role_index(["Buyer", "Seller"], "  same  ") == 1
        assert resolve_initiator_role_index(["Buyer", "Seller"], " opposite ") == 2


# ---------------------------------------------------------------------------
# get_role_agent, get_minimizer_reservation, get_maximizer_reservation
# ---------------------------------------------------------------------------
class TestTeamAccessors:
    @pytest.fixture
    def team(self):
        return {
            "Agent 1": MagicMock(name="agent1"),
            "Agent 2": MagicMock(name="agent2"),
            "Value 1": 10,
            "Value 2": 20,
        }

    @pytest.mark.unit
    def test_get_role_agent_1(self, team):
        assert get_role_agent(team, 1) is team["Agent 1"]

    @pytest.mark.unit
    def test_get_role_agent_2(self, team):
        assert get_role_agent(team, 2) is team["Agent 2"]

    @pytest.mark.unit
    def test_get_role_agent_invalid_index(self, team):
        with pytest.raises(ValueError, match="Invalid role index"):
            get_role_agent(team, 3)

    @pytest.mark.unit
    def test_get_role_agent_zero_index(self, team):
        with pytest.raises(ValueError, match="Invalid role index"):
            get_role_agent(team, 0)

    @pytest.mark.unit
    def test_get_minimizer_reservation(self, team):
        assert get_minimizer_reservation(team) == 10

    @pytest.mark.unit
    def test_get_maximizer_reservation(self, team):
        assert get_maximizer_reservation(team) == 20


# ---------------------------------------------------------------------------
# get_minimizer_maximizer
# ---------------------------------------------------------------------------
class TestGetMinimizerMaximizer:
    @pytest.mark.unit
    def test_initiator_role_1(self):
        team_a, team_b = {"name": "A"}, {"name": "B"}
        mini, maxi = get_minimizer_maximizer(team_a, team_b, 1)
        assert mini is team_a
        assert maxi is team_b

    @pytest.mark.unit
    def test_initiator_role_2(self):
        team_a, team_b = {"name": "A"}, {"name": "B"}
        mini, maxi = get_minimizer_maximizer(team_a, team_b, 2)
        assert mini is team_b
        assert maxi is team_a


# ---------------------------------------------------------------------------
# is_valid_termination
# ---------------------------------------------------------------------------
class TestIsValidTermination:
    TERM_MSG = "Pleasure doing business with you"

    @pytest.mark.unit
    def test_no_termination_phrase(self):
        msg = {"content": "Just chatting"}
        assert is_valid_termination(msg, [], self.TERM_MSG) is False

    @pytest.mark.unit
    def test_termination_phrase_empty_history(self):
        msg = {"content": f"Great! {self.TERM_MSG}"}
        assert is_valid_termination(msg, [], self.TERM_MSG) is True

    @pytest.mark.unit
    def test_termination_phrase_no_history(self):
        msg = {"content": f"Great! {self.TERM_MSG}"}
        assert is_valid_termination(msg, None, self.TERM_MSG) is True

    @pytest.mark.unit
    def test_sufficient_agreement_indicators(self):
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "I agree to the deal at $15"},
            {"content": "Deal accepted at $15"},
            {"content": "Great, the deal is confirmed at $15"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is True

    @pytest.mark.unit
    def test_insufficient_agreement_indicators(self):
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "Hello there"},
            {"content": "What do you think?"},
            {"content": "I'm not sure about this"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is False

    @pytest.mark.unit
    def test_inconsistent_values_rejected(self):
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "I agree to $10"},
            {"content": "Deal confirmed at $50"},  # wildly different
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is False

    @pytest.mark.unit
    def test_consistent_values_accepted(self):
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "I agree to $15.00"},
            {"content": "Deal confirmed at $15"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is True

    @pytest.mark.unit
    def test_uses_last_4_messages(self):
        msg = {"content": f"{self.TERM_MSG}"}
        # Old messages have no indicators, recent ones do
        history = [
            {"content": "random chat"},
            {"content": "more random"},
            {"content": "still chatting"},
            {"content": "I agree to $15"},
            {"content": "Deal accepted at $15"},
            {"content": "Confirmed, deal at $15"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is True

    @pytest.mark.unit
    def test_dollar_and_comma_stripped(self):
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "I agree to $1,500"},
            {"content": "Deal confirmed at $1,500"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is True

    @pytest.mark.unit
    def test_no_values_in_history_still_accepts(self):
        """When no numeric values found, value consistency check is skipped."""
        msg = {"content": f"{self.TERM_MSG}"}
        history = [
            {"content": "I agree to the terms"},
            {"content": "Deal accepted, everything is settled"},
        ]
        assert is_valid_termination(msg, history, self.TERM_MSG) is True


# ---------------------------------------------------------------------------
# build_llm_config
# ---------------------------------------------------------------------------
class TestBuildLlmConfig:
    @pytest.mark.unit
    def test_non_gpt5_includes_temperature(self):
        config = build_llm_config("gpt-4o-mini", "sk-test")
        assert config["config_list"] == [{"model": "gpt-4o-mini", "api_key": "sk-test"}]
        assert config["temperature"] == 0.3
        assert config["top_p"] == 0.5

    @pytest.mark.unit
    def test_gpt5_excludes_temperature(self):
        config = build_llm_config("gpt-5-mini", "sk-test")
        assert config["config_list"] == [{"model": "gpt-5-mini", "api_key": "sk-test"}]
        assert "temperature" not in config
        assert "top_p" not in config

    @pytest.mark.unit
    def test_gpt5_nano_excludes_temperature(self):
        config = build_llm_config("gpt-5-nano", "sk-test")
        assert "temperature" not in config

    @pytest.mark.unit
    def test_custom_temperature(self):
        config = build_llm_config("gpt-4o", "sk-test", temperature=0.7, top_p=0.9)
        assert config["temperature"] == 0.7
        assert config["top_p"] == 0.9


# ---------------------------------------------------------------------------
# is_invalid_api_key_error
# ---------------------------------------------------------------------------
class TestIsInvalidApiKeyError:
    @pytest.mark.unit
    def test_invalid_api_key_message(self):
        assert is_invalid_api_key_error(Exception("Invalid API key provided")) is True

    @pytest.mark.unit
    def test_incorrect_api_key_message(self):
        assert is_invalid_api_key_error(Exception("Incorrect API key")) is True

    @pytest.mark.unit
    def test_invalid_api_key_underscore(self):
        assert is_invalid_api_key_error(Exception("Error: invalid_api_key")) is True

    @pytest.mark.unit
    def test_unauthorized_message(self):
        assert is_invalid_api_key_error(Exception("Request unauthorized")) is True

    @pytest.mark.unit
    def test_authentication_message(self):
        assert is_invalid_api_key_error(Exception("Authentication failed")) is True

    @pytest.mark.unit
    def test_401_status_code(self):
        assert is_invalid_api_key_error(Exception("HTTP 401 error")) is True

    @pytest.mark.unit
    def test_unrelated_error(self):
        assert is_invalid_api_key_error(Exception("Connection timeout")) is False

    @pytest.mark.unit
    def test_rate_limit_error(self):
        assert is_invalid_api_key_error(Exception("Rate limit exceeded")) is False

    @pytest.mark.unit
    def test_case_insensitive(self):
        assert is_invalid_api_key_error(Exception("INVALID API KEY")) is True
