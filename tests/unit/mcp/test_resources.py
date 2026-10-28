# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The resources of the MCP server (capability mcp-server, "Guide resources"; change c0195)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from fenolite.agent import guide
from fenolite.cli.api import discover
from fenolite.mcp.backend import FenoliteBackend
from fenolite.mcp.resources import CAPABILITIES, GUIDE, Resources


def test_page_read() -> None:
    """Scenario "A page read": the text is the page that `fenolite guide start --json` returns."""
    resources = Resources(lambda: "{}")
    (content,) = resources.read(GUIDE + "start") or []
    reply = subprocess.run(
        [sys.executable, "-m", "fenolite", "guide", "start", "--json"],
        capture_output=True,
        check=True,
        env={**os.environ, "PYTHONUTF8": "1"},  # as the server runs its children (Windows writes cp1252 else)
    )
    assert content["mimeType"] == "text/markdown"
    assert content["text"] == json.loads(reply.stdout)["result"]["text"]


def test_every_page_is_listed() -> None:
    listed = Resources(lambda: "{}").list()
    uris = [entry["uri"] for entry in listed]
    assert uris == [GUIDE + page.topic for page in guide.pages()] + [CAPABILITIES]
    assert all(entry["name"] and entry["mimeType"] for entry in listed)


def test_unknown_resource() -> None:
    resources = Resources(lambda: "{}")
    assert resources.read(GUIDE + "nope") is None and resources.read("file:///etc/passwd") is None


def test_capabilities_resource(tmp_path: Path) -> None:
    resources = FenoliteBackend(discover(), root=tmp_path, timeout=120).guide
    (content,) = resources.read(CAPABILITIES) or []
    reply = json.loads(content["text"])
    assert reply["command"] == "capabilities" and "commands" in reply["result"]
    assert resources.read(CAPABILITIES) == [content]  # read once, then kept
