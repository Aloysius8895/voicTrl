"""Which devices may connect, and the live connections of those that have."""

from __future__ import annotations

import hmac
import json
import logging
from dataclasses import dataclass
from typing import Iterable

from pydantic import BaseModel
from starlette.websockets import WebSocket

from pagent.protocol import build_frame

log = logging.getLogger(__name__)

SPEAKS_FOR_USER = {"watch", "phone"}  # device kinds whose utterances count as the user's


@dataclass(frozen=True)
class Device:
    id: str
    kind: str  # "watch" | "phone" | "laptop" | "waker"
    token: str


class DeviceRegistry:
    def __init__(self, devices: Iterable[Device]) -> None:
        self._devices = list(devices)

    @classmethod
    def from_json(cls, raw: str) -> DeviceRegistry:
        """`{"watch-1": {"kind": "watch", "token": "..."}, ...}`"""
        return cls(Device(id=id_, kind=d["kind"], token=d["token"]) for id_, d in json.loads(raw).items())

    def all(self) -> list[Device]:
        return list(self._devices)

    def authenticate(self, token: str) -> Device | None:
        found = None
        for d in self._devices:  # no early exit: compare against every token
            if hmac.compare_digest(d.token.encode(), token.encode()):
                found = d
        return found


class Hub:
    """The open connection of each device, for pushing frames to it."""

    def __init__(self) -> None:
        self._conns: dict[str, tuple[Device, WebSocket]] = {}

    def attach(self, device: Device, ws: WebSocket) -> None:
        self._conns[device.id] = (device, ws)

    def detach(self, device: Device, ws: WebSocket) -> None:
        if self._conns.get(device.id, (None, None))[1] is ws:
            del self._conns[device.id]

    def is_online(self, device_id: str) -> bool:
        return device_id in self._conns

    async def send_to_kind(self, kind: str, body: BaseModel) -> int:
        """Push to every connected device of this kind; returns how many got it."""
        sent = 0
        for device, ws in list(self._conns.values()):
            if device.kind != kind:
                continue
            try:
                await ws.send_text(build_frame(body))
                sent += 1
            except Exception:  # a dead socket must not stop the others
                log.warning("could not push to %s", device.id, exc_info=True)
        return sent
