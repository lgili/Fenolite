# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Images in MCP replies (capability mcp-server, "Images in replies"; change c0196): the PNG files a reply
plans or writes are sent as image content, from the staged plan of a dry run or from the written files."""

from __future__ import annotations

import base64
import sys
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.api import discover
from fenolite.mcp.backend import IMAGES, FenoliteBackend
from fenolite.mcp.protocol import Call

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
COMMANDS = discover()
FAKE = """\
import json, sys
names = [f"view{index}.png" for index in range(5)]
for index, name in enumerate(names):
    open(name, "wb").write(b"\\x89PNG fake " + bytes([index]))
written = [{"path": name, "sha256": ""} for name in names]
if "fail" in sys.argv:
    error = {"code": "FEN-3001", "message": "x", "hint": "", "retryable": False, "where": ""}
    print(json.dumps(error), file=sys.stderr)
    sys.exit(3)
envelope = {"ok": True, "command": "render", "result": {"views": names}, "receipt": {"written": written}}
print(json.dumps(envelope))
"""


@pytest.fixture(autouse=True)
def state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))


def fake(root: Path) -> FenoliteBackend:
    root.mkdir(parents=True, exist_ok=True)
    script = root.parent / "fake_fenolite.py"
    script.write_text(FAKE, encoding="utf-8")
    return FenoliteBackend(COMMANDS, root=root, timeout=60, executable=[sys.executable, str(script)])


def images(reply: dict[str, Any]) -> list[bytes]:
    return [base64.b64decode(item["data"]) for item in reply["content"] if item["type"] == "image"]


def test_written_pngs_are_sent_up_to_the_cap(tmp_path: Path) -> None:
    reply = fake(tmp_path / "p").call("fenolite_check", {"path": "b"}, Call())
    sent = images(reply)
    assert len(sent) == IMAGES and sent[0] == b"\x89PNG fake \x00"
    assert reply["content"][0]["type"] == "text"  # the envelope stays first
    assert "view4.png" in reply["content"][-1]["text"]  # what was left out is named


def test_an_error_carries_no_image(tmp_path: Path) -> None:
    reply = fake(tmp_path / "p").call("fenolite_check", {"path": "fail"}, Call())
    assert reply["isError"] is True and images(reply) == []
