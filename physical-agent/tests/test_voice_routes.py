"""语音页的后端：总控启动和停止 Agora Agent，并记住哪个是当前语音会话。

Seam: 总控的 GET /get_config、POST /startAgent、POST /stopAgent（Agora 换成假的）。
三个接口的形状照 Agora 官方样例 recipe-agent-mcp 的后端，这样它的网页前端可以接上来（我们的副本只多带一个手机令牌）：
docs/research/05-agora-think-and-transcript.md 的 D 节。
"""

import pytest
from starlette.testclient import TestClient

from pagent import protocol as p
from pagent.coordinator.agora import AgoraError, FakeAgora
from pagent.coordinator.app import create_app
from pagent.coordinator.devices import Device, DeviceRegistry
from pagent.coordinator.voice import VoiceSessions

DEVICES = DeviceRegistry([
    Device(id="watch-1", kind="watch", token="watch-token"),
    Device(id="phone-1", kind="phone", token="phone-token"),
])
PHONE = {"Authorization": "Bearer phone-token"}


@pytest.fixture
def world():
    agora, sessions = FakeAgora(), VoiceSessions()
    app = create_app(agora=agora, devices=DEVICES, sessions=sessions)
    with TestClient(app) as client:
        yield client, agora, sessions


def start(client, headers=PHONE, channel="ch-1", agent_uid=20001, user_uid=1001):
    return client.post("/startAgent", headers=headers, json={
        "channelName": channel, "rtcUid": agent_uid, "userUid": user_uid, "agentMode": "pipeline"})


def watch_says(client, text: str) -> p.Display:
    with client.websocket_connect("/ws/device") as ws:
        ws.send_text(p.build_frame(p.Hello(token="watch-token")))
        ws.receive_text()
        ws.send_text(p.build_frame(p.Utterance(text=text)))
        return p.parse_frame(ws.receive_text()).body


def test_get_config_hands_the_voice_page_what_it_needs_to_join_a_channel(world):
    client, _, _ = world

    response = client.get("/get_config", headers=PHONE)

    body = response.json()
    data = body["data"]
    assert (response.status_code, body["code"]) == (200, 0)
    assert data["app_id"] == "fake-app-id"
    assert data["channel_name"].startswith("pagent-")
    assert data["uid"].isdigit() and data["agent_uid"].isdigit() and data["uid"] != data["agent_uid"]
    assert data["token"] == f"fake-token:{data['channel_name']}:{data['uid']}"


def test_starting_an_agent_makes_it_the_voice_session_that_utterances_go_to(world):
    client, agora, _ = world

    response = start(client, channel="ch-1", agent_uid=20001, user_uid=1001)
    watch_says(client, "wake laptop A")

    data = response.json()["data"]
    assert (response.status_code, response.json()["code"]) == (200, 0)
    assert agora.started == [("ch-1", 20001, 1001)]
    assert agora.thoughts == [(data["agent_id"], "wake laptop A")]


def test_stopping_the_agent_ends_the_voice_session(world):
    client, agora, _ = world
    agent_id = start(client).json()["data"]["agent_id"]

    response = client.post("/stopAgent", headers=PHONE, json={"agentId": agent_id})
    shown = watch_says(client, "wake laptop A")

    assert (response.status_code, response.json()["code"]) == (200, 0)
    assert agora.stopped == [agent_id]
    assert shown.title == "Open the voice page on your phone"


def test_starting_again_stops_the_agent_that_was_running_so_none_is_left_behind(world):
    client, agora, sessions = world
    first = start(client, channel="ch-1").json()["data"]["agent_id"]

    second = start(client, channel="ch-2").json()["data"]["agent_id"]

    assert agora.stopped == [first]
    assert sessions.agent_id == second != first


def test_when_agora_refuses_to_start_the_agent_the_page_gets_the_reason_and_no_session_begins(world):
    client, agora, sessions = world
    agora.fail_next = AgoraError("start failed: HTTP 403 InvalidPermission", status=403)

    response = start(client)

    assert response.status_code == 502
    assert "InvalidPermission" in response.json()["detail"]
    assert sessions.agent_id is None


@pytest.mark.parametrize("headers, status", [
    ({}, 401),
    ({"Authorization": "Bearer wrong-token"}, 401),
    ({"Authorization": "Bearer watch-token"}, 403),
])
def test_only_the_phone_may_use_the_voice_routes(world, headers, status):
    client, agora, _ = world

    responses = [client.get("/get_config", headers=headers), start(client, headers=headers),
                 client.post("/stopAgent", headers=headers, json={"agentId": "agent-1"})]

    assert [r.status_code for r in responses] == [status] * 3
    assert agora.started == [] and agora.stopped == []


def test_voice_url_puts_the_phone_token_after_the_hash():
    from pagent.coordinator.voice_url import voice_url

    devices = '{"watch-1": {"kind": "watch", "token": "w"}, "phone-1": {"kind": "phone", "token": "abc-_123"}}'

    assert voice_url(devices, "http://localhost:3000/") == "http://localhost:3000/#token=abc-_123"
