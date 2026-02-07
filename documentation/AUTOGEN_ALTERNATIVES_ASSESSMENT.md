# Assessment: Should We Replace AutoGen?

## Executive Summary

This document evaluates whether the AI Assistant Competition platform should migrate
away from Microsoft AutoGen to an alternative multi-agent framework. The assessment
covers the current AutoGen integration surface, known risks, candidate alternatives,
and a recommendation.

**Recommendation:** The project should migrate away from AutoGen to direct OpenAI API
calls with a game-aware abstraction layer. The framework is entering maintenance mode
as Microsoft merges it into the Microsoft Agent Framework (GA targeted Q1 2026), the
package ecosystem is fragmented (`autogen` vs `pyautogen` vs `ag2`), and the project's
usage is narrow enough that migration would be straightforward. Critically, future game
types (prisoner's dilemma, multi-party negotiations, auctions) do **not** require a
multi-agent framework — they are better served by a clean `ConversationEngine` +
`GameRunner` architecture built on direct API calls.

---

## 1. Current AutoGen Usage

The project uses a small surface area of AutoGen, confined to four files:

### Classes Used

| AutoGen Class        | Where Used                       | Purpose                              |
|----------------------|----------------------------------|--------------------------------------|
| `ConversableAgent`   | `negotiations_agents.py:36-53`   | Negotiation agents (2 per team)      |
| `UserProxyAgent`     | `negotiations_summary.py:97-103` | Proxy for summary evaluation         |
| `AssistantAgent`     | `negotiations_summary.py:109-136`| Analyzes transcripts for deal values |

### API Surface

The following AutoGen APIs are actually called:

- **Agent construction**: `ConversableAgent(name, llm_config, human_input_mode, system_message, is_termination_msg, chat_messages)`
- **Agent construction**: `UserProxyAgent(name, llm_config, human_input_mode, is_termination_msg, code_execution_config)`
- **Agent construction**: `AssistantAgent(name, llm_config, human_input_mode, is_termination_msg, system_message)`
- **Chat initiation**: `agent.initiate_chat(other_agent, clear_history, max_turns, message)` — returns a chat result
- **System message update**: `agent.update_system_message(new_message)` — called in `negotiations.py:96-98`
- **Chat result access**: `chat.chat_history` — list of `{"name": ..., "content": ...}` dicts
- **Agent properties**: `agent.name`

### LLM Configuration

Built via `build_llm_config()` in `negotiations_common.py:134-139`:
```python
{"config_list": [{"model": model, "api_key": api_key}], "temperature": 0.3, "top_p": 0.5}
```

### Key Observation

The project does **not** use any of AutoGen's advanced features:
- No group chat orchestration
- No code execution (the `code_execution_config` on `UserProxyAgent` is set but never triggered)
- No tool/function calling
- No nested chats
- No custom reply functions
- No human-in-the-loop flows

The usage is essentially: **create two agents, run a turn-limited conversation, read the transcript**. This is a thin wrapper around OpenAI's chat completions API.

---

## 2. Risks of Staying on AutoGen

### 2.1 Maintenance Mode

Microsoft announced in October 2025 that AutoGen and Semantic Kernel are being merged
into the **Microsoft Agent Framework**, targeting 1.0 GA by end of Q1 2026. AutoGen is
now in maintenance mode — bug fixes and security patches only, no new features. This
means the project will eventually need to migrate regardless.

### 2.2 Package Ecosystem Confusion

The AutoGen package landscape is fragmented:

- **`pyautogen`** on PyPI — Microsoft lost and regained admin access; versions after
  0.2.34 were briefly from a different maintainer. Now a proxy for `autogen-agentchat`.
- **`autogen`** on PyPI — now an alias for `ag2` (community fork continuing v0.2).
- **`autogen-agentchat`** — Microsoft's official v0.4+ package.
- **`ag2`** — community-led fork continuing the v0.2 line.

The project's `pyproject.toml` lists `autogen` as a dependency with no version pin,
meaning installs could pull in either the `ag2` fork or the official Microsoft package
depending on resolution order. The `requirements.txt` pins `autogen>=0.10.0`.

### 2.3 Python Version Constraints

The project's `pyproject.toml` includes `requires-python = ">=3.9,<3.14"` with the
comment "autogen requires Python < 3.14". This constraint is imposed solely by AutoGen
and limits the project's ability to adopt newer Python versions.

### 2.4 Heavyweight Dependency

AutoGen pulls in a large dependency tree for features this project never uses (code
execution, Docker integration, group chat, etc.). This increases install times, security
surface area, and potential for dependency conflicts.

---

## 3. Candidate Alternatives

### 3.1 Direct OpenAI API (Recommended)

Since the project only uses AutoGen for turn-based two-agent conversations backed by
OpenAI models, the simplest alternative is to call the OpenAI Chat Completions API
directly.

**Pros:**
- Eliminates a large transitive dependency
- The project already depends on `openai`
- Full control over retry logic, token usage, and error handling
- No Python version constraints from the framework
- No risk of upstream breaking changes or package confusion
- Simpler debugging — no framework abstraction layers

**Cons:**
- Must implement the conversation loop (trivial — ~50 lines)
- Must manage message history manually (already done partially)

**Migration effort:** Low. The core loop is: alternate calls to `openai.chat.completions.create()` with each agent's system prompt and the growing message history, check termination after each turn.

### 3.2 LangGraph

A graph-based orchestration framework from the LangChain ecosystem.

**Pros:**
- Strong production reliability, built-in retries and observability
- Good for complex workflows with branching and error recovery
- Active development and large community

**Cons:**
- Overkill for this project's simple two-agent conversation pattern
- Adds LangChain as a dependency (large ecosystem)
- Steeper learning curve for contributors
- Graph-based paradigm doesn't map naturally to turn-based negotiation

**Migration effort:** Medium. Requires remodeling the conversation as a state graph.

### 3.3 CrewAI

A role-based multi-agent framework emphasizing team collaboration.

**Pros:**
- Role-based abstraction maps reasonably well to negotiation roles (buyer/seller)
- Simple API, easy to learn
- Active development

**Cons:**
- Still an external dependency with its own breaking-change risk
- Less mature than LangGraph
- Role/task abstraction adds unnecessary structure for simple back-and-forth chat

**Migration effort:** Low-Medium. Agent creation maps fairly directly.

### 3.4 PydanticAI

A Python-native, type-safe agent framework.

**Pros:**
- Schema-first approach for reliable structured outputs
- Lightweight, Pythonic
- Good for projects already using Pydantic

**Cons:**
- Newer, smaller community
- Not specifically designed for multi-agent conversations

**Migration effort:** Medium.

### 3.5 OpenAI Agents SDK

OpenAI's native agent-building toolkit.

**Pros:**
- First-party OpenAI support
- Built-in function calling and tool use
- Maintained by the LLM provider

**Cons:**
- Vendor lock-in to OpenAI
- Experimental / evolving API

**Migration effort:** Low-Medium.

---

## 4. Comparison Matrix

| Criterion                         | Stay on AutoGen | Direct OpenAI API | LangGraph | CrewAI |
|-----------------------------------|:---:|:---:|:---:|:---:|
| Migration effort                  | None | Low | Medium | Low-Med |
| Long-term maintenance risk        | High | Low | Low | Medium |
| Dependency weight                 | Heavy | Minimal | Heavy | Medium |
| Python version flexibility        | Restricted | Unrestricted | Unrestricted | Unrestricted |
| Package ecosystem stability       | Poor | Stable | Good | Good |
| Matches project complexity        | Overpowered | Right-sized | Overpowered | Slightly over |
| Learning curve for contributors   | Medium | Low | High | Medium |
| Debugging transparency            | Low | High | Medium | Medium |

---

## 5. Migration Sketch (Direct OpenAI API)

If we choose the direct OpenAI API approach, here is a rough outline of what changes:

### Replace `negotiations_agents.py`

Instead of creating `autogen.ConversableAgent` objects, create plain data objects:

```python
@dataclass
class NegotiationAgent:
    name: str
    system_message: str
    is_termination_msg: Callable[[dict], bool]
```

### Replace `negotiations_summary.py`

Replace `UserProxyAgent` + `AssistantAgent` with a single OpenAI call:

```python
def evaluate_deal_summary(chat_history, summary_prompt, ...):
    response = openai.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": summary_system_prompt},
            {"role": "user", "content": summary_context + summary_prompt},
        ],
        temperature=0.3,
    )
    summary_text = response.choices[0].message.content
    return summary_text, parse_deal_value(summary_text, summary_termination_message)
```

### Replace `initiate_chat` in `negotiations.py`

Implement a simple conversation loop:

```python
def run_negotiation(agent1, agent2, starting_message, max_turns):
    history = []
    current_message = starting_message
    for turn in range(max_turns):
        # Agent 2 responds
        response = openai.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": agent2.system_message},
                *history,
                {"role": "user", "content": current_message},
            ],
        )
        reply = response.choices[0].message.content
        history.append({"role": "user", "content": current_message})
        history.append({"role": "assistant", "content": reply})
        if agent2.is_termination_msg({"content": reply}):
            break
        # Swap roles for next turn
        agent1, agent2 = agent2, agent1
        current_message = reply
    return history
```

### Files Modified

| File | Change |
|------|--------|
| `negotiations_agents.py` | Replace `autogen.ConversableAgent` with dataclass |
| `negotiations_summary.py` | Replace `UserProxyAgent`/`AssistantAgent` with direct API call |
| `negotiations.py` | Replace `initiate_chat` with conversation loop |
| `negotiations_common.py` | Update `build_llm_config` to return OpenAI-native config |
| `pyproject.toml` | Remove `autogen` dependency, remove Python <3.14 constraint |
| `requirements.txt` | Remove `autogen>=0.10.0` |

### Tests

Existing unit tests in `tests/unit/test_negotiations_logic.py` and
`tests/unit/test_negotiations_scoring.py` test pure logic functions
(`compute_deal_scores`, `parse_deal_value`, `is_valid_termination`, etc.) and should
remain unaffected. Integration tests that mock AutoGen agents would need updating.

---

## 6. Future Game Scenarios: Impact on Framework Choice

The current platform only implements zero-sum bilateral negotiation. However, the
database already has scaffolding for a prisoner's dilemma mode (`prisoners_dilemma_config`
table, `game_modes` table, UI stubs in `game_modes.py`), and there is clear educational
value in expanding the game repertoire. This section analyzes how future game types
would affect the framework decision.

### 6.1 Prisoner's Dilemma (Iterated)

**What it requires:**
- Two agents play repeated rounds of cooperate/defect
- Each agent sees the history of prior rounds and chooses simultaneously
- A payoff matrix determines scores (already stored as JSONB in `prisoners_dilemma_config`)
- Agents may communicate before deciding (cheap talk) or decide silently

**Architectural patterns:**

| Variant | Conversation Pattern | Framework Needs |
|---------|---------------------|-----------------|
| **Silent PD** (no communication) | Each agent submits a decision per round independently; no dialogue | Simple: two parallel API calls per round, no conversation at all |
| **Cheap-talk PD** | Agents discuss, then each privately submits a decision | Two-phase per round: (1) conversation loop, (2) independent decision calls |
| **Iterated PD with memory** | Same as above but across N rounds with cumulative history | State management across rounds; growing context windows |

**Framework implications:**
- **Direct OpenAI API** handles all variants easily. Silent PD is trivial (parallel
  completions). Cheap-talk PD reuses the same conversation loop from zero-sum. The
  private decision step is just a separate API call with a constrained prompt
  ("respond with COOPERATE or DEFECT"). Iteration is a for-loop with accumulated state.
- **AutoGen** adds no value here. The `initiate_chat` abstraction doesn't support the
  "converse then decide privately" split, so you'd fight the framework.
- **LangGraph** could model the cooperate/talk/decide phases as graph nodes, but this
  is unnecessary complexity for what is fundamentally a loop.

### 6.2 Multi-Party Negotiation (3+ Agents)

**What it requires:**
- Three or more agents negotiate simultaneously (e.g., trade deals, coalition
  formation, resource allocation)
- Turn-taking protocol: round-robin, free-for-all, or structured proposal/response
- Possible side conversations (bilateral within multi-party)
- Coalition dynamics — subgroups may form alliances

**Architectural patterns:**

| Variant | Conversation Pattern | Framework Needs |
|---------|---------------------|-----------------|
| **Round-robin multilateral** | Agents take turns addressing the group (like a meeting) | Single shared message history, each agent responds in turn |
| **Hub-and-spoke** | A mediator agent coordinates, agents respond to mediator | Star topology: mediator ↔ each agent; mediator synthesizes |
| **Free-form with side channels** | Agents can address specific others or the group | Multiple concurrent conversation threads; routing logic |
| **Coalition formation** | Agents negotiate in subgroups, then present joint positions | Dynamic group composition; subgroup conversations |

**Framework implications:**
- **Direct OpenAI API** handles round-robin multilateral cleanly: maintain one message
  list, cycle through agents, each sees the full history. Hub-and-spoke is also
  straightforward. Free-form with side channels requires more bookkeeping (multiple
  conversation threads with routing) but is entirely doable — it's just data structures.
  Estimated additional complexity: ~100-150 lines for a flexible multi-party engine.
- **AutoGen's GroupChat** is designed exactly for multi-party scenarios — it manages
  speaker selection, shared history, and turn-taking. However, it assumes a specific
  conversation pattern (all agents share one history, a "manager" selects speakers).
  Side channels and coalition subgroups don't map cleanly to GroupChat.
- **LangGraph** becomes more compelling here. Multi-party negotiations with branching
  (side channels, coalitions) map well to a graph where nodes are conversation
  states and edges are transitions. However, this is still premature unless the project
  actually builds free-form multi-party games.
- **CrewAI** handles role-based multi-agent teams naturally. Its delegation and
  collaboration patterns are a reasonable fit for coalition games.

### 6.3 Auction / Bidding Games

**What it requires:**
- Multiple agents submit bids (sealed or open)
- An auctioneer mechanism determines winners and prices
- Strategies evolve across rounds (e.g., ascending, descending, Vickrey auctions)

**Framework implications:**
- Mostly a **game-engine problem**, not an agent-framework problem. The auctioneer
  is deterministic logic, not an LLM. Each agent makes independent decisions given
  the auction state. Direct API calls are the natural fit — call each agent once per
  round with the current state.

### 6.4 Diplomacy / Complex Multi-Phase Games

**What it requires:**
- Multiple phases per turn (negotiate → commit → resolve)
- Private and public channels
- Binding/non-binding commitments
- Long-term strategy across many rounds

**Framework implications:**
- This is the most complex scenario and the only one where a framework arguably helps.
  Direct API calls still work but require careful state management.
- LangGraph's state machine model is well-suited for phase transitions.
- However, this type of game is far beyond the current project scope (university
  course platform for teaching negotiation basics).

### 6.5 Summary: Do Future Needs Change the Recommendation?

| Game Type | Direct OpenAI API | AutoGen | LangGraph | CrewAI |
|-----------|:---:|:---:|:---:|:---:|
| Zero-sum bilateral (current) | Easy | Overkill | Overkill | Overkill |
| Prisoner's dilemma (silent) | Trivial | Poor fit | Overkill | Overkill |
| Prisoner's dilemma (cheap-talk) | Easy | OK fit | Overkill | Overkill |
| Multi-party round-robin | Easy | Good fit (GroupChat) | Good fit | Good fit |
| Multi-party with side channels | Moderate (~150 LOC) | Poor fit | Good fit | Moderate |
| Auctions | Easy | Poor fit | Unnecessary | Unnecessary |
| Complex diplomacy games | Moderate-Hard | Moderate | Good fit | Moderate |

**Key insight:** The only scenario where a framework provides meaningful value over
direct API calls is **multi-party negotiation with complex routing** (side channels,
coalitions, dynamic group composition). Even then, the framework buys convenience, not
capability — all patterns are implementable with direct API calls.

**Updated recommendation:** The direct OpenAI API approach remains the best choice.
Here's why:

1. **Prisoner's dilemma is simpler than the current game.** It needs less agent
   orchestration, not more. AutoGen's `initiate_chat` is actually a poor fit for the
   "talk then decide privately" pattern.

2. **Multi-party round-robin is a modest extension.** Instead of alternating between 2
   agents, cycle through N agents on a shared history. This is a small change to the
   conversation loop (~20 additional lines), not a reason to adopt a framework.

3. **The framework only helps at the "complex diplomacy" level,** which is well beyond
   the educational scope of this platform. If that scenario materializes, adopting
   LangGraph at that point would be straightforward — the direct-API abstraction layer
   translates cleanly to graph nodes.

4. **Building on direct API calls creates a better teaching platform.** Students and
   contributors can understand and debug the negotiation engine without learning a
   third-party framework's abstractions.

### 6.6 Recommended Architecture for Multi-Game Support

To support current and foreseeable future games, the abstraction layer should be
designed as follows:

```python
@dataclass
class GameAgent:
    """An LLM-backed participant in any game type."""
    name: str
    system_message: str
    model: str
    api_key: str
    temperature: float = 0.3

class ConversationEngine:
    """Runs turn-based conversations between 2+ agents."""

    def run_bilateral(self, agent1, agent2, opening, max_turns, termination_fn):
        """Two-agent back-and-forth (zero-sum negotiation)."""
        ...

    def run_multilateral(self, agents, opening, max_turns, speaker_order_fn, termination_fn):
        """N-agent round-robin or custom speaker order."""
        ...

    def single_decision(self, agent, context, constraint):
        """One-shot decision call (e.g., cooperate/defect in PD)."""
        ...

class GameRunner:
    """Orchestrates game-specific logic."""

    def run_zero_sum(self, team1, team2, config): ...
    def run_prisoners_dilemma(self, team1, team2, config, num_iterations): ...
    def run_multilateral_negotiation(self, teams, config): ...
```

This design:
- Separates **conversation mechanics** (how agents talk) from **game logic** (rules,
  scoring, phases)
- Supports bilateral and multilateral conversations through the same engine
- Handles prisoner's dilemma naturally: `run_bilateral()` for cheap talk +
  `single_decision()` for the cooperate/defect choice
- Is framework-agnostic — each method is 20-50 lines of OpenAI API calls
- Can be wrapped by LangGraph nodes later if complex orchestration is ever needed

---

## 7. Recommendation

**Migrate to direct OpenAI API calls with a game-aware abstraction layer.** The
rationale:

1. **The project uses ~5% of AutoGen's feature set.** The actual need is a turn-based
   conversation loop with termination logic — something achievable in ~50-80 lines of
   plain Python + OpenAI SDK.

2. **AutoGen is entering maintenance mode.** Microsoft is consolidating into the Agent
   Framework. Staying on AutoGen means a forced migration later, potentially to a more
   complex target.

3. **The package situation is unstable.** The `autogen`/`pyautogen`/`ag2` confusion
   creates real risk of broken installs and supply-chain issues.

4. **Removing AutoGen eliminates the Python <3.14 constraint** and significantly
   reduces the dependency footprint.

5. **Migration effort is low.** The narrow API surface means the change is confined to
   3-4 files with straightforward replacements.

6. **Future game types don't need a framework.** Prisoner's dilemma is *simpler* than
   the current game. Multi-party round-robin is a ~20-line extension. The only scenario
   where a framework would help (complex diplomacy with side channels) is far beyond
   the platform's educational scope.

7. **The direct-API approach creates a better foundation for multi-game support.** A
   `ConversationEngine` + `GameRunner` architecture (see Section 6.6) cleanly separates
   conversation mechanics from game rules, making it easy to add prisoner's dilemma,
   auctions, or multi-party games without adopting a framework.

### Suggested Approach

1. Create a `ConversationEngine` class with `run_bilateral()`, `run_multilateral()`,
   and `single_decision()` methods (see Section 6.6).
2. Create a `GameRunner` class that encapsulates game-specific logic (zero-sum scoring,
   prisoner's dilemma payoff matrices, etc.).
3. Migrate `evaluate_deal_summary` to a direct OpenAI call via `single_decision()`.
4. Remove `autogen` from dependencies.
5. Verify all existing tests pass.
6. Run an end-to-end negotiation to confirm behavioral equivalence.
7. Implement prisoner's dilemma game logic using the new architecture.

---

## References

- [AutoGen v0.2 to v0.4 Migration Guide](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/migration-guide.html)
- [AutoGen to Microsoft Agent Framework Migration](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/)
- [Top 5 Open-Source Agentic AI Frameworks in 2026](https://research.aimultiple.com/agentic-frameworks/)
- [LangGraph vs CrewAI vs AutoGen Comparison](https://o-mega.ai/articles/langgraph-vs-crewai-vs-autogen-top-10-agent-frameworks-2026)
- [AI Agent Framework Landscape 2025](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- [AutoGen Alternatives (Sider)](https://sider.ai/blog/ai-tools/best-autogen-alternatives-for-multi-agent-ai-in-2025)
- [AutoGen Alternatives (ZenML)](https://www.zenml.io/blog/autogen-alternatives)
