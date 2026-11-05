# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The static gallery of a ``fenolite-library`` release (changes c0279 and c0405, ``docs/library-repo.md``,
"Gallery").

An index page with a card grid (search, filters by kind and licence, a light and dark theme), one page per
item of the release index and the benchmark page, styled by ``assets/site.css`` and ``assets/site.js``.
Every item page shows the attribution line ("Converted from the open-source design <title> by <authors>
(<link>), licence <SPDX>. Rendered by Fenolite <version>. Not endorsed by the authors.", or "Authored for
fenolite-library."), the item's images, a facts table, the proof result, the ``fenolite get`` command and
links to the item folder, its LICENSE and NOTICE. Images are made by Fenolite only (``Media``): symbols,
footprints and devices drawn from the library viewer's scenes, board views and block schematics rendered
by the library's workflow; no upstream image is used. An item whose image could not be made shows a
placeholder that names why. An item with ``trademarks.restricted`` gets no card. Card text describes; it
never says the item is a product of the upstream's owner. Nothing is loaded from another origin.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any, cast
from urllib.parse import urlsplit

from fenolite.library.gallery_assets import (
    CSS,
    JS,
    LOGO,
    NO_IMAGE_ICON,
    SEARCH_ICON,
    THEME_BOOT,
    THEME_ICON,
)
from fenolite.library.gallery_images import Media
from fenolite.library.items import KINDS

REPOSITORY = "https://github.com/lgili/fenolite-library"
NOT_ENDORSED = "Not endorsed by the authors."
ASSETS = ("assets/site.css", "assets/site.js")
PLURAL = {
    "symbol": "symbols",
    "footprint": "footprints",
    "device": "devices",
    "block": "blocks",
    "board": "boards",
}
NO_MEDIA = "no image was made for this item"
CURRENT = ' aria-current="page"'


def _e(value: object) -> str:
    return html.escape(str(value))


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


def _page(
    title: str, body: str, depth: int, *, version: str, fenolite_version: str, current: str = ""
) -> bytes:
    up = "../" * depth
    nav = "".join(
        f'<a href="{up}{href}"{CURRENT if href == current else ""}>{label}</a>'
        for href, label in (("index.html", "Gallery"), ("bench.html", "Benchmark"))
    )
    text = (
        '<!doctype html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{_e(title)}</title>"
        f'<meta name="description" content="fenolite-library {_e(version)}: symbols, footprints, devices, '
        'blocks and boards, each with its upstream licence.">'
        f'<link rel="stylesheet" href="{up}assets/site.css">{THEME_BOOT}</head><body>\n'
        f'<header class="top"><div class="wrap"><a class="brand" href="{up}index.html">{LOGO}'
        f'<span>fenolite-library</span><span class="ver">v{_e(version)}</span></a><nav>{nav}'
        f'<a class="hide-sm" href="{REPOSITORY}">GitHub</a>'
        f'<button class="theme" type="button" aria-label="Switch light and dark theme">{THEME_ICON}</button>'
        f'</nav></div></header>\n<main class="wrap">\n{body}\n</main>\n'
        '<footer class="wrap foot">Each item keeps its upstream licence; the repository\'s own licence '
        "does not "
        f"cover the items. Images are rendered by Fenolite {_e(fenolite_version)} from the release "
        f'<a href="{REPOSITORY}/tree/v{_e(version)}">v{_e(version)}</a>; '
        "no upstream image is used.</footer>\n"
        f'<script src="{up}assets/site.js" defer></script></body></html>\n'
    )
    return text.encode("utf-8")


def _placeholder(reason: str) -> str:
    return (
        f'<div class="placeholder" role="img" aria-label="No image: {_e(reason)}">{NO_IMAGE_ICON}'
        f'<strong>No image</strong><p class="why">{_e(reason)}</p></div>'
    )


def _kind_badge(kind: str) -> str:
    return f'<span class="badge kind k-{_e(kind)}">{_e(kind)}</span>'


def _proof_badge(row: Mapping[str, Any]) -> str:
    proof = str(row.get("proof") or "")
    if not proof:
        return ""
    tone = "ok" if proof.startswith("pass") else "warn"
    return f'<span class="badge {tone}">proof: {_e(proof)}</span>'


def _source(record: Mapping[str, Any]) -> str:
    upstream = record.get("upstream")
    if record.get("origin") != "converted" or not isinstance(upstream, dict):
        return "Authored for fenolite-library"
    upstream = cast(Mapping[str, Any], upstream)
    link = str(upstream.get("source_location") or upstream.get("url") or "")
    parts = urlsplit(link)
    label = (parts.netloc + parts.path) if parts.netloc else link
    commit = str(upstream.get("commit") or "")
    tail = f" at <code>{_e(commit[:12])}</code>" if commit else ""
    return f'<a href="{_e(link)}">{_e(label)}</a>{tail}' if link.startswith("https://") else _e(link) + tail


PAPER_VIEWS = frozenset({"symbol.svg", "schematic.svg"})


def _ground(name: str) -> str:
    """The class that gives an image its own ground: paper for schematics, the board colour otherwise."""
    return "paper" if name in PAPER_VIEWS else "board"


def _views_html(media: Media | None, title: str) -> str:
    if media is None or (not media.views and media.missing is None):
        return f'<section class="previews">{_placeholder(NO_MEDIA)}</section>'
    figures = [
        f'<figure><img src="{_e(view.name)}" class="{_ground(view.name)}" '
        f'alt="{_e(title)}, {_e(view.caption)}, rendered by Fenolite">'
        f"<figcaption>{_e(view.caption)}</figcaption></figure>"
        for view in media.views
    ]
    if media.missing is not None:
        figures.append(_placeholder(media.missing))
    return '<section class="previews">' + "".join(figures) + "</section>"


def card(
    row: Mapping[str, Any],
    record: Mapping[str, Any],
    *,
    version: str,
    fenolite_version: str,
    media: Media | None = None,
) -> bytes:
    """The page of one item."""
    page = str(row["gallery"])
    depth = page.count("/")
    up = "../" * depth
    title, kind = str(row.get("title")), str(row.get("kind"))
    path = str(row.get("path"))
    folder = f"{REPOSITORY}/tree/v{version}/{path}"
    blob = f"{REPOSITORY}/blob/v{version}/{path}"
    licence = f"{row.get('spdx')}{' (reciprocal)' if row.get('reciprocal') else ''}"
    facts: list[tuple[str, str]] = [
        ("Kind", _e(kind)),
        ("Identifier", f"<code>{_e(row.get('id'))}</code>"),
        ("Version", _e(row.get("version"))),
        ("Licence", _e(licence)),
        ("Source", _source(record)),
        ("Proof", _e(row.get("proof") or "not applicable")),
        ("Evidence", _e(row.get("evidence"))),
    ]
    tags = cast(list[str], row.get("tags") or [])
    if tags:
        facts.append(("Tags", _e(", ".join(tags))))
    if media is not None:
        facts.extend((name, _e(value)) for name, value in media.facts)
        facts.extend(
            (label, f'<a href="{up}{_e(target)}">{_e(target.rsplit("/", 2)[-2])}</a>')
            for label, target in media.links
        )
    rows = "".join(f'<tr><th scope="row">{name}</th><td>{value}</td></tr>' for name, value in facts)
    table = ""
    if media is not None and media.table is not None:
        head, body_rows = media.table
        table = (
            f'<div class="panel"><h2>{_e(head[0])}s</h2><div class="table-wrap"><table><thead><tr>'
            + "".join(f"<th>{_e(h)}</th>" for h in head)
            + "</tr></thead><tbody>"
            + "".join("<tr>" + "".join(f"<td>{_e(c)}</td>" for c in r) + "</tr>" for r in body_rows)
            + "</tbody></table></div></div>"
        )
    group = PLURAL.get(kind, kind)
    body = (
        f'<p class="crumbs"><a href="{up}index.html">Gallery</a> / {_e(group)} / {_e(row.get("id"))}</p>\n'
        f'<div class="item-head"><div class="badges">{_kind_badge(kind)}'
        f'<span class="badge">{_e(licence)}</span>{_proof_badge(row)}</div>'
        f"<h1>{_e(title)}</h1>"
        f'<p class="summary">{_e(row.get("summary") or "")}</p></div>\n'
        f"{_views_html(media, title)}\n"
        f'<p class="attribution">{_e(attribution_line(row, record, fenolite_version))}</p>\n'
        '<div class="columns"><div><div class="panel"><h2>Facts</h2><div class="table-wrap">'
        f'<table class="facts"><tbody>{rows}</tbody></table></div></div>{table}</div>'
        '<aside><div class="panel"><h2>Get it</h2>'
        f'<div class="cmd"><code id="get-command">{_e(get_command(row, version))}</code>'
        '<button class="copy" type="button" data-copy="get-command">Copy</button></div>'
        f'<ul class="links"><li><a href="{_e(folder)}">Item folder</a> '
        "(LICENSE, NOTICE, PROVENANCE.json)</li>"
        f'<li><a href="{_e(blob)}/LICENSE">Licence text</a></li>'
        f'<li><a href="{_e(blob)}/NOTICE">NOTICE</a></li>'
        f'<li><a href="{_e(blob)}/PROVENANCE.json">Provenance record</a></li></ul></div></aside></div>'
    )
    return _page(title, body, depth, version=version, fenolite_version=fenolite_version)


def _thumb(row: Mapping[str, Any], media: Media | None) -> str:
    folder = str(row["gallery"]).rsplit("/", 1)[0]
    if media is None or not media.views:
        reason = media.missing if media is not None and media.missing else NO_MEDIA
        return f'<div class="thumb">{_placeholder(reason)}</div>'
    views = media.views[:2] if row.get("kind") == "device" else media.views[:1]  # a board card: top
    images = "".join(
        f'<img src="{_e(folder)}/{_e(view.name)}" class="{_ground(view.name)}" '
        f'alt="{_e(row.get("title"))}, {_e(view.caption)}" '
        'loading="lazy">'
        for view in views
    )
    return f'<div class="thumb{" pair" if len(views) == 2 else ""}">{images}</div>'


def _levels(row: Mapping[str, Any]) -> str:
    levels = cast(Mapping[str, Any], row.get("levels") or {})
    return ", ".join(f"{k}: {v}" for k, v in levels.items())


def visible_rows(
    index: Mapping[str, Any], records: Mapping[str, Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """The rows that get a card, in gallery order: rows with a gallery page, without restricted marks."""
    order = {kind: n for n, kind in enumerate(KINDS)}
    rows = sorted(
        (r for r in cast(list[Mapping[str, Any]], index.get("items", [])) if r.get("gallery")),
        key=lambda r: (order.get(str(r.get("kind")), len(KINDS)), str(r.get("id"))),
    )
    shown: list[Mapping[str, Any]] = []
    for row in rows:
        trademarks = records.get(str(row.get("path")), {}).get("trademarks")
        if isinstance(trademarks, dict) and cast(dict[str, Any], trademarks).get("restricted") is True:
            continue
        shown.append(row)
    return shown


def _index(
    rows: Sequence[Mapping[str, Any]],
    records: Mapping[str, Mapping[str, Any]],
    media: Mapping[str, Media],
    *,
    version: str,
    fenolite_version: str,
) -> bytes:
    counts: dict[str, int] = {}
    for row in rows:
        counts[str(row.get("kind"))] = counts.get(str(row.get("kind")), 0) + 1
    kinds = [kind for kind in KINDS if kind in counts]
    licences = sorted({str(row.get("spdx")) for row in rows})
    stats = "".join(
        f"<li><strong>{counts[k]}</strong> {_e(PLURAL.get(k, k) if counts[k] != 1 else k)}</li>"
        for k in kinds
    )
    chips = '<button class="chip" type="button" data-kind="all" aria-pressed="true">All</button>' + "".join(
        f'<button class="chip" type="button" data-kind="{_e(k)}" aria-pressed="false">'
        f"{_e(PLURAL.get(k, k))}</button>"
        for k in kinds
    )
    options = '<option value="all">All licences</option>' + "".join(
        f'<option value="{_e(spdx)}">{_e(spdx)}</option>' for spdx in licences
    )
    cards: list[str] = []
    for row in rows:
        record = records.get(str(row.get("path")), {})
        line = attribution_line(row, record, fenolite_version)
        words = " ".join(
            str(value)
            for value in (
                row.get("title"),
                row.get("id"),
                row.get("summary"),
                row.get("kind"),
                row.get("spdx"),
            )
        )
        words += " " + " ".join(cast(list[str], row.get("tags") or []))
        cards.append(
            f'<li class="card" data-kind="{_e(row.get("kind"))}" data-licence="{_e(row.get("spdx"))}" '
            f'data-text="{_e(words.lower())}"><a href="{_e(row["gallery"])}">'
            f"{_thumb(row, media.get(str(row.get('path'))))}"
            f'<div class="body"><h2>{_e(row.get("title"))}</h2><p class="badges">'
            f'{_kind_badge(str(row.get("kind")))}<span class="badge">{_e(row.get("spdx"))}</span></p>'
            f'<p class="attr">{_e(line)}</p></div></a></li>'
        )
    total = len(rows)
    body = (
        f'<section class="hero"><h1>fenolite-library {_e(version)}</h1>'
        "<p>Symbols, footprints, devices, blocks and boards converted to Fenolite's formats or authored "
        "for the "
        "library. Each item keeps its upstream licence and its provenance; every image is rendered by "
        f'Fenolite.</p><ul class="stats">{stats}</ul></section>\n'
        '<div class="toolbar" role="search"><label class="search">'
        f'{SEARCH_ICON}<span hidden>Search</span><input id="q" type="search" '
        'placeholder="Search by name, id or tag" '
        'autocomplete="off"></label>'
        f'<div class="chips" role="group" aria-label="Kind">{chips}</div>'
        '<label><span hidden>Licence</span><select id="licence" aria-label="Licence">'
        f"{options}</select></label>"
        f'<span class="count" id="count">{total} {"item" if total == 1 else "items"}</span></div>\n'
        f'<ul class="grid">{"".join(cards)}</ul>\n'
        '<p class="empty" id="empty" hidden>No item matches the search and filters.</p>'
    )
    return _page(
        f"fenolite-library {version}", body, 0, version=version, fenolite_version=fenolite_version,
        current="index.html",
    )  # fmt: skip


def _bench(bench: Sequence[Mapping[str, Any]], *, version: str, fenolite_version: str) -> bytes:
    def result(value: object) -> str:
        text = str(value)
        tone = "result-pass" if text.startswith("pass") or text == "equal" else "result-fail"
        return f'<span class="{tone}">{_e(text)}</span>'

    table = "".join(
        f"<tr><td><code>{_e(r.get('id'))}</code></td><td>{result(r.get('result'))}</td>"
        f"<td>{_e(_levels(r))}</td><td>{_e(r.get('seconds'))}</td><td>{_e(r.get('differences'))}</td></tr>"
        for r in bench
    )
    body = (
        '<section class="hero"><h1>Benchmark</h1><p>Every board replayed and proved with the newest '
        "Fenolite.</p></section>\n"
        + (
            '<div class="panel"><div class="table-wrap"><table><thead><tr><th>Board</th><th>Result</th>'
            "<th>Levels</th><th>Seconds</th><th>Differences</th></tr></thead>"
            f"<tbody>{table}</tbody></table></div></div>"
            if bench
            else '<div class="panel"><p>No benchmark has run yet.</p></div>'
        )
    )
    return _page(
        "Benchmark", body, 0, version=version, fenolite_version=fenolite_version, current="bench.html"
    )


def site(
    index: Mapping[str, Any],
    records: Mapping[str, Mapping[str, Any]],
    *,
    fenolite_version: str,
    bench: Sequence[Mapping[str, Any]] = (),
    media: Mapping[str, Media] | None = None,
) -> dict[str, bytes]:
    """The files of the site: path → bytes. ``records`` maps an item's path to its ``PROVENANCE.json``,
    ``media`` an item's path to its images and facts."""
    version = str(index.get("version"))
    images = media or {}
    rows = visible_rows(index, records)
    files: dict[str, bytes] = {ASSETS[0]: CSS.encode("utf-8"), ASSETS[1]: JS.encode("utf-8")}
    for row in rows:
        path = str(row.get("path"))
        item = images.get(path)
        page = str(row["gallery"])
        files[page] = card(
            row, records.get(path, {}), version=version, fenolite_version=fenolite_version, media=item
        )
        folder = page.rsplit("/", 1)[0]
        for view in item.views if item is not None else ():
            files[f"{folder}/{view.name}"] = view.data
    files["index.html"] = _index(rows, records, images, version=version, fenolite_version=fenolite_version)
    files["bench.html"] = _bench(bench, version=version, fenolite_version=fenolite_version)
    return dict(sorted(files.items()))


__all__ = [
    "ASSETS",
    "NOT_ENDORSED",
    "REPOSITORY",
    "attribution_line",
    "card",
    "get_command",
    "site",
    "visible_rows",
]
