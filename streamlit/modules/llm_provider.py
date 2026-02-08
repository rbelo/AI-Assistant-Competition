"""Provider-agnostic LLM configuration.

Supports OpenAI and any OpenAI-compatible API (OpenRouter, Azure, local LLMs)
by accepting an optional base_url parameter.
"""

from dataclasses import dataclass


@dataclass
class LLMConfig:
    """Configuration for an OpenAI-compatible LLM provider.

    Args:
        model: Model identifier (e.g., "gpt-5-mini", "openai/gpt-4o" for OpenRouter).
        api_key: API key for the provider.
        base_url: Base URL for the API. None uses the OpenAI default.
                  For OpenRouter: "https://openrouter.ai/api/v1"
                  For Azure: "https://<resource>.openai.azure.com/openai/deployments/<deployment>"
        temperature: Sampling temperature. None omits the parameter (use provider default).
        top_p: Nucleus sampling parameter. None omits the parameter.
    """

    model: str
    api_key: str
    base_url: str = None
    temperature: float = None
    top_p: float = None
