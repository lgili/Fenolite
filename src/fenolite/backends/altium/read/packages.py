# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The package checks of Altium's query language over a component's pads (change c0462, design D3).

S-2212 ("Attribute Checks") defines ``IsBGA``, ``IsSOIC`` and ``IsLCC`` by rows and columns of a
component's pads, its pad count and its surface-mount pads; ``docs/formats/altium/rule-file.md``, "Package
checks", paraphrases them. A row is a line of pad centres of one y, a column one of one x, both within
``LINE_TOLERANCE`` file units, on a component turned by a multiple of 90 degrees. Whether Altium groups
pads into rows the same way is not confirmed: the checks carry ``INFERRED``
(``H-A-RD-PRJ-SCOPE-PACKAGE``) until the kit run of task 5.1 agrees on every component of the public
rows. A component turned by another angle is not decided: ``PackageUndecided``.
"""

# evidence: see import_evidence, read.project

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence

from fenolite.backends.altium.read.scope import ScopeComponent

LINE_TOLERANCE = 100
"""Two pad centres within this many file units (0.01 mil) share a row or a column (``INFERRED``)."""


class PackageUndecided(ValueError):
    """The pads of a component do not decide a package check."""


def _lines(values: Sequence[int]) -> list[int]:
    """The number of pads on each line of ``values`` (coordinates), lines grouped within the tolerance."""
    counts: list[int] = []
    last: int | None = None
    for value in sorted(values):
        if last is None or value - last > LINE_TOLERANCE:
            counts.append(0)
        counts[-1] += 1
        last = value
    return counts


def grid(component: ScopeComponent) -> tuple[list[int], list[int]]:
    """The pad counts of the rows and of the columns of ``component``."""
    turn = component.rotation % 90
    if min(turn, 90 - turn) > 1e-6:
        raise PackageUndecided(
            f"{component.designator or 'a component'} is turned by {component.rotation} degrees: its rows of "
            "pads are not along the board's axes"
        )
    return _lines([pad.y for pad in component.pads]), _lines([pad.x for pad in component.pads])


def _all_smd(component: ScopeComponent) -> bool:
    return bool(component.pads) and all(pad.smd for pad in component.pads)


def is_bga(component: ScopeComponent) -> bool:
    """At least 10 rows and 10 columns, fewer than 6 more of one than of the other, at least half of rows
    times columns pads, all surface mount."""
    if not _all_smd(component):
        return False
    rows, columns = (len(lines) for lines in grid(component))
    count = len(component.pads)
    return rows >= 10 and columns >= 10 and abs(rows - columns) < 6 and 2 * count >= rows * columns


def is_soic(component: ScopeComponent) -> bool:
    """All surface mount, as many pads as rows times columns, and two rows of at least 3 columns or two
    columns of at least 3 rows."""
    if not _all_smd(component):
        return False
    rows, columns = (len(lines) for lines in grid(component))
    if len(component.pads) != rows * columns:
        return False
    return (rows == 2 and columns >= 3) or (columns == 2 and rows >= 3)


def is_lcc(component: ScopeComponent) -> bool:
    """Two rows of at least 4 pads and two columns of at least 4 pads, all surface mount."""
    if not _all_smd(component):
        return False
    rows, columns = grid(component)
    return sum(1 for n in rows if n >= 4) == 2 and sum(1 for n in columns if n >= 4) == 2


PACKAGE_CHECKS: Mapping[str, Callable[[ScopeComponent], bool]] = {
    "IsBGA": is_bga,
    "IsSOIC": is_soic,
    "IsLCC": is_lcc,
}
"""The package checks by function name."""

__all__ = ["LINE_TOLERANCE", "PACKAGE_CHECKS", "PackageUndecided", "grid", "is_bga", "is_lcc", "is_soic"]
