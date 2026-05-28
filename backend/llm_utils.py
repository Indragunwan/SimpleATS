"""Utilities for configuring LLM clients from environment or .env file.

Provides helper to load Sumopod-related settings from environment variables
and return a config dict suitable to pass to `call_llm` (it includes the
`llm_client` callable from `llm_clients.sumopod_llm_client`).
"""
import os
from typing import Dict

from .llm_clients import sumopod_llm_client


def get_sumopod_config_from_env() -> Dict:
    """Return a config dict for Sumopod LLM client using environment vars.

    Environment variables used:
    - SUMOPOD_API_KEY (required)
    - SUMOPOD_BASE_URL (optional, default: https://ai.sumopod.com)
    - SUMOPOD_ENDPOINT (optional, default: /v1/chat)
    - SUMOPOD_API_KEY_HEADER (optional, default: Authorization)
    - SUMOPOD_API_KEY_PREFIX (optional, default: Bearer )
    """
    api_key = os.environ.get("SUMOPOD_API_KEY")
    if not api_key:
        raise RuntimeError("SUMOPOD_API_KEY not set in environment")

    return {
        "llm_client": sumopod_llm_client,
        "api_key": api_key,
        "base_url": os.environ.get("SUMOPOD_BASE_URL", "https://ai.sumopod.com"),
        "endpoint": os.environ.get("SUMOPOD_ENDPOINT", "/v1/chat"),
        "api_key_header": os.environ.get("SUMOPOD_API_KEY_HEADER", "Authorization"),
        "api_key_value_prefix": os.environ.get("SUMOPOD_API_KEY_PREFIX", "Bearer "),
    }

