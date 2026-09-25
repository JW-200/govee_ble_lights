"""Bundled Govee scene data and BLE frames for controller-run effects."""

from __future__ import annotations

import base64
import json
from functools import lru_cache
from pathlib import Path

from .govee_ble import GoveeBLE


@lru_cache(maxsize=16)
def load_native_scenes(model: str) -> dict[str, dict]:
    """Return bundled scenes for a known model, or an empty mapping."""
    if not model.isalnum():
        return {}
    path = Path(__file__).parent / "native_scenes" / f"{model}.json"
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def _frame(data: bytearray) -> bytes:
    data[19] = GoveeBLE.sign_payload(data[:19])
    return bytes(data)


def build_native_scene_frames(scene: dict) -> list[bytes]:
    """Upload a scene parameter with A3 frames, then activate its scene code."""
    code = int(scene["code"])
    if not 0 <= code <= 0xFFFF:
        raise ValueError("Invalid native scene code")
    param = base64.b64decode(scene.get("param", ""), validate=True)
    frames: list[bytes] = []
    if param:
        first = bytearray(20)
        first[0:5] = bytes((0xA3, 0x00, 0x01, 0x00, 0x02))
        first[5 : 5 + min(len(param), 14)] = param[:14]
        remaining = param[14:]
        chunks = [remaining[i : i + 17] for i in range(0, len(remaining), 17)]
        if len(chunks) > 255:
            raise ValueError("Native scene is too large")
        first[3] = max(2, len(chunks) + 1)
        frames.append(_frame(first))
        for index, chunk in enumerate(chunks[:-1], start=1):
            packet = bytearray(20)
            packet[0:2] = bytes((0xA3, index))
            packet[2 : 2 + len(chunk)] = chunk
            frames.append(_frame(packet))
        last = bytearray(20)
        last[0:2] = bytes((0xA3, 0xFF))
        if chunks:
            last[2 : 2 + len(chunks[-1])] = chunks[-1]
        frames.append(_frame(last))

    frames.append(
        GoveeBLE.build_packet(
            GoveeBLE.LEDFrameType.COMMAND,
            GoveeBLE.LEDCommand.COLOR,
            [0x04, code & 0xFF, code >> 8],
        )
    )
    return frames
