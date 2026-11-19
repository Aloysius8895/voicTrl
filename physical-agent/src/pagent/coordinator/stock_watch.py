"""The watch on its factory firmware (ESP-Claw) cannot open our WebSocket. It
can be told where its LLM lives, so the coordinator poses as that LLM: each
thing the user says arrives as an OpenAI-style chat request, and the text of
the reply is what the watch shows.

Request and response shapes: docs/research/06-watch-voice-input-routes.md, 2.3.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from pagent.coordinator.devices import SPEAKS_FOR_USER, DeviceRegistry
from pagent.coordinator.relay import UtteranceRelay
from pagent.protocol import Utterance, new_id

# The firmware prefixes the first utterance of an AI Create session with an
# instruction for its own LLM, ending in this marker.
_INSTRUCTION_START = "Trusted AI Create mode instruction:"
_INSTRUCTION_END = "User request:\n"

# After each turn the firmware's memory module asks the LLM to pull facts out of
# what the user said. It is not something the user said to us; this answer
# tells it there is nothing to remember.
_MEMORY_EXTRACTION_START = "You extract long-term memory candidates"
_NO_MEMORIES = '{"memories":[]}'

NOT_FORWARDED = "Didn't catch that. Please say it again."


class ChatMessage(BaseModel):
    role: str
    content: Any = None


class ChatRequest(BaseModel):
    model: str = "pagent"
    messages: list[ChatMessage]


def _text(content: Any) -> str:
    """Message content as plain text; OpenAI also allows a list of parts."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(part.get("text", "") for part in content if isinstance(part, dict))
    return ""


def _utterance_text(text: str) -> str:
    if text.startswith(_INSTRUCTION_START) and _INSTRUCTION_END in text:
        return text.split(_INSTRUCTION_END, 1)[1]
    return text


def stock_watch_router(devices: DeviceRegistry, relay: UtteranceRelay) -> APIRouter:
    router = APIRouter()

    @router.post("/v1/chat/completions")
    async def chat_completions(body: ChatRequest, authorization: str = Header(default="")) -> dict:
        scheme, _, token = authorization.partition(" ")
        device = devices.authenticate(token) if scheme.lower() == "bearer" else None
        if device is None:
            raise HTTPException(status_code=401, detail="device token required")
        if device.kind not in SPEAKS_FOR_USER:
            raise HTTPException(status_code=403, detail="this device may not speak for the user")

        system = next((_text(m.content) for m in body.messages if m.role == "system"), "")
        user = next((_text(m.content) for m in reversed(body.messages) if m.role == "user"), None)
        if user is None:
            raise HTTPException(status_code=400, detail="no user message")

        if system.startswith(_MEMORY_EXTRACTION_START):
            reply = _NO_MEMORIES
        else:
            shown = await relay.handle(device.id, Utterance(text=_utterance_text(user)))
            if shown is None:
                reply = NOT_FORWARDED
            else:
                reply = f"{shown.title}: {shown.body}" if shown.body else shown.title

        return {
            "id": new_id("chatcmpl"),
            "object": "chat.completion",
            "created": int(time.time()),
            "model": body.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": reply},
                "finish_reason": "stop",
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    return router
