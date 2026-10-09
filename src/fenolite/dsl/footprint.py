# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small builder for project-authored footprint library definitions."""

from __future__ import annotations

import re
from typing import cast, get_args

from fenolite.core.coords import Point, Size
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg
from fenolite.model.board import Graphic, Pad, PadFabProperty, Padstack
from fenolite.model.library import FootprintDef, FootprintKind

_IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.+-]*$")
_FAB_PROPERTIES: tuple[str, ...] = get_args(PadFabProperty)
_THROUGH_ONLY = ("castellated", "mechanical")
"""Marks that KiCad's DRC reports as ``padstack`` on a pad that is not ``thru_hole`` (``H-K-PAD-FABPROP``)."""


class Footprint:
    """Author a library footprint with DSL lengths (``mm()``, ``mil()``, ``nm()`` or unit strings).

    Coordinates are local to the footprint origin. The definition is immutable once exposed via
    :attr:`definition`; pads and graphics are emitted in declaration order.
    """

    def __init__(
        self, library: str, name: str, *, kind: FootprintKind = "unspecified", description: str = ""
    ) -> None:
        if not isinstance(library, str) or not _IDENT.fullmatch(library):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"unsafe footprint library name {library!r}")
        if not isinstance(name, str) or not _IDENT.fullmatch(name):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"unsafe footprint name {name!r}")
        if kind not in ("smd", "through_hole", "unspecified"):
            raise DslError(f"unsupported footprint kind {kind!r}")
        if not isinstance(description, str):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError("footprint description must be text")
        self.library, self.name, self.kind, self.description = library, name, kind, description
        self._pads: list[Pad] = []
        self._graphics: list[Graphic] = []
        self._net_ties: list[tuple[str, ...]] = []

    @property
    def lib_id(self) -> str:
        return f"{self.library}:{self.name}"

    def pad(
        self,
        number: str,
        *,
        at: tuple[object, object],
        size: tuple[object, object],
        shape: str = "rect",
        kind: str | None = None,
        drill: object | None = None,
        drill_shape: str = "round",
        drill_length: object | None = None,
        drill_rotation: object | None = None,
        layers: tuple[str, ...] | None = None,
        rotation: object = 0,
        shared: bool = False,
        fab_property: str | None = None,
    ) -> None:
        """Declare one pad. ``fab_property`` is its fabrication mark (``Pad.fab_property``): ``bga``,
        ``fiducial_global``, ``fiducial_local``, ``test_point``, ``heatsink``, ``castellated``,
        ``mechanical`` or ``press_fit``. The two that KiCad expects on a plated hole (``castellated``,
        ``mechanical``) are refused on a pad that is not ``thru_hole``."""
        pad_kind = kind or ("thru_hole" if self.kind == "through_hole" else "smd")
        if pad_kind not in ("smd", "thru_hole", "np_thru_hole"):
            raise DslError(f"unsupported authored pad kind {kind!r}")
        # a hole that is not plated may be unnumbered, as the mounting holes of KiCad's library (c0102)
        unnumbered = number == "" and pad_kind == "np_thru_hole"
        if not isinstance(number, str) or (not number and not unnumbered):  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError(
                f"pad number {number!r} must be a non-empty string; only an np_thru_hole pad is unnumbered"
            )
        occurrences = sum(p.number == number for p in self._pads)
        if unnumbered:
            if shared:
                raise DslError(f"footprint {self.lib_id}: an unnumbered pad is never shared")
        elif occurrences and not shared:
            raise DslError(f"footprint {self.lib_id}: pad {number!r} is declared twice")
        elif shared and not occurrences:
            raise DslError(f"footprint {self.lib_id}: shared pad {number!r} has no earlier pad")
        if shape not in ("circle", "rect", "oval", "roundrect"):
            raise DslError(f"unsupported authored pad shape {shape!r}")
        if fab_property is not None and fab_property not in _FAB_PROPERTIES:
            raise DslError(
                f"unsupported fab_property {fab_property!r}; expected one of {', '.join(_FAB_PROPERTIES)}"
            )
        if fab_property in _THROUGH_ONLY and pad_kind != "thru_hole":
            raise DslError(
                f"fab_property {fab_property!r} needs a thru_hole pad, and pad {number!r} is {pad_kind}: "
                "KiCad's DRC reports such a pad as a padstack problem"
            )
        x, y = as_nm(at[0], name="pad x"), as_nm(at[1], name="pad y")
        w, h = as_nm(size[0], name="pad width"), as_nm(size[1], name="pad height")
        if w <= 0 or h <= 0:
            raise DslError("pad dimensions must be positive")
        hole: Nm | None = None if drill is None else as_nm(drill, name="pad drill")
        if drill_shape not in ("round", "slot"):
            raise DslError(f"unsupported authored drill shape {drill_shape!r}")
        hole_length = None if drill_length is None else as_nm(drill_length, name="pad drill length")
        pad_rotation = as_udeg(rotation, name="pad rotation")
        hole_rotation = 0 if drill_rotation is None else as_udeg(drill_rotation, name="pad drill rotation")
        if drill_shape == "slot" and hole_length is None:
            raise DslError("a slotted drill needs a positive drill_length")
        if drill_shape == "round" and (hole_length is not None or drill_rotation not in (None, 0)):
            raise DslError("drill_length and drill_rotation apply only to a slotted drill")
        if pad_kind == "smd" and hole is not None:
            raise DslError("a drill only belongs to a through-hole pad")
        if pad_kind != "smd" and (hole is None or hole <= 0):
            raise DslError("a through-hole pad needs a positive drill")
        if hole is not None and hole > min(w, h):
            raise DslError("pad drill cannot be larger than its pad")
        if hole_length is not None and (hole is None or hole_length < hole or hole_length > max(w, h)):
            raise DslError("slot length must be at least the drill width and no larger than its pad")
        if shape == "circle" and w != h:
            raise DslError("a circular pad must have equal width and height; use shape='oval' otherwise")
        default_layers = ("*.Cu", "*.Mask") if pad_kind != "smd" else ("F.Cu", "F.Paste", "F.Mask")
        pad_key = f"{self.lib_id}:pad:{number}"
        if unnumbered:
            pad_key += f":{occurrences + 1}"  # "<lib id>:pad::<k>", the k-th unnumbered pad from 1
        elif occurrences:
            pad_key += f":shared:{occurrences + 1}"
        self._pads.append(
            Pad(
                id=derived_id("pad", "fenolite.dsl", pad_key),
                number=number,
                shape=shape,  # type: ignore[arg-type]
                size=Size(w, h),
                position=Point(x, y),
                rotation=pad_rotation,
                kind=pad_kind,  # type: ignore[arg-type]
                drill=hole,
                padstack=(
                    Padstack(
                        id=derived_id("pst", "fenolite.dsl", f"{pad_key}:padstack"),
                        hole_shape="slot",
                        hole_length=hole_length,
                        hole_rotation=hole_rotation,
                    )
                    if drill_shape == "slot"
                    else None
                ),
                layers=layers or default_layers,
                fab_property=cast("PadFabProperty | None", fab_property),
            )
        )

    def graphic(
        self, kind: str, *, layer: str, points: tuple[tuple[object, object], ...], width: object
    ) -> None:
        if kind not in ("line", "rect", "circle", "polygon"):
            raise DslError(f"unsupported footprint graphic {kind!r}")
        if not isinstance(layer, str) or not layer:  # type: ignore[reportUnnecessaryIsInstance]
            raise DslError("graphic layer must be a non-empty string")
        minimum = 3 if kind == "polygon" else 2
        if len(points) < minimum:
            raise DslError(f"{kind} needs at least {minimum} point(s)")
        converted = tuple(Point(as_nm(x, name="graphic x"), as_nm(y, name="graphic y")) for x, y in points)
        stroke = as_nm(width, name="graphic width")
        if stroke < 0:
            raise DslError("graphic width cannot be negative")
        self._graphics.append(
            Graphic(
                id=derived_id("gfx", "fenolite.dsl", f"{self.lib_id}:graphic:{len(self._graphics)}"),
                kind=kind,  # type: ignore[arg-type]
                layer=layer,
                points=converted,
                width=stroke,
            )
        )

    def line(
        self, start: tuple[object, object], end: tuple[object, object], *, layer: str, width: object
    ) -> None:
        self.graphic("line", layer=layer, points=(start, end), width=width)

    def rect(
        self, start: tuple[object, object], end: tuple[object, object], *, layer: str, width: object
    ) -> None:
        self.graphic("rect", layer=layer, points=(start, end), width=width)

    def circle(
        self, center: tuple[object, object], edge: tuple[object, object], *, layer: str, width: object
    ) -> None:
        self.graphic("circle", layer=layer, points=(center, edge), width=width)

    def polygon(self, points: tuple[tuple[object, object], ...], *, layer: str, width: object) -> None:
        self.graphic("polygon", layer=layer, points=points, width=width)

    def net_tie(self, *numbers: str) -> None:
        """Declare one net-tie group: pads of different nets that this footprint joins on purpose, through
        overlapping pads or a copper graphic (``docs/dsl.md``, "Net ties"). The copper check then does not
        judge two pads of the group against each other, as KiCad's DRC does not."""
        if len(numbers) < 2:
            raise DslError(f"footprint {self.lib_id}: net_tie() needs at least two pad numbers")
        for number in numbers:
            if not isinstance(number, str) or not number.strip() or "," in number:  # type: ignore[reportUnnecessaryIsInstance]
                raise DslError(
                    f"footprint {self.lib_id}: net_tie() takes pad numbers as non-empty strings without "
                    f"a comma, not {number!r}"
                )
        if len(set(numbers)) != len(numbers):
            raise DslError(f"footprint {self.lib_id}: net_tie() names a pad twice in {numbers!r}")
        self._net_ties.append(tuple(numbers))

    @property
    def definition(self) -> FootprintDef:
        """Immutable library definition used by builders and backend writers."""
        known = {pad.number for pad in self._pads}
        grouped: set[str] = set()
        for group in self._net_ties:
            for number in group:
                if number not in known:
                    raise DslError(
                        f"footprint {self.lib_id}: net_tie() names pad {number!r}, which the footprint "
                        "does not have"
                    )
                if number in grouped:
                    raise DslError(
                        f"footprint {self.lib_id}: pad {number!r} is in two net-tie groups; a pad belongs "
                        "to one group"
                    )
            grouped.update(group)
        return FootprintDef(
            id=derived_id("fpd", "fenolite.dsl", self.lib_id),
            name=self.name,
            library=self.library,
            description=self.description,
            kind=cast(FootprintKind, self.kind),
            pads=tuple(self._pads),
            graphics=tuple(self._graphics),
            net_ties=tuple(self._net_ties),
        )


__all__ = ["Footprint"]
