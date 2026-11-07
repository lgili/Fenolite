# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library gallery ROOT --release DIR --out DIR [--renders DIR]``: plan the static gallery of a
release (changes c0279 and c0405; ``fenolite.library.gallery``). ``DIR`` of ``--release`` holds the release
assets of ``library release`` (its ``index.json``), and a ``bench.json`` (the benchmark table) when one was
made. Symbols, footprints and devices are drawn by Fenolite from the item's own files, read as ``library
check`` reads them. ``--renders`` mirrors the gallery folders with the images that need KiCad or item code:
``top.svg`` and ``bottom.svg`` of a board, the sheet of a block (``schematic.kicad_sch``, drawn by Fenolite,
or a ready ``schematic.svg``), and ``failures.json`` (``{item id: reason}``). An image that cannot be made
becomes a placeholder naming why; ``result.placeholders`` lists them and the site is still planned. Each
attribution comes from the item's ``PROVENANCE.json`` (change c0418): a provenance the gallery cannot
attribute is a ``library.provenance-invalid`` error (``result.provenance``) and nothing is planned."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

import fenolite
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Evidence, Level
from fenolite.library.codes import issue
from fenolite.library.gallery import attribution_problems, site, visible_rows
from fenolite.library.gallery_images import Media, View, footprint_media, scene_svg, symbol_media
from fenolite.library.items import PROVENANCE_FILE, ItemError, load_json

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBRARY-GET",))
KIND = "library-gallery"
BENCH = "bench.json"
FAILURES = "failures.json"
RENDERED: Mapping[str, tuple[tuple[str, str], ...]] = {
    "board": (("top.svg", "top side"), ("bottom.svg", "bottom side")),
    "block": (("schematic.svg", "usage schematic"),),
}
"""Kinds whose images come from ``--renders``: file name and caption."""
NO_RENDER = "no render was supplied"
BLOCK_SHEET = "schematic.kicad_sch"
"""A block's sheet in ``--renders``: Fenolite draws it as ``schematic.svg``, cropped and without its frame."""


def schematic_svg(text: str, *, name: str, title: str) -> bytes:
    """The SVG of one KiCad schematic sheet, drawn by Fenolite's schematic viewer (``scene_svg``).
    Raises ``FormatError`` on a sheet it cannot read and ``ValueError`` on an empty one."""
    from fenolite.view import themes
    from fenolite.view.kicad_schematic import build_kicad_schematic_scene

    scene = build_kicad_schematic_scene(text, name=name, palette=themes.palette("kicad"))
    return scene_svg(scene, name=name, title=title)


def _path(given: str, ctx: Context) -> Path:
    return Path(given) if Path(given).is_absolute() else ctx.cwd / given


def _files(row: Mapping[str, Any]) -> list[str]:
    return sorted(str(f.get("path")) for f in cast(list[dict[str, Any]], row.get("files") or []))


def _drawn(row: Mapping[str, Any], root: Path, ctx: Context, read: list[Path]) -> Media:
    """A symbol's or a footprint's media, drawn from the item's own definition files."""
    from fenolite.cli._library_check import LIB_SUFFIXES, _read  # pyright: ignore[reportPrivateUsage]
    from fenolite.view.catalog import catalog_scene

    kind = str(row.get("kind"))
    folder = root / str(row.get("path"))
    candidates = [
        folder / name
        for name in _files(row)
        if Path(name).suffix == ".toml" or Path(name).suffix.lower() in LIB_SUFFIXES
    ]
    errors: list[str] = []
    for path in candidates:
        try:
            items = _read(path, ctx.cwd)
        except Exception as exc:  # noqa: BLE001 - a broken definition gets a placeholder, never a failed site
            errors.append(f"{path.name}: {exc}")
            continue
        for item in items:
            try:
                if kind == "symbol" and item.symbol is not None:
                    media = symbol_media(item.symbol, catalog_scene(item.symbol))
                elif kind == "footprint" and item.footprint is not None:
                    media = footprint_media(item.footprint, catalog_scene(item.footprint))
                else:
                    continue
            except Exception as exc:  # noqa: BLE001 - as above: drawing failed, the page names why
                errors.append(f"{path.name}: drawing failed: {exc}")
                continue
            read.extend([path, *item.extra_files])
            return media
    reason = "; ".join(errors) or f"no {kind} definition was found in the item's files"
    return Media(missing=f"Fenolite could not draw this {kind} ({reason})")


def _device(
    row: Mapping[str, Any], media: Mapping[tuple[str, str], Media], pages: Mapping[tuple[str, str], str]
) -> Media:
    views: list[View] = []
    links: list[tuple[str, str]] = []
    facts: list[tuple[str, str]] = []
    missing: list[str] = []
    for dep in cast(list[dict[str, Any]], row.get("depends") or []):
        key = (str(dep.get("kind")), str(dep.get("id")))
        if key[0] not in ("symbol", "footprint"):
            continue
        facts.append((key[0].capitalize(), key[1]))
        if key in pages:
            links.append((f"{key[0].capitalize()} page", pages[key]))
        found = media.get(key)
        if found is None:
            missing.append(f"its {key[0]} {key[1]} is not in this release")
        elif found.views:
            views.append(found.views[0])
        elif found.missing:
            missing.append(found.missing)
    if not views and not missing:
        missing.append("the device names no symbol or footprint")
    return Media(
        views=tuple(views), missing="; ".join(missing) or None, facts=tuple(facts), links=tuple(links)
    )


def _rendered(
    row: Mapping[str, Any], root: Path, renders: Path | None, failures: Mapping[str, str], read: list[Path]
) -> Media:
    kind = str(row.get("kind"))
    folder = str(row["gallery"]).rsplit("/", 1)[0]
    views: list[View] = []
    absent = False
    drawn_error = None
    for name, caption in RENDERED[kind]:
        path = renders / folder / name if renders is not None else None
        sheet = renders / folder / BLOCK_SHEET if renders is not None and kind == "block" else None
        if sheet is not None and sheet.is_file():
            read.append(sheet)
            try:
                text = sheet.read_text(encoding="utf-8")
                data = schematic_svg(text, name=BLOCK_SHEET, title=f"Block {row.get('id')}, usage schematic")
                views.append(View(name, caption, data))
            except (OSError, UnicodeDecodeError, FormatError, ValueError) as exc:
                drawn_error = f"Fenolite could not draw the block schematic ({exc})"
        elif path is not None and path.is_file():
            views.append(View(name, caption, path.read_bytes()))
            read.append(path)
        else:
            absent = True
    facts: list[tuple[str, str]] = []
    if kind == "board":
        files = cast(list[dict[str, Any]], row.get("files") or [])
        facts.append(("Files", str(len(files))))
        if row.get("bytes"):
            facts.append(("Archive size", f"{int(row['bytes']) / 1000:.0f} kB"))
    block = root / str(row.get("path")) / "block.json"
    if kind == "block" and block.is_file():
        try:
            record = cast(dict[str, Any], json.loads(block.read_text(encoding="utf-8")).get("record") or {})
            read.append(block)
            ports = [str(p.get("name")) for p in cast(list[dict[str, Any]], record.get("ports") or [])]
            params = [str(p.get("name")) for p in cast(list[dict[str, Any]], record.get("params") or [])]
            facts += [("Ports", ", ".join(ports) or "none"), ("Parameters", ", ".join(params) or "none")]
            facts.append(
                ("Parts", ", ".join(str(p) for p in cast(list[Any], record.get("parts") or [])) or "none")
            )
        except (OSError, ValueError, AttributeError):
            pass
    reason = drawn_error
    if absent:
        reason = failures.get(str(row.get("id"))) or NO_RENDER
        reason = f"the {'board render' if kind == 'board' else 'block schematic'} is missing: {reason}"
    return Media(views=tuple(views), missing=reason, facts=tuple(facts))


def gallery_command(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.path) != 2 or not args.release or not args.out:
        raise CliError(
            "FEN-2001",
            "library gallery takes ROOT, --release DIR and --out DIR",
            hint="fenolite library gallery . --release dist --out site --dry-run",
        )
    root, release = _path(args.path[1], ctx), _path(args.release, ctx)
    renders = _path(args.renders, ctx) if getattr(args, "renders", None) else None
    if renders is not None and not renders.is_dir():
        raise CliError("FEN-3001", f"--renders {args.renders} is not a folder", where="--renders")
    index_file = release / "index.json"
    try:
        index = load_json(index_file.read_bytes(), "index.json")
    except OSError as exc:
        raise CliError(
            "FEN-3001", f"--release {args.release} holds no index.json", where="--release"
        ) from exc
    except ItemError as exc:
        raise CliError("FEN-3004", str(exc), where="index.json") from exc
    records: dict[str, dict[str, Any]] = {}
    read: list[Path] = [index_file]
    for row in cast(list[dict[str, Any]], index.get("items", [])):
        path = root / str(row.get("path")) / PROVENANCE_FILE
        try:
            records[str(row.get("path"))] = load_json(path.read_bytes(), PROVENANCE_FILE)
            read.append(path)
        except (OSError, ItemError) as exc:
            raise CliError(
                "FEN-3001", f"{row.get('path')}/{PROVENANCE_FILE}: {exc}", where=str(row.get("path"))
            ) from exc
    bench: list[dict[str, Any]] = []
    if (release / BENCH).is_file():
        bench = cast(list[dict[str, Any]], json.loads((release / BENCH).read_text(encoding="utf-8")))
        read.append(release / BENCH)
    failures: dict[str, str] = {}
    if renders is not None and (renders / FAILURES).is_file():
        try:
            loaded = json.loads((renders / FAILURES).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise CliError("FEN-3004", f"--renders {FAILURES}: {exc}", where="--renders") from exc
        failures = {str(k): str(v) for k, v in cast(dict[str, Any], loaded).items()}
        read.append(renders / FAILURES)
    rows = visible_rows(index, records)
    unattributed = [
        issue("library.provenance-invalid", problem, where=str(row.get("path")))
        for row in rows
        for problem in attribution_problems(row, records.get(str(row.get("path")), {}))
    ]
    if unattributed:
        # A page may claim nothing its provenance does not say (change c0418): no fallback, no write.
        return Result(
            result={
                "release": index.get("version"),
                "out": Path(args.out).as_posix().rstrip("/"),
                "cards": [],
                "hidden": [],
                "placeholders": [],
                "provenance": [i.message for i in unattributed],
            },
            issues=tuple(unattributed),
            evidence=EVIDENCE,
            depends=depends_on(ctx.cwd, *sorted(set(read))),
        )
    drawn: dict[tuple[str, str], Media] = {}
    pages = {(str(r.get("kind")), str(r.get("id"))): str(r["gallery"]) for r in rows}
    for row in cast(list[dict[str, Any]], index.get("items", [])):
        if row.get("kind") in ("symbol", "footprint"):
            drawn[(str(row["kind"]), str(row.get("id")))] = _drawn(row, root, ctx, read)
    media: dict[str, Media] = {}
    for row in rows:
        kind = str(row.get("kind"))
        if kind in ("symbol", "footprint"):
            media[str(row.get("path"))] = drawn[(kind, str(row.get("id")))]
        elif kind == "device":
            media[str(row.get("path"))] = _device(row, drawn, pages)
        elif kind in RENDERED:
            media[str(row.get("path"))] = _rendered(row, root, renders, failures, read)
    files = site(index, records, fenolite_version=fenolite.__version__, bench=bench, media=media)
    out = Path(args.out).as_posix().rstrip("/")
    placeholders = [
        {"id": str(row.get("id")), "kind": str(row.get("kind")), "reason": item.missing}
        for row in rows
        if (item := media.get(str(row.get("path")))) is not None and item.missing is not None
    ]
    return Result(
        result={
            "release": index.get("version"),
            "out": out,
            "cards": [str(row["gallery"]) for row in rows],
            "hidden": sorted(
                str(r.get("id"))
                for r in cast(list[dict[str, Any]], index.get("items", []))
                if not r.get("gallery") or str(r.get("gallery")) not in files
            ),
            "placeholders": placeholders,
        },
        evidence=EVIDENCE,
        writes=tuple(PlannedWrite(f"{out}/{name}", data, KIND) for name, data in files.items()),
        depends=depends_on(ctx.cwd, *sorted(set(read))),
    )


__all__ = ["gallery_command"]
