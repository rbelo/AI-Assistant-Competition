import re

from .conversation_engine import GameAgent
from .negotiations_common import clean_agent_message


def _build_summary_context(chat_history, role1_name=None, role2_name=None, history_size=4):
    if not chat_history:
        return ""

    if history_size is None:
        recent_history = chat_history
    else:
        recent_history = chat_history[-history_size:] if history_size else []

    summary_context = ""
    for entry in recent_history:
        content = entry.get("content", "")
        if role1_name and role2_name:
            content = clean_agent_message(role1_name, role2_name, content)
        summary_context += f"{entry.get('name', '')}: {content}\n\n\n"
    return summary_context


def _extract_summary_text(summary_eval, summary_agent_name):
    if not summary_eval or not getattr(summary_eval, "chat_history", None):
        return ""

    for entry in reversed(summary_eval.chat_history):
        if entry.get("name") == summary_agent_name and entry.get("content"):
            return entry["content"]

    last_entry = summary_eval.chat_history[-1]
    return last_entry.get("content", "") if last_entry else ""


def parse_deal_value(summary_text, summary_termination_message):
    if not summary_text or not summary_termination_message:
        return -1

    for line in summary_text.splitlines():
        stripped = line.strip()
        if summary_termination_message in stripped:
            value_str = stripped.split(summary_termination_message, 1)[1].strip()
            value_str = value_str.replace("$", "").replace(",", "")
            match = re.findall(r"-?\d+(?:[.,]\d+)?", value_str)
            if not match:
                return -1
            try:
                return float(match[0].replace(",", "."))
            except Exception:
                return -1

    return -1


def evaluate_deal_summary(
    engine,
    chat_history,
    summary_prompt,
    summary_termination_message,
    summary_agent,
    role1_name=None,
    role2_name=None,
    history_size=4,
):
    if not summary_agent or not engine:
        return "", -1

    summary_context = _build_summary_context(chat_history, role1_name, role2_name, history_size)
    summary_text = engine.single_decision(summary_agent, summary_context + (summary_prompt or ""))
    return summary_text, parse_deal_value(summary_text, summary_termination_message)


def extract_summary_from_transcript(transcript, summary_termination_message):
    if not transcript:
        return "", -1

    parts = [part.strip() for part in transcript.split("\n\n\n") if part.strip()]
    if not parts:
        return "", -1

    summary_text = parts[-1]
    if summary_termination_message and summary_termination_message not in summary_text:
        return "", -1

    return summary_text, parse_deal_value(summary_text, summary_termination_message)


def build_summary_agent(summary_termination_message, negotiation_termination_message, include_summary=False):
    summary_prefix = ""
    if include_summary:
        summary_prefix = "Provide a concise 2-3 sentence summary before the final line.\n"

    return GameAgent(
        name="Summary_Agent",
        system_message=f"""You are a sophisticated negotiation analyzer. Your task is to determine if a negotiation has reached a valid agreement.

Key Requirements:
1. Analyze the ENTIRE conversation, not just the last few messages
2. Look for explicit agreement on a specific value from BOTH parties
3. Verify that the agreed value is consistent throughout the conversation
4. Check for confirmation messages from both parties
5. Ensure the negotiation follows a natural flow and reaches a legitimate conclusion
6. Consider the negotiation context and expected value ranges

To determine if there is a valid agreement:
- Both parties must explicitly agree on the same value
- The agreement must be confirmed by both parties
- The conversation must end naturally with {negotiation_termination_message}
- The agreement must be consistent with the negotiation context
- There must be no contradictions or retractions of the agreement

Your response format:
{summary_prefix}- If there is a valid agreement: '{summary_termination_message} [agreed_value]'
- If there is no valid agreement: '{summary_termination_message} -1'

Be thorough in your analysis and only report an agreement if ALL conditions are met.""",
    )
