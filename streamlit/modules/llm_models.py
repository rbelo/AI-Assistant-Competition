"""Shared LLM model catalog used across simulation and playground UIs."""

MODEL_OPTIONS = ["gpt-5.2", "gpt-5-mini", "gpt-5-nano"]

MODEL_EXPLANATIONS = {
    "gpt-5.2": "State-of-the-art quality option for best negotiation performance.",
    "gpt-5-mini": "Recommended default for negotiation quality, consistency, and speed.",
    "gpt-5-nano": "Lowest-cost option for quick experimentation and batch tests.",
}
