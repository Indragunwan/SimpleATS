"""Example LLM client implementations for use with `call_llm` in ai_service.py.

Provide an async callable `sumopod_llm_client(system_message, user_message, config)`
and pass it to `call_llm(..., config={"llm_client": sumopod_llm_client, ...})`.

Configuration keys:
- `api_key` (required) — API key string.
- `base_url` (optional) — base URL for the Sumopod API (default: https://ai.sumopod.com).
- `api_key_header` (optional) — header name for API key (default: 'Authorization', value prefixed with 'Bearer ').
- `endpoint` (optional) — path relative to base_url to POST (default: /v1/chat)
"""
from typing import Optional
import json
import httpx


async def sumopod_llm_client(system_message: str, user_message: str, config: Optional[dict] = None) -> str:
    """Call a Sumopod-compatible LLM HTTP endpoint and return text response.

    This is a minimal example; adapt payload/headers to your provider's API.
    """
    cfg = config or {}
    api_key = cfg.get("api_key")
    if not api_key:
        raise RuntimeError("sumopod_llm_client requires config['api_key']")

    base_url = cfg.get("base_url", "https://ai.sumopod.com").rstrip("/")
    endpoint = cfg.get("endpoint", "/v1/chat")
    url = f"{base_url}{endpoint}"

    header_name = cfg.get("api_key_header", "Authorization")
    header_value = cfg.get("api_key_value_prefix", "Bearer ") + api_key

    payload = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": user_message},
        ],
        # allow provider-specific options via config
        **(cfg.get("provider_options", {})),
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        headers = {header_name: header_value, "Content-Type": "application/json"}
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    # Attempt to extract text from common response shapes
    # 1) data['choices'][0]['message']['content']
    try:
        return data["choices"][0]["message"]["content"]
    except Exception:
        pass
    # 2) data['text']
    if isinstance(data, dict) and "text" in data:
        return data["text"]
    # else fallback to raw json
    return json.dumps(data, ensure_ascii=False)
