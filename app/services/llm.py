import json
from collections.abc import AsyncIterator

import httpx

from app.core.config import settings


class LLMError(Exception):
    pass


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }


def _url() -> str:
    return settings.llm_base_url.rstrip("/") + "/chat/completions"


async def stream_chat(messages: list[dict], tools: list[dict]) -> AsyncIterator[dict]:
    """Stream an OpenAI-compatible Chat Completions response.

    The yielded events are normalized enough for the agent runtime while
    preserving the full assistant tool-call message at the end.
    """
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "tools": tools,
        "tool_choice": "auto",
        # The harness deliberately executes only one tool at a time.
        "parallel_tool_calls": False,
        "stream": True,
    }

    content_parts: list[str] = []
    tool_calls: dict[int, dict] = {}

    timeout = httpx.Timeout(120.0, connect=20.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            async with client.stream("POST", _url(), headers=_headers(), json=payload) as response:
                if response.status_code >= 400:
                    body = await response.aread()
                    raise LLMError(f"LLM API returned {response.status_code}: {body.decode(errors='replace')}")

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue

                    choices = chunk.get("choices") or []
                    if not choices:
                        continue

                    delta = choices[0].get("delta") or {}
                    text = delta.get("content")
                    if text:
                        content_parts.append(text)
                        yield {"type": "content_delta", "content": text}

                    for tc in delta.get("tool_calls") or []:
                        index = tc.get("index", 0)
                        current = tool_calls.setdefault(
                            index,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if tc.get("id"):
                            current["id"] = tc["id"]
                        if tc.get("type"):
                            current["type"] = tc["type"]
                        function = tc.get("function") or {}
                        if function.get("name"):
                            current["function"]["name"] += function["name"]
                        if function.get("arguments"):
                            current["function"]["arguments"] += function["arguments"]
                        yield {"type": "tool_call_delta", "index": index}

                    finish_reason = choices[0].get("finish_reason")
                    if finish_reason:
                        yield {"type": "finish", "reason": finish_reason}
        except httpx.HTTPError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc

    ordered_calls = [tool_calls[i] for i in sorted(tool_calls)]
    yield {
        "type": "message_complete",
        "message": {
            "role": "assistant",
            "content": "".join(content_parts) or None,
            "tool_calls": ordered_calls or None,
        },
    }
