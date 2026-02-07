"""Provider-agnostic conversation engine for multi-agent games.

Replaces Microsoft AutoGen with direct OpenAI-compatible API calls.
Supports any provider that exposes an OpenAI-compatible chat completions endpoint
(OpenAI, OpenRouter, Azure, local LLMs via llama.cpp / vLLM / etc.).
"""

from dataclasses import dataclass

from openai import OpenAI

from .llm_provider import LLMConfig


@dataclass
class GameAgent:
    """An LLM-backed participant in any game type."""

    name: str
    system_message: str


class ChatResult:
    """Result of a conversation, with the same shape the rest of the codebase expects."""

    def __init__(self, chat_history):
        self.chat_history = chat_history


class ConversationEngine:
    """Runs turn-based conversations between 2+ agents via any OpenAI-compatible API."""

    def __init__(self, llm_config):
        kwargs = {"api_key": llm_config.api_key}
        if llm_config.base_url:
            kwargs["base_url"] = llm_config.base_url
        self.client = OpenAI(**kwargs)
        self.model = llm_config.model
        self.temperature = llm_config.temperature
        self.top_p = llm_config.top_p

    def _call_llm(self, system_message, messages):
        """Make a single chat-completion call and return the assistant's text."""
        api_messages = [{"role": "system", "content": system_message}]
        api_messages.extend(messages)

        kwargs = {"model": self.model, "messages": api_messages}
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if self.top_p is not None:
            kwargs["top_p"] = self.top_p

        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _build_perspective(self, history, agent_name):
        """Build the OpenAI messages list from one agent's point of view.

        The agent's own prior messages become ``assistant`` and every other
        participant's messages become ``user``.
        """
        messages = []
        for entry in history:
            role = "assistant" if entry["name"] == agent_name else "user"
            messages.append({"role": role, "content": entry["content"]})
        return messages

    def _generate_reply(self, agent, history):
        perspective = self._build_perspective(history, agent.name)
        return self._call_llm(agent.system_message, perspective)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_bilateral(self, agent1, agent2, max_turns, termination_fn=None):
        """Two-agent back-and-forth (e.g. zero-sum negotiation).

        *agent1* opens the conversation by generating its first message via
        an LLM call.  Then agents alternate for up to *max_turns* exchanges
        (each agent speaks once per exchange).

        Args:
            agent1: Initiating agent (generates the opening message).
            agent2: Responding agent.
            max_turns: Maximum number of full exchanges.
            termination_fn: ``fn(msg_dict, history) -> bool``.  Called
                after every generated message.  Return *True* to stop.

        Returns:
            A :class:`ChatResult` whose ``chat_history`` is a list of
            ``{"name": str, "content": str}`` dicts.
        """
        # Agent 1 generates its own opening message
        opening = self._call_llm(agent1.system_message, [])
        history = [{"name": agent1.name, "content": opening}]
        if termination_fn and termination_fn({"content": opening}, history):
            return ChatResult(history)

        for _ in range(max_turns):
            # Agent 2 responds
            reply = self._generate_reply(agent2, history)
            history.append({"name": agent2.name, "content": reply})
            if termination_fn and termination_fn({"content": reply}, history):
                break

            # Agent 1 responds
            reply = self._generate_reply(agent1, history)
            history.append({"name": agent1.name, "content": reply})
            if termination_fn and termination_fn({"content": reply}, history):
                break

        return ChatResult(history)

    def run_multilateral(self, agents, opening_agent, max_turns,
                         speaker_order_fn=None, termination_fn=None):
        """N-agent conversation (e.g. multi-party negotiation).

        *opening_agent* generates the first message via an LLM call, then
        speakers are chosen by *speaker_order_fn* (defaults to round-robin
        starting from the next agent after the opener).

        Args:
            agents: All participating agents (including the opener).
            opening_agent: Agent that generates the first message.
            max_turns: Maximum number of generated messages after the opener.
            speaker_order_fn: ``fn(agents, history) -> iterator of GameAgent``.
                Defaults to round-robin.
            termination_fn: ``fn(msg_dict, history) -> bool``.

        Returns:
            A :class:`ChatResult`.
        """
        opening = self._call_llm(opening_agent.system_message, [])
        history = [{"name": opening_agent.name, "content": opening}]
        if termination_fn and termination_fn({"content": opening}, history):
            return ChatResult(history)

        if speaker_order_fn is not None:
            speaker_iter = speaker_order_fn(agents, history)
        else:
            start_idx = 0
            for i, a in enumerate(agents):
                if a.name == opening_agent.name:
                    start_idx = (i + 1) % len(agents)
                    break

            def _round_robin():
                idx = start_idx
                while True:
                    yield agents[idx % len(agents)]
                    idx += 1

            speaker_iter = _round_robin()

        for _ in range(max_turns):
            agent = next(speaker_iter)
            reply = self._generate_reply(agent, history)
            history.append({"name": agent.name, "content": reply})
            if termination_fn and termination_fn({"content": reply}, history):
                break

        return ChatResult(history)

    def single_decision(self, agent, user_message):
        """One-shot LLM call (e.g. cooperate/defect in Prisoner's Dilemma, or summary evaluation).

        Returns:
            The assistant's response text.
        """
        messages = [{"role": "user", "content": user_message}]
        return self._call_llm(agent.system_message, messages)
