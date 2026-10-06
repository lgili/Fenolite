# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Extraction: the placements of a board, read back for the source tree (``docs/lens.md``, "sync").

In the lens vocabulary the board is the complement and the script is the view: ``extract_placements`` reads
out of the board what ``placements.toml`` holds. Pure, and without geometry.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.lens.placements import SourcePlacement
from fenolite.lens.preserve import LayoutMatch, off_board
from fenolite.model.design import Design


@dataclass(frozen=True)
class Extracted:
    """``placements``: component path → placement in the written frame, in path order. ``unplaced``: the
    matched parts whose footprint is off the board, which stay out of the file so they are staged again."""

    placements: Mapping[str, SourcePlacement]
    unplaced: tuple[str, ...] = ()


def extract_placements(board: Design, match: LayoutMatch, *, design: Design) -> Extracted:
    """The placement of every matched footprint that lies on the board. Orphans and board-only footprints
    are not extracted."""
    placements: dict[str, SourcePlacement] = {}
    unplaced: list[str] = []
    for path, found in sorted(match.matches.items()):
        fp = found.footprint
        if off_board(fp, design, board):
            unplaced.append(path)
            continue
        placements[path] = SourcePlacement(fp.position, fp.rotation, fp.side, fp.locked)
    return Extracted(MappingProxyType(placements), tuple(unplaced))


__all__ = ["Extracted", "extract_placements"]
