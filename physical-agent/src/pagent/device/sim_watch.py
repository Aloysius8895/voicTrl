"""模拟手表：每输入一行就发出一条话语，并打印收到的显示。

    uv run --env-file .env python -m pagent.device.sim_watch --device watch-1

令牌只从环境变量读取：--device 从 PAGENT_DEVICES 里按设备名取，否则用 PAGENT_DEVICE_TOKEN。输入结束（Ctrl+Z 回车，或管道读完）后
再等 --linger 秒收完显示就退出。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

from pagent import protocol as p

CLOSE_NO_HELLO = 4401  # the coordinator's close code for a missing or bad hello


def render(display: p.Display) -> str:
    text = f"{display.title}: {display.body}" if display.body else display.title
    return f"[watch] {text}" + ("  ~bzzt~" if display.vibrate else "")


async def _print_displays(ws: ClientConnection) -> None:
    async for raw in ws:
        try:
            msg = p.parse_frame(raw)
        except p.ProtocolError as e:
            print(f"[watch] bad frame from coordinator: {e}", flush=True)
            continue
        if msg.type == p.DISPLAY:
            print(render(msg.body), flush=True)


async def _send_lines(ws: ClientConnection, lang: str) -> None:
    loop = asyncio.get_running_loop()
    while line := await loop.run_in_executor(None, sys.stdin.readline):
        if line.strip():
            await ws.send(p.build_frame(p.Utterance(text=line.strip(), lang=lang)))


async def run(url: str, token: str, lang: str, linger: float) -> int:
    try:
        async with connect(url) as ws:
            # The token goes in the first frame, never in the URL or a header.
            await ws.send(p.build_frame(p.Hello(token=token)))
            try:
                ack = p.parse_frame(await ws.recv())
            except ConnectionClosed as e:
                if e.rcvd is not None and e.rcvd.code == CLOSE_NO_HELLO:
                    print("[watch] coordinator did not accept the token; check PAGENT_DEVICE_TOKEN",
                          file=sys.stderr)
                    return 1
                raise
            print(f"[watch] connected to {url} as {ack.body.device_id} ({ack.body.kind}); "
                  "type what the user says", flush=True)
            printer = asyncio.create_task(_print_displays(ws))
            try:
                await _send_lines(ws, lang)
                await asyncio.sleep(linger)
            finally:
                printer.cancel()
    except (ConnectionClosed, OSError) as e:
        print(f"[watch] connection lost: {e}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--url", default="ws://127.0.0.1:8000/ws/device")
    ap.add_argument("--lang", default="en")
    ap.add_argument("--linger", type=float, default=2.0)
    ap.add_argument("--device", help="从环境变量 PAGENT_DEVICES 里按设备名取令牌，例如 watch-1")
    args = ap.parse_args()
    if args.device:
        try:
            token = json.loads(os.environ.get("PAGENT_DEVICES", "{}"))[args.device]["token"]
        except (KeyError, ValueError):
            print(f"PAGENT_DEVICES has no device named {args.device!r}", file=sys.stderr)
            return 2
    else:
        token = os.environ.get("PAGENT_DEVICE_TOKEN")
    if not token:
        print("pass --device <name> (with PAGENT_DEVICES set) or set PAGENT_DEVICE_TOKEN", file=sys.stderr)
        return 2
    return asyncio.run(run(args.url, token, args.lang, args.linger))


if __name__ == "__main__":
    sys.exit(main())
