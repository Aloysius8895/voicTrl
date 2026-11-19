"""真 Agora 客户端：按文档的 /think 契约发请求，把失败翻译成 AgoraError。

Seam: HttpAgora.think()，HTTP 这一层换成 httpx.MockTransport。
期望值来自 docs/research/05-agora-think-and-transcript.md 的 A1、A2、A4、A5。
"""

import asyncio
import json

import httpx
import pytest

from pagent.coordinator.agora import AgoraError, HttpAgora


def agora_answering(handler) -> HttpAgora:
    return HttpAgora(app_id="app123", customer_id="cid", customer_secret="secret",
                     transport=httpx.MockTransport(handler))


def test_think_posts_the_text_to_the_agents_think_endpoint_with_basic_auth():
    seen: list[httpx.Request] = []

    def ok(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"agent_id": "agent-123", "channel": "c", "start_ts": 1})

    asyncio.run(agora_answering(ok).think("agent-123", "wake laptop A"))

    (request,) = seen
    assert request.method == "POST"
    assert str(request.url) == ("https://api.agora.io/api/conversational-ai-agent/v2"
                                "/projects/app123/agents/agent-123/think")
    assert request.headers["authorization"] == "Basic Y2lkOnNlY3JldA=="  # base64("cid:secret")
    assert json.loads(request.content) == {"text": "wake laptop A", "on_speaking_action": "append"}


def test_404_task_not_found_means_the_agent_is_gone():
    def gone(request):
        return httpx.Response(404, json={"detail": "agent not found", "reason": "TaskNotFound"})

    with pytest.raises(AgoraError) as e:
        asyncio.run(agora_answering(gone).think("agent-123", "wake laptop A"))

    assert (e.value.status, e.value.agent_gone) == (404, True)


def test_other_failures_keep_the_session_and_carry_agoras_reason():
    def busy(request):
        return httpx.Response(429, json={"detail": "slow down", "reason": "ResourceQuotaLimitExceeded"})

    with pytest.raises(AgoraError) as e:
        asyncio.run(agora_answering(busy).think("agent-123", "wake laptop A"))

    assert (e.value.status, e.value.agent_gone) == (429, False)
    assert "ResourceQuotaLimitExceeded" in str(e.value)


def test_a_network_failure_is_an_agora_error_without_a_status():
    def unreachable(request):
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(AgoraError) as e:
        asyncio.run(agora_answering(unreachable).think("agent-123", "wake laptop A"))

    assert (e.value.status, e.value.agent_gone) == (None, False)


def test_from_env_names_every_missing_variable(monkeypatch):
    for name in ("AGORA_APP_ID", "AGORA_CUSTOMER_ID", "AGORA_CUSTOMER_SECRET", "AGORA_APP_CERTIFICATE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("AGORA_APP_ID", "app123")

    with pytest.raises(RuntimeError) as e:
        HttpAgora.from_env()

    assert "AGORA_CUSTOMER_ID" in str(e.value) and "AGORA_CUSTOMER_SECRET" in str(e.value)
    assert "AGORA_APP_CERTIFICATE" in str(e.value)
    assert "AGORA_APP_ID" not in str(e.value)
