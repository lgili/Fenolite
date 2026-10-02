# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad backend as seen through ``fenolite.backends.base``: detection, reading, writing and
capabilities."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.base import CapabilityReport, ReadResult, WriteResult
from fenolite.backends.kicad import versions
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.presentation import DrawingSheet

SYMBOL_DIR_SUFFIX = ".kicad_symdir"

CAPABILITIES = CapabilityReport(
    name="kicad",
    read_kinds=("kicad_pcb", "kicad_mod", "kicad_sym"),
    write_kinds=("kicad_pcb", "kicad_mod", "kicad_dru", "kicad_pro", "kicad_wks"),
    targets=versions.TARGET_MAJORS,
    default_target=versions.DEFAULT_TARGET,
    downgrade="unsupported",
    operations=("detect", "read", "write", "lower"),
    evidence=Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ", "H-K-PCB-WRITE")),
)

_READ_KINDS = frozenset({versions.FileKind.BOARD, versions.FileKind.FOOTPRINT, versions.FileKind.SYMBOL_LIB})


def _kind(path: Path) -> versions.FileKind | None:
    if path.suffix == SYMBOL_DIR_SUFFIX:
        return versions.FileKind.SYMBOL_LIB
    kind = versions.kind_for_suffix(path.name)
    return kind if kind in _READ_KINDS else None


class KicadBackend:
    """KiCad files read by Fenolite's own readers (``kicad-cli`` is an oracle, never a dependency)."""

    name = "kicad"

    def detect(self, path: Path) -> bool:
        """True for a board, a footprint file, a symbol library file or a symbol folder (by name)."""
        return _kind(path) is not None

    def read(self, path: Path, *, issues: list[Issue] | None = None) -> ReadResult:
        """Read a board into a ``Design``, or a library file into a ``Library``."""
        from fenolite.backends.kicad import mod, sym
        from fenolite.model.library import Library

        kind = _kind(path)
        found: list[Issue] = []
        if kind is versions.FileKind.FOOTPRINT:
            footprint = mod.read_footprint(path, issues=found)
            result = ReadResult(
                Library(name=footprint.library, footprints=(footprint,)), tuple(found), mod.EVIDENCE
            )
        elif kind is versions.FileKind.SYMBOL_LIB:
            symbols = sym.read_symbol_library(path, issues=found)
            name = path.stem
            result = ReadResult(Library(name=name, symbols=symbols), tuple(found), sym.EVIDENCE)
        elif kind is versions.FileKind.BOARD:
            from fenolite.backends.kicad import pcb

            design = pcb.read_board(path, issues=found)
            result = ReadResult(design, (*found, *design.validate()), pcb.EVIDENCE)
        else:
            raise ValueError(f"{path.name!r} is not a KiCad board, footprint or symbol library")
        if issues is not None:
            issues.extend(found)
        return result

    def write(self, design: Design, *, target: int | None = None, allow_lossy: bool = False) -> WriteResult:
        """The design's board as ``.kicad_pcb`` text for ``target`` (the default target when ``None``).

        Nothing is written to disk; see ``pcb.write_board`` for the errors.
        """
        from fenolite.backends.kicad import pcb

        chosen = CAPABILITIES.default_target if target is None else target
        assert chosen is not None
        return pcb.write_board(design, target=chosen, allow_lossy=allow_lossy)

    def lower(
        self,
        design: Design,
        *,
        name: str,
        target: int | None = None,
        existing_project: str | None = None,
        allow_lossy: bool = False,
        issues: list[Issue] | None = None,
    ) -> dict[str, str]:
        """The coherent set (board, project, rules) of ``design``: ``triad.write_triad``'s files.

        ``target=None`` means the default target; nothing is written to disk.
        """
        from fenolite.backends.kicad.triad import write_triad

        chosen = CAPABILITIES.default_target if target is None else target
        assert chosen is not None
        return write_triad(
            design,
            name=name,
            target=chosen,
            existing_project=existing_project,
            allow_lossy=allow_lossy,
            issues=issues,
        )

    def write_sheet(
        self, sheet: DrawingSheet, *, target: int | None = None, allow_lossy: bool = False
    ) -> WriteResult:
        """``sheet`` as ``.kicad_wks`` text (``wks.write_drawing_sheet``); ``target=None`` means the default
        target, which selects the emit check only."""
        from fenolite.backends.kicad.wks import write_drawing_sheet

        chosen = CAPABILITIES.default_target if target is None else target
        assert chosen is not None
        return write_drawing_sheet(sheet, target=chosen, allow_lossy=allow_lossy)

    def capabilities(self) -> CapabilityReport:
        return CAPABILITIES


__all__ = ["CAPABILITIES", "SYMBOL_DIR_SUFFIX", "KicadBackend"]
