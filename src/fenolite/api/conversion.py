# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.convert``: a conversion, verified (capability design-conversion, "Conversion verified by
equivalence", "Differences matched to the report" and "Conversion without verification"; change c0159).

``convert`` calls ``fenolite.convert.convert_project``, writes the files into a private temporary folder,
reads the direction's read-back file with the target backend and compares it with the design that was
written through ``fenolite.api.equivalent``, at the highest level both hold, under the direction's profile
(``fenolite/convert/data/profiles.toml``). Each difference is then matched against the report: one that a
lost item explains (``convert.report.EXPLAINS``) is listed under ``explained`` with the lost kind, any other
gives one ``convert.unexplained`` error. Nothing outside the temporary folder is written.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

from fenolite.api.equivalence import EquivalenceResult, equivalent
from fenolite.checks.equivalence import Profile, load_profiles
from fenolite.checks.equivalence.model import Difference
from fenolite.convert import PROFILES_FILE, Conversion, convert_project, profiles_text
from fenolite.convert.codes import issue
from fenolite.convert.direction import Target
from fenolite.convert.report import Explainer
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level


@cache
def profiles() -> dict[str, Profile]:
    """The verification profiles by name."""
    return {profile.name: profile for profile in load_profiles(profiles_text(), file=PROFILES_FILE)}


@dataclass(frozen=True, slots=True)
class Explained:
    """A difference of the read-back that a lost item of the report explains, with the lost kind."""

    difference: Difference
    kind: str


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """A conversion with its verification: the comparison (``None`` without one), the differences it
    explained and those it did not, the issues in order and the evidence."""

    conversion: Conversion
    equivalence: EquivalenceResult | None
    explained: tuple[Explained, ...]
    unexplained: tuple[Difference, ...]
    issues: tuple[Issue, ...]
    evidence: Evidence

    def equivalence_json(self) -> dict[str, Any] | None:
        """``result.equivalence`` of ``fenolite convert``: the reply of ``fenolite equivalent`` with the
        explained differences and the count of the unexplained ones; ``None`` without verification."""
        if self.equivalence is None:
            return None
        reply = self.equivalence.to_json()
        reply["explained"] = [
            {
                "level": found.difference.level,
                "kind": found.difference.kind,
                "where": found.difference.where,
                "field": found.difference.field,
                "a": found.difference.a,
                "b": found.difference.b,
                "by": found.kind,
            }
            for found in self.explained
        ]
        reply["unexplained"] = len(self.unexplained)
        return reply


def _unexplained(difference: Difference) -> Issue:
    message = (
        f"{difference.where}: {difference.field} is {difference.a or 'nothing'!r} in the source and "
        f"{difference.b or 'nothing'!r} in the converted project (level {difference.level}, "
        f"{difference.kind}), and no loss of the report explains it"
    )
    hint = "a writer changed the design without saying so: report it with the source"
    return issue("convert.unexplained", message, where=difference.where, hint=hint)


SCHEMATIC_LEVEL = 2
"""The level at which a downgrade's root schematic is compared with the source's (change c0162)."""


def _schematic(
    conversion: Conversion, folder: Path, profile: Profile | None
) -> tuple[Difference, ...] | Issue:
    """The differences between the source's root schematic and the written one at level 2, or the
    ``convert.schematic-unverified`` warning when they cannot be compared (change c0162)."""
    assert conversion.schematic is not None
    source = conversion.source.root / f"{conversion.source.name}{PurePosixPath(conversion.schematic).suffix}"
    try:
        found = equivalent(source, folder / conversion.schematic, level=SCHEMATIC_LEVEL, profile=profile)
    except FenoliteError as error:
        return issue(
            "convert.schematic-unverified",
            f"the schematic was not compared with the source's: {error}",
            where=conversion.schematic,
            hint=getattr(error, "hint", "") or "install kicad-cli to compare the schematic too",
        )
    return found.report.differences if found.report is not None else ()


def verify_conversion(conversion: Conversion, *, profile: Profile | None = None) -> ConversionResult:
    """The verification of ``conversion``: its files read back from a private temporary folder and
    compared with the design that was written, and a downgrade's root schematic with the source's at level
    2. ``profile`` overrides the conversion's."""
    chosen = (
        profile if profile is not None else profiles().get(conversion.profile or conversion.direction.profile)
    )
    schematic: tuple[Difference, ...] | Issue = ()
    with tempfile.TemporaryDirectory(prefix="fenolite-convert-") as name:
        folder = Path(name)
        for key, data in conversion.files.items():
            target = folder.joinpath(*PurePosixPath(key).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        compared = equivalent(conversion.design, folder / conversion.read_back, profile=chosen)
        if conversion.schematic is not None:
            schematic = _schematic(conversion, folder, chosen)
    explainer = Explainer(conversion.design, conversion.report)
    explained: list[Explained] = []
    unexplained: list[Difference] = []
    report = compared.report
    for difference in report.differences if report is not None else ():
        kind = explainer.explain(difference.kind, difference.where, difference.a, difference.b)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append(Explained(difference, kind))
    unexplained += schematic if not isinstance(schematic, Issue) else ()
    notes = (schematic,) if isinstance(schematic, Issue) else ()
    # the comparison's own errors are its differences: each is explained, or one convert.unexplained; its
    # notices are kept, and the read-back's own reader notes are not the conversion's
    kept = tuple(
        found for found in compared.issues if found.severity != "error" and found.code.startswith("equiv.")
    )
    issues = (*conversion.issues, *(_unexplained(d) for d in unexplained), *notes, *kept)
    evidence = Evidence.combine(conversion.evidence, compared.evidence)
    return ConversionResult(conversion, compared, tuple(explained), tuple(unexplained), issues, evidence)


def convert(
    source: str | Path,
    *,
    to: Target,
    kicad_version: int = 10,
    allow_lossy: bool = False,
    bodies: str = "extruded",
    name: str | None = None,
    verify: bool = True,
) -> ConversionResult:
    """Convert ``source`` to ``to`` and, with ``verify``, check the written project against the source
    (capability design-conversion, "Conversion verified by equivalence"). The arguments are those of
    ``fenolite.convert.convert_project``; its errors are raised unchanged. Without ``verify`` the result
    holds no comparison, one ``convert.no-verify`` warning, and the evidence ``UNVERIFIED``."""
    conversion = convert_project(
        source, to=to, kicad_version=kicad_version, allow_lossy=allow_lossy, bodies=bodies, name=name
    )
    if verify:
        return verify_conversion(conversion)
    warning = issue(
        "convert.no-verify",
        "the converted project was not read back and compared with the source",
        hint="run without --no-verify to check the conversion",
    )
    evidence = Evidence(Level.UNVERIFIED, None, conversion.evidence.hypotheses)
    return ConversionResult(conversion, None, (), (), (*conversion.issues, warning), evidence)


__all__ = ["ConversionResult", "Explained", "convert", "profiles", "verify_conversion"]
