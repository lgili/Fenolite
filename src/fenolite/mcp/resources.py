# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The resources of the MCP server (capability mcp-server, "Guide resources"; change c0195).

Each page of the agent guide is ``fenolite://guide/<topic>`` (Markdown, the page that
``fenolite guide <topic> --json`` returns), and the reply of ``fenolite capabilities --json --no-tools`` is
``fenolite://capabilities``. The pages are read from the installed package; the capabilities reply comes
from the ``capabilities`` callable, once."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fenolite.agent import guide

GUIDE = "fenolite://guide/"
CAPABILITIES = "fenolite://capabilities"
Json = dict[str, Any]


class Resources:
    """The guide pages and the capabilities reply; ``capabilities`` gives the reply's JSON text."""

    def __init__(self, capabilities: Callable[[], str]) -> None:
        self._capabilities = capabilities
        self._reply: str | None = None

    def list(self) -> list[Json]:
        listed: list[Json] = [
            {
                "uri": GUIDE + page.topic,
                "name": page.topic,
                "title": page.title,
                "description": page.summary,
                "mimeType": "text/markdown",
            }
            for page in guide.pages()
        ]
        listed.append(
            {
                "uri": CAPABILITIES,
                "name": "capabilities",
                "title": "fenolite capabilities",
                "description": "the commands, extras and external tools of the installed version",
                "mimeType": "application/json",
            }
        )
        return listed

    def read(self, uri: str) -> list[Json] | None:
        if uri == CAPABILITIES:
            if self._reply is None:
                self._reply = self._capabilities()
            return [{"uri": uri, "mimeType": "application/json", "text": self._reply}]
        if not uri.startswith(GUIDE):
            return None
        topic = uri.removeprefix(GUIDE)
        found = next((page for page in guide.pages() if page.topic == topic), None)
        if found is None:
            return None
        return [{"uri": uri, "mimeType": "text/markdown", "text": found.text}]


__all__ = ["CAPABILITIES", "GUIDE", "Resources"]
