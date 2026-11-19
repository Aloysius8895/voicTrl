"""The voice page's backend: join details for a channel, and starting and
stopping the voice assistant in it.

The three routes have the shape of the backend in Agora's recipe-agent-mcp
sample, so that sample's web page (voice-page/) works against the coordinator;
our copy of the page adds the phone's device token to each request.
"""

from __future__ import annotations

import logging
import random
import time

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel

from pagent.coordinator.agora import AgoraClient, AgoraError, ToolServer
from pagent.coordinator.devices import DeviceRegistry
from pagent.coordinator.voice import VoiceSessions

log = logging.getLogger(__name__)


class StartAgentRequest(BaseModel):
    channelName: str
    rtcUid: int   # the agent's uid in the channel
    userUid: int  # the voice page's uid


class StopAgentRequest(BaseModel):
    agentId: str


def voice_router(agora: AgoraClient, devices: DeviceRegistry, sessions: VoiceSessions,
                 tools: ToolServer | None = None) -> APIRouter:
    """`tools` is where a started agent can call the coordinator's tools, if anywhere."""
    def require_phone(authorization: str = Header(default="")) -> None:
        # Starting an agent costs money, so only the phone (the voice page) may.
        scheme, _, token = authorization.partition(" ")
        device = devices.authenticate(token) if scheme.lower() == "bearer" else None
        if device is None:
            raise HTTPException(status_code=401, detail="device token required")
        if device.kind != "phone":
            raise HTTPException(status_code=403, detail="only the phone runs the voice page")

    router = APIRouter(dependencies=[Depends(require_phone)])

    @router.get("/get_config")
    async def get_config(channel: str | None = Query(default=None),
                         uid: int | None = Query(default=None)) -> dict:
        user_uid = uid if uid and uid > 0 else random.randint(1000, 9_999_999)
        channel_name = channel or f"pagent-{int(time.time())}-{random.randint(1000, 9999)}"
        return {"code": 0, "msg": "success", "data": {
            "app_id": agora.app_id,
            "token": agora.user_token(channel_name, user_uid),
            "uid": str(user_uid),
            "channel_name": channel_name,
            "agent_uid": str(random.randint(10_000_000, 99_999_999)),
        }}

    @router.post("/startAgent")
    async def start_agent(body: StartAgentRequest) -> dict:
        running = sessions.agent_id
        if running is not None:
            # One user, one voice session: do not leave the old agent running (and billing).
            try:
                await agora.stop_agent(running)
            except AgoraError as e:
                log.warning("could not stop previous agent %s: %s", running, e)
            sessions.stop()
        try:
            agent_id = await agora.start_agent(body.channelName, body.rtcUid, body.userUid, tools)
        except AgoraError as e:
            log.error("could not start an agent in %s: %s", body.channelName, e)
            raise HTTPException(status_code=502, detail=str(e)) from e
        sessions.start(agent_id)
        log.info("voice session started: agent %s in %s", agent_id, body.channelName)
        return {"code": 0, "msg": "success", "data": {
            "agent_id": agent_id, "channel_name": body.channelName,
            "status": "started", "agent_mode": "pipeline"}}

    @router.post("/stopAgent")
    async def stop_agent(body: StopAgentRequest) -> dict:
        try:
            await agora.stop_agent(body.agentId)
        except AgoraError as e:
            if not e.agent_gone:  # already gone is as good as stopped
                log.error("could not stop agent %s: %s", body.agentId, e)
                raise HTTPException(status_code=502, detail=str(e)) from e
        if sessions.agent_id == body.agentId:
            sessions.stop()
        log.info("voice session ended: agent %s", body.agentId)
        return {"code": 0, "msg": "success"}

    return router
