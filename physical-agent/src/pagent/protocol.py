"""Wire protocol shared by the coordinator, device agents and firmware.

Every WebSocket frame is one JSON object (an Envelope). A connection proves who
it is once, with the token in its first frame (hello). After that, device
identity always comes from the connection, never from fields in a payload.
"""

from __future__ import annotations

import secrets
import time
import uuid
from typing import Any

from pydantic import BaseModel, Field, ValidationError

SCHEMA_VERSION = "1.0"

# device -> coordinator
HELLO = "hello"
HEARTBEAT = "heartbeat"
COMMAND_ACK = "command_ack"
COMMAND_PROGRESS = "command_progress"
COMMAND_RESULT = "command_result"
UTTERANCE = "utterance"
AGENT_TRANSCRIPT = "agent_transcript"  # voice page (phone) -> coordinator

# coordinator -> device
HELLO_ACK = "hello_ack"
COMMAND_DISPATCH = "command_dispatch"
COMMAND_CANCEL = "command_cancel"
RESULT_ACK = "result_ack"
DISPLAY = "display"


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def new_nonce() -> str:
    return "DEMO-" + secrets.token_hex(2).upper()


class Envelope(BaseModel):
    v: str = SCHEMA_VERSION
    type: str
    id: str = Field(default_factory=lambda: new_id("msg"))
    ts: float = Field(default_factory=time.time)
    payload: dict[str, Any] = Field(default_factory=dict)


class Utterance(BaseModel):
    """One thing the user said, already turned into text by the watch."""

    text: str
    lang: str = "en"
    final: bool = True


class Display(BaseModel):
    """One screen of content for the watch, optionally with a vibration."""

    title: str
    body: str = ""
    vibrate: bool = False


class AgentTranscript(BaseModel):
    """What the voice assistant said in one turn, as the voice page received it.
    `turn_id` is Agora's turn number; `final` is false while the turn is still
    being spoken."""

    text: str
    turn_id: int | None = None
    final: bool = True


class Hello(BaseModel):
    """The first frame on every connection: the device's token. Nothing else is
    accepted until it has been checked."""

    token: str


class HelloAck(BaseModel):
    """The coordinator's answer to a good hello: who this connection now is."""

    device_id: str
    kind: str


PAYLOAD_MODELS: dict[str, type[BaseModel]] = {
    HELLO: Hello,
    HELLO_ACK: HelloAck,
    UTTERANCE: Utterance,
    DISPLAY: Display,
    AGENT_TRANSCRIPT: AgentTranscript,
}
_TYPE_OF = {model: type_ for type_, model in PAYLOAD_MODELS.items()}


def build_frame(body: BaseModel) -> str:
    """Wrap a payload model in an envelope of its registered type."""
    return Envelope(type=_TYPE_OF[type(body)], payload=body.model_dump()).model_dump_json()


class Message(BaseModel):
    """A received frame: the envelope plus its payload parsed into the model
    registered for that type (a plain dict for types without one)."""

    type: str
    id: str
    body: Any


class ProtocolError(ValueError):
    """The frame is not a valid envelope, or its payload does not fit its type."""


def parse_frame(raw: str | bytes) -> Message:
    try:
        env = Envelope.model_validate_json(raw)
        model = PAYLOAD_MODELS.get(env.type)
        body = model.model_validate(env.payload) if model else env.payload
    except ValidationError as e:
        # Say what was wrong, never what was sent: a rejected hello may hold a
        # token, and this text ends up in logs.
        problems = e.errors(include_input=False, include_url=False, include_context=False)
        raise ProtocolError("; ".join(
            f"{'.'.join(str(part) for part in err['loc']) or 'frame'}: {err['msg']}" for err in problems
        )) from None
    return Message(type=env.type, id=env.id, body=body)


class ErrorCode:
    DEVICE_NOT_FOUND = "DEVICE_NOT_FOUND"
    DEVICE_AMBIGUOUS = "DEVICE_AMBIGUOUS"
    DEVICE_UNREACHABLE = "DEVICE_UNREACHABLE"
    WAKE_NOT_SUPPORTED = "WAKE_NOT_SUPPORTED"
    WAKE_TIMED_OUT = "WAKE_TIMED_OUT"
    WAITING_USER_SESSION = "WAITING_USER_SESSION"
    CAPABILITY_NOT_AVAILABLE = "CAPABILITY_NOT_AVAILABLE"
    FILE_NOT_FOUND = "FILE_NOT_FOUND"
    FILE_AMBIGUOUS = "FILE_AMBIGUOUS"
    ARTIFACT_HASH_MISMATCH = "ARTIFACT_HASH_MISMATCH"
    WORKSPACE_PATH_REJECTED = "WORKSPACE_PATH_REJECTED"
    CODING_AUTH_REQUIRED = "CODING_AUTH_REQUIRED"
    CODING_TASK_FAILED = "CODING_TASK_FAILED"
    PREVIEW_NOT_REACHABLE = "PREVIEW_NOT_REACHABLE"
    VERIFICATION_FAILED = "VERIFICATION_FAILED"
    COMMAND_TIMEOUT = "COMMAND_TIMEOUT"
    COMMAND_LOST = "COMMAND_LOST"
    ACTION_CANCELLED = "ACTION_CANCELLED"
    NOTHING_TO_DO = "NOTHING_TO_DO"
    COORDINATOR_RESTARTED = "COORDINATOR_RESTARTED"
    INTERNAL = "INTERNAL"


class TaskStatus:
    QUEUED = "queued"
    WAITING_DEVICE = "waiting_device"
    RUNNING = "running"
    VERIFYING = "verifying"
    WAITING_USER = "waiting_user"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"

    TERMINAL = frozenset({SUCCEEDED, FAILED, CANCELLED})
