# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The equivalence triangle for the oracle tests (capability design-equivalence, "Triangle evidence over
the corpus"; change c0045): one PCB document read by Fenolite's Altium backend and by ``kicad-cli pcb
import`` followed by the KiCad reader, compared under the importer's exclusion profile."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest
from _resources import kicad_cli

from fenolite.backends import registry
from fenolite.backends.kicad import altium_import
from fenolite.backends.kicad.cli import KicadCliError, cli_for
from fenolite.checks.equivalence import (
    EquivalenceReport,
    Profile,
    Tolerances,
    compare_designs,
    levels,
    load_profiles,
    norm,
    select_profile,
)
from fenolite.model.board import FootprintInstance, Pad
from fenolite.model.design import Design

KNOWN_IMPORT_FAILURES: dict[str, tuple[int, str]] = {
    # The Linux build of kicad-cli 10.0.6 dies in its own importer on this board with an unhandled C++
    # exception whose class differs from run to run; the macOS build imports it
    # (tests/kicad/altium/test_pcbdoc_read_oracle.py). Only the stable part of KiCad's message is matched.
    "altium-third-party-pcbdoc-02": (255, "Unhandled exception class"),
}
"""Row id → the exit code and a part of the output of a ``kicad-cli`` run that is known to fail in KiCad's
own importer. Such a row is skipped where the tool fails and compared where it succeeds."""
TIMEOUT = 900


@dataclass(frozen=True)
class Sides:
    """Fenolite's read (``a``), the read of KiCad's conversion (``b``) and the tool version."""

    a: Design
    b: Design
    version: str


@dataclass(frozen=True)
class Measured:
    """The largest differences left between the paired footprints and pads after the translation, in nm
    and microdegrees, and the count of paired footprints on the bottom side."""

    footprints: int
    bottom: int
    position: int
    pad_position: int
    size: int
    drill: int
    rotation: int
    pad_rotation: int

    @property
    def length(self) -> int:
        return max(self.position, self.pad_position, self.size, self.drill)


@cache
def _sides(source: Path, row: str) -> Sides | KicadCliError:
    path = kicad_cli()
    assert path is not None
    try:
        found = altium_import.import_design(cli_for(Path(path), timeout=TIMEOUT), source)
    except KicadCliError as error:
        return error
    backend = registry.for_path(source)
    assert backend is not None
    return Sides(backend.read(source).design, found.read.design, found.tool_version)


def sides(source: Path, row: str = "") -> Sides:
    """Both reads of ``source``. A row of ``KNOWN_IMPORT_FAILURES`` on which the tool fails as recorded is
    skipped by its id; any other failure of the tool fails the test."""
    found = _sides(source, row)
    if isinstance(found, KicadCliError):
        known = KNOWN_IMPORT_FAILURES.get(row)
        output = found.run.stdout + found.run.stderr
        if known is not None and found.run.returncode == known[0] and known[1] in output:
            pytest.skip(f"{row}: kicad-cli pcb import exits {known[0]} in its own importer (recorded)")
        raise found
    return found


def profile_for(version: str) -> Profile:
    profiles = load_profiles(altium_import.exclusions_text(), file=altium_import.EXCLUSIONS_FILE)
    found = select_profile(profiles, altium_import.PROFILE, version)
    assert found is not None, f"no exclusion profile for kicad-cli {version}: measure it and add one"
    return found


def report(found: Sides, *, rules: bool = True, ignore_refs: tuple[str, ...] = ()) -> EquivalenceReport:
    """The comparison at levels 1 to 4 under the profile of the running version; ``rules=False`` keeps its
    frame and tolerance and applies no rule."""
    profile = profile_for(found.version)
    return compare_designs(
        found.a,
        found.b,
        level=4,
        tolerances=Tolerances(profile.tolerance_nm, profile.tolerance_udeg),
        frame=profile.frame,
        ignore_refs=ignore_refs,
        rules=profile.rules if rules else (),
    )


def measure(found: Sides, ignore_refs: tuple[str, ...] = ()) -> Measured:
    """The largest numeric differences between the two reads, whatever the tolerance."""
    _, refs = levels.level_components(found.a, found.b, ignore_refs=ignore_refs)
    wide = Tolerances(10**9, 0)
    _, pairs = levels.level_footprints(found.a, found.b, refs, wide)
    shift = norm.translation((one.position, other.position) for _, one, other in pairs)
    position = pad_position = size = drill = rotation = pad_rotation = bottom = 0
    for _, one, other in pairs:
        bottom += one.side == "bottom"
        position = max(
            position,
            abs(other.position.x - one.position.x - shift.x),
            abs(other.position.y - one.position.y - shift.y),
        )
        rotation = max(rotation, norm.angle_distance(one.rotation, other.rotation))
        groups = {
            number: sorted(pads, key=lambda p: (p.position.x, p.position.y)) for number, pads in _by(one)
        }
        others = {
            number: sorted(pads, key=lambda p: (p.position.x, p.position.y)) for number, pads in _by(other)
        }
        for number, pads in groups.items():
            if len(pads) != len(others.get(number, ())):
                continue
            for pad, twin in zip(pads, others[number], strict=True):
                pad_position = max(
                    pad_position, abs(pad.position.x - twin.position.x), abs(pad.position.y - twin.position.y)
                )
                straight = max(abs(pad.size.w - twin.size.w), abs(pad.size.h - twin.size.h))
                turned = max(abs(pad.size.w - twin.size.h), abs(pad.size.h - twin.size.w))
                quarter = norm.angle_distance(pad.rotation, twin.rotation + norm.QUARTER_TURN, norm.HALF_TURN)
                is_turned = turned < straight and quarter == 0
                size = max(size, turned if is_turned else straight)
                if pad.drill is not None and twin.drill is not None:
                    drill = max(drill, abs(pad.drill - twin.drill))
                periods = (norm.pad_symmetry(pad, Tolerances()), norm.pad_symmetry(twin, Tolerances()))
                if periods[0] is not None and periods[1] is not None and not is_turned:
                    period = min(periods[0], periods[1])
                    pad_rotation = max(pad_rotation, norm.angle_distance(pad.rotation, twin.rotation, period))
    return Measured(len(pairs), bottom, position, pad_position, size, drill, rotation, pad_rotation)


def _by(footprint: FootprintInstance) -> list[tuple[str, list[Pad]]]:
    groups: dict[str, list[Pad]] = {}
    for pad in footprint.pads:
        groups.setdefault(pad.number, []).append(pad)
    return list(groups.items())


def counts_line(name: str, found: EquivalenceReport) -> str:
    """One line per level: ``<name> level N: compared C, differences D, excluded E``."""
    return "\n".join(
        f"{name} level {level.level}: compared {level.compared}, differences {len(level.differences)}, "
        f"excluded {len(level.excluded)}"
        for level in found.levels
    )
