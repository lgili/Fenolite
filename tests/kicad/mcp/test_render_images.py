# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Images of a real render in an MCP reply (capability mcp-server, "Images in replies"; change c0196), with
``kicad-cli``: run by the job ``kicad-10``, which has it."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli.api import discover
from fenolite.mcp.backend import FenoliteBackend
from fenolite.mcp.protocol import Call

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
COMMANDS = discover()


@pytest.fixture(autouse=True)
def state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))


def images(reply: dict[str, Any]) -> list[bytes]:
    return [base64.b64decode(item["data"]) for item in reply["content"] if item["type"] == "image"]


@pytest.mark.needs_kicad
def test_dry_run_of_a_render_is_seen(tmp_path: Path) -> None:
    """Scenario "A dry run of a render is seen"."""
    root = tmp_path / "p"
    root.mkdir()
    backend = FenoliteBackend(COMMANDS, root=root, timeout=300)
    arguments = {"path": str(BOARD), "out": "views", "png": True, "width": 400, "height": 300}
    reply = backend.call("fenolite_render", arguments, Call())
    assert reply["isError"] is False, reply["structuredContent"]
    rows = [r for r in reply["structuredContent"]["result"]["plan"] if r["path"].endswith(".png")]
    sent = images(reply)
    assert len(sent) == len(rows) == 2
    assert sorted(hashlib.sha256(data).hexdigest() for data in sent) == sorted(r["sha256"] for r in rows)
    assert all(data.startswith(b"\x89PNG") for data in sent)
    assert not (root / "views").exists()  # a dry run writes nothing
