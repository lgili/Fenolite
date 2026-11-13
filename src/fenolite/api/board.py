# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed reads and analyses of a board (capability python-api, "Typed design and board reads" and "Typed
board analyses"; change c0206; ``docs/api.md``).

Each function returns the records of the package that computes it, never a dictionary: ``read_design``
the ``ReadSide`` that ``equivalent`` compares, ``read_board`` a ``Board`` with its board-frame pads,
``connectivity`` the ``ConnectivityReport`` of ``fenolite.analysis.connectivity``, and ``analyze_current``
and ``analyze_distances`` the ``AnalysisReport`` of ``fenolite.analysis``. The analyses take a ``Board`` or
the path of one and measure with the defaults of ``fenolite analyze``. Nothing is written and no process
is started.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeAlias

from fenolite.analysis.boundary import OVERLAP_NEEDS_GEO, board_boundary
from fenolite.analysis.connectivity import ConnectivityReport, NetIsland, net_islands
from fenolite.analysis.connectivity import connectivity as net_connectivity
from fenolite.analysis.current import analyze_current as current_report
from fenolite.analysis.distance import analyze_distances as distance_report
from fenolite.analysis.report import AnalysisReport
from fenolite.analysis.requirements import Requirements, load_requirements
from fenolite.api.sides import (
    DEFAULT_TIMEOUT,
    ReadSide,
    SideError,
    SideUsageError,
    existing,
    notices,
    read_side,
)
from fenolite.backends import registry
from fenolite.backends.base import BoardFrame, BoardPad
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm
from fenolite.geometry.errors import BACKEND_UNAVAILABLE
from fenolite.model.design import Design

if TYPE_CHECKING:
    from fenolite.backends.altium.edit.session import Session

PathInput = str | os.PathLike[str]
"""A path as ``str`` or ``Path``."""
GEO_HINT = "pip install 'fenolite[geo]'"


class ExtraMissingError(SideError):
    """An analysis needs an extra that is not installed (``FEN-6001``): the union of overlapping cut-outs
    and slots of a board outline needs ``geo``."""

    cli_code = "FEN-6001"


@dataclass(frozen=True, slots=True)
class Board:
    """A board as read: the file name, its SHA-256, the backend, the design, the board-frame pads
    (``None`` when the backend gives no board frame), the reader's warnings and infos (it raises its
    errors) and the evidence of the reading."""

    name: str
    sha256: str
    backend: str
    design: Design
    pads: tuple[BoardPad, ...] | None
    issues: tuple[Issue, ...]
    evidence: Evidence


BoardInput: TypeAlias = "Board | PathInput | Session"
"""A ``Board``, the path of a board, a KiCad project file or a project folder, or an Altium edit
``Session`` (its pending edits; change c0501)."""
ISSUE_CODES: dict[str, Severity] = {"api.pending-edit": "info"}
"""The codes of a board read (change c0501)."""


def read_design(
    path: PathInput, *, kicad_cli: str | None = None, timeout: float = DEFAULT_TIMEOUT
) -> ReadSide:
    """The design at ``path``, read as ``fenolite equivalent`` reads a side: a board or document any backend
    reads, a KiCad project or folder resolved to its board, a root KiCad schematic with its sheets, or a
    ``.fenolite/`` folder of a built design. ``kicad_cli`` and ``timeout`` serve a schematic that needs
    the tool. Raises ``SideMissingError`` for a missing path and ``SideUsageError`` (a ``ValueError``) for
    one no backend reads or a library; a reader's error keeps its type."""
    return read_side(os.fspath(path), kicad_cli=kicad_cli, timeout=timeout)


def read_board(path: PathInput | Session) -> Board:
    """The board at ``path`` (a board file, a KiCad project file or a project folder) with its board-frame
    pads, or the board of the pending edits of an Altium edit ``Session`` (change c0501). Raises
    ``SideMissingError`` for a missing path and ``SideUsageError`` for a file that is not a board or a
    refused queue; a reader's error keeps its type."""
    from fenolite.backends.altium.edit.session import Session

    if isinstance(path, Session):
        return _pending(path)
    given = existing(Path(os.fspath(path)))
    board = resolve_board(given) if given.is_dir() or given.suffix == ".kicad_pro" else given
    backend = registry.for_path(board)
    if backend is None:
        raise SideUsageError(f"no backend reads {board.name}", where=board.name, hint="pass a board file")
    found: list[Issue] = []
    read = backend.read(board, issues=found)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise SideUsageError(f"{board.name} is not a board", where=board.name, hint="pass a board file")
    pads = backend.board_pads(design, issues=found) if isinstance(backend, BoardFrame) else None
    digest = hashlib.sha256(board.read_bytes()).hexdigest()
    return Board(board.name, digest, backend.name, design, pads, notices(found), read.evidence)


def _pending(session: Session) -> Board:
    """The board of ``Session.pending()`` (change c0501, design D1): read from the bytes a commit would
    write, with ``api.pending-edit`` naming the number of queued operations."""
    from fenolite.backends.altium.backend import AltiumBackend

    name = session.path.name
    data, refused = session.pending()
    if data is None:
        message = "; ".join(i.message for i in refused) or "the queued edits are refused"
        raise SideUsageError(message, where=name, hint="read the session's issues")
    backend = AltiumBackend()
    found: list[Issue] = []
    read = backend.board_from_bytes(data, file=name, issues=found)
    design = read.content
    if not isinstance(design, Design) or design.board is None:
        raise SideUsageError(f"{name} is not a board", where=name, hint="pass a board file")
    pads = backend.board_pads(design, issues=found)
    count = len(session.queued)
    found.append(Issue("api.pending-edit", "info", f"the board of {name} with {count} queued edits", name))
    digest = hashlib.sha256(data).hexdigest()
    return Board(name, digest, backend.name, design, pads, notices(found), read.evidence)


def _board(given: Any) -> Board:
    return given if isinstance(given, Board) else read_board(given)


def _requirements(given: Requirements | PathInput | None) -> Requirements | None:
    """The requirements given, or those of the TOML file at a path (``FormatError`` names the key)."""
    if given is None or isinstance(given, Requirements):
        return given
    path = existing(Path(os.fspath(given)))
    return load_requirements(path.read_text(encoding="utf-8"), file=path.name)


def connectivity(board: BoardInput, *, nets: Collection[str] | None = None) -> ConnectivityReport:
    """The islands and the open connections of each net of the board, as ``fenolite net`` and ``fenolite
    ready`` count them; ``nets`` limits the report to the nets of those names."""
    read = _board(board)
    return net_connectivity(read.design, pads=read.pads, nets=nets)


def islands(
    board: BoardInput, *, nets: Collection[str] | None = None, without: Collection[str] = ()
) -> dict[str, tuple[NetIsland, ...]]:
    """The counted islands of each net with their members (``analysis.connectivity.net_islands``);
    ``without`` names tracks, arcs, vias or zones (model id,
    native id or locator) whose copper is left out first, and an unknown name raises ``KeyError`` (change
    c0500). Saved fills are not poured again after a cut."""
    read = _board(board)
    return net_islands(read.design, pads=read.pads, nets=nets, without=without)


def analyze_current(
    board: BoardInput,
    *,
    temp_rise_mk: int | None = None,
    copper_thickness: Mapping[str, Nm] | None = None,
    via_plating: Nm | None = None,
    requirements: Requirements | PathInput | None = None,
) -> AnalysisReport:
    """The current capacity of each track, arc and via, as ``fenolite analyze --kinds current`` measures it:
    ``temp_rise_mk`` in millikelvin, thicknesses in nanometres per copper layer, ``requirements`` the
    user's rows or the path of their TOML file. Fenolite assumes no value the board does not hold."""
    read = _board(board)
    return current_report(
        read.design,
        temp_rise_mk=temp_rise_mk,
        copper_thickness=copper_thickness,
        via_plating=via_plating,
        requirements=_requirements(requirements),
    )


def analyze_distances(
    board: BoardInput,
    *,
    pairs: Sequence[tuple[str, str]] = (),
    within: Nm | None = None,
    requirements: Requirements | PathInput | None = None,
    board_thickness: Nm | None = None,
    groove: Nm | None = None,
    insulation: bool = False,
) -> AnalysisReport:
    """The gaps, the clearance and the creepage between pairs of nets, as ``fenolite analyze --kinds
    clearance,creepage`` measures them, and with ``insulation`` the distance through the laminate. The
    options are those of the command, lengths in nanometres. Raises ``ExtraMissingError`` when the
    board's cut-outs overlap and the ``geo`` extra is not installed."""
    read = _board(board)
    assert read.design.board is not None  # a Board holds a board
    boundary = board_boundary(read.design.board, thickness=board_thickness)
    if boundary.problem == OVERLAP_NEEDS_GEO:
        raise ExtraMissingError(
            f"{BACKEND_UNAVAILABLE}: the cut-outs and slots of the board outline overlap, and their union "
            "needs the geo extra",
            where=BACKEND_UNAVAILABLE,
            hint=GEO_HINT,
        )
    return distance_report(
        read.design,
        pads=read.pads,
        boundary=boundary,
        pairs=pairs,
        within=within,
        requirements=_requirements(requirements),
        groove=groove,
        insulation=insulation,
    )


__all__ = [
    "Board",
    "BoardInput",
    "ExtraMissingError",
    "PathInput",
    "analyze_current",
    "analyze_distances",
    "connectivity",
    "read_board",
    "read_design",
]
