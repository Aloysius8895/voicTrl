"""The coordinator's HTTP and WebSocket surface."""

from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from pagent import protocol as p
from pagent.coordinator.agora import AgoraClient, ToolServer
from pagent.coordinator.tools import RequireToken, build_tools
from pagent.coordinator.devices import SPEAKS_FOR_USER, Device, DeviceRegistry, Hub
from pagent.coordinator.relay import AnswerRelay, UtteranceRelay
from pagent.coordinator.stock_watch import stock_watch_router
from pagent.coordinator.voice import VoiceSessions
from pagent.coordinator.voice_routes import voice_router

log = logging.getLogger(__name__)


HELLO_TIMEOUT_S = 5.0
CLOSE_NO_HELLO = 4401  # private close code: the connection never proved who it is


class VoiceSessionIn(BaseModel):
    agent_id: str


def create_app(
    *,
    agora: AgoraClient,
    devices: DeviceRegistry,
    sessions: VoiceSessions | None = None,
    admin_token: str | None = None,
    hello_timeout: float = HELLO_TIMEOUT_S,
    mcp_token: str | None = None,
    public_url: str | None = None,
) -> FastAPI:
    """`mcp_token` turns on the assistant's tool endpoint (/mcp). `public_url` is
    the address Agora's cloud can reach this coordinator at; agents are only told
    about the tools when both are set."""
    sessions = sessions or VoiceSessions()
    hub = Hub()
    relay = UtteranceRelay(agora, sessions)
    answers = AnswerRelay()
    tools = build_tools(devices, hub, public_url) if mcp_token else None
    tool_server = (ToolServer(endpoint=f"{public_url.rstrip('/')}/mcp", token=mcp_token)
                   if mcp_token and public_url else None)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if tools is None:
            yield
            return
        async with tools.session_manager.run():  # a mounted app's own lifespan is not run
            yield

    app = FastAPI(title="pagent coordinator", lifespan=lifespan)

    async def assistant_said(transcript: p.AgentTranscript) -> None:
        shown = answers.handle(transcript)
        if shown is not None:
            await hub.send_to_kind("watch", shown)

    app.state.assistant_said = assistant_said
    app.include_router(stock_watch_router(devices, relay))
    app.include_router(voice_router(agora, devices, sessions, tool_server))

    def require_admin(authorization: str = Header(default="")) -> None:
        scheme, _, token = authorization.partition(" ")
        ok = admin_token and scheme.lower() == "bearer" and hmac.compare_digest(token.encode(), admin_token.encode())
        if not ok:
            raise HTTPException(status_code=401, detail="admin token required")

    # Until the coordinator starts the Agora agent itself, the operator tells it
    # which running agent is the current voice session.
    @app.put("/api/voice/session", dependencies=[Depends(require_admin)])
    async def set_voice_session(body: VoiceSessionIn) -> dict:
        sessions.start(body.agent_id)
        return {"agent_id": sessions.agent_id}

    @app.delete("/api/voice/session", dependencies=[Depends(require_admin)])
    async def end_voice_session() -> dict:
        sessions.stop()
        return {"agent_id": None}

    @app.get("/healthz")
    async def healthz() -> dict:
        return {"ok": True, "voice_session": sessions.agent_id is not None}

    async def await_hello(ws: WebSocket) -> Device | None:
        """The device behind this connection, if its first frame arrives in time
        and is a hello with a known token."""
        try:
            msg = p.parse_frame(await asyncio.wait_for(ws.receive_text(), hello_timeout))
        except (asyncio.TimeoutError, p.ProtocolError):
            return None
        return devices.authenticate(msg.body.token) if msg.type == p.HELLO else None

    @app.websocket("/ws/device")
    async def device_ws(ws: WebSocket) -> None:
        # Anyone may open the socket, but nothing is read from it except one
        # hello, and it is closed unless that hello holds a device token.
        await ws.accept()
        try:
            device = await await_hello(ws)
        except WebSocketDisconnect:
            return
        if device is None:
            log.warning("closed a connection from %s: no valid hello", ws.client.host if ws.client else "?")
            await ws.close(code=CLOSE_NO_HELLO)
            return
        await ws.send_text(p.build_frame(p.HelloAck(device_id=device.id, kind=device.kind)))
        hub.attach(device, ws)
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = p.parse_frame(raw)
                except p.ProtocolError as e:
                    log.warning("bad frame from %s: %s", device.id, e)
                    continue
                if msg.type == p.UTTERANCE:
                    if device.kind not in SPEAKS_FOR_USER:
                        log.warning("ignored utterance from %s (%s)", device.id, device.kind)
                        continue
                    shown = await relay.handle(device.id, msg.body)
                    if shown is not None:
                        await ws.send_text(p.build_frame(shown))
                elif msg.type == p.AGENT_TRANSCRIPT:
                    if device.kind != "phone":  # only the voice page hears the assistant
                        log.warning("ignored agent_transcript from %s (%s)", device.id, device.kind)
                        continue
                    await assistant_said(msg.body)
        except WebSocketDisconnect:
            pass
        finally:
            hub.detach(device, ws)

    if tools is not None:
        # The SDK's app serves /mcp itself; mounted at the root, and last, so that
        # the coordinator's own routes are matched first.
        app.mount("/", RequireToken(tools.streamable_http_app(), mcp_token))

    return app
