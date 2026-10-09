# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What a direction of conversion is and what its writer returns (capability design-conversion,
"Conversion package"; change c0159). The registry of directions is ``fenolite.convert.DIRECTIONS``."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Literal

from fenolite.convert.report import ConversionReport
from fenolite.convert.sources import SourceProject
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence
from fenolite.model.design import Design

Target = Literal["kicad", "altium"]
TARGETS: tuple[Target, ...] = ("altium", "kicad")
BODIES = ("extruded", "off")


@dataclass(frozen=True, slots=True)
class Options:
    """What a conversion is asked for besides its source: the KiCad major of a KiCad target, what to do
    with component bodies in an Altium target, and the stem of the written files (``None``: the
    source's)."""

    kicad_version: int = 10
    bodies: str = "extruded"
    name: str | None = None


@dataclass(frozen=True, slots=True)
class Written:
    """What a direction's writer returns: the files of the target project by name, the report, the design
    it wrote (the ids of the report are its ids), the writer's own issues, and the name of the file that
    the target backend reads back to verify the conversion."""

    files: Mapping[str, bytes]
    report: ConversionReport
    design: Design
    read_back: str
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class Direction:
    """One registered direction: the source and target backends, the writer, the evidence of its writes,
    whether it is experimental, the name of its verification profile (``data/profiles.toml``), the KiCad
    majors a KiCad target is written for, and the kinds its writer can name in a report."""

    source: str
    target: Target
    write: Callable[[SourceProject, Options], Written]
    evidence: Evidence
    experimental: bool
    profile: str
    targets: tuple[int, ...] = ()
    kinds: tuple[str, ...] = field(default=())

    def to_json(self) -> dict[str, object]:
        """The entry of ``capabilities.conversions``."""
        return {
            "from": self.source,
            "to": self.target,
            "targets": list(self.targets),
            "experimental": self.experimental,
            "evidence": {
                "level": self.evidence.level.value,
                "oracle": self.evidence.oracle,
                "hypotheses": list(self.evidence.hypotheses),
            },
        }


class TargetLimitError(FenoliteError):
    """The target writer cannot hold the design at all (an Altium document larger than a compound file
    without DIFAT sectors): nothing is converted, with or without consent to losses."""

    cli_code = "FEN-7001"

    def __init__(self, message: str, *, hint: str = "") -> None:
        self.hint = hint
        super().__init__(message)


__all__ = [
    "BODIES",
    "TARGETS",
    "Direction",
    "Options",
    "Target",
    "TargetLimitError",
    "Written",
]
