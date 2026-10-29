# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden SVG assertions never update their references."""

from __future__ import annotations

import shlex
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from pathlib import Path
from urllib.parse import quote

from fenolite.analysis.boundary import board_boundary
from fenolite.analysis.copper import copper_layers
from fenolite.analysis.pour import pour_copper
from fenolite.analysis.region import Region, draw_region, mm, whole_region
from fenolite.cli._region import parse_region
from fenolite.testing.design import DEFAULT_TIMESTAMP, TestingError, load
from fenolite.testing.svgdiff import compare


def assert_render(
    path: str | Path,
    golden: str | Path,
    *,
    net: str | Sequence[str] = (),
    region: str | Region | tuple[int, int, int, int] | None = None,
    layers: Sequence[str] | None = None,
    seed: int = 0,
    timestamp: str = DEFAULT_TIMESTAMP,
) -> None:
    """Compare canonical model SVG bytes; on failure show a bounded, keyed diff and review commands."""
    highlighted = tuple(sorted(set((net,) if isinstance(net, str) else net)))
    with load(path, seed=seed, timestamp=timestamp) as design:
        board = design.board
        assert board.design.board is not None
        for name in highlighted:
            design.net(name)
        if layers is not None:
            for layer in layers:
                if layer not in copper_layers(board.design.board):
                    raise TestingError(f"unknown copper layer {layer!r}")
        boundary = board_boundary(board.design.board)
        rect = (
            parse_region(region)
            if isinstance(region, str)
            else Region(*region)
            if isinstance(region, tuple)
            else region or whole_region(boundary)
        )
        pour = pour_copper(board.design, pads=board.pads, boundary=boundary)
        data = draw_region(
            board.design,
            region=rect,
            pads=board.pads,
            boundary=boundary,
            pour=pour,
            highlight=highlighted,
            layers=layers,
        ).svg
    reference = Path(golden)
    previous = reference.read_bytes() if reference.is_file() else b""
    if previous == data:
        return
    try:
        diff = compare(previous, data)
    except (ET.ParseError, UnicodeError) as error:
        raise TestingError(f"invalid golden {reference}: {error}") from error
    args = ["fenolite", "render", str(path)]
    for name in highlighted:
        args += [f"--net={name}"]
    if region is not None or not highlighted:
        args += ["--region=" + ",".join(mm(v) + "mm" for v in (rect.x0, rect.y0, rect.x1, rect.y1))]
    if layers is not None:
        args += ["--layers", ",".join(layers)]
    args += ["--seed", str(seed), "--timestamp", timestamp, "-o", str(reference.parent)]
    command = shlex.join(args)
    filename = (
        "net-" + quote(highlighted[0], safe="") + ".svg"
        if len(highlighted) == 1
        else "nets.svg"
        if highlighted
        else "region.svg"
    )
    extra = (
        ""
        if reference.name == filename
        else f"\nThe renderer writes {reference.parent / filename}; after review, rename it to {reference}."
    )
    version = ""
    if previous and ET.fromstring(previous).get("data-render") != ET.fromstring(data).get("data-render"):
        version = "\nRender version differs; review the style change."
    raise TestingError(
        f"golden {reference} {'is missing' if not previous else 'differs'} "
        f"({diff.added} added, {diff.removed} removed, {diff.changed} changed; "
        f"first 20 lines shown){version}\n"
        + "\n".join(diff.lines)
        + f"\nregenerate after review:\n  {command} --dry-run\n  {command} --confirm --plan <plan_id>"
        + extra
    )
