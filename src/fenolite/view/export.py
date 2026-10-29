# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged viewer page, live or with a project and its scenes embedded (capability board-viewer,
"Viewer page")."""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any, cast

from fenolite.view.compact import pack, unpack

DATA_MARK = "/*__DATA__*/null"
LIVE_MARK = "/*__LIVE__*/false"
CSS_MARK = "/*__CSS__*/"
JS_MARK = "/*__JS__*/"


@cache
def template() -> str:
    """The page as packaged, with its two placeholders: the shell ``static/page.html`` with the committed
    bundles ``static/viewer.css`` and ``static/viewer.js`` inlined (change c0247; ``viewer/build.mjs``
    makes the three files from ``viewer/src``)."""
    static = resources.files("fenolite.view").joinpath("static")
    shell, css, js = (
        static.joinpath(name).read_text(encoding="utf-8") for name in ("page.html", "viewer.css", "viewer.js")
    )
    return shell.replace(CSS_MARK, css, 1).replace(JS_MARK, js, 1)


def _json(value: Any) -> str:
    # `</` would end the script element; the escape keeps the JSON value unchanged
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/")


def page(
    tree: dict[str, Any] | None = None,
    scenes: dict[str, dict[str, Any]] | None = None,
    *,
    open_id: str | None = None,
    live: bool = False,
    select: str | None = None,
    marks: list[dict[str, Any]] | None = None,
) -> str:
    """The page: with ``tree`` and ``scenes`` (document id → scene) embedded, a standalone file; with
    ``live``, the page of the server, which fetches both. Each scene is embedded packed (``compact.pack``,
    change c0182) and decoded by the page when its document is opened. ``select`` (a part or net) and
    ``marks`` (``review.to_json``) are what ``--select`` and ``--marks`` give the page (change c0189)."""
    html = template()
    if tree is not None:
        packed = {doc_id: pack(scene) for doc_id, scene in (scenes or {}).items()}
        data = {"project": tree, "scenes": packed, "open": open_id, "select": select, "marks": marks or []}
        html = html.replace(DATA_MARK, _json(data), 1)
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
    if not isinstance(value, dict):
        return None
    data = cast("dict[str, Any]", value)
    scenes = cast("dict[str, Any]", data.get("scenes") or {})
    return data | {"scenes": {doc_id: unpack(scene) for doc_id, scene in scenes.items()}}


__all__ = ["embedded", "page", "template"]
