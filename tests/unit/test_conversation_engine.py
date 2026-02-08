"""Unit tests for ConversationEngine with a mocked OpenAI client.

These tests verify conversation-loop logic (turn-taking, perspective
building, termination, speaker rotation) without making real API calls.
"""

import pytest
from unittest.mock import MagicMock, patch, call

import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "streamlit"))

from modules.llm_provider import LLMConfig
from modules.conversation_engine import ConversationEngine, GameAgent, ChatResult


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_engine(replies):
    """Create a ConversationEngine whose LLM returns *replies* in order.

    Args:
        replies: list of strings the mocked LLM will return, one per call.

    Returns:
        (engine, mock_create) – the engine and the underlying
        ``client.chat.completions.create`` mock for assertions.
    """
    config = LLMConfig(model="test-model", api_key="sk-test")
    with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        MockOpenAI.return_value = mock_client

        responses = []
        for text in replies:
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = text
            responses.append(resp)

        mock_client.chat.completions.create.side_effect = responses
        engine = ConversationEngine(config)
        # Re-assign to keep the side_effect working
        engine.client = mock_client
        return engine, mock_client.chat.completions.create


# ---------------------------------------------------------------------------
# run_bilateral
# ---------------------------------------------------------------------------

class TestRunBilateral:
    @pytest.mark.unit
    def test_basic_conversation_structure(self):
        """Two agents talk for 2 turns — expect 5 messages (opener + 2×2)."""
        engine, mock_create = _make_engine([
            "Hello, I'd like to buy your item.",    # agent1 opener
            "Sure, let's discuss the price.",       # agent2 turn 1
            "How about $15?",                       # agent1 turn 1
            "I can do $17.",                         # agent2 turn 2
            "Deal at $17.",                          # agent1 turn 2
        ])

        a1 = GameAgent(name="Buyer", system_message="You are a buyer.")
        a2 = GameAgent(name="Seller", system_message="You are a seller.")

        result = engine.run_bilateral(a1, a2, max_turns=2)

        assert isinstance(result, ChatResult)
        assert len(result.chat_history) == 5
        # Alternation: Buyer, Seller, Buyer, Seller, Buyer
        names = [m["name"] for m in result.chat_history]
        assert names == ["Buyer", "Seller", "Buyer", "Seller", "Buyer"]
        assert result.chat_history[0]["content"] == "Hello, I'd like to buy your item."
        assert mock_create.call_count == 5

    @pytest.mark.unit
    def test_termination_stops_early(self):
        """Conversation ends when termination_fn fires on agent2's reply."""
        engine, mock_create = _make_engine([
            "Let's negotiate.",                     # agent1 opener
            "Pleasure doing business with you",     # agent2 — triggers termination
        ])

        a1 = GameAgent(name="Buyer", system_message="buyer")
        a2 = GameAgent(name="Seller", system_message="seller")

        term_fn = lambda msg, history: "Pleasure doing business" in msg["content"]
        result = engine.run_bilateral(a1, a2, max_turns=10, termination_fn=term_fn)

        assert len(result.chat_history) == 2
        assert result.chat_history[-1]["name"] == "Seller"
        # Only 2 LLM calls: opener + one agent2 reply
        assert mock_create.call_count == 2

    @pytest.mark.unit
    def test_termination_on_agent1_reply(self):
        """Termination fires on agent1's reply mid-conversation."""
        engine, _ = _make_engine([
            "Hi there.",                            # agent1 opener
            "What's your offer?",                   # agent2
            "Pleasure doing business with you",     # agent1 — triggers termination
        ])

        a1 = GameAgent(name="Buyer", system_message="buyer")
        a2 = GameAgent(name="Seller", system_message="seller")

        term_fn = lambda msg, history: "Pleasure doing business" in msg["content"]
        result = engine.run_bilateral(a1, a2, max_turns=10, termination_fn=term_fn)

        assert len(result.chat_history) == 3
        assert result.chat_history[-1]["name"] == "Buyer"

    @pytest.mark.unit
    def test_termination_on_opening_message(self):
        """If the opener itself triggers termination, return immediately."""
        engine, _ = _make_engine([
            "Pleasure doing business with you",     # agent1 opener triggers term
        ])

        a1 = GameAgent(name="Buyer", system_message="buyer")
        a2 = GameAgent(name="Seller", system_message="seller")

        term_fn = lambda msg, history: "Pleasure doing business" in msg["content"]
        result = engine.run_bilateral(a1, a2, max_turns=10, termination_fn=term_fn)

        assert len(result.chat_history) == 1
        assert result.chat_history[0]["name"] == "Buyer"

    @pytest.mark.unit
    def test_max_turns_respected(self):
        """With max_turns=1, only one exchange happens after the opener."""
        engine, mock_create = _make_engine([
            "Opening.",         # agent1 opener
            "Reply one.",       # agent2 turn 1
            "Reply two.",       # agent1 turn 1
        ])

        a1 = GameAgent(name="A", system_message="a")
        a2 = GameAgent(name="B", system_message="b")

        result = engine.run_bilateral(a1, a2, max_turns=1)

        assert len(result.chat_history) == 3  # opener + 1 exchange (2 msgs)
        assert mock_create.call_count == 3

    @pytest.mark.unit
    def test_zero_max_turns(self):
        """With max_turns=0, only the opener is generated."""
        engine, _ = _make_engine(["Just the opener."])

        a1 = GameAgent(name="A", system_message="a")
        a2 = GameAgent(name="B", system_message="b")

        result = engine.run_bilateral(a1, a2, max_turns=0)

        assert len(result.chat_history) == 1
        assert result.chat_history[0]["name"] == "A"

    @pytest.mark.unit
    def test_no_termination_fn(self):
        """Without a termination function, runs for all max_turns."""
        engine, _ = _make_engine([
            "Open.",        # opener
            "R1.",          # agent2 turn 1
            "R2.",          # agent1 turn 1
            "R3.",          # agent2 turn 2
            "R4.",          # agent1 turn 2
        ])

        a1 = GameAgent(name="A", system_message="a")
        a2 = GameAgent(name="B", system_message="b")

        result = engine.run_bilateral(a1, a2, max_turns=2, termination_fn=None)

        assert len(result.chat_history) == 5


# ---------------------------------------------------------------------------
# perspective building
# ---------------------------------------------------------------------------

class TestPerspectiveBuilding:
    @pytest.mark.unit
    def test_own_messages_as_assistant(self):
        """An agent sees its own prior messages as 'assistant'."""
        config = LLMConfig(model="m", api_key="k")
        with patch("modules.conversation_engine.OpenAI"):
            engine = ConversationEngine(config)

        history = [
            {"name": "Buyer", "content": "I want to buy"},
            {"name": "Seller", "content": "I want to sell"},
            {"name": "Buyer", "content": "How about $10?"},
        ]

        perspective = engine._build_perspective(history, "Buyer")

        assert perspective == [
            {"role": "assistant", "content": "I want to buy"},
            {"role": "user", "content": "I want to sell"},
            {"role": "assistant", "content": "How about $10?"},
        ]

    @pytest.mark.unit
    def test_other_messages_as_user(self):
        """An agent sees all other agents' messages as 'user'."""
        config = LLMConfig(model="m", api_key="k")
        with patch("modules.conversation_engine.OpenAI"):
            engine = ConversationEngine(config)

        history = [
            {"name": "Buyer", "content": "I want to buy"},
            {"name": "Seller", "content": "I want to sell"},
        ]

        perspective = engine._build_perspective(history, "Seller")

        assert perspective[0] == {"role": "user", "content": "I want to buy"}
        assert perspective[1] == {"role": "assistant", "content": "I want to sell"}

    @pytest.mark.unit
    def test_multilateral_perspective(self):
        """In a 3-agent chat, an agent sees both others as 'user'."""
        config = LLMConfig(model="m", api_key="k")
        with patch("modules.conversation_engine.OpenAI"):
            engine = ConversationEngine(config)

        history = [
            {"name": "Alice", "content": "msg1"},
            {"name": "Bob", "content": "msg2"},
            {"name": "Charlie", "content": "msg3"},
        ]

        perspective = engine._build_perspective(history, "Bob")

        assert perspective == [
            {"role": "user", "content": "msg1"},
            {"role": "assistant", "content": "msg2"},
            {"role": "user", "content": "msg3"},
        ]


# ---------------------------------------------------------------------------
# LLM call arguments
# ---------------------------------------------------------------------------

class TestLLMCallArguments:
    @pytest.mark.unit
    def test_system_message_passed_to_api(self):
        """The agent's system_message is sent as the first API message."""
        engine, mock_create = _make_engine(["response"])

        a = GameAgent(name="A", system_message="You are a test agent.")
        engine.single_decision(a, "What do you do?")

        call_kwargs = mock_create.call_args[1]
        messages = call_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "You are a test agent."}
        assert messages[1] == {"role": "user", "content": "What do you do?"}

    @pytest.mark.unit
    def test_temperature_and_top_p_passed(self):
        """When set, temperature and top_p are included in API kwargs."""
        config = LLMConfig(model="m", api_key="k", temperature=0.7, top_p=0.9)
        with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "ok"
            mock_client.chat.completions.create.return_value = resp

            engine = ConversationEngine(config)
            engine.client = mock_client
            engine.single_decision(GameAgent(name="A", system_message="sys"), "hi")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["temperature"] == 0.7
            assert call_kwargs["top_p"] == 0.9

    @pytest.mark.unit
    def test_temperature_and_top_p_omitted_when_none(self):
        """When None, temperature and top_p are not passed to the API."""
        config = LLMConfig(model="m", api_key="k", temperature=None, top_p=None)
        with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "ok"
            mock_client.chat.completions.create.return_value = resp

            engine = ConversationEngine(config)
            engine.client = mock_client
            engine.single_decision(GameAgent(name="A", system_message="sys"), "hi")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert "temperature" not in call_kwargs
            assert "top_p" not in call_kwargs

    @pytest.mark.unit
    def test_base_url_passed_to_openai_client(self):
        """When base_url is set, it's passed to the OpenAI constructor."""
        config = LLMConfig(model="m", api_key="k", base_url="https://openrouter.ai/api/v1")
        with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
            ConversationEngine(config)
            MockOpenAI.assert_called_once_with(
                api_key="k", base_url="https://openrouter.ai/api/v1"
            )

    @pytest.mark.unit
    def test_base_url_omitted_when_none(self):
        """When base_url is None, only api_key is passed to OpenAI."""
        config = LLMConfig(model="m", api_key="k", base_url=None)
        with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
            ConversationEngine(config)
            MockOpenAI.assert_called_once_with(api_key="k")

    @pytest.mark.unit
    def test_model_passed_to_api(self):
        """The configured model name is included in every API call."""
        config = LLMConfig(model="gpt-5-mini", api_key="k")
        with patch("modules.conversation_engine.OpenAI") as MockOpenAI:
            mock_client = MagicMock()
            MockOpenAI.return_value = mock_client
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = "ok"
            mock_client.chat.completions.create.return_value = resp

            engine = ConversationEngine(config)
            engine.client = mock_client
            engine.single_decision(GameAgent(name="A", system_message="sys"), "hi")

            call_kwargs = mock_client.chat.completions.create.call_args[1]
            assert call_kwargs["model"] == "gpt-5-mini"


# ---------------------------------------------------------------------------
# single_decision
# ---------------------------------------------------------------------------

class TestSingleDecision:
    @pytest.mark.unit
    def test_returns_llm_response(self):
        """single_decision returns the LLM's text."""
        engine, _ = _make_engine(["cooperate"])

        a = GameAgent(name="Player", system_message="You are playing PD.")
        result = engine.single_decision(a, "Do you cooperate or defect?")

        assert result == "cooperate"

    @pytest.mark.unit
    def test_single_api_call(self):
        """single_decision makes exactly one API call."""
        engine, mock_create = _make_engine(["answer"])

        a = GameAgent(name="A", system_message="sys")
        engine.single_decision(a, "question")

        assert mock_create.call_count == 1


# ---------------------------------------------------------------------------
# run_multilateral
# ---------------------------------------------------------------------------

class TestRunMultilateral:
    @pytest.mark.unit
    def test_round_robin_3_agents(self):
        """Three agents take turns in round-robin order after the opener."""
        engine, _ = _make_engine([
            "Alice opens.",     # Alice opener
            "Bob speaks.",      # Bob (next after Alice)
            "Charlie speaks.",  # Charlie
            "Alice again.",     # Alice
        ])

        alice = GameAgent(name="Alice", system_message="a")
        bob = GameAgent(name="Bob", system_message="b")
        charlie = GameAgent(name="Charlie", system_message="c")

        result = engine.run_multilateral(
            agents=[alice, bob, charlie],
            opening_agent=alice,
            max_turns=3,
        )

        names = [m["name"] for m in result.chat_history]
        assert names == ["Alice", "Bob", "Charlie", "Alice"]
        assert len(result.chat_history) == 4  # opener + 3 turns

    @pytest.mark.unit
    def test_round_robin_starts_after_opener(self):
        """If Bob opens, round-robin starts from Charlie (next in list)."""
        engine, _ = _make_engine([
            "Bob opens.",       # Bob opener
            "Charlie speaks.",  # Charlie (next after Bob)
            "Alice speaks.",    # Alice
        ])

        alice = GameAgent(name="Alice", system_message="a")
        bob = GameAgent(name="Bob", system_message="b")
        charlie = GameAgent(name="Charlie", system_message="c")

        result = engine.run_multilateral(
            agents=[alice, bob, charlie],
            opening_agent=bob,
            max_turns=2,
        )

        names = [m["name"] for m in result.chat_history]
        assert names == ["Bob", "Charlie", "Alice"]

    @pytest.mark.unit
    def test_custom_speaker_order(self):
        """A custom speaker_order_fn overrides round-robin."""
        engine, _ = _make_engine([
            "Alice opens.",
            "Charlie first.",   # custom order: Charlie, Charlie, Bob
            "Charlie again.",
            "Bob finally.",
        ])

        alice = GameAgent(name="Alice", system_message="a")
        bob = GameAgent(name="Bob", system_message="b")
        charlie = GameAgent(name="Charlie", system_message="c")

        def custom_order(agents, history):
            yield charlie
            yield charlie
            yield bob

        result = engine.run_multilateral(
            agents=[alice, bob, charlie],
            opening_agent=alice,
            max_turns=3,
            speaker_order_fn=custom_order,
        )

        names = [m["name"] for m in result.chat_history]
        assert names == ["Alice", "Charlie", "Charlie", "Bob"]

    @pytest.mark.unit
    def test_termination_in_multilateral(self):
        """Termination stops multilateral conversations."""
        engine, _ = _make_engine([
            "Alice opens.",
            "DONE",            # Bob terminates
        ])

        alice = GameAgent(name="Alice", system_message="a")
        bob = GameAgent(name="Bob", system_message="b")

        term_fn = lambda msg, history: msg["content"] == "DONE"
        result = engine.run_multilateral(
            agents=[alice, bob],
            opening_agent=alice,
            max_turns=10,
            termination_fn=term_fn,
        )

        assert len(result.chat_history) == 2

    @pytest.mark.unit
    def test_termination_on_multilateral_opener(self):
        """If the opener triggers termination, return immediately."""
        engine, _ = _make_engine(["DONE"])

        alice = GameAgent(name="Alice", system_message="a")
        bob = GameAgent(name="Bob", system_message="b")

        term_fn = lambda msg, history: msg["content"] == "DONE"
        result = engine.run_multilateral(
            agents=[alice, bob],
            opening_agent=alice,
            max_turns=10,
            termination_fn=term_fn,
        )

        assert len(result.chat_history) == 1


# ---------------------------------------------------------------------------
# bilateral perspective correctness (integration-style with mock)
# ---------------------------------------------------------------------------

class TestBilateralPerspectiveCorrectness:
    """Verify that the API receives the correct perspective for each agent."""

    @pytest.mark.unit
    def test_agent2_sees_agent1_opener_as_user(self):
        """Agent2's first API call should see agent1's opener as 'user'."""
        engine, mock_create = _make_engine([
            "Buyer says hello.",    # agent1 opener
            "Seller responds.",     # agent2
        ])

        a1 = GameAgent(name="Buyer", system_message="buyer_sys")
        a2 = GameAgent(name="Seller", system_message="seller_sys")

        # Terminate after agent2 speaks (not on opener)
        term_fn = lambda msg, h: msg["content"] == "Seller responds."
        engine.run_bilateral(a1, a2, max_turns=1, termination_fn=term_fn)

        # Second call is agent2's perspective
        second_call = mock_create.call_args_list[1]
        messages = second_call[1]["messages"]
        # System message for seller
        assert messages[0] == {"role": "system", "content": "seller_sys"}
        # Agent1's opener seen as 'user'
        assert messages[1] == {"role": "user", "content": "Buyer says hello."}

    @pytest.mark.unit
    def test_agent1_second_turn_sees_full_history(self):
        """Agent1's second message should see the full conversation so far."""
        engine, mock_create = _make_engine([
            "Open.",        # agent1 opener
            "Reply.",       # agent2
            "Counter.",     # agent1 second turn
        ])

        a1 = GameAgent(name="A", system_message="sys_a")
        a2 = GameAgent(name="B", system_message="sys_b")

        engine.run_bilateral(a1, a2, max_turns=1)

        # Third call is agent1's second turn
        third_call = mock_create.call_args_list[2]
        messages = third_call[1]["messages"]
        assert messages[0] == {"role": "system", "content": "sys_a"}
        # Agent1 sees its own opener as 'assistant'
        assert messages[1] == {"role": "assistant", "content": "Open."}
        # Agent1 sees agent2's reply as 'user'
        assert messages[2] == {"role": "user", "content": "Reply."}
