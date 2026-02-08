"""Integration tests for ConversationEngine with real OpenAI API calls.

These tests are **opt-in**. They only run when the following environment
variables are set:

    RUN_CONVERSATION_ENGINE_TEST=1
    OPENAI_API_KEY=sk-...          (or E2E_OPENAI_API_KEY)

Run with:
    RUN_CONVERSATION_ENGINE_TEST=1 OPENAI_API_KEY=sk-... \
        python -m pytest tests/integration/test_conversation_engine_api.py -v
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "streamlit"))

from modules.conversation_engine import ConversationEngine, GameAgent
from modules.llm_provider import LLMConfig

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

SKIP_REASON = "Skipped: set RUN_CONVERSATION_ENGINE_TEST=1 and OPENAI_API_KEY to run"

_should_run = os.environ.get("RUN_CONVERSATION_ENGINE_TEST") == "1"
_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("E2E_OPENAI_API_KEY")

pytestmark = pytest.mark.skipif(
    not (_should_run and _api_key),
    reason=SKIP_REASON,
)

MODEL = os.environ.get("TEST_MODEL", "gpt-4o-mini")


@pytest.fixture(scope="module")
def engine():
    config = LLMConfig(model=MODEL, api_key=_api_key, temperature=0.3)
    return ConversationEngine(config)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


class TestBilateralRealAPI:
    @pytest.mark.integration
    def test_short_negotiation_completes(self, engine):
        """A 2-turn bilateral negotiation returns a valid ChatResult."""
        buyer = GameAgent(
            name="Buyer",
            system_message=(
                "You are a buyer negotiating to purchase a laptop. "
                "Your maximum budget is $800. Try to get the lowest price. "
                "Keep your responses to 1-2 sentences."
            ),
        )
        seller = GameAgent(
            name="Seller",
            system_message=(
                "You are a seller negotiating to sell a laptop. "
                "Your minimum price is $500. Try to get the highest price. "
                "Keep your responses to 1-2 sentences."
            ),
        )

        result = engine.run_bilateral(buyer, seller, max_turns=2)

        # Basic structural checks
        assert result.chat_history is not None
        assert len(result.chat_history) >= 2  # at least opener + 1 reply
        assert len(result.chat_history) <= 5  # opener + 2 exchanges max

        # Alternation check
        for msg in result.chat_history:
            assert "name" in msg
            assert "content" in msg
            assert isinstance(msg["content"], str)
            assert len(msg["content"]) > 0

        # First message is from buyer (initiator)
        assert result.chat_history[0]["name"] == "Buyer"

    @pytest.mark.integration
    def test_termination_with_real_api(self, engine):
        """Termination function stops the conversation when phrase detected."""
        term_phrase = "DEAL COMPLETE"

        buyer = GameAgent(
            name="Buyer",
            system_message=(
                "You are buying a book. Offer $10 and immediately say "
                f"'{term_phrase}' to end the negotiation. "
                "Keep your response to 1 sentence."
            ),
        )
        seller = GameAgent(
            name="Seller",
            system_message=(
                "You are selling a book for $10. Accept any offer. "
                f"When you agree, say '{term_phrase}'. "
                "Keep your response to 1 sentence."
            ),
        )

        def term_fn(msg, history):
            return term_phrase in msg["content"]

        result = engine.run_bilateral(buyer, seller, max_turns=5, termination_fn=term_fn)

        # Should terminate early (well under 5 full exchanges = 11 messages)
        assert len(result.chat_history) <= 5
        # At least the opener should exist
        assert len(result.chat_history) >= 1


class TestMultilateralRealAPI:
    @pytest.mark.integration
    def test_three_agent_conversation(self, engine):
        """A 3-agent multilateral conversation produces valid output."""
        alice = GameAgent(
            name="Alice",
            system_message="You are Alice in a group discussion about where to eat lunch. You prefer pizza. Keep responses to 1 sentence.",
        )
        bob = GameAgent(
            name="Bob",
            system_message="You are Bob in a group discussion about where to eat lunch. You prefer sushi. Keep responses to 1 sentence.",
        )
        charlie = GameAgent(
            name="Charlie",
            system_message="You are Charlie in a group discussion about where to eat lunch. You prefer tacos. Keep responses to 1 sentence.",
        )

        result = engine.run_multilateral(
            agents=[alice, bob, charlie],
            opening_agent=alice,
            max_turns=3,
        )

        assert len(result.chat_history) == 4  # opener + 3 turns
        assert result.chat_history[0]["name"] == "Alice"

        # All messages have content
        for msg in result.chat_history:
            assert len(msg["content"]) > 0


class TestSingleDecisionRealAPI:
    @pytest.mark.integration
    def test_single_decision_returns_text(self, engine):
        """single_decision returns a non-empty string."""
        agent = GameAgent(
            name="Player",
            system_message=(
                "You are playing the prisoner's dilemma. " "Respond with exactly one word: 'cooperate' or 'defect'."
            ),
        )

        result = engine.single_decision(agent, "Your opponent cooperated last round. What do you do?")

        assert isinstance(result, str)
        assert len(result) > 0
        # Should contain one of the expected responses
        lower = result.lower()
        assert "cooperate" in lower or "defect" in lower
