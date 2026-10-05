# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The KiCad backend as seen through ``fenolite.backends.base``: detection, reading, writing, validation
and capabilities."""

# evidence: none, the facade of the registered backend: a read or a write returns its module's evidence

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fenolite.backends.base import (
    BoardFrame,
    BoardPad,
    CapabilityReport,
    DesignRules,
    DesignRulesSource,
    PlacedExtent,
    ProjectSet,
    ReadResult,
    Validation,
    Validator,
    WriteResult,
)
from fenolite.backends.kicad import pcb, versions
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design
from fenolite.model.presentation import DrawingSheet

SYMBOL_DIR_SUFFIX = ".kicad_symdir"

CAPABILITIES = CapabilityReport(
    name="kicad",
    read_kinds=("kicad_pcb", "kicad_mod", "kicad_sym"),
    write_kinds=(
        "kicad_pcb",
        "kicad_mod",
        "kicad_dru",
        "kicad_pro",
        "kicad_wks",
        "kicad_lib_table",
        "kicad_sch",
    ),
    targets=versions.TARGET_MAJORS,
    default_target=versions.DEFAULT_TARGET,
    downgrade="unsupported",
    operations=("detect", "read", "write", "lower", "validate"),
    evidence=Evidence.combine(pcb.EVIDENCE, pcb.WRITE_EVIDENCE),
)
"""The evidence is what ``read`` and ``write`` return for an arbitrary board, never a literal: a register
row may be stronger, because it states what its test covered (``backend-protocol``, "Capability reports")."""

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

    def board_pads(self, design: Design, *, issues: list[Issue] | None = None) -> tuple[BoardPad, ...]:
        """Every pad of the board in the board frame (``frame.board_pads``; ``BoardFrame`` protocol)."""
        from fenolite.backends.kicad import frame

        return frame.board_pads(design, issues=issues)

    def placed_extents(
        self, design: Design, *, issues: list[Issue] | None = None
    ) -> tuple[PlacedExtent, ...]:
        """Every footprint's courtyard in the board frame (``frame.placed_extents``)."""
        from fenolite.backends.kicad import frame

        return frame.placed_extents(design, issues=issues)

    def design_rules(
        self, design: Design, project: ProjectSet, *, issues: list[Issue] | None = None
    ) -> DesignRules:
        """The clearance rules of the project file and the rules file next to the board, applied to
        ``design`` (``copperrules.design_rules_from_texts``; ``DesignRulesSource`` protocol).

        Only ``<stem>.kicad_pro`` and ``<stem>.kicad_dru`` of the copy set are read. The major is the
        project file's, else the default target. A file that cannot be read is named in ``unread``.
        """
        from fenolite.backends.kicad import copperrules

        board = PurePosixPath(project.board)
        texts: dict[str, str | None] = {}
        unreadable: list[tuple[str, str]] = []
        for suffix in (".kicad_pro", ".kicad_dru"):
            name = board.with_suffix(suffix).as_posix()
            path = project.files.get(name)
            texts[suffix] = None
            if path is not None:
                try:
                    texts[suffix] = path.read_text(encoding="utf-8")
                except (OSError, UnicodeDecodeError) as error:
                    unreadable.append((PurePosixPath(name).name, str(error)))
        found = copperrules.design_rules_from_texts(
            design,
            project_text=texts[".kicad_pro"],
            rules_text=texts[".kicad_dru"],
            major=copperrules.project_major(texts[".kicad_pro"]),
            file_stem=board.stem,
            issues=issues,
        )
        if not unreadable:
            return found
        return DesignRules(
            found.design,
            found.min_clearance,
            found.rules_over_classes,
            found.floor_over_rules,
            found.opaque_clearance_rules,
            tuple(sorted((*found.unread, *unreadable))),
            found.evidence,
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

    def validate(self, path: Path, *, issues: list[Issue] | None = None) -> Validation:
        """Read a board once and check its same-version rebuild (RT1, ``roundtrip.rt1``).

        The reader's ``FormatError`` is raised unchanged; any other kind raises ``ValueError``.
        """
        from fenolite.backends.kicad.roundtrip import rt1

        kind = _kind(path)
        if kind is not versions.FileKind.BOARD:
            what = kind.value if kind is not None else "an unknown kind"
            raise ValueError(f"{path.name!r} is {what}; only a KiCad board can be validated")
        read = self.read(path, issues=issues)  # raises the reader's FormatError, invalid UTF-8 included
        return Validation(read, rt1(path.read_bytes().decode("utf-8"), file=path.name))

    def capabilities(self) -> CapabilityReport:
        return CAPABILITIES


_VALIDATOR: Validator = KicadBackend()
"""The KiCad backend satisfies ``Validator`` (checked by pyright)."""
_FRAME: BoardFrame = KicadBackend()
"""The KiCad backend satisfies ``BoardFrame`` (checked by pyright)."""
_RULES_SOURCE: DesignRulesSource = KicadBackend()
"""The KiCad backend satisfies ``DesignRulesSource`` (checked by pyright)."""


__all__ = ["CAPABILITIES", "SYMBOL_DIR_SUFFIX", "KicadBackend"]
