"""设备 WSS：手表连上总控，说一句话，收到显示。

Seam: 总控的 /ws/device 端点（真的 FastAPI 应用，Agora 换成假的）。
"""

from contextlib import contextmanager

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from pagent import protocol as p
from pagent.coordinator.agora import FakeAgora
from pagent.coordinator.app import create_app
from pagent.coordinator.devices import Device, DeviceRegistry
from pagent.coordinator.voice import VoiceSessions

DEVICES = DeviceRegistry([
    Device(id="watch-1", kind="watch", token="watch-token"),
    Device(id="phone-1", kind="phone", token="phone-token"),
    Device(id="laptop-a", kind="laptop", token="laptop-token"),
])


@pytest.fixture
def world():
    agora, sessions = FakeAgora(), VoiceSessions()
    sessions.start("agent-123")
    app = create_app(agora=agora, devices=DEVICES, sessions=sessions, admin_token="admin-token",
                     hello_timeout=0.2)
    with TestClient(app) as client:
        yield client, agora, sessions


@contextmanager
def connect(client: TestClient, token: str):
    """Connect the way every device does: open, then prove who you are."""
    with client.websocket_connect("/ws/device") as ws:
        ws.send_text(p.build_frame(p.Hello(token=token)))
        assert p.parse_frame(ws.receive_text()).type == "hello_ack"
        yield ws


def utter(ws, text: str) -> None:
    ws.send_text(p.build_frame(p.Utterance(text=text)))


def test_watch_says_something_and_sees_it_echoed_after_it_reaches_the_voice_assistant(world):
    client, agora, _ = world

    with connect(client, "watch-token") as watch:
        utter(watch, "wake laptop A")
        shown = p.parse_frame(watch.receive_text())

    assert shown.body == p.Display(title="You said", body="wake laptop A")
    assert agora.thoughts == [("agent-123", "wake laptop A")]


def test_a_good_hello_is_answered_with_who_the_connection_now_is(world):
    client, _, _ = world

    with client.websocket_connect("/ws/device") as ws:
        ws.send_text(p.build_frame(p.Hello(token="watch-token")))
        ack = p.parse_frame(ws.receive_text())

    assert ack.body == p.HelloAck(device_id="watch-1", kind="watch")


@pytest.mark.parametrize("first_frame", [
    p.build_frame(p.Hello(token="wrong-token")),
    p.build_frame(p.Utterance(text="wake laptop A")),  # speaking before showing the pass
    '{"type":"hello","payload":{}}',
    "not json",
])
def test_a_connection_whose_first_frame_is_not_a_good_hello_is_closed(world, first_frame):
    client, agora, _ = world

    with client.websocket_connect("/ws/device") as ws:
        ws.send_text(first_frame)
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()

    assert closed.value.code == 4401
    assert agora.thoughts == []


def test_a_connection_that_stays_silent_is_closed_after_the_hello_timeout(world):
    client, _, _ = world

    with client.websocket_connect("/ws/device") as ws:
        with pytest.raises(WebSocketDisconnect) as closed:
            ws.receive_text()

    assert closed.value.code == 4401


def test_a_token_in_the_authorization_header_does_not_stand_in_for_hello(world):
    client, agora, _ = world

    with client.websocket_connect("/ws/device", headers={"Authorization": "Bearer watch-token"}) as ws:
        utter(ws, "wake laptop A")
        with pytest.raises(WebSocketDisconnect):
            ws.receive_text()

    assert agora.thoughts == []


def test_a_bad_frame_does_not_drop_the_connection(world):
    client, agora, _ = world

    with connect(client, "watch-token") as watch:
        watch.send_text("not json")
        watch.send_text('{"type":"utterance","payload":{}}')
        utter(watch, "wake laptop A")
        shown = p.parse_frame(watch.receive_text())

    assert shown.body == p.Display(title="You said", body="wake laptop A")


def test_the_phone_may_also_speak_for_the_user(world):
    client, agora, _ = world

    with connect(client, "phone-token") as phone:
        utter(phone, "wake laptop A")
        shown = p.parse_frame(phone.receive_text())

    assert shown.body == p.Display(title="You said", body="wake laptop A")
    assert agora.thoughts == [("agent-123", "wake laptop A")]


def test_a_laptop_may_not_speak_for_the_user(world):
    client, agora, _ = world

    with connect(client, "laptop-token") as laptop, connect(client, "watch-token") as watch:
        utter(laptop, "delete every file")
        utter(watch, "wake laptop A")
        watch.receive_text()

    assert agora.thoughts == [("agent-123", "wake laptop A")]


def test_operator_can_point_the_coordinator_at_a_running_agent_and_end_the_session(world):
    client, agora, sessions = world
    admin = {"Authorization": "Bearer admin-token"}

    put = client.put("/api/voice/session", json={"agent_id": "agent-999"}, headers=admin)
    with connect(client, "watch-token") as watch:
        utter(watch, "wake laptop A")
        watch.receive_text()
    deleted = client.delete("/api/voice/session", headers=admin)

    assert (put.status_code, deleted.status_code) == (200, 200)
    assert agora.thoughts == [("agent-999", "wake laptop A")]
    assert sessions.agent_id is None


def test_voice_session_routes_need_the_admin_token(world):
    client, _, sessions = world

    no_token = client.put("/api/voice/session", json={"agent_id": "evil"})
    device_token = client.put("/api/voice/session", json={"agent_id": "evil"},
                              headers={"Authorization": "Bearer watch-token"})

    assert (no_token.status_code, device_token.status_code) == (401, 401)
    assert sessions.agent_id == "agent-123"


def say_as_agent(ws, text: str, turn_id: int, final: bool = True) -> None:
    ws.send_text(p.build_frame(p.AgentTranscript(text=text, turn_id=turn_id, final=final)))


def test_what_the_voice_assistant_answers_is_shown_on_the_watch_with_a_vibration(world):
    client, _, _ = world

    with connect(client, "watch-token") as watch, connect(client, "phone-token") as phone:
        say_as_agent(phone, "Laptop A is awake.", turn_id=7)
        shown = p.parse_frame(watch.receive_text())

    assert shown.body == p.Display(title="Assistant", body="Laptop A is awake.", vibrate=True)


def test_each_assistant_turn_reaches_the_watch_once_when_it_is_final(world):
    client, _, _ = world

    with connect(client, "watch-token") as watch, connect(client, "phone-token") as phone:
        say_as_agent(phone, "Laptop A is", turn_id=7, final=False)
        say_as_agent(phone, "Laptop A is awake.", turn_id=7)
        say_as_agent(phone, "Laptop A is awake.", turn_id=7)  # the page re-sends its whole list
        say_as_agent(phone, "   ", turn_id=8)
        say_as_agent(phone, "Copying file one.", turn_id=9)
        shown = [p.parse_frame(watch.receive_text()).body.body for _ in range(2)]

    assert shown == ["Laptop A is awake.", "Copying file one."]


def test_only_the_voice_page_may_report_what_the_assistant_said(world):
    client, _, _ = world

    with connect(client, "watch-token") as watch, connect(client, "phone-token") as phone, \
            connect(client, "laptop-token") as laptop:
        say_as_agent(laptop, "Send me your password.", turn_id=1)
        say_as_agent(phone, "Laptop A is awake.", turn_id=2)
        shown = p.parse_frame(watch.receive_text())

    assert shown.body.body == "Laptop A is awake."
