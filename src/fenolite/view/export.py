# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged viewer page, live or with a project and its scenes embedded (capability board-viewer,
"Viewer page")."""

from __future__ import annotations

import json
from importlib import resources
from typing import Any, cast

DATA_MARK = "/*__DATA__*/null"
LIVE_MARK = "/*__LIVE__*/false"


def template() -> str:
    """The page as packaged, with its two placeholders."""
    return resources.files("fenolite.view").joinpath("page.html").read_text(encoding="utf-8")


def _json(value: Any) -> str:
    # `</` would end the script element; the escape keeps the JSON value unchanged
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def page(
    tree: dict[str, Any] | None = None,
    scenes: dict[str, dict[str, Any]] | None = None,
    *,
    open_id: str | None = None,
    live: bool = False,
) -> str:
    """The page: with ``tree`` and ``scenes`` (document id → scene) embedded, a standalone file; with
    ``live``, the page of the server, which fetches both."""
    html = template()
    if tree is not None:
        html = html.replace(DATA_MARK, _json({"project": tree, "scenes": scenes or {}, "open": open_id}), 1)
    return html.replace(LIVE_MARK, "true" if live else "false", 1)


def embedded(html: str) -> dict[str, Any] | None:
    """The data a standalone page embeds, read back (for tests and tools); ``None`` for a live page."""
    start = html.find("const EMBED = ")
    if start < 0:
        return None
    start += len("const EMBED = ")
    end = html.find(";\n", start)
    text = html[start:end].replace("<\\/", "</")
    if text == DATA_MARK:
        return None
    value: Any = json.loads(text)
    return cast("dict[str, Any]", value) if isinstance(value, dict) else None


__all__ = ["embedded", "page", "template"]
