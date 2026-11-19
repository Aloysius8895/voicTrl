"""语音助手的工具：Agora 云端经 MCP（/mcp，Bearer 令牌）调用总控。

Seam: 总控的 POST /mcp，按 MCP 的 streamable HTTP 说真协议（JSON-RPC），Agora 换成假的。
挂载方式照 Agora 官方样例 recipe-agent-mcp（mcp 1.x 的 FastMCP，默认设置）。
"""

import json

import pytest
from starlette.testclient import TestClient

from pagent import protocol as p
from pagent.coordinator.agora import FakeAgora, ToolServer
from pagent.coordinator.app import create_app
from pagent.coordinator.devices import Device, DeviceRegistry
from pagent.coordinator.voice import VoiceSessions

DEVICES = DeviceRegistry([
    Device(id="watch-1", kind="watch", token="watch-token"),
    Device(id="phone-1", kind="phone", token="phone-token"),
    Device(id="laptop-a", kind="laptop", token="laptop-a-token"),
    Device(id="laptop-b", kind="laptop", token="laptop-b-token"),
])
PUBLIC_URL = "http://testserver"  # the host TestClient sends


@pytest.fixture
def world():
    agora = FakeAgora()
    app = create_app(agora=agora, devices=DEVICES, sessions=VoiceSessions(),
                     mcp_token="mcp-token", public_url=PUBLIC_URL)
    with TestClient(app) as client:
        yield client, agora


class McpCaller:
    """The few steps of MCP's streamable HTTP that a client like Agora performs."""

    def __init__(self, client: TestClient, token: str = "mcp-token") -> None:
        self.client, self.token, self.session, self.next_id = client, token, None, 1

    def post(self, method: str, params: dict | None = None, *, notification: bool = False):
        headers = {"Accept": "application/json, text/event-stream", "Authorization": f"Bearer {self.token}"}
        if self.session:
            headers["mcp-session-id"] = self.session
        body = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            body["id"], self.next_id = self.next_id, self.next_id + 1
        return self.client.post("/mcp", json=body, headers=headers)

    def call(self, method: str, params: dict | None = None) -> dict:
        response = self.post(method, params)
        assert response.status_code == 200, response.text
        if response.headers["content-type"].startswith("text/event-stream"):
            data = next(line[5:] for line in response.text.splitlines() if line.startswith("data:"))
            return json.loads(data)["result"]
        return response.json()["result"]

    def initialize(self) -> "McpCaller":
        response = self.post("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                                            "clientInfo": {"name": "test", "version": "1"}})
        assert response.status_code == 200, response.text
        self.session = response.headers.get("mcp-session-id")
        self.post("notifications/initialized", notification=True)
        return self

    def tool(self, name: str, arguments: dict | None = None) -> str:
        result = self.call("tools/call", {"name": name, "arguments": arguments or {}})
        assert not result.get("isError"), result
        return "\n".join(part["text"] for part in result["content"] if part["type"] == "text")


def online(client: TestClient, token: str):
    ws = client.websocket_connect("/ws/device")
    conn = ws.__enter__()
    conn.send_text(p.build_frame(p.Hello(token=token)))
    conn.receive_text()
    return ws


def test_the_assistant_is_offered_a_tool_that_lists_devices(world):
    client, _ = world

    tools = McpCaller(client).initialize().call("tools/list")["tools"]

    assert [tool["name"] for tool in tools] == ["listDevices"]


def test_list_devices_says_which_of_the_users_devices_are_online_right_now(world):
    client, _ = world
    laptop_a = online(client, "laptop-a-token")
    try:
        answer = McpCaller(client).initialize().tool("listDevices")
    finally:
        laptop_a.__exit__(None, None, None)

    assert "laptop-a (laptop): online" in answer
    assert "laptop-b (laptop): offline" in answer
    assert "watch-1 (watch): offline" in answer


@pytest.mark.parametrize("token", ["", "wrong-token", "phone-token"])
def test_the_tool_endpoint_refuses_callers_without_the_assistants_token(world, token):
    client, _ = world

    response = McpCaller(client, token=token).post("initialize", {
        "protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}})

    assert response.status_code == 401


def test_without_a_tool_token_the_coordinator_has_no_tool_endpoint():
    app = create_app(agora=FakeAgora(), devices=DEVICES, sessions=VoiceSessions())

    with TestClient(app) as client:
        response = McpCaller(client).post("initialize")

    assert response.status_code == 404


def test_an_agent_is_started_with_the_coordinators_public_tool_endpoint_and_token(world):
    client, agora = world

    client.post("/startAgent", headers={"Authorization": "Bearer phone-token"},
                json={"channelName": "ch-1", "rtcUid": 20001, "userUid": 1001})

    assert agora.started_with_tools == [ToolServer(endpoint="http://testserver/mcp", token="mcp-token")]


def test_without_a_public_address_the_agent_is_started_without_tools():
    agora = FakeAgora()
    app = create_app(agora=agora, devices=DEVICES, sessions=VoiceSessions(), mcp_token="mcp-token")

    with TestClient(app) as client:
        client.post("/startAgent", headers={"Authorization": "Bearer phone-token"},
                    json={"channelName": "ch-1", "rtcUid": 20001, "userUid": 1001})

    assert agora.started_with_tools == [None]
