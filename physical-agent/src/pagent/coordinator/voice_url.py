"""打印打开语音页用的链接。

    uv run --env-file .env python -m pagent.coordinator.voice_url

链接的 # 后面带着手机的设备令牌。# 后面的部分只留在浏览器里，不会发给任何服务器；
语音页读到后会把它从地址栏里去掉。这个链接等于手机的通行证，不要发给别人。
"""

from __future__ import annotations

import argparse
import json
import os
import sys


def voice_url(devices_json: str, base: str) -> str:
    """The voice page link for the first phone in the device table."""
    devices = json.loads(devices_json)
    phone = next((d for d in devices.values() if d.get("kind") == "phone"), None)
    if phone is None:
        raise LookupError("PAGENT_DEVICES has no device of kind 'phone'")
    return f"{base.rstrip('/')}/#token={phone['token']}"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="http://localhost:3000", help="语音页的地址")
    args = ap.parse_args()
    try:
        print(voice_url(os.environ.get("PAGENT_DEVICES", "{}"), args.base))
    except (LookupError, ValueError) as e:
        print(e, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
