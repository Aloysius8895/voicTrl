"""The voice assistant's tools. Agora's cloud calls them over MCP (streamable
HTTP at /mcp) while the assistant is thinking, so every tool must answer fast:
anything slow starts a task and returns at once.

Served the way Agora's recipe-agent-mcp sample serves its tools: the official
`mcp` SDK's FastMCP with default settings, mounted in the coordinator's process.
"""

from __future__ import annotations

import hmac
from urllib.parse import urlparse

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from pagent.coordinator.devices import DeviceRegistry, Hub


def build_tools(devices: DeviceRegistry, hub: Hub, public_url: str | None) -> FastMCP:
    public = urlparse(public_url or "")
    public_host = [public.netloc] if public.netloc else []
    public_origin = [f"{public.scheme}://{public.netloc}"] if public.scheme and public.netloc else []
    mcp = FastMCP(
        "pagent",
        instructions="Tools for the user's own devices.",
        # The SDK refuses requests whose Host it does not expect (DNS-rebinding
        # protection), so the coordinator's public host has to be listed.
        transport_security=TransportSecuritySettings(
            allowed_hosts=["127.0.0.1:*", "localhost:*", "[::1]:*", *public_host],
            allowed_origins=["http://127.0.0.1:*", "http://localhost:*", "http://[::1]:*", *public_origin],
        ),
    )

    # Tool names are camelCase: Agora puts all tools in one namespace that only
    # allows letters and digits.
    @mcp.tool(name="listDevices")
    def list_devices() -> str:
        """List the user's devices by name, what kind each is, and whether it is
        online right now. A device that is offline may be asleep."""
        return "\n".join(
            f"{d.id} ({d.kind}): {'online' if hub.is_online(d.id) else 'offline'}" for d in devices.all()
        )

    return mcp


class RequireToken:
    """Lets a request through to the tools only with `Authorization: Bearer <token>`."""

    def __init__(self, app: ASGIApp, token: str) -> None:
        self._app, self._expected = app, f"Bearer {token}".encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            given = dict(scope["headers"]).get(b"authorization", b"")
            if not hmac.compare_digest(given, self._expected):
                await JSONResponse({"detail": "tool token required"}, status_code=401)(scope, receive, send)
                return
        await self._app(scope, receive, send)
