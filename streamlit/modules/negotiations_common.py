import re

from .llm_provider import LLMConfig


def clean_agent_message(agent_name_1, agent_name_2, message):
    if not message:
        return ""

    pattern = rf"^\s*(?:{re.escape(agent_name_1)}|{re.escape(agent_name_2)})\s*:\s*"
    clean_message = re.sub(pattern, "", message, flags=re.IGNORECASE)
    return clean_message


def parse_team_name(team_name):
    if not team_name:
        return None, None
    parts = team_name.split("_")
    if len(parts) < 2:
        return None, None
    class_part = parts[0].replace("Class", "")
    group_part = parts[1].replace("Group", "")
    try:
        group_part = int(group_part)
    except ValueError:
        pass
    return class_part, group_part


def compute_deal_scores(deal, maximizer_value, minimizer_value, precision=2):
    if deal is None:
        return 0, 0

    if maximizer_value < minimizer_value:
        if deal < maximizer_value:
            return 0, 1
        if deal > minimizer_value:
            return 1, 0
        ratio = round((deal - maximizer_value) / (minimizer_value - maximizer_value), precision)
        ratio = max(0, min(1, ratio))
        return round(ratio, precision), round(1 - ratio, precision)

    if deal > maximizer_value:
        return 1, 0
    if deal < minimizer_value:
        return 0, 1

    return 0, 0


def resolve_initiator_role_index(name_roles, conversation_order):
    if not conversation_order:
        return 1

    normalized = str(conversation_order).strip()
    if normalized == "same":
        return 1
    if normalized == "opposite":
        return 2

    if normalized == name_roles[0]:
        return 1
    if normalized == name_roles[1]:
        return 2

    return 1


def get_role_agent(team, role_index):
    if role_index == 1:
        return team["Agent 1"]
    if role_index == 2:
        return team["Agent 2"]
    raise ValueError(f"Invalid role index: {role_index}")


def get_minimizer_reservation(team):
    return team["Value 1"]


def get_maximizer_reservation(team):
    return team["Value 2"]


def get_minimizer_maximizer(initiator_team, responder_team, initiator_role_index):
    if initiator_role_index == 1:
        return initiator_team, responder_team
    return responder_team, initiator_team


def is_valid_termination(msg, history, negotiation_termination_message):
    if negotiation_termination_message not in msg["content"]:
        return False

    if not history:
        return True

    last_messages = history[-4:] if len(history) >= 4 else history

    agreement_indicators = [
        "agree",
        "accepted",
        "deal",
        "settled",
        "confirmed",
        "final",
        "conclude",
        "complete",
        "done",
    ]

    agreement_count = sum(
        1 for m in last_messages if any(indicator in m["content"].lower() for indicator in agreement_indicators)
    )

    if agreement_count < 2:
        return False

    values = []
    for m in last_messages:
        clean_content = m["content"].replace("$", "").replace(",", "")
        numbers = re.findall(r"-?\d+(?:\.\d+)?", clean_content)
        if numbers:
            values.extend([float(n) for n in numbers])

    if values:
        max_diff = max(values) * 0.05
        if max(values) - min(values) > max_diff:
            return False

    return True


def build_llm_config(model, api_key, temperature=0.3, top_p=0.5, base_url=None):
    """Build an LLMConfig for any OpenAI-compatible provider.

    Args:
        model: Model identifier (e.g. "gpt-5-mini", "openai/gpt-4o" for OpenRouter).
        api_key: API key for the provider.
        temperature: Sampling temperature (omitted for gpt-5 family).
        top_p: Nucleus sampling (omitted for gpt-5 family).
        base_url: API base URL.  ``None`` uses the OpenAI default.
                  For OpenRouter pass ``"https://openrouter.ai/api/v1"``.
    """
    if model.startswith("gpt-5"):
        return LLMConfig(model=model, api_key=api_key, base_url=base_url)
    return LLMConfig(model=model, api_key=api_key, base_url=base_url, temperature=temperature, top_p=top_p)


def is_invalid_api_key_error(error):
    message = str(error).lower()
    return (
        "invalid api key" in message
        or "incorrect api key" in message
        or "invalid_api_key" in message
        or "unauthorized" in message
        or "authentication" in message
        or "401" in message
    )


# ---------------------------------------------------------------------------
# Prisoner's Dilemma helpers
# ---------------------------------------------------------------------------

PD_DECISION_KEYWORD = "FINAL_DECISION:"
PD_ACTIONS = frozenset({"cooperate", "defect"})

DEFAULT_PD_PAYOFF_MATRIX = {
    "cooperate_cooperate": [3, 3],
    "cooperate_defect": [0, 5],
    "defect_cooperate": [5, 0],
    "defect_defect": [1, 1],
}


def compute_pd_scores(action_a, action_b, payoff_matrix):
    """Look up payoffs from the matrix given both players' actions.

    *payoff_matrix* maps ``"<action_a>_<action_b>"`` to ``[score_a, score_b]``.
    Returns ``(score_a, score_b)`` or ``(0, 0)`` for invalid / unparseable actions.
    """
    if action_a not in PD_ACTIONS or action_b not in PD_ACTIONS:
        return 0, 0
    key = f"{action_a}_{action_b}"
    payoffs = payoff_matrix.get(key)
    if payoffs is None:
        return 0, 0
    return payoffs[0], payoffs[1]


def parse_pd_action(text):
    """Extract ``'cooperate'`` or ``'defect'`` from an agent's private decision.

    Looks first for the ``FINAL_DECISION:`` keyword, then falls back to the
    last occurrence of either action word in the text.  Returns *None* when
    neither action can be identified.
    """
    if not text:
        return None

    text_lower = text.lower()
    keyword = PD_DECISION_KEYWORD.lower()

    # Primary: look for the explicit keyword
    if keyword in text_lower:
        after = text_lower.split(keyword, 1)[1].strip()
        if after.startswith("cooperate"):
            return "cooperate"
        if after.startswith("defect"):
            return "defect"

    # Fallback: last occurrence of either action word
    last_action = None
    last_pos = -1
    for action in ("cooperate", "defect"):
        pos = text_lower.rfind(action)
        if pos > last_pos:
            last_pos = pos
            last_action = action

    return last_action
