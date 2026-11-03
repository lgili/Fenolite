# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The value of a drawn schematic: what ``schematic.toml`` (schema ``fenolite.drawn-schematic.v0``) holds
(capability ``design-model``, "Drawn schematic value"; change c0276; ``docs/drawn-schematic.md``).

A drawn schematic is the drawing of a design's schematic that a person or a CAD tool made: symbol poses,
wires, junctions, labels, buses and sheet references. It never holds a value, a reference, a footprint or a
net: code owns those, and the drawing is proved to mean the code's netlist
(``fenolite.model.drawn_connect``). A drawn symbol names its component by its path relative to the module
of its sheet instance, so one drawn sheet can stand for several module instances (a repeated sheet).

Positions are integer nanometres in the sheet frame (Y down) and angles integer microdegrees; no field
holds a float. Every value is frozen and hashable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from fenolite.core.coords import Point, Size
from fenolite.core.units import Nm, Udeg
from fenolite.model.presentation import TitleBlock

SCHEMA = "fenolite.drawn-schematic.v0"
"""The schema of the drawn schematic file this version reads and writes."""
DrawnLabelKind = Literal["local", "global", "hierarchical"]
DrawnShape = Literal["", "input", "output", "bidirectional", "tri_state", "passive"]
ROTATIONS: frozenset[int] = frozenset({0, 90_000_000, 180_000_000, 270_000_000})
"""The angles of symbols, power symbols, labels and sheet pins, in µdeg."""
FIELD_ROTATIONS: frozenset[int] = frozenset({0, 90_000_000})
"""The angles of a field pose, in µdeg."""
MIRRORS: frozenset[str] = frozenset({"", "x", "y"})
JUSTIFY_WORDS: frozenset[str] = frozenset({"left", "right", "top", "bottom", "mirror"})
TITLE_FIELDS: tuple[str, ...] = (
    "title", "date", "revision", "organization", "doc_id", "responsible", "approver",
)  # fmt: skip
"""The text fields of a drawn title block, in file order; ``param.<name>`` pairs follow."""


def title_pairs(block: TitleBlock | None) -> tuple[tuple[str, str], ...]:
    """The (field, text) pairs of ``block`` that are not empty, in file order."""
    if block is None:
        return ()
    pairs = [(name, getattr(block, name)) for name in TITLE_FIELDS if getattr(block, name)]
    pairs += [(f"param.{k}", v) for k, v in sorted(block.params.items())]
    return tuple(pairs)


def _check_angle(value: int, allowed: frozenset[int], what: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{what} is whole µdeg, not {value!r}")
    if value not in allowed:
        raise ValueError(f"{what} {value} µdeg is not one of {sorted(allowed)}")


def _check_point(value: Point, what: str) -> None:
    if not isinstance(value.x, int) or not isinstance(value.y, int):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{what} is whole nanometres, not {value!r}")


def _check_length(value: object, what: str, *, positive: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{what} is whole nanometres, not {value!r}")
    if value < 0 or (positive and value == 0):
        raise ValueError(f"{what} must be {'positive' if positive else 'nonnegative'}")


def _check_justify(value: str, what: str) -> None:
    if not isinstance(value, str):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"{what}: justify is text, not {value!r}")
    if any(word not in JUSTIFY_WORDS for word in value.split()) or value != " ".join(value.split()):
        raise ValueError(f"{what}: justify {value!r} must be canonical words of {sorted(JUSTIFY_WORDS)}")


@dataclass(frozen=True, slots=True)
class DrawnFont:
    """Optional font attributes, with exact canonical presence (change c0326).

    Size is width/height in nm, independently of a backend's written axis order. ``None``, false and
    zero stay distinct in the model; a native backend must prove their effective meaning or refuse.
    A font names a face only; it never contains a font file or requests one from the filesystem.
    """

    size: Size | None = None
    thickness: Nm | None = None
    bold: bool | None = None
    italic: bool | None = None
    face: str | None = None

    def __post_init__(self) -> None:
        if all(value is None for value in (self.size, self.thickness, self.bold, self.italic, self.face)):
            raise ValueError("an empty drawn font is absent; use font=None")
        if self.size is not None:
            if not isinstance(self.size, Size):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError("drawn font size is a Size in whole nanometres")
            _check_length(self.size.w, "drawn font width", positive=True)
            _check_length(self.size.h, "drawn font height", positive=True)
        if self.thickness is not None:
            _check_length(self.thickness, "drawn font thickness")
        for name, value in (("bold", self.bold), ("italic", self.italic)):
            if value is not None and not isinstance(value, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError(f"drawn font {name} is a boolean or None")
        if self.face is not None:
            if not isinstance(self.face, str):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError("drawn font face is a name")
            if not self.face.strip() or not self.face.isprintable() or any(c in self.face for c in "/\\"):
                raise ValueError("drawn font face is a nonempty name without controls or a path")


def _check_font(value: DrawnFont | None) -> None:
    if value is not None and not isinstance(value, DrawnFont):  # pyright: ignore[reportUnnecessaryIsInstance]
        raise TypeError("drawn font is a DrawnFont or None")


@dataclass(frozen=True, slots=True)
class DrawnField:
    """The pose of one field (``Reference``, ``Value`` or another property) of a drawn symbol."""

    name: str
    at: Point
    rotation: Udeg = 0
    justify: str = ""
    """Blank-separated words of ``JUSTIFY_WORDS``; ``""`` centres the text on ``at``."""
    hide: bool = False
    font: DrawnFont | None = None

    def __post_init__(self) -> None:
        _check_point(self.at, f"field {self.name} position")
        _check_angle(self.rotation, FIELD_ROTATIONS, f"field {self.name} rotation")
        _check_justify(self.justify, f"field {self.name}")
        _check_font(self.font)


@dataclass(frozen=True, slots=True)
class DrawnSheetProperty:
    """Literal custom sheet-reference text and its pose; built-in name/file text stays code-owned."""

    name: str
    text: str
    at: Point
    rotation: Udeg = 0
    justify: str = ""
    hide: bool = False
    font: DrawnFont | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.name, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("a custom sheet property name is text")
        if not self.name or not self.name.isprintable() or self.name in {"Sheetname", "Sheetfile"}:
            raise ValueError("a custom sheet property has a nonempty nonreserved printable name")
        if not isinstance(self.text, str):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("a custom sheet property value is text")
        if type(self.hide) is not bool:
            raise TypeError("a custom sheet property hide flag is boolean")
        _ = self.pose  # validate the supported pose/font forms using DrawnField
        if any(type(value) is not int for value in (self.at.x, self.at.y, self.rotation)):
            raise TypeError("custom sheet property coordinates and rotation are integer units, not booleans")

    @property
    def pose(self) -> DrawnField:
        return DrawnField(self.name, self.at, self.rotation, self.justify, self.hide, self.font)


@dataclass(frozen=True, slots=True)
class DrawnSymbol:
    """One unit of a code component, named by its path relative to the module of its sheet instance."""

    part: str
    unit: int
    at: Point
    rotation: Udeg = 0
    mirror: str = ""
    fields: tuple[DrawnField, ...] = ()
    symbol: str = ""
    """Optional native library binding for this unit; its logical pins must match the code symbol."""

    def __post_init__(self) -> None:
        if not self.part:
            raise ValueError("a drawn symbol names its part")
        if isinstance(self.unit, bool) or not isinstance(self.unit, int) or self.unit < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"symbol {self.part}: unit {self.unit!r} is not a whole number from 1")
        _check_point(self.at, f"symbol {self.part} position")
        _check_angle(self.rotation, ROTATIONS, f"symbol {self.part} rotation")
        if self.mirror not in MIRRORS:
            raise ValueError(f"symbol {self.part}: mirror {self.mirror!r} is not '', 'x' or 'y'")


@dataclass(frozen=True, slots=True)
class DrawnPower:
    """A power symbol: a global connection named ``net``, drawn with the library symbol ``symbol``."""

    symbol: str
    net: str
    at: Point
    rotation: Udeg = 0
    fields: tuple[DrawnField, ...] = ()
    mirror: str = ""

    def __post_init__(self) -> None:
        if not self.symbol or not self.net:
            raise ValueError("a power symbol names its library symbol and its net")
        _check_point(self.at, f"power {self.net} position")
        _check_angle(self.rotation, ROTATIONS, f"power {self.net} rotation")
        if self.mirror not in MIRRORS:
            raise ValueError(f"power {self.net}: mirror {self.mirror!r} is not '', 'x' or 'y'")


@dataclass(frozen=True, slots=True)
class DrawnLabel:
    """A local, global or hierarchical label; ``shape`` is ``""`` for a local label."""

    kind: DrawnLabelKind
    text: str
    at: Point
    rotation: Udeg = 0
    shape: DrawnShape = ""
    font: DrawnFont | None = None
    justify: str | None = None
    """None keeps the legacy role-selected anchor; an explicit empty string centres the text."""
    intersheet_refs: DrawnField | None = None
    """The fixed global-label reference placeholder pose; effective text requires project context."""

    def __post_init__(self) -> None:
        if self.kind not in ("local", "global", "hierarchical"):
            raise ValueError(f"label kind {self.kind!r} is not local, global or hierarchical")
        if not self.text:
            raise ValueError("a label has a text")
        if self.intersheet_refs is not None:
            if not isinstance(self.intersheet_refs, DrawnField):  # pyright: ignore[reportUnnecessaryIsInstance]
                raise TypeError("intersheet_refs is a DrawnField or None")
            if self.kind != "global":
                raise ValueError("intersheet_refs belongs to a global label only")
            if self.intersheet_refs.name != "Intersheetrefs":
                raise ValueError("intersheet_refs has the fixed field name Intersheetrefs")
        _check_point(self.at, f"label {self.text} position")
        _check_angle(self.rotation, ROTATIONS, f"label {self.text} rotation")
        _check_font(self.font)
        if self.justify is not None:
            _check_justify(self.justify, f"label {self.text}")


@dataclass(frozen=True, slots=True)
class DrawnPin:
    """A pin of a drawn sheet reference: its name, shape, connection point and angle."""

    name: str
    shape: DrawnShape
    at: Point
    rotation: Udeg = 0
    font: DrawnFont | None = None
    justify: str | None = None
    """None keeps the legacy box-edge anchor; an explicit empty string centres the text."""

    def __post_init__(self) -> None:
        if not self.name or not self.shape:
            raise ValueError("a sheet pin has a name and a shape")
        _check_point(self.at, f"sheet pin {self.name} position")
        _check_angle(self.rotation, ROTATIONS, f"sheet pin {self.name} rotation")
        _check_font(self.font)
        if self.justify is not None:
            _check_justify(self.justify, f"sheet pin {self.name}")


@dataclass(frozen=True, slots=True)
class DrawnSheetRef:
    """A reference to the drawn sheet ``sheet``: one instance showing the parts of the code module
    ``module``, relative to the module of the instance that holds the reference (``""``: the same
    module)."""

    key: str
    sheet: str
    module: str
    name: str
    at: Point
    size: Size
    page: str
    file: str = ""
    pins: tuple[DrawnPin, ...] = ()
    fields: tuple[DrawnField, ...] = ()
    """Optional Sheetname/Sheetfile poses and effects; their text stays in name/file."""
    properties: tuple[DrawnSheetProperty, ...] = ()
    """Ordered custom property texts and poses; never overrides Sheetname or Sheetfile."""

    def __post_init__(self) -> None:
        if not self.key or not self.sheet or not self.name:
            raise ValueError("a sheet reference has a key, a sheet and a name")
        _check_point(self.at, f"sheet reference {self.key} position")
        if self.size.w <= 0 or self.size.h <= 0:
            raise ValueError(f"sheet reference {self.key}: its size must be positive")
        if not isinstance(self.fields, tuple) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(pose, DrawnField)  # pyright: ignore[reportUnnecessaryIsInstance]
            for pose in self.fields
        ):
            raise TypeError("sheet reference fields are a tuple of DrawnField poses")
        names = tuple(pose.name for pose in self.fields)
        if len(names) != len(set(names)) or set(names) - {"Sheetname", "Sheetfile"}:
            raise ValueError("sheet reference fields uniquely name Sheetname or Sheetfile")
        if not isinstance(self.properties, tuple) or any(  # pyright: ignore[reportUnnecessaryIsInstance]
            not isinstance(prop, DrawnSheetProperty)  # pyright: ignore[reportUnnecessaryIsInstance]
            for prop in self.properties
        ):
            raise TypeError("sheet reference properties are a tuple of DrawnSheetProperty values")
        property_names = tuple(prop.name for prop in self.properties)
        if len(property_names) != len(set(property_names)):
            raise ValueError("custom sheet property names are unique")


@dataclass(frozen=True, slots=True)
class DrawnJunction:
    """A junction; ``diameter`` 0 is the target's default size."""

    at: Point
    diameter: Nm = 0

    def __post_init__(self) -> None:
        _check_point(self.at, "junction position")
        if isinstance(self.diameter, bool) or not isinstance(self.diameter, int) or self.diameter < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise ValueError(f"junction diameter {self.diameter!r} is not whole nanometres from 0")


@dataclass(frozen=True, slots=True)
class DrawnBusEntry:
    """A bus entry from ``at`` to ``at + size``."""

    at: Point
    size: Point

    def __post_init__(self) -> None:
        _check_point(self.at, "bus entry position")
        _check_point(self.size, "bus entry size")

    @property
    def end(self) -> Point:
        return Point(self.at.x + self.size.x, self.at.y + self.size.y)


@dataclass(frozen=True, slots=True)
class DrawnBusAlias:
    """A bus alias of a sheet: ``name`` stands for ``members``."""

    name: str
    members: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class DrawnOpaque:
    """An item the model does not hold, kept verbatim: one KiCad S-expression and optionally Altium text."""

    kicad: str
    altium: str = ""


@dataclass(frozen=True, slots=True)
class DrawnSheet:
    """One drawn sheet, keyed by ``key``. A ``generated`` sheet holds no item: the generator draws it."""

    key: str
    paper: str = "A4"
    title_block: tuple[tuple[str, str], ...] = ()
    """The title block as (field, text) pairs: the fields of ``TitleBlock`` and ``param.<name>``; empty for
    the board's title block."""
    generated: bool = False
    symbols: tuple[DrawnSymbol, ...] = ()
    powers: tuple[DrawnPower, ...] = ()
    wires: tuple[tuple[Point, ...], ...] = ()
    """Wire polylines; each pair of points is one segment."""
    buses: tuple[tuple[Point, ...], ...] = ()
    bus_entries: tuple[DrawnBusEntry, ...] = ()
    junctions: tuple[DrawnJunction, ...] = ()
    no_connects: tuple[Point, ...] = ()
    labels: tuple[DrawnLabel, ...] = ()
    bus_aliases: tuple[DrawnBusAlias, ...] = ()
    sheet_refs: tuple[DrawnSheetRef, ...] = ()
    opaques: tuple[DrawnOpaque, ...] = ()

    def __post_init__(self) -> None:
        for polyline in (*self.wires, *self.buses):
            if len(polyline) < 2:
                raise ValueError(f"sheet {self.key}: a wire or bus has two or more points")
            for point in polyline:
                _check_point(point, f"sheet {self.key} wire point")

    def block(self) -> TitleBlock | None:
        """The title block as a ``TitleBlock``, or ``None`` when the sheet takes the board's."""
        if not self.title_block:
            return None
        texts = {k: v for k, v in self.title_block if not k.startswith("param.")}
        params = {k.removeprefix("param."): v for k, v in self.title_block if k.startswith("param.")}
        return TitleBlock(**texts, params=params)

    def segments(self) -> tuple[tuple[Point, Point], ...]:
        """The wire segments, in order; a segment of zero length is left out."""
        return _segments(self.wires)

    def bus_segments(self) -> tuple[tuple[Point, Point], ...]:
        """The bus segments, in order; a segment of zero length is left out."""
        return _segments(self.buses)


def _segments(polylines: tuple[tuple[Point, ...], ...]) -> tuple[tuple[Point, Point], ...]:
    return tuple(
        (polyline[i], polyline[i + 1])
        for polyline in polylines
        for i in range(len(polyline) - 1)
        if polyline[i] != polyline[i + 1]
    )


@dataclass(frozen=True, slots=True)
class DrawnInstance:
    """One instance of a drawn sheet: the code module whose parts it shows, the sheet key, the reference
    keys and names from the root (empty for the root), and the index of its parent instance."""

    module: str
    sheet: str
    keys: tuple[str, ...] = ()
    names: tuple[str, ...] = ()
    parent: int | None = None
    ref: DrawnSheetRef | None = None

    @property
    def path(self) -> str:
        """The instance's own key path, ``""`` for the root and ``a/b`` below it."""
        return "/".join(self.keys)

    def component(self, part: str) -> str:
        """The component path of the drawn ``part`` in this instance."""
        return f"{self.module}/{part}" if self.module else part


def join_module(parent: str, child: str) -> str:
    """The module path of a reference ``child`` (relative) under the module ``parent``."""
    if not child:
        return parent
    return f"{parent}/{child}" if parent else child


def _natural(text: str) -> tuple[tuple[int, int | str], ...]:
    found: list[tuple[int, int | str]] = []
    digits = ""
    other = ""
    for char in text:
        if char.isdigit():
            if other:
                found.append((1, other))
                other = ""
            digits += char
        else:
            if digits:
                found.append((0, int(digits)))
                digits = ""
            other += char
    if digits:
        found.append((0, int(digits)))
    if other:
        found.append((1, other))
    return tuple(found)


@dataclass(frozen=True, slots=True)
class DrawnSchematic:
    """A drawn schematic: the key of its root sheet and its sheets in file order."""

    root: str
    sheets: tuple[DrawnSheet, ...] = field(default=())

    def sheet(self, key: str) -> DrawnSheet | None:
        return next((sheet for sheet in self.sheets if sheet.key == key), None)

    def walk(self) -> tuple[tuple[DrawnInstance, ...], tuple[tuple[str, ...], ...], tuple[str, ...]]:
        """The instances in page order (depth first, the references of a sheet by page), the cycles met
        (each the sheet keys around it) and the references that name no sheet (``sheet:ref`` keys)."""
        found: list[DrawnInstance] = []
        cycles: list[tuple[str, ...]] = []
        unknown: list[str] = []
        root = self.sheet(self.root)
        if root is None:
            return (), (), (self.root,)

        def visit(index: int, trail: tuple[str, ...]) -> None:
            instance = found[index]
            sheet = self.sheet(instance.sheet)
            if sheet is None:
                return
            refs = sorted(enumerate(sheet.sheet_refs), key=lambda pair: (_natural(pair[1].page), pair[0]))
            for _, ref in refs:
                child = self.sheet(ref.sheet)
                if child is None:
                    unknown.append(f"{sheet.key}:{ref.key}")
                    continue
                if ref.sheet in trail:
                    cycle = (*trail[trail.index(ref.sheet) :], ref.sheet)
                    if not any(set(cycle) == set(known) for known in cycles):
                        cycles.append(cycle)
                    continue
                found.append(
                    DrawnInstance(
                        join_module(instance.module, ref.module),
                        ref.sheet,
                        (*instance.keys, ref.key),
                        (*instance.names, ref.name),
                        index,
                        ref,
                    )
                )
                visit(len(found) - 1, (*trail, ref.sheet))

        found.append(DrawnInstance("", root.key))
        visit(0, (root.key,))
        return tuple(found), tuple(cycles), tuple(unknown)

    def instances(self) -> tuple[tuple[str, str], ...]:
        """``(module path, sheet key)`` of every instance, in page order; the root is ``("", root)``."""
        return tuple((instance.module, instance.sheet) for instance in self.walk()[0])


__all__ = [
    "FIELD_ROTATIONS",
    "JUSTIFY_WORDS",
    "MIRRORS",
    "ROTATIONS",
    "SCHEMA",
    "TITLE_FIELDS",
    "DrawnBusAlias",
    "DrawnBusEntry",
    "DrawnField",
    "DrawnFont",
    "DrawnInstance",
    "DrawnJunction",
    "DrawnLabel",
    "DrawnLabelKind",
    "DrawnOpaque",
    "DrawnPin",
    "DrawnPower",
    "DrawnSchematic",
    "DrawnSheet",
    "DrawnSheetProperty",
    "DrawnSheetRef",
    "DrawnShape",
    "DrawnSymbol",
    "join_module",
    "title_pairs",
]
