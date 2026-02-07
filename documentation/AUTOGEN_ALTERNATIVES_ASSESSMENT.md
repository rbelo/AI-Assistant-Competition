# Assessment: Should We Replace AutoGen?

## Executive Summary

This document evaluates whether the AI Assistant Competition platform should migrate
away from Microsoft AutoGen to an alternative multi-agent framework. The assessment
covers the current AutoGen integration surface, known risks, candidate alternatives,
and a recommendation.

**Recommendation:** The project should consider migrating away from AutoGen. The
framework is entering maintenance mode as Microsoft merges it into the Microsoft Agent
Framework (GA targeted Q1 2026), the package ecosystem has been fragmented and
confusing (`autogen` vs `pyautogen` vs `ag2`), and the project's actual usage of
AutoGen is narrow enough that migration would be straightforward.

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

## 6. Recommendation

**Migrate to direct OpenAI API calls.** The rationale:

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

### Suggested Approach

1. Create a thin abstraction layer (`NegotiationAgent` dataclass + `run_negotiation()`
   function) that replaces AutoGen agents.
2. Migrate `evaluate_deal_summary` to a direct OpenAI call.
3. Remove `autogen` from dependencies.
4. Verify all existing tests pass.
5. Run an end-to-end negotiation to confirm behavioral equivalence.

---

## References

- [AutoGen v0.2 to v0.4 Migration Guide](https://microsoft.github.io/autogen/stable//user-guide/agentchat-user-guide/migration-guide.html)
- [AutoGen to Microsoft Agent Framework Migration](https://learn.microsoft.com/en-us/agent-framework/migration-guide/from-autogen/)
- [Top 5 Open-Source Agentic AI Frameworks in 2026](https://research.aimultiple.com/agentic-frameworks/)
- [LangGraph vs CrewAI vs AutoGen Comparison](https://o-mega.ai/articles/langgraph-vs-crewai-vs-autogen-top-10-agent-frameworks-2026)
- [AI Agent Framework Landscape 2025](https://langfuse.com/blog/2025-03-19-ai-agent-comparison)
- [AutoGen Alternatives (Sider)](https://sider.ai/blog/ai-tools/best-autogen-alternatives-for-multi-agent-ai-in-2025)
- [AutoGen Alternatives (ZenML)](https://www.zenml.io/blog/autogen-alternatives)
