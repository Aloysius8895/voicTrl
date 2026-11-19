"""The coordinator's view of Agora Conversational AI: one method per REST
operation it uses, so tests and local runs can swap in FakeAgora."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Awaitable, Callable, Protocol

import httpx

log = logging.getLogger(__name__)


class AgoraError(Exception):
    """Agora refused or failed a call. `agent_gone` means the agent is no longer
    running, so the voice session it belonged to is over."""

    def __init__(self, message: str, *, status: int | None = None, agent_gone: bool = False) -> None:
        super().__init__(message)
        self.status = status
        self.agent_gone = agent_gone


@dataclass(frozen=True)
class ToolServer:
    """Where Agora's cloud reaches the coordinator's tools (MCP), and the token it must send."""

    endpoint: str
    token: str


class AgoraClient(Protocol):
    app_id: str

    async def think(self, agent_id: str, text: str) -> None:
        """Inject `text` into the agent's conversation as if the user said it."""

    def user_token(self, channel: str, uid: int) -> str:
        """A token that lets the voice page join `channel` as `uid` (audio and messages)."""

    async def start_agent(self, channel: str, agent_uid: int, user_uid: int,
                          tools: ToolServer | None = None) -> str:
        """Start the voice assistant in `channel`, listening to `user_uid`, able to
        call the tools at `tools` if given. Returns its agent id."""

    async def stop_agent(self, agent_id: str) -> None:
        """Stop a running agent."""


class FakeAgora:
    """Stands in for Agora in tests and local runs: records every injected
    text, and fails the next call when `fail_next` is set. With `echo`, it logs
    each call and, if `on_answer` is set, makes up the assistant's answer."""

    app_id = "fake-app-id"

    def __init__(self, *, echo: bool = False) -> None:
        self.thoughts: list[tuple[str, str]] = []
        self.started: list[tuple[str, int, int]] = []
        self.started_with_tools: list[ToolServer | None] = []
        self.stopped: list[str] = []
        self.fail_next: AgoraError | None = None
        self.on_answer: Callable[[str], Awaitable[None]] | None = None
        self._echo = echo

    def _maybe_fail(self) -> None:
        if self.fail_next is not None:
            err, self.fail_next = self.fail_next, None
            raise err

    def user_token(self, channel: str, uid: int) -> str:
        return f"fake-token:{channel}:{uid}"

    async def start_agent(self, channel: str, agent_uid: int, user_uid: int,
                          tools: ToolServer | None = None) -> str:
        self._maybe_fail()
        self.started.append((channel, agent_uid, user_uid))
        self.started_with_tools.append(tools)
        return f"fake-agent-{len(self.started)}"

    async def stop_agent(self, agent_id: str) -> None:
        self._maybe_fail()
        self.stopped.append(agent_id)

    async def think(self, agent_id: str, text: str) -> None:
        self._maybe_fail()
        self.thoughts.append((agent_id, text))
        if self._echo:
            log.info("[fake agora] POST /agents/%s/think text=%r", agent_id, text)
            if self.on_answer is not None:
                await self.on_answer(f"(fake answer) I heard: {text}")


# The voice assistant itself. Speech-to-text, the LLM and text-to-speech are the
# ones Agora manages (no vendor keys of our own), as in Agora's recipe-agent-mcp.
GREETING = "Hi, I am listening. What should your devices do?"
INSTRUCTIONS = (
    "You are the voice assistant of a personal agent that controls the user's own "
    "computers. Answer in one or two short spoken sentences. Use your tools to find "
    "out about the user's devices instead of guessing. If you cannot do something "
    "yet, say so plainly."
)
# The agent leaves on its own this long after the voice page has left the channel.
IDLE_TIMEOUT_S = 300


class HttpAgora:
    """The real Agora. /think goes over HTTPS with basicAuth (Customer ID and
    Secret); tokens and starting or stopping an agent go through Agora's Python
    SDK, which signs with the App Certificate.
    /think contract: docs/research/05-agora-think-and-transcript.md, section A."""

    BASE = "https://api.agora.io/api/conversational-ai-agent/v2"

    def __init__(
        self,
        *,
        app_id: str,
        customer_id: str,
        customer_secret: str,
        app_certificate: str = "",
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.app_id = app_id
        self._app_certificate = app_certificate
        self._sdk_client = None
        self._auth = httpx.BasicAuth(customer_id, customer_secret)
        self._timeout = timeout
        self._transport = transport

    @classmethod
    def from_env(cls) -> HttpAgora:
        names = ("AGORA_APP_ID", "AGORA_CUSTOMER_ID", "AGORA_CUSTOMER_SECRET", "AGORA_APP_CERTIFICATE")
        missing = [n for n in names if not os.environ.get(n)]
        if missing:
            raise RuntimeError("missing environment variables: " + ", ".join(missing))
        app_id, customer_id, customer_secret, app_certificate = (os.environ[n] for n in names)
        return cls(app_id=app_id, customer_id=customer_id, customer_secret=customer_secret,
                   app_certificate=app_certificate)

    def _sdk(self):
        if self._sdk_client is None:
            from agora_agent import Area, AsyncAgora
            self._sdk_client = AsyncAgora(area=Area.US, app_id=self.app_id,
                                          app_certificate=self._app_certificate)
        return self._sdk_client

    def user_token(self, channel: str, uid: int) -> str:
        from agora_agent.agentkit.token import generate_convo_ai_token
        return generate_convo_ai_token(app_id=self.app_id, app_certificate=self._app_certificate,
                                       channel_name=channel, uid=uid, token_expire=3600)

    async def start_agent(self, channel: str, agent_uid: int, user_uid: int,
                          tools: ToolServer | None = None) -> str:
        from agora_agent.agentkit import Agent, McpServerConfig
        from agora_agent.agentkit.vendors import DeepgramSTT, MiniMaxTTS, OpenAI

        llm_options: dict = {}
        if tools is not None:
            # Agora's cloud calls our MCP endpoint itself; transport defaults to streamable_http.
            llm_options["mcp_servers"] = [McpServerConfig(
                name="pagent", endpoint=tools.endpoint,
                headers={"Authorization": f"Bearer {tools.token}"})]

        agent = Agent(
            client=self._sdk(),
            greeting=GREETING,
            failure_message="Please wait a moment.",
            max_history=50,
            # RTM carries the transcripts the voice page shows and forwards.
            advanced_features={"enable_rtm": True},
            parameters={"audio_scenario": "chorus", "data_channel": "rtm",
                        "enable_error_message": True, "enable_metrics": True},
            turn_detection={"config": {
                "speech_threshold": 0.5,
                "start_of_speech": {"mode": "vad", "vad_config": {
                    "interrupt_duration_ms": 160, "prefix_padding_ms": 300}},
                "end_of_speech": {"mode": "vad", "vad_config": {"silence_duration_ms": 480}},
            }},
        )
        agent = (
            agent.with_stt(DeepgramSTT(model="nova-3", language="en"))
            .with_llm(OpenAI(model="gpt-4o-mini", greeting_message=GREETING,
                             system_messages=[{"role": "system", "content": INSTRUCTIONS}],
                             **llm_options))
            .with_tts(MiniMaxTTS(model="speech_2_6_turbo", voice_id="English_captivating_female1"))
        )
        if tools is not None:
            # Without this switch the model never sees the tools, and nothing reports an error.
            agent = agent.with_tools()
        session = agent.create_async_session(
            channel=channel, agent_uid=str(agent_uid), remote_uids=[str(user_uid)],
            enable_string_uid=False, idle_timeout=IDLE_TIMEOUT_S, expires_in=3600,
        )
        try:
            return await session.start()
        except Exception as e:
            raise _sdk_error("start", e) from e

    async def stop_agent(self, agent_id: str) -> None:
        try:
            await self._sdk().stop_agent(agent_id)
        except Exception as e:
            raise _sdk_error("stop", e) from e

    async def think(self, agent_id: str, text: str) -> None:
        # `on_speaking_action` defaults to `ignore`, which would silently drop
        # what the user said while the assistant is talking; `append` queues it
        # as the next turn instead.
        body = {"text": text, "on_speaking_action": "append"}
        url = f"{self.BASE}/projects/{self.app_id}/agents/{agent_id}/think"
        try:
            async with httpx.AsyncClient(auth=self._auth, timeout=self._timeout,
                                         transport=self._transport) as http:
                resp = await http.post(url, json=body)
        except httpx.HTTPError as e:
            raise AgoraError(f"could not reach Agora: {e!r}") from e
        if resp.is_success:
            return
        try:
            err = resp.json()
        except ValueError:
            err = {}
        reason, detail = err.get("reason", ""), err.get("detail", "")
        raise AgoraError(
            f"think failed: HTTP {resp.status_code} {reason} {detail}".strip(),
            status=resp.status_code,
            # 404 / TaskNotFound: "Agent not found or has exited".
            agent_gone=resp.status_code == 404 or reason == "TaskNotFound",
        )


def _sdk_error(action: str, e: Exception) -> AgoraError:
    """An SDK failure as an AgoraError. The SDK's ApiError carries the HTTP
    status and Agora's JSON body; anything else is a network or local failure."""
    status = getattr(e, "status_code", None)
    body = getattr(e, "body", None)
    reason = body.get("reason", "") if isinstance(body, dict) else ""
    detail = body.get("detail", "") if isinstance(body, dict) else ""
    if status is None:
        return AgoraError(f"{action} failed: {e!r}")
    return AgoraError(f"{action} failed: HTTP {status} {reason} {detail}".strip(), status=status,
                      agent_gone=status == 404 or reason == "TaskNotFound")
