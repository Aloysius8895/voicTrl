"""出厂固件的手表（W1）：手表把总控当成它的 LLM，总控从聊天请求里取出话语。

Seam: 总控的 POST /v1/chat/completions（真的 FastAPI 应用，Agora 换成假的）。
请求和响应的形状来自 docs/research/06-watch-voice-input-routes.md 第 2.3 节。
"""

import pytest
from starlette.testclient import TestClient

from pagent.coordinator.agora import FakeAgora
from pagent.coordinator.app import create_app
from pagent.coordinator.devices import Device, DeviceRegistry
from pagent.coordinator.voice import VoiceSessions

DEVICES = DeviceRegistry([
    Device(id="watch-1", kind="watch", token="watch-token"),
    Device(id="laptop-a", kind="laptop", token="laptop-token"),
])
WATCH = {"Authorization": "Bearer watch-token"}
SYSTEM = {"role": "system", "content": "You are the assistant on an ESP32 device. ..."}


@pytest.fixture
def world():
    agora, sessions = FakeAgora(), VoiceSessions()
    sessions.start("agent-123")
    app = create_app(agora=agora, devices=DEVICES, sessions=sessions)
    with TestClient(app) as client:
        yield client, agora, sessions


def chat(client, *messages, headers=WATCH, **extra):
    body = {"model": "device-chat", "max_tokens": 1024, "messages": list(messages), **extra}
    return client.post("/v1/chat/completions", json=body, headers=headers)


def said(response) -> str:
    (choice,) = response.json()["choices"]
    assert choice["message"]["role"] == "assistant"
    return choice["message"]["content"]


def test_the_last_user_message_is_taken_as_the_utterance_and_the_reply_is_shown_on_the_watch(world):
    client, agora, _ = world

    response = chat(
        client, SYSTEM,
        {"role": "user", "content": "what time is it"},
        {"role": "assistant", "content": "You said: what time is it"},
        {"role": "user", "content": "wake laptop A"},
        tools=[{"type": "function", "function": {"name": "activate_skill", "parameters": {}}}],
    )

    assert response.status_code == 200
    assert agora.thoughts == [("agent-123", "wake laptop A")]
    assert said(response) == "You said: wake laptop A"


def test_the_ai_create_instruction_the_firmware_puts_before_the_first_utterance_is_removed(world):
    client, agora, _ = world

    chat(client, SYSTEM, {"role": "user", "content": (
        'Trusted AI Create mode instruction: Before responding, call activate_skill with skill_id '
        '"ai_create_quick" and follow the activated Skill.\n\nUser request:\nwake laptop A')})

    assert agora.thoughts == [("agent-123", "wake laptop A")]


def test_the_firmwares_memory_extraction_request_gets_an_empty_result_and_is_not_an_utterance(world):
    client, agora, _ = world

    response = chat(
        client,
        {"role": "system", "content": "You extract long-term memory candidates from the user's "
                                      "latest message for an ESP32 agent.\n- intent=replace when ..."},
        {"role": "user", "content": "wake laptop A"},
    )

    assert said(response) == '{"memories":[]}'
    assert agora.thoughts == []


def test_an_utterance_that_is_not_forwarded_still_gets_words_for_the_watch(world):
    client, agora, sessions = world

    too_short = chat(client, SYSTEM, {"role": "user", "content": "uh"})
    sessions.stop()
    no_session = chat(client, SYSTEM, {"role": "user", "content": "wake laptop A"})

    assert said(too_short) == "Didn't catch that. Please say it again."
    assert said(no_session) == "Open the voice page on your phone"
    assert agora.thoughts == []


@pytest.mark.parametrize("headers, status", [
    ({}, 401),
    ({"Authorization": "Bearer wrong-token"}, 401),
    ({"Authorization": "Bearer laptop-token"}, 403),
])
def test_only_a_device_that_may_speak_for_the_user_can_use_the_endpoint(world, headers, status):
    client, agora, _ = world

    response = chat(client, SYSTEM, {"role": "user", "content": "wake laptop A"}, headers=headers)

    assert response.status_code == status
    assert agora.thoughts == []


def test_a_request_without_a_user_message_is_rejected(world):
    client, agora, _ = world

    response = chat(client, SYSTEM)

    assert response.status_code == 400
    assert agora.thoughts == []
