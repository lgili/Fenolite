# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.equivalent``: whether two designs are equivalent, level by level (capability
design-equivalence, "Public equivalence API", "Public equivalence API inputs" and "Public API errors and
effects"; change c0158).

The function reads its two sides as ``fenolite equivalent`` does (``sides.py``), runs
``checks.equivalence.compare_designs`` and returns an ``EquivalenceResult`` whose ``to_json()`` is the
command's ``result``. It writes no file and runs no tool unless ``against`` is given or a schematic side
needs ``kicad-cli``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fenolite.api.sides import (
    DEFAULT_TIMEOUT,
    ReadSide,
    SideUsageError,
    existing,
    import_tool,
    imported,
    read_side,
)
from fenolite.backends.kicad import altium_import
from fenolite.checks.equivalence import (
    LEVEL_NAMES,
    LEVELS,
    EquivalenceReport,
    Profile,
    Tolerances,
    compare_designs,
    difference_issues,
    load_profiles,
    max_level,
    select_profile,
)
from fenolite.checks.equivalence import codes as equivalence_codes
from fenolite.checks.equivalence.model import FRAMES, Difference, Frame
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

AGAINST = ("kicad-import",)
"""The oracles ``against`` names: the board that ``kicad-cli pcb import`` converts side ``a`` to."""
PCB_DOCUMENT = ".pcbdoc"
TOLERANCE_FIELDS = ("length_nm", "angle_udeg", "length_ppm")
SideInput = str | Path | Design
"""A side: a path of any side the command reads, or a design."""


@dataclass(frozen=True, slots=True)
class Side:
    """What the reply says of one side: its name (no folder), the SHA-256 of a file (``None`` for a folder,
    a design and the triangle's import), the backend, the input kind, the netlist source (``board``,
    ``circuit`` or ``schematic``), the counts of components and footprints, the ``kicad-cli`` version of
    the triangle's side ``b``, and for a schematic side the number of its power symbols."""

    name: str
    sha256: str | None
    backend: str
    kind: str
    netlist_source: str
    components: int
    footprints: int
    tool_version: str | None = None
    power_symbols: int | None = None

    def to_json(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "path": self.name,
            "sha256": self.sha256,
            "backend": self.backend,
            "netlist_source": self.netlist_source,
            "components": self.components,
            "footprints": self.footprints,
        }
        if self.tool_version is not None:
            row["tool_version"] = self.tool_version
        if self.power_symbols is not None:
            row["power_symbols"] = self.power_symbols
        return row


@dataclass(frozen=True, slots=True)
class EquivalenceResult:
    """A comparison: the report (``None`` when the triangle's converter gave no board, so no level ran),
    the two sides (``b`` ``None`` in that case), the exclusion profile applied, the issues in the command's
    order and the evidence."""

    report: EquivalenceReport | None
    a: Side
    b: Side | None
    profile: Profile | None
    issues: tuple[Issue, ...]
    evidence: Evidence
    tool_version: str | None = None
    """The ``kicad-cli`` version of a triangle whose converter gave no board."""

    @property
    def equivalent(self) -> bool:
        return self.report is not None and self.report.equivalent

    def to_json(self) -> dict[str, Any]:
        """The ``result`` of ``fenolite equivalent`` (schema ``fenolite.equivalent.v0``)."""
        if self.report is None:
            return {
                "level": 0,
                "equivalent": False,
                "sides": {"a": self.a.to_json(), "b": None},
                "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0},
                "frame": "relative",
                "translation": [0, 0],
                "levels": [],
                "differences": [],
                "notices": [],
                "excluded": [],
                "profile": None,
                "tool_version": self.tool_version,
            }
        report, profile = self.report, self.profile
        assert self.b is not None
        return {
            "level": report.levels[-1].level,
            "equivalent": report.equivalent,
            "sides": {"a": self.a.to_json(), "b": self.b.to_json()},
            "tolerances": {
                "length_nm": report.tolerances.length_nm,
                "angle_udeg": report.tolerances.angle_udeg,
                "length_ppm": report.tolerances.length_ppm,
            },
            "frame": report.frame,
            "translation": [report.translation.x, report.translation.y],
            "levels": [
                {
                    "level": level.level,
                    "name": LEVEL_NAMES[level.level],
                    "compared": level.compared,
                    "differences": len(level.differences),
                    "excluded": len(level.excluded),
                    "notices": len(level.notices),
                    "summary": dict(level.summary),
                }
                for level in report.levels
            ],
            "differences": [_row(difference) for difference in report.differences],
            "notices": [_row(notice) for notice in report.notices],
            "excluded": [{**_row(found.difference), "rule": found.rule_id} for found in report.excluded],
            "profile": None
            if profile is None
            else {"name": profile.name, "tool_version": profile.tool_version, "rules": len(profile.rules)},
        }


def _row(difference: Difference) -> dict[str, Any]:
    return {
        "level": difference.level,
        "kind": difference.kind,
        "where": difference.where,
        "field": difference.field,
        "a": difference.a,
        "b": difference.b,
    }


def public_side(side: ReadSide) -> Side:
    """The reply's view of a side as read."""
    board = side.design.board
    footprints = len(board.footprints) if board is not None else 0
    source = side.netlist_source or ("board" if footprints else "circuit")
    return Side(
        side.name, side.sha256, side.backend, side.kind, source, len(side.design.circuit.components),
        footprints, side.tool_version, side.power_symbols,
    )  # fmt: skip


def _import_messages(messages: tuple[str, ...]) -> list[Issue]:
    counts = Counter(messages)
    return [
        equivalence_codes.issue("equiv.import-message", f"kicad-cli pcb import, {count} time(s): {text}")
        for text, count in sorted(counts.items())
    ]


def _tolerances(given: Tolerances | Mapping[str, int] | None, profile: Profile | None) -> Tolerances:
    """``given`` itself, or the values a mapping names over the profile's (else 0)."""
    if isinstance(given, Tolerances):
        return given
    named = dict(given or {})
    unknown = sorted(set(named) - set(TOLERANCE_FIELDS))
    if unknown:
        raise SideUsageError(f"tolerances has no field {unknown[0]!r}", where="tolerances")
    values = {
        "length_nm": profile.tolerance_nm if profile else 0,
        "angle_udeg": profile.tolerance_udeg if profile else 0,
        "length_ppm": profile.tolerance_ppm if profile else 0,
    }
    values.update(named)
    try:
        return Tolerances(**values)
    except (TypeError, ValueError) as error:
        raise SideUsageError(str(error), where="tolerances") from None


def _path(given: str | Path) -> Path:
    return existing(Path(given))


def equivalent(
    a: SideInput,
    b: SideInput | None,
    *,
    level: int | None = None,
    tolerances: Tolerances | Mapping[str, int] | None = None,
    frame: Frame | None = None,
    ignore_refs: Sequence[str] = (),
    profile: Profile | None = None,
    against: str | None = None,
    kicad_cli: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> EquivalenceResult:
    """Compare ``a`` with ``b`` (capability design-equivalence, "Public equivalence API").

    ``a`` and ``b`` are paths of any side ``fenolite equivalent`` reads, or designs; ``b`` is ``None``
    exactly when ``against`` is ``"kicad-import"``, and side ``b`` is then the board ``kicad-cli pcb import``
    converts the Altium PCB document ``a`` to, compared under the importer's exclusion profile. ``level``
    ``None`` runs the highest level both sides hold. ``tolerances`` is a ``Tolerances``, or a mapping of
    the fields to set over the profile's values (else 0); ``frame`` ``None`` is the profile's frame, else
    ``absolute`` (``relative`` for the triangle).

    A usage fault raises ``SideUsageError``, a ``ValueError``; a missing path ``SideMissingError``; a
    reader's error keeps its type and code; a missing or wrong ``kicad-cli`` raises ``ToolMissingError`` or
    ``ToolMajorError``.
    """
    if against is not None and against not in AGAINST:
        raise SideUsageError(f"against is one of {', '.join(AGAINST)}, got {against!r}", where="against")
    if (b is None) == (against is None):
        raise SideUsageError("give b or against='kicad-import', not both and not neither", where="b")
    if level is not None and (type(level) is not int or level not in LEVELS):
        raise SideUsageError(f"level is one of {', '.join(map(str, LEVELS))}, got {level!r}", where="level")
    if frame is not None and frame not in FRAMES:
        raise SideUsageError(f"frame is one of {', '.join(FRAMES)}, got {frame!r}", where="frame")
    notices: list[Issue] = []
    if against is None:
        assert b is not None
        side_a = read_side(a, kicad_cli=kicad_cli, timeout=timeout)
        side_b = read_side(b, kicad_cli=kicad_cli, timeout=timeout)
        applied = profile
        chosen_frame: Frame = frame or (profile.frame if profile else "absolute")
    else:
        if profile is not None:
            raise SideUsageError(
                "against='kicad-import' uses the importer's own profile; profile does not apply",
                where="profile",
            )
        if isinstance(a, Design):
            raise SideUsageError(
                "against='kicad-import' compares an Altium PCB document, not a design", where="a"
            )
        source = _path(a)
        if not source.is_file() or source.suffix.lower() != PCB_DOCUMENT:
            raise SideUsageError(
                f"against='kicad-import' compares an Altium PCB document, and {source.name} is none",
                where=source.name,
                hint="pass a .PcbDoc file",
            )
        cli = import_tool(kicad_cli, timeout)
        side_a = read_side(source)
        found = imported(cli, source, side_a.name)
        if isinstance(found, Issue):
            evidence = Evidence(side_a.evidence.level, altium_import.ORACLE, side_a.evidence.hypotheses)
            return EquivalenceResult(
                None, public_side(side_a), None, None, (found, *side_a.issues), evidence, cli.version()
            )
        side_b = found
        version = cli.version()
        profiles = load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)
        applied = select_profile(profiles, altium_import.PROFILE, version)
        if applied is None:
            notices.append(
                equivalence_codes.issue(
                    "equiv.no-exclusion-profile",
                    f"no exclusion profile for kicad-cli {version}: the comparison ran with no rule, in the "
                    "relative frame and without tolerance",
                )
            )
        chosen_frame = frame or (applied.frame if applied else "relative")
    chosen = _tolerances(tolerances, applied)
    try:
        report = compare_designs(
            side_a.design,
            side_b.design,
            level=max_level(side_a.design, side_b.design) if level is None else level,
            tolerances=chosen,
            frame=chosen_frame,
            ignore_refs=tuple(ignore_refs),
            rules=applied.rules if applied else (),
        )
    except ValueError as error:
        raise SideUsageError(str(error), where="level") from None
    notices += _import_messages(side_b.messages)
    evidence = Evidence.combine(side_a.evidence, side_b.evidence)
    if against is not None:
        evidence = Evidence(evidence.level, altium_import.ORACLE, evidence.hypotheses)
    return EquivalenceResult(
        report,
        public_side(side_a),
        public_side(side_b),
        applied,
        (*difference_issues(report), *notices, *side_a.issues, *side_b.issues),
        evidence,
    )


__all__ = ["AGAINST", "EquivalenceResult", "Side", "SideInput", "equivalent", "public_side"]
