# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public per-family footprint generators (change c0260, capability footprint-generators).

``generate(package)`` draws a footprint from one ``fenolite.package.v0`` record by its ``family``:
``chip``, ``molded``, ``gullwing``, ``nolead``, ``grid``, ``to``, ``dip``, ``header`` or ``connector``.
It is pure: no file, no clock, no environment. Lands come from the manufacturer's ``[land]`` when the
record gives one, else from the worst-case calculator with the Fenolite-authored constants of
``lands.LANDS`` (``INFERRED``); the drawing follows the record's versioned convention.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from fenolite.catalog.footprints import naming
from fenolite.catalog.footprints._draft import Context, Draft, Refused, deltas_view
from fenolite.catalog.footprints.bodies import bodies as body_volumes
from fenolite.catalog.footprints.codes import ISSUE_CODES, issue, sort_issues
from fenolite.catalog.footprints.drawing import DRAWINGS, NAMESPACE, draw0, draw1
from fenolite.catalog.footprints.grid import draw_grid
from fenolite.catalog.footprints.gullwing import draw_gullwing
from fenolite.catalog.footprints.lands import LANDS, LandTable
from fenolite.catalog.footprints.nolead import draw_nolead
from fenolite.catalog.footprints.record import Package, check_density, read_package
from fenolite.catalog.footprints.through_hole import draw_connector, draw_dip, draw_header, draw_to
from fenolite.catalog.footprints.two_terminal import draw_chip, draw_molded
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.library import FootprintDef

GENERATOR_VERSION = 1
"""The version of every family generator (``<family>/1`` in the stamp)."""
DEFAULT_LIBRARY = "Local"
"""The library nickname of a generated footprint whose record has no ``id`` namespace."""

_FAMILIES: Mapping[str, Callable[[Context], Draft]] = MappingProxyType(
    {
        "chip": draw_chip,
        "molded": draw_molded,
        "gullwing": draw_gullwing,
        "nolead": draw_nolead,
        "grid": draw_grid,
        "to": draw_to,
        "dip": draw_dip,
        "header": draw_header,
    }
)


@dataclass(frozen=True, slots=True)
class LandReport:
    """Where the land came from and its numbers (decision 7). ``z``, ``g`` and ``x`` are those of the first
    facing rows; ``pad`` is the (length, width) of their land; ``deltas`` the manufacturer's land minus the
    calculated one, per number, when both exist."""

    source: str
    evidence: str
    table: int | None = None
    z: Nm | None = None
    g: Nm | None = None
    x: Nm | None = None
    pad: tuple[Nm, Nm] | None = None
    drill: Nm | None = None
    pad_diameter: Nm | None = None
    deltas: Mapping[str, Nm] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class Generated:
    """The result of ``generate``: the footprint (``None`` on an error finding), the land report, the
    stamp and the sorted ``package.*`` findings."""

    footprint: FootprintDef | None
    land: LandReport
    stamp: str
    issues: tuple[Issue, ...]
    name: str = ""
    courtyard: tuple[Nm, Nm, Nm, Nm] | None = None
    """``(x0, y0, x1, y1)`` of the courtyard rectangle."""


def positions_of(package: Package) -> tuple[int, ...]:
    """The position counts of a ``connector`` series, in order; ``()`` for another family."""
    if package.family != "connector":
        return ()
    first, last = package.keys.raw("positions")  # type: ignore[misc]
    return tuple(range(first, last + 1))  # pyright: ignore[reportUnknownArgumentType]


def series_name(package: Package, positions: int) -> str:
    """The name of one position count of a connector series, from ``name_pattern``."""
    from fenolite.core.units import format_length

    pitch = package.keys.length("pitch")
    pitch_text = format_length(pitch.nominal or 0, "mm")[:-2] if pitch is not None else ""
    pattern = package.keys.text("name_pattern") or ""
    try:
        return pattern.format(series=package.keys.text("series"), n=positions, pitch=pitch_text)
    except (KeyError, IndexError, ValueError):
        raise FormatError(
            f"name_pattern {pattern!r} may use only {{series}}, {{n}} and {{pitch}}",
            file=package.file,
            locator="name_pattern",
        ) from None


def stamp_of(package: Package) -> str:
    """``gullwing/1 lands/1 drawing/1 nominal`` or ``gullwing/1 manufacturer drawing/1``."""
    head = f"{package.family}/{GENERATOR_VERSION}"
    if package.land is not None:
        return f"{head} manufacturer drawing/{package.drawing}"
    return f"{head} lands/{package.lands} drawing/{package.drawing} {package.density}"


def _table(package: Package, override: LandTable | None) -> LandTable | None:
    if override is not None:
        return override
    if package.lands is None:
        return None
    table = LANDS.get(package.lands)
    if table is None:
        raise FormatError(
            f"lands/{package.lands} is not a released constant table "
            f"(released: {', '.join(map(str, LANDS))})",
            file=package.file,
            locator="generate.lands",
        )
    return table


def generate(
    package: Package | str,
    *,
    density: str = "nominal",
    positions: int | None = None,
    library: str | None = None,
    table: LandTable | None = None,
) -> Generated:
    """Draw ``package`` (a parsed record or its TOML text). ``positions`` picks one position count of a
    connector series (default: the first); ``library`` names the footprint's library (default: the
    record's id namespace, else ``Local``); ``table`` replaces the record's constant table (tests and
    calibration). ``FormatError`` (``FEN-3004``) for an unreadable record or a reserved density."""
    if isinstance(package, str):
        package = read_package(package)
    check_density(density)
    if package.drawing not in DRAWINGS:
        raise FormatError(
            f"drawing/{package.drawing} is not a released convention "
            f"(released: {', '.join(map(str, DRAWINGS))})",
            file=package.file,
            locator="generate.drawing",
        )
    name = package.name
    count = 0
    if package.family == "connector":
        counts = positions_of(package)
        count = counts[0] if positions is None else positions
        if count not in counts:
            raise FormatError(
                f"{count} positions lie outside the series {counts[0]}..{counts[-1]}",
                file=package.file,
                locator="positions",
            )
        name = series_name(package, count)
    elif positions is not None:
        raise FormatError(
            f"positions apply to a connector series, not to {package.family!r}", file=package.file
        )
    lands = _table(package, table)
    ctx = Context(package, lands)
    stamp = stamp_of(package)
    evidence = package.evidence if package.land is not None else "INFERRED"
    library = library or package.namespace or DEFAULT_LIBRARY
    try:
        if package.family != "connector":
            ctx.issues += naming.check(package)
            if any(i.severity == "error" for i in ctx.issues):
                raise Refused("name")
        draft = (
            draw_connector(ctx, count) if package.family == "connector" else _FAMILIES[package.family](ctx)
        )
    except Refused:
        draft = None
    numbers = ctx.land
    report = LandReport(
        source="manufacturer" if package.land is not None else "calculated",
        evidence=evidence,
        table=package.lands if package.land is None else None,
        z=numbers.z,
        g=numbers.g,
        x=numbers.x,
        pad=numbers.pad,
        drill=numbers.drill,
        pad_diameter=numbers.pad_diameter,
        deltas=deltas_view(numbers.deltas),
    )
    if draft is not None and package.land is not None:
        source = package.land.text("source")
        if numbers.deltas:
            key = max(sorted(numbers.deltas), key=lambda k: abs(numbers.deltas[k]))
            detail = f"the largest difference from the calculated land is {key} {numbers.deltas[key]:+d} nm"
        else:
            detail = "no calculated land to compare (the land class has no goals or a bound is missing)"
        ctx.issues.append(
            issue(
                "package.land-override",
                f"the manufacturer's land ({source}) is used; {detail}",
                where=ctx.where("land"),
            )
        )
    issues = sort_issues(ctx.issues)
    if draft is None or any(i.severity == "error" for i in issues):
        return Generated(None, report, stamp, issues, name=name)
    footprint, courtyard = _footprint(package, name, library, draft, lands, stamp)
    return Generated(footprint, report, stamp, issues, name=name, courtyard=courtyard)


def _description(package: Package, name: str, stamp: str) -> str:
    summary = package.summary or f"{name} ({package.family} package)"
    if package.drawing == 0:
        if package.evidence == "INFERRED":
            return f"{summary}; land pattern remains INFERRED and requires part-specific review"
        return summary
    if package.land is not None:
        land = f"manufacturer {package.land.text('source')}"
    else:
        land = f"calculated lands/{package.lands} {package.density} (INFERRED)"
    return f"{summary}. {stamp}; land: {land}"


def _footprint(
    package: Package, name: str, library: str, draft: Draft, table: LandTable | None, stamp: str
) -> tuple[FootprintDef, tuple[Nm, Nm, Nm, Nm]]:
    lib_id = f"{library}:{name}"
    if package.drawing == 0:
        drawn = draw0(name, draft, table)
    else:
        drawn = draw1(name, lib_id, draft, table if table is not None else LANDS[1])
    box = drawn.courtyard
    volumes = body_volumes(package, draft, lib_id)
    models = (model_path(library, name),) if volumes and package.drawing >= 1 else ()
    footprint = FootprintDef(
        id=derived_id("fpd", NAMESPACE, lib_id),
        native_ids={"fenolite": lib_id},
        name=name,
        library=library,
        description=_description(package, name, stamp),
        kind=draft.kind,
        pads=drawn.pads,
        graphics=drawn.graphics,
        models=models,
        bodies=volumes,
    )
    return footprint, (box.x0, box.y0, box.x1, box.y1)


MODEL_ROOT = "${KIPRJMOD}/lib"
"""Where a ``drawing >= 1`` footprint names its STEP model (decision 13): ``lib/<library>.3dshapes``
beside the project, which ``fenolite build`` writes."""


def model_path(library: str, name: str) -> str:
    """``${KIPRJMOD}/lib/<library>.3dshapes/<name>.step``."""
    return f"{MODEL_ROOT}/{library}.3dshapes/{name}.step"


__all__ = [
    "DEFAULT_LIBRARY",
    "GENERATOR_VERSION",
    "ISSUE_CODES",
    "Generated",
    "LandReport",
    "MODEL_ROOT",
    "Package",
    "generate",
    "model_path",
    "positions_of",
    "read_package",
    "series_name",
    "stamp_of",
]
