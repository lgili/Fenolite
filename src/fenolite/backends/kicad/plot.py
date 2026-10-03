# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review views of a board through ``kicad-cli`` (capability manufacturing-exports, "Render views"; facts:
``docs/formats/kicad/cli.md``, "Exports and renders").

Two SVG plots (``pcb export svg``) and two rendered PNG images (``pcb render``). A view is a review
artefact, never a verdict: a view that cannot be produced is reported, and nothing else changes.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Literal

from fenolite.backends.kicad.cli import RENDER_DIR, CliRun, KicadCli
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-EXPORT-RENDER",))
"""``KICAD-VERIFIED``: ``H-K-EXPORT-RENDER`` holds on 9.0.9 and 10.0.6 (c0024 task 6.2)."""
DEFAULT_WIDTH = 1600
DEFAULT_HEIGHT = 1200
FRONT_LAYERS = ("F.Cu", "F.SilkS", "F.Fab", "Edge.Cuts")
BACK_LAYERS = ("B.Cu", "B.SilkS", "B.Fab", "Edge.Cuts")


@dataclass(frozen=True, slots=True)
class View:
    """A review view: its file name, its kind and the side it shows."""

    name: str
    kind: Literal["svg", "png"]
    side: Literal["top", "bottom"]


VIEWS: Mapping[str, View] = MappingProxyType(
    {
        "front.svg": View("front.svg", "svg", "top"),
        "back.svg": View("back.svg", "svg", "bottom"),
        "top.png": View("top.png", "png", "top"),
        "bottom.png": View("bottom.png", "png", "bottom"),
    }
)


def svg_arguments(view: View) -> list[str]:
    """``pcb export svg`` for one side, as one file: the back view is mirrored."""
    layers = FRONT_LAYERS if view.side == "top" else BACK_LAYERS
    args = ["pcb", "export", "svg", "--mode-single", "--layers", ",".join(layers)]
    if view.side == "bottom":
        args.append("--mirror")
    return [*args, "-o", f"{RENDER_DIR}/{view.name}"]


def _first_line(run: CliRun) -> str:
    lines = [line.strip() for line in (run.stderr or run.stdout).splitlines() if line.strip()]
    return lines[0].replace("<tmp>/", "").replace("<tmp>", ".") if lines else ""


def plot_view(
    cli: KicadCli,
    name: str,
    board: Path,
    files: Mapping[str, Path],
    *,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
) -> tuple[bytes | None, str]:
    """``(data, message)`` for the view ``name`` of a copy of ``board``: the file's bytes, or ``None`` and
    why (a timeout, a non-zero exit, no file)."""
    view = VIEWS[name]
    if view.kind == "svg":
        run = cli.export(svg_arguments(view), board, files=files, out=RENDER_DIR)
        produced = f"{RENDER_DIR}/{view.name}"
    else:
        run = cli.render(board, side=view.side, width=width, height=height, files=files)
        produced = f"{RENDER_DIR}/{view.side}.png"
    if run.outcome == "timeout":
        return None, f"kicad-cli timed out after {cli.timeout:g} s"
    data = run.outputs.get(produced)
    if run.returncode != 0 or not data:
        return None, f"exit {run.returncode}: {_first_line(run) or 'kicad-cli wrote no file'}"
    return data, ""


def view_digest(name: str, data: bytes) -> str:
    """The SHA-256 of a view for comparing two plots: an SVG without its ``<title>`` line, where
    ``kicad-cli`` 9.0 writes the date; a PNG as it is."""
    if VIEWS[name].kind == "svg":
        lines = data.splitlines(keepends=True)
        data = b"".join(line for line in lines if not line.lstrip().startswith(b"<title>"))
    return hashlib.sha256(data).hexdigest()


def png_size(data: bytes) -> tuple[int, int] | None:
    """``(width, height)`` from a PNG's header, or ``None`` when ``data`` is no PNG."""
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


__all__ = [
    "BACK_LAYERS",
    "DEFAULT_HEIGHT",
    "DEFAULT_WIDTH",
    "EVIDENCE",
    "FRONT_LAYERS",
    "VIEWS",
    "View",
    "plot_view",
    "png_size",
    "svg_arguments",
    "view_digest",
]
