# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One layer of an impedance target: ``trace(layer, refs=…, width=…, gap=…)`` (``docs/impedance.md``;
change c0105).

The geometry is always the user's: Fenolite computes no width or gap into a design. ``design.rules
.impedance()`` takes the traces and checks them together.
"""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm


@dataclass(frozen=True, slots=True)
class Trace:
    """One layer of an impedance target: the signal layer, its reference layers as given, the width and
    the gap (``None`` for a single-ended trace), in nanometres."""

    layer: str
    refs: tuple[str, ...]
    width: Nm
    gap: Nm | None = None


def _length(value: object, what: str) -> Nm:
    length = as_nm(value, name=what)
    if length <= 0:
        raise DslError(f"{what} must be above 0")
    return length


def trace(layer: str, *, refs: str | tuple[str, ...], width: object, gap: object = None) -> Trace:
    """One layer of an impedance target: ``layer`` a copper layer name, ``refs`` one reference layer or a
    tuple of two, ``width`` the track width and ``gap`` the gap between the two tracks of a pair (lengths
    with a unit, for example ``mm(0.2)``)."""
    if not isinstance(layer, str) or not layer:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError(f"trace(): the layer must be a layer name such as 'F.Cu', not {layer!r}")
    names = (refs,) if isinstance(refs, str) else refs
    if (
        not isinstance(names, tuple)  # pyright: ignore[reportUnnecessaryIsInstance]
        or len(names) not in (1, 2)
        or not all(isinstance(n, str) and n for n in names)  # pyright: ignore[reportUnnecessaryIsInstance]
        or len(set(names)) != len(names)
    ):
        raise DslError(
            f"trace({layer!r}): refs must be one layer name or a tuple of two distinct names, not {refs!r}"
        )
    if layer in names:
        raise DslError(f"trace({layer!r}): a layer is not its own reference")
    return Trace(
        layer,
        names,
        _length(width, f"trace({layer!r}): width"),
        None if gap is None else _length(gap, f"trace({layer!r}): gap"),
    )


__all__ = ["Trace", "trace"]
