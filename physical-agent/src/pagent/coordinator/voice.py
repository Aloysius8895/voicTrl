"""Which Agora agent is the current voice session. The demo has one user, so
there is at most one session at a time."""

from __future__ import annotations


class VoiceSessions:
    def __init__(self) -> None:
        self._agent_id: str | None = None

    @property
    def agent_id(self) -> str | None:
        return self._agent_id

    def start(self, agent_id: str) -> None:
        self._agent_id = agent_id

    def stop(self) -> None:
        self._agent_id = None
