"""启动总控。

    python -m pagent.coordinator --fake-agora

所有密钥只从环境变量读取（示例见 config/examples/coordinator.env.example）：
  PAGENT_DEVICES       设备表 JSON：{"watch-1": {"kind": "watch", "token": "..."}}
  PAGENT_ADMIN_TOKEN   管理接口（/api/voice/session）的令牌
  PAGENT_MCP_TOKEN     语音助手调用工具（/mcp）要带的令牌；不设就没有工具
  PAGENT_PUBLIC_URL    Agora 云端能访问到总控的公网 HTTPS 地址；不设时 Agent 启动后不带工具
  AGORA_*              见 pagent.coordinator.agora.HttpAgora.from_env（--fake-agora 时不需要）
"""

from __future__ import annotations

import argparse
import logging
import os
import sys

import uvicorn

from pagent.coordinator.agora import FakeAgora
from pagent.coordinator.app import create_app
from pagent.coordinator.devices import DeviceRegistry
from pagent.coordinator.voice import VoiceSessions
from pagent.protocol import AgentTranscript

FAKE_AGENT_ID = "fake-agent"


def main() -> int:
    ap = argparse.ArgumentParser(description="pagent coordinator")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--fake-agora", action="store_true",
                    help="不连 Agora：/think 只打印，并假装语音助手回了一句")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # its request lines carry the App ID

    raw_devices = os.environ.get("PAGENT_DEVICES")
    if not raw_devices:
        print("set PAGENT_DEVICES (see config/examples/coordinator.env.example)", file=sys.stderr)
        return 2
    devices = DeviceRegistry.from_json(raw_devices)
    sessions = VoiceSessions()

    if args.fake_agora:
        agora = FakeAgora(echo=True)
        sessions.start(FAKE_AGENT_ID)  # a fake session is always "running"
    else:
        from pagent.coordinator.agora import HttpAgora
        try:
            agora = HttpAgora.from_env()
        except RuntimeError as e:
            print(f"{e} (or run with --fake-agora)", file=sys.stderr)
            return 2

    app = create_app(agora=agora, devices=devices, sessions=sessions,
                     admin_token=os.environ.get("PAGENT_ADMIN_TOKEN"),
                     mcp_token=os.environ.get("PAGENT_MCP_TOKEN") or None,
                     public_url=os.environ.get("PAGENT_PUBLIC_URL") or None)
    if not os.environ.get("PAGENT_MCP_TOKEN"):
        logging.warning("PAGENT_MCP_TOKEN is not set: the assistant has no tools")
    elif not os.environ.get("PAGENT_PUBLIC_URL"):
        logging.warning("PAGENT_PUBLIC_URL is not set: /mcp is served, but agents are started without "
                        "tools because Agora's cloud has no address to call")
    if args.fake_agora:
        # Stand in for the voice page too: the made-up answer goes to the watch
        # the same way a real agent_transcript would.
        async def answer(text: str) -> None:
            await app.state.assistant_said(AgentTranscript(text=text))
        agora.on_answer = answer
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
