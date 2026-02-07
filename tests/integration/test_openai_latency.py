"""
Integration latency test for direct OpenAI API calls.

This is intentionally opt-in to avoid accidental cost in CI/local runs.
Enable with:
    RUN_OPENAI_LATENCY_TEST=1 OPENAI_API_KEY=... pytest tests/integration/test_openai_latency.py -v
"""

import os
import time

import pytest
from openai import OpenAI


def _env(name, default=""):
    return os.getenv(name, default).strip()


def _get_api_key():
    return _env("OPENAI_API_KEY") or _env("E2E_OPENAI_API_KEY")


@pytest.mark.integration
@pytest.mark.requires_secrets
@pytest.mark.slow
def test_openai_first_token_latency_streaming():
    """
    Measure API latency directly:
    - time_to_first_token_seconds: when first content token arrives
    - total_seconds: stream completion time
    """
    if _env("RUN_OPENAI_LATENCY_TEST") != "1":
        pytest.skip("Set RUN_OPENAI_LATENCY_TEST=1 to run real OpenAI latency checks.")

    api_key = _get_api_key()
    if not api_key:
        pytest.skip("OPENAI_API_KEY (or E2E_OPENAI_API_KEY) is required for latency test.")

    model = _env("OPENAI_LATENCY_MODEL", "gpt-5-nano")
    client = OpenAI(api_key=api_key)

    prompt = "Reply with exactly: OK"

    start = time.perf_counter()
    first_token_seconds = None
    final_output_text = ""
    incomplete_reason = None

    request_kwargs = {
        "model": model,
        "input": prompt,
        "max_output_tokens": int(_env("OPENAI_LATENCY_MAX_OUTPUT_TOKENS", "256")),
        "stream": True,
    }
    if model.startswith("gpt-5"):
        # Reduce token burn on reasoning so we can reliably observe text deltas.
        request_kwargs["reasoning"] = {"effort": "minimal"}

    stream = client.responses.create(**request_kwargs)

    total_text_parts = []
    for event in stream:
        event_type = getattr(event, "type", "") or ""
        delta = getattr(event, "delta", None)

        # Primary path: text deltas from Responses streaming API.
        if event_type == "response.output_text.delta" and delta:
            total_text_parts.append(delta)
            if first_token_seconds is None:
                first_token_seconds = time.perf_counter() - start
            continue

        # Fallback: final text event may contain completed output text.
        if event_type == "response.output_text.done" and delta:
            total_text_parts.append(delta)
            if first_token_seconds is None:
                first_token_seconds = time.perf_counter() - start

        if event_type in {"response.completed", "response.incomplete"}:
            response_obj = getattr(event, "response", None)
            if response_obj is not None:
                final_output_text = getattr(response_obj, "output_text", "") or final_output_text
                details = getattr(response_obj, "incomplete_details", None)
                if details is not None:
                    incomplete_reason = getattr(details, "reason", None) or str(details)

    total_seconds = time.perf_counter() - start
    response_text = "".join(total_text_parts).strip()
    if not response_text:
        response_text = str(final_output_text).strip()

    assert first_token_seconds is not None, (
        "No streamed token received from API. "
        f"model={model}, incomplete_reason={incomplete_reason}, response_text={response_text!r}"
    )
    assert total_seconds >= first_token_seconds

    # Keep thresholds loose (environment/network dependent), but catch pathological hangs.
    assert first_token_seconds < 120, f"First token took too long: {first_token_seconds:.2f}s"
    assert total_seconds < 180, f"Total response took too long: {total_seconds:.2f}s"
    assert response_text, "API returned empty streamed content."
