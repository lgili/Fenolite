# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The static gallery of a ``fenolite-library`` release (change c0279, ``docs/library-repo.md``,
"Gallery").

One card page per item of the release index, an index page and the benchmark page. Every card shows the
attribution line ("Converted from the open-source design <title> by <authors> (<link>), licence <SPDX>.
Rendered by Fenolite <version>. Not endorsed by the authors.", or "Authored for fenolite-library."), the
proof result, the ``fenolite get`` command and a link to the item folder. Images are made by Fenolite only:
a board card shows ``top.svg`` and ``bottom.svg`` beside its page, which the library's gallery workflow
renders with ``fenolite render``; no upstream image is used. An item with ``trademarks.restricted`` gets no
card. Card text describes; it never says the item is a product of the upstream's owner.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fenolite.library.items import KINDS

REPOSITORY = "https://github.com/lgili/fenolite-library"
NOT_ENDORSED = "Not endorsed by the authors."
STYLE = (
    "body{font-family:system-ui,sans-serif;max-width:60rem;margin:2rem auto;padding:0 1rem;color:#222}"
    "figure{display:inline-block;margin:0 1rem 1rem 0}img{max-width:28rem;border:1px solid #ccc}"
    "code{background:#f4f4f4;padding:0 .2rem}table{border-collapse:collapse}"
    "td,th{border:1px solid #ccc;padding:.2rem .5rem}"
)


def attribution_line(row: Mapping[str, Any], record: Mapping[str, Any], fenolite_version: str) -> str:
    """The attribution line of a card (plain text)."""
    if record.get("origin") != "converted" or not isinstance(record.get("upstream"), dict):
        spdx = row.get("spdx")
        return f"Authored for fenolite-library, licence {spdx}. Rendered by Fenolite {fenolite_version}."
    upstream = cast(Mapping[str, Any], record["upstream"])
    link = upstream.get("source_location") or upstream.get("url")
    authors = ", ".join(cast(list[str], record.get("authors") or [])) or "its authors"
    return (
        f"Converted from the open-source design {row.get('title')} by {authors} ({link}), "
        f"licence {row.get('spdx')}. "
        f"Rendered by Fenolite {fenolite_version}. {NOT_ENDORSED}"
    )


def get_command(row: Mapping[str, Any], version: str) -> str:
    extra = "" if row.get("spdx") == "CC0-1.0" else f" --accept-licence {row.get('spdx')}"
    return f"fenolite get {row.get('kind')} {row.get('id')} --release {version}{extra} --dry-run"


def _page(title: str, body: str, depth: int) -> bytes:
    up = "../" * depth
    text = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{html.escape(title)}</title>"
        f'<style>{STYLE}</style></head><body>\n<p><a href="{up}index.html">fenolite-library gallery</a> · '
        f'<a href="{up}bench.html">benchmark</a></p>\n{body}\n</body></html>\n'
    )
    return text.encode("utf-8")


def card(row: Mapping[str, Any], record: Mapping[str, Any], *, version: str, fenolite_version: str) -> bytes:
    """The card page of one item."""
    page = str(row["gallery"])
    depth = page.count("/")
    title = str(row.get("title"))
    images = ""
    if row.get("kind") == "board":
        images = "".join(
            f'<figure><img src="{side}.svg" alt="{html.escape(title)}, {side} side, rendered by Fenolite">'
            f"<figcaption>{side}</figcaption></figure>"
            for side in ("top", "bottom")
        )
    folder = f"{REPOSITORY}/tree/v{version}/{row.get('path')}"
    body = (
        f"<h1>{html.escape(title)}</h1>\n<p>{html.escape(str(row.get('summary') or ''))}</p>\n{images}\n"
        f'<p class="attribution">{html.escape(attribution_line(row, record, fenolite_version))}</p>\n'
        f"<ul><li>Item: {html.escape(str(row.get('kind')))} <code>{html.escape(str(row.get('id')))}</code> "
        f"{html.escape(str(row.get('version')))}</li>"
        f"<li>Licence: {html.escape(str(row.get('spdx')))}"
        f"{' (reciprocal)' if row.get('reciprocal') else ''}</li>"
        f"<li>Proof: {html.escape(str(row.get('proof') or 'not applicable'))}</li>"
        f"<li>Evidence: {html.escape(str(row.get('evidence')))}</li>"
        f"<li>Get it: <code>{html.escape(get_command(row, version))}</code></li>"
        f'<li><a href="{html.escape(folder)}">Item folder</a> (LICENSE, NOTICE, PROVENANCE.json)</li></ul>'
    )
    return _page(title, body, depth)


def _levels(row: Mapping[str, Any]) -> str:
    levels = cast(Mapping[str, Any], row.get("levels") or {})
    return ", ".join(f"{k}: {v}" for k, v in levels.items())


def site(
    index: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    fenolite_version: str,
    bench: Sequence[Mapping[str, Any]] = (),
) -> dict[str, bytes]:
    """The files of the site: path → bytes. ``records`` maps an item's path to its ``PROVENANCE.json``."""
    version = str(index.get("version"))
    order = {kind: n for n, kind in enumerate(KINDS)}
    rows = sorted(
        (r for r in cast(list[Mapping[str, Any]], index.get("items", [])) if r.get("gallery")),
        key=lambda r: (order.get(str(r.get("kind")), len(KINDS)), str(r.get("id"))),
    )
    files: dict[str, bytes] = {}
    entries: list[str] = []
    for row in rows:
        record = records.get(str(row.get("path")), {})
        trademarks = record.get("trademarks")
        if isinstance(trademarks, dict) and cast(dict[str, Any], trademarks).get("restricted") is True:
            continue
        files[str(row["gallery"])] = card(row, record, version=version, fenolite_version=fenolite_version)
        entries.append(
            f'<li><a href="{html.escape(str(row["gallery"]))}">{html.escape(str(row.get("title")))}</a> '
            f"({html.escape(str(row.get('kind')))}, {html.escape(str(row.get('spdx')))})</li>"
        )
    intro = (
        f"<h1>fenolite-library {html.escape(version)}</h1>\n"
        "<p>Items converted to Fenolite's formats or authored "
        "for the library. Each item keeps its upstream licence; images are rendered by Fenolite.</p>\n"
    )
    files["index.html"] = _page(f"fenolite-library {version}", intro + "<ul>" + "".join(entries) + "</ul>", 0)
    table = "".join(
        f"<tr><td>{html.escape(str(r.get('id')))}</td><td>{html.escape(str(r.get('result')))}</td>"
        f"<td>{html.escape(_levels(r))}</td>"
        f"<td>{html.escape(str(r.get('seconds')))}</td><td>{html.escape(str(r.get('differences')))}</td></tr>"
        for r in bench
    )
    body = "<h1>Benchmark</h1>\n<p>Every board replayed and proved with the newest Fenolite.</p>\n" + (
        f"<table><tr><th>board</th><th>result</th><th>levels</th><th>seconds</th><th>differences</th></tr>{table}</table>"
        if bench
        else "<p>No benchmark has run yet.</p>"
    )
    files["bench.html"] = _page("Benchmark", body, 0)
    return dict(sorted(files.items()))


__all__ = ["NOT_ENDORSED", "REPOSITORY", "attribution_line", "card", "get_command", "site"]
