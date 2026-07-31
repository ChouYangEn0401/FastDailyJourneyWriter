"""Thin wrapper around the Anthropic SDK.

Centralises the three things every call here needs: streaming (these are long
generations — a full HTML page can run tens of thousands of tokens), adaptive
thinking, and refusal handling. Claude Opus 5 can decline a request with a
successful HTTP 200 and ``stop_reason == "refusal"``, so ``stop_reason`` is
checked before any content is read.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings

log = logging.getLogger(__name__)

#: Opting into server-side fallbacks means a policy decline is re-served by
#: Anthropic's recommended fallback model inside the same call, instead of
#: coming back to us as an unusable empty response.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AIUnavailable(RuntimeError):
    """No API key configured, or the SDK is not installed."""


class AIRefused(RuntimeError):
    """The model declined the request."""


def is_available() -> bool:
    if not settings.ai_enabled:
        return False
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return True


def _client():
    if not settings.ai_enabled:
        raise AIUnavailable(
            "尚未設定 ANTHROPIC_API_KEY，AI 功能停用（其他功能不受影響）。"
        )
    try:
        import anthropic
    except ImportError as exc:  # pragma: no cover
        raise AIUnavailable("anthropic 套件未安裝：pip install anthropic") from exc
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _collect_text(message: Any) -> str:
    return "".join(
        block.text for block in message.content if getattr(block, "type", "") == "text"
    ).strip()


def complete(
    *,
    system: str,
    user: str,
    max_tokens: int = 32000,
    effort: str = "high",
    schema: dict[str, Any] | None = None,
) -> str:
    """Run one streamed request and return the text response.

    ``schema`` turns on structured outputs, in which case the returned string
    is guaranteed-parseable JSON matching the schema.
    """
    client = _client()

    output_config: dict[str, Any] = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}

    params: dict[str, Any] = {
        "model": settings.model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "thinking": {"type": "adaptive"},
        "output_config": output_config,
    }

    message = _stream(client, params, with_fallbacks=True)

    if getattr(message, "stop_reason", None) == "refusal":
        details = getattr(message, "stop_details", None)
        category = getattr(details, "category", None) if details else None
        raise AIRefused(f"模型拒絕了這個請求（{category or 'unspecified'}）。")

    text = _collect_text(message)
    if not text:
        raise AIRefused("模型沒有回傳內容。")
    return text


def _stream(client, params: dict[str, Any], *, with_fallbacks: bool):
    """Stream a request, retrying without the fallback beta if it isn't supported."""
    if with_fallbacks:
        try:
            with client.beta.messages.stream(
                **params, betas=[FALLBACK_BETA], fallbacks="default"
            ) as stream:
                return stream.get_final_message()
        except TypeError:
            log.info("SDK does not support server-side fallbacks; retrying without.")
        except Exception as exc:  # noqa: BLE001
            if "fallback" not in str(exc).lower():
                raise
            log.info("Server-side fallbacks rejected (%s); retrying without.", exc)

    with client.beta.messages.stream(**params) as stream:
        return stream.get_final_message()


def complete_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int = 8000,
    effort: str = "medium",
) -> dict[str, Any]:
    raw = complete(
        system=system,
        user=user,
        schema=schema,
        max_tokens=max_tokens,
        effort=effort,
    )
    return json.loads(raw)
