# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Typed records of Altium schematics and schematic libraries (``docs/formats/altium/schematic-records.md``).

Every record keeps its payload and its property list; typed attributes are read-only views computed from the
property list (or, for a binary pin, from its decoded fields), so a typed value never disagrees with the kept
bytes. Each class declares ``FIELDS``, the keys and key patterns it reads (``X<n>``: any decimal ``n``);
``MODELED`` lists them, and ``unknown_keys`` lists the keys of a record that no field covers. One class per
record id of the closed table ``RECORD_TYPES``; any other record is an ``UnknownRecord``.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from typing import ClassVar, Literal

from fenolite.backends.altium.read.sch.props import UTF8_PREFIX, PropertyList, decode_value, parse_int
from fenolite.backends.altium.read.sch.units import FRAC_PER_UNIT, Color, Point, SchLength, parse_udeg

Kind = Literal["integer", "boolean", "text", "colour", "length", "fraction", "real", "count", "quarter"]
INT: Kind = "integer"
BOOL: Kind = "boolean"
TEXT: Kind = "text"
COLOR: Kind = "colour"
LENGTH: Kind = "length"
FRAC: Kind = "fraction"
REAL: Kind = "real"
COUNT: Kind = "count"
QUARTER: Kind = "quarter"
NUMERIC: frozenset[str] = frozenset({INT, COLOR, LENGTH, FRAC, COUNT, QUARTER})
DEFAULTS: dict[str, str] = {
    INT: "0",
    BOOL: "false",
    TEXT: '""',
    COLOR: "0 (black)",
    LENGTH: "0",
    FRAC: "0",
    REAL: "0",
    COUNT: "0",
    QUARTER: "0",
}
"""The value a missing key reads as, by kind, for the record page."""

StreamName = Literal["main", "additional", "data"]


@dataclass(frozen=True, slots=True)
class RecordRef:
    """A record by its index space and its index: ``main`` (``FileHeader`` or the first ASCII section),
    ``additional`` (the ``Additional`` stream or section) or ``data`` (a library component's ``Data``)."""

    stream: str
    index: int


@dataclass(frozen=True, slots=True)
class FieldSpec:
    """One modelled key (or key pattern with ``<n>``), its value kind and the attribute that reads it."""

    key: str
    kind: Kind
    attribute: str = ""


def F(key: str, kind: Kind, attribute: str = "") -> FieldSpec:
    return FieldSpec(key, kind, attribute)


def _len_fields(key: str, attribute: str) -> tuple[FieldSpec, ...]:
    """A length key and its ``_FRAC`` key."""
    return (F(key, LENGTH, attribute), F(f"{key}_FRAC", FRAC, attribute))


def _point_fields(prefix: str, attribute: str) -> tuple[FieldSpec, ...]:
    return _len_fields(f"{prefix}.X", attribute) + _len_fields(f"{prefix}.Y", attribute)


POINTS_FIELDS: tuple[FieldSpec, ...] = (
    F("LOCATIONCOUNT", COUNT, "points"),
    *_len_fields("X<n>", "points"),
    *_len_fields("Y<n>", "points"),
)
BASE_FIELDS: tuple[FieldSpec, ...] = (
    F("RECORD", INT, "record_id"),
    F("OWNERINDEX", INT, "owner"),
    F("OWNERPARTID", INT, "owner_part"),
    F("OWNERPARTDISPLAYMODE", INT, "owner_display_mode"),
    F("OWNERINDEXADDITIONALLIST", BOOL, "owner"),
    F("INDEXINSHEET", INT, "index_in_sheet"),
    F("UNIQUEID", TEXT, "unique_id"),
)
"""Keys every typed record models (``schematic-records.md``, "Every record")."""


def _pattern(key: str) -> re.Pattern[str]:
    return re.compile("^" + re.escape(key).replace("<n>", r"(\d+)").replace("<i>", r"(\d+)") + "$")


@dataclass(frozen=True, slots=True)
class Font:
    """One entry of a font table (``FONTIDCOUNT``, ``SIZE<i>``, ``FONTNAME<i>`` …), 1-based."""

    index: int
    name: str
    size: int
    italic: bool = False
    bold: bool = False
    underline: bool = False
    rotation: int = 0


@dataclass(frozen=True, slots=True)
class DataFile:
    """One data file of an implementation: ``MODELDATAFILEENTITY<i>``, ``MODELDATAFILEKIND<i>``,
    ``MODELDATAFILE<i>``. The file name is text and is never opened."""

    index: int
    entity: str
    kind: str
    file: str


@dataclass(frozen=True, slots=True)
class PinFields:
    """The decoded fields of a binary pin (``schematic-library.md``, "Pin fields"); strings stay raw."""

    record_id: int
    unknown_byte: int
    owner_part: int
    display_mode: int
    inner_edge: int
    outer_edge: int
    inside: int
    outside: int
    description: bytes
    formal_type: int
    electrical: int
    conglomerate: int
    length: int
    x: int
    y: int
    color: int
    name: bytes
    designator: bytes
    swap_group: bytes
    part_and_sequence: bytes
    default_value: bytes
    strings_read: int
    tail: bytes
    codepage: str = "cp1252"


@dataclass(frozen=True, slots=True)
class SchRecord:
    """One record: where it is (``ref``, ``offset``), its frame ``kind``, its exact ``payload``, its property
    list (``None`` for a binary record) and its place in the owner tree. ``segments`` say how the property
    list's bytes are laid out in the payload: per piece, its length and the bytes after it (a NUL, a line end,
    or ``|>`` and a line end for a continued ASCII line)."""

    ref: RecordRef
    kind: int
    payload: bytes
    offset: int
    props: PropertyList | None
    segments: tuple[tuple[int, bytes], ...] = ()
    owner: RecordRef | None = None
    children: tuple[RecordRef, ...] = ()
    bad_keys: tuple[str, ...] = ()
    pin_fields: PinFields | None = None
    pin_fracs: tuple[int, int, int] | None = None

    RECORD_ID: ClassVar[int | None] = None
    FIELDS: ClassVar[tuple[FieldSpec, ...]] = BASE_FIELDS
    MODELED: ClassVar[tuple[str, ...]] = ()
    _EXACT: ClassVar[dict[str, FieldSpec]] = {}
    _PATTERNS: ClassVar[tuple[tuple[re.Pattern[str], FieldSpec], ...]] = ()
    _SPEC_CACHE: ClassVar[dict[str, FieldSpec | None]] = {}

    def __init_subclass__(cls) -> None:
        exact: dict[str, FieldSpec] = {}
        patterns: list[tuple[re.Pattern[str], FieldSpec]] = []
        for spec in cls.FIELDS:
            if "<" in spec.key:
                patterns.append((_pattern(spec.key), spec))
            else:
                exact.setdefault(spec.key, spec)
        cls._EXACT = exact
        cls._PATTERNS = tuple(patterns)
        cls._SPEC_CACHE = {}
        cls.MODELED = tuple(dict.fromkeys(spec.key for spec in cls.FIELDS))

    # --- the closed vocabulary ---------------------------------------------------------------------------

    @classmethod
    def spec_for(cls, key: str) -> FieldSpec | None:
        """The field that models the folded ``key`` (a ``%UTF8%`` twin maps to its plain key), or ``None``."""
        cache = cls._SPEC_CACHE
        if key in cache:
            return cache[key]
        plain = key[len(UTF8_PREFIX) :] if key.startswith(UTF8_PREFIX) else key
        spec = cls._EXACT.get(plain)
        if spec is None:
            spec = next((candidate for pattern, candidate in cls._PATTERNS if pattern.match(plain)), None)
        if len(cache) < 4096:
            cache[key] = spec
        return spec

    # --- identity ----------------------------------------------------------------------------------------

    @property
    def record_id(self) -> int | None:
        if self.pin_fields is not None:
            return self.pin_fields.record_id
        if self.props is None:
            return None
        return parse_int(self.props.raw("RECORD"))

    @property
    def binary(self) -> bool:
        return self.pin_fields is not None

    @property
    def owner_part(self) -> int:
        if self.pin_fields is not None:
            return self.pin_fields.owner_part
        return self._int("OWNERPARTID", -1)

    @property
    def owner_display_mode(self) -> int:
        if self.pin_fields is not None:
            return self.pin_fields.display_mode
        return self._int("OWNERPARTDISPLAYMODE", 0)

    @property
    def index_in_sheet(self) -> int:
        return self._int("INDEXINSHEET")

    @property
    def unique_id(self) -> str:
        return self._text("UNIQUEID")

    @property
    def owner_index(self) -> int | None:
        """The raw ``OWNERINDEX`` (``None`` when absent or not an integer)."""
        if self.props is None:
            return None
        return parse_int(self.props.raw("OWNERINDEX"))

    @property
    def unknown_keys(self) -> tuple[str, ...]:
        """The folded keys that ``MODELED`` does not cover, and modelled keys whose value did not parse, in
        file order."""
        if self.props is None:
            return ()
        bad = set(self.bad_keys)
        return tuple(key for key in self.props.keys() if key in bad or self.spec_for(key) is None)

    # --- typed helpers -----------------------------------------------------------------------------------

    def _int(self, key: str, default: int = 0) -> int:
        return default if self.props is None else self.props.int(key, default)

    def _bool(self, key: str) -> bool:
        return self.props is not None and self.props.bool(key)

    def _text(self, key: str) -> str:
        return "" if self.props is None else self.props.text(key)

    def _len(self, key: str) -> SchLength:
        return SchLength.of(self._int(key), self._int(f"{key}_FRAC"))

    def _point(self, prefix: str) -> Point:
        return (self._len(f"{prefix}.X"), self._len(f"{prefix}.Y"))

    def _color(self, key: str) -> Color:
        return Color.of(self._int(key))

    def _udeg(self, key: str) -> int:
        if self.props is None:
            return 0
        raw = self.props.raw(key)
        if raw is None:
            return 0
        value = parse_udeg(raw.decode("latin-1"))
        return 0 if value is None else value

    def _indexes(self, pattern: str) -> tuple[int, ...]:
        """The sorted numbers ``n`` of the keys matching ``pattern`` (e.g. ``X(\\d+)``)."""
        if self.props is None:
            return ()
        compiled = re.compile(f"^{pattern}$")
        found = {int(m.group(1)) for key in self.props.keys() if (m := compiled.match(key))}
        return tuple(sorted(found))

    def trusted_count(self, key: str) -> int:
        """The value of the count ``key`` when the record can hold it (0 to the payload's length in bytes),
        else 0: a count never drives a loop longer than the record."""
        if self.props is None:
            return 0
        value = parse_int(self.props.raw(key))
        if value is None or not 0 <= value <= len(self.payload):
            return 0
        return value

    def _points(self) -> tuple[Point, ...]:
        """Points 1 to ``LOCATIONCOUNT`` (a point whose keys are all left out is (0, 0)), and any point with a
        key past the count."""
        present = set(self._indexes(r"X(\d+)")) | set(self._indexes(r"Y(\d+)"))
        numbers = sorted(present | set(range(1, self.trusted_count("LOCATIONCOUNT") + 1)))
        return tuple((self._len(f"X{n}"), self._len(f"Y{n}")) for n in numbers)


MODELED_BASE = tuple(spec.key for spec in BASE_FIELDS)


class PropertyRecord(SchRecord):
    """A header record (``FileHeader``, ``Additional``, ``Storage``, ``SectionKeys`` or a section line): a
    property list without ``RECORD``."""

    __slots__ = ()
    FIELDS = (
        F("HEADER", TEXT, "header"),
        F("WEIGHT", INT, "weight"),
        F("MINORVERSION", INT),
        F("UNIQUEID", TEXT),
    )

    @property
    def header(self) -> str:
        return self._text("HEADER")


class UnknownRecord(SchRecord):
    """A record with no class: an id outside the table, a binary record that is not a pin, a malformed
    record, or an empty ASCII line. Its property list, when it has one, is kept whole."""

    __slots__ = ()


class _Located(SchRecord):
    __slots__ = ()

    @property
    def location(self) -> Point:
        return self._point("LOCATION")

    @property
    def color(self) -> Color:
        return self._color("COLOR")


class _Graphic(_Located):
    __slots__ = ()

    @property
    def line_width(self) -> int:
        return self._int("LINEWIDTH")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def solid(self) -> bool:
        return self._bool("ISSOLID")

    @property
    def not_accessible(self) -> bool:
        return self._bool("ISNOTACCESIBLE")

    @property
    def corner(self) -> Point:
        return self._point("CORNER")


class _Text(_Located):
    __slots__ = ()

    @property
    def text(self) -> str:
        return self._text("TEXT")

    @property
    def font_id(self) -> int:
        return self._int("FONTID")

    @property
    def orientation(self) -> int:
        return self._int("ORIENTATION")


class _Polyline(_Graphic):
    __slots__ = ()

    @property
    def points(self) -> tuple[Point, ...]:
        return self._points()


GRAPHIC_FIELDS = (
    *_point_fields("LOCATION", "location"),
    F("COLOR", COLOR, "color"),
    F("LINEWIDTH", INT, "line_width"),
    F("ISNOTACCESIBLE", BOOL, "not_accessible"),
)
FILL_FIELDS = (F("AREACOLOR", COLOR, "area_color"), F("ISSOLID", BOOL, "solid"))
TEXT_FIELDS = (
    *_point_fields("LOCATION", "location"),
    F("COLOR", COLOR, "color"),
    F("TEXT", TEXT, "text"),
    F("FONTID", INT, "font_id"),
    F("ORIENTATION", QUARTER, "orientation"),
)


# --- sheet and components -------------------------------------------------------------------------------


class Component(_Located):
    """Record 1: a placed component (schematic) or the symbol's component record (library)."""

    __slots__ = ()
    RECORD_ID = 1
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        F("LIBREFERENCE", TEXT, "lib_reference"),
        F("COMPONENTDESCRIPTION", TEXT, "description"),
        F("DESIGNITEMID", TEXT, "design_item_id"),
        F("SOURCELIBRARYNAME", TEXT, "source_library"),
        F("LIBRARYPATH", TEXT, "library_path"),
        F("TARGETFILENAME", TEXT, "target_file_name"),
        F("PARTCOUNT", INT, "part_count"),
        F("CURRENTPARTID", INT, "current_part"),
        F("DISPLAYMODECOUNT", INT, "display_mode_count"),
        F("DISPLAYMODE", INT, "display_mode"),
        F("ORIENTATION", QUARTER, "orientation"),
        F("ISMIRRORED", BOOL, "mirrored"),
        F("COLOR", COLOR, "color"),
        F("AREACOLOR", COLOR, "area_color"),
        F("COMPONENTKIND", INT, "component_kind"),
        F("PARTIDLOCKED", BOOL, "part_id_locked"),
        F("DESIGNATORLOCKED", BOOL, "designator_locked"),
        F("PINSMOVEABLE", BOOL, "pins_moveable"),
        F("SHEETPARTFILENAME", TEXT, "sheet_part_file_name"),
        F("ALIASLIST", TEXT, "alias_list"),
        F("DATABASETABLENAME", TEXT, "database_table_name"),
        F("NOTUSEDBTABLENAME", BOOL, "not_use_db_table_name"),
    )

    @property
    def lib_reference(self) -> str:
        return self._text("LIBREFERENCE")

    @property
    def description(self) -> str:
        return self._text("COMPONENTDESCRIPTION")

    @property
    def design_item_id(self) -> str:
        return self._text("DESIGNITEMID")

    @property
    def source_library(self) -> str:
        return self._text("SOURCELIBRARYNAME")

    @property
    def library_path(self) -> str:
        return self._text("LIBRARYPATH")

    @property
    def target_file_name(self) -> str:
        return self._text("TARGETFILENAME")

    @property
    def orientation(self) -> int:
        return self._int("ORIENTATION")

    @property
    def mirrored(self) -> bool:
        return self._bool("ISMIRRORED")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def part_count(self) -> int:
        """``PARTCOUNT − 1``; 1 when the key is missing or the result is below 1."""
        if self.props is None or not self.props.has("PARTCOUNT"):
            return 1
        return max(1, self._int("PARTCOUNT") - 1)

    @property
    def current_part(self) -> int:
        return self._int("CURRENTPARTID", 1)

    @property
    def display_mode_count(self) -> int:
        return self._int("DISPLAYMODECOUNT", 1)

    @property
    def display_mode(self) -> int:
        return self._int("DISPLAYMODE", 0)

    @property
    def component_kind(self) -> int:
        return self._int("COMPONENTKIND")

    @property
    def part_id_locked(self) -> bool:
        return self._bool("PARTIDLOCKED")

    @property
    def designator_locked(self) -> bool:
        return self._bool("DESIGNATORLOCKED")

    @property
    def pins_moveable(self) -> bool:
        return self._bool("PINSMOVEABLE")

    @property
    def sheet_part_file_name(self) -> str:
        return self._text("SHEETPARTFILENAME")

    @property
    def alias_list(self) -> str:
        return self._text("ALIASLIST")

    @property
    def database_table_name(self) -> str:
        return self._text("DATABASETABLENAME")

    @property
    def not_use_db_table_name(self) -> bool:
        return self._bool("NOTUSEDBTABLENAME")


DIRECTIONS: dict[int, tuple[int, int]] = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
"""Bits 0 and 1 of ``PINCONGLOMERATE``: rightwards, upwards, leftwards, downwards."""


class Pin(SchRecord):
    """Record 2, a pin: a property list (``RECORD=2``) or a binary pin record (``binary`` is ``True``)."""

    __slots__ = ()
    RECORD_ID = 2
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        *_len_fields("PINLENGTH", "length"),
        F("NAME", TEXT, "name"),
        F("DESIGNATOR", TEXT, "designator"),
        F("DESCRIPTION", TEXT, "description"),
        F("ELECTRICAL", INT, "electrical"),
        F("PINCONGLOMERATE", INT, "direction"),
        F("FORMALTYPE", INT, "formal_type"),
        F("SYMBOL_INNEREDGE", INT, "inner_edge"),
        F("SYMBOL_OUTEREDGE", INT, "outer_edge"),
        F("SYMBOL_INNER", INT, "inside"),
        F("SYMBOL_OUTER", INT, "outside"),
        F("SWAPIDPIN", TEXT, "swap_group"),
        F("SWAPIDPART", TEXT, "part_and_sequence"),
        F("COLOR", COLOR, "color"),
    )

    @property
    def name(self) -> str:
        fields = self.pin_fields
        return self._decoded(fields.name) if fields is not None else self._text("NAME")

    @property
    def designator(self) -> str:
        fields = self.pin_fields
        return self._decoded(fields.designator) if fields is not None else self._text("DESIGNATOR")

    @property
    def description(self) -> str:
        fields = self.pin_fields
        return self._decoded(fields.description) if fields is not None else self._text("DESCRIPTION")

    @property
    def swap_group(self) -> str:
        fields = self.pin_fields
        return self._decoded(fields.swap_group) if fields is not None else self._text("SWAPIDPIN")

    @property
    def part_and_sequence(self) -> str:
        fields = self.pin_fields
        return self._decoded(fields.part_and_sequence) if fields is not None else self._text("SWAPIDPART")

    @property
    def default_value(self) -> str:
        """The fifth short string of a binary pin; a text pin has no modelled key for it, so ``""``."""
        fields = self.pin_fields
        return self._decoded(fields.default_value) if fields is not None else ""

    def _decoded(self, raw: bytes) -> str:
        return decode_value(raw, self.codepage)[0].strip()

    @property
    def codepage(self) -> str:
        """The code page the reader was given."""
        if self.pin_fields is not None:
            return self.pin_fields.codepage
        return "cp1252" if self.props is None else self.props.codepage

    @property
    def electrical(self) -> int:
        fields = self.pin_fields
        return fields.electrical if fields is not None else self._int("ELECTRICAL")

    @property
    def conglomerate(self) -> int:
        fields = self.pin_fields
        return fields.conglomerate if fields is not None else self._int("PINCONGLOMERATE")

    @property
    def direction(self) -> int:
        return self.conglomerate & 0x03

    @property
    def hidden(self) -> bool:
        return bool(self.conglomerate & 0x04)

    @property
    def name_shown(self) -> bool:
        return bool(self.conglomerate & 0x08)

    @property
    def designator_shown(self) -> bool:
        return bool(self.conglomerate & 0x10)

    @property
    def formal_type(self) -> int:
        fields = self.pin_fields
        return fields.formal_type if fields is not None else self._int("FORMALTYPE")

    @property
    def inner_edge(self) -> int:
        fields = self.pin_fields
        return fields.inner_edge if fields is not None else self._int("SYMBOL_INNEREDGE")

    @property
    def outer_edge(self) -> int:
        fields = self.pin_fields
        return fields.outer_edge if fields is not None else self._int("SYMBOL_OUTEREDGE")

    @property
    def inside(self) -> int:
        fields = self.pin_fields
        return fields.inside if fields is not None else self._int("SYMBOL_INNER")

    @property
    def outside(self) -> int:
        fields = self.pin_fields
        return fields.outside if fields is not None else self._int("SYMBOL_OUTER")

    @property
    def color(self) -> Color:
        fields = self.pin_fields
        return Color.of(fields.color) if fields is not None else self._color("COLOR")

    @property
    def location(self) -> Point:
        fields = self.pin_fields
        if fields is None:
            return self._point("LOCATION")
        fracs = self.pin_fracs or (0, 0, 0)
        return (SchLength.of(fields.x, fracs[0]), SchLength.of(fields.y, fracs[1]))

    @property
    def length(self) -> SchLength:
        fields = self.pin_fields
        if fields is None:
            return self._len("PINLENGTH")
        fracs = self.pin_fracs or (0, 0, 0)
        return SchLength.of(fields.length, fracs[2])

    @property
    def hot_end(self) -> Point:
        """``location`` moved by ``length`` in the pin's direction: the electrical end."""
        x, y = self.location
        dx, dy = DIRECTIONS[self.direction]
        step = self.length.value
        return (SchLength(x.value + dx * step), SchLength(y.value + dy * step))

    @property
    def strings_read(self) -> int:
        """How many of the five short strings a binary pin held; 0 for a text pin."""
        return 0 if self.pin_fields is None else self.pin_fields.strings_read

    @property
    def tail(self) -> bytes:
        return b"" if self.pin_fields is None else self.pin_fields.tail

    @property
    def unknown_byte(self) -> int:
        return 0 if self.pin_fields is None else self.pin_fields.unknown_byte

    @property
    def fraction_source(self) -> str:
        """``"PinFrac"`` when a decoded side stream added fractions to this pin, else ``""``."""
        return "PinFrac" if self.pin_fracs is not None else ""


class Designator(_Text):
    """Record 34: the designator of a component."""

    __slots__ = ()
    RECORD_ID = 34
    FIELDS = (
        *BASE_FIELDS,
        *TEXT_FIELDS,
        F("NAME", TEXT, "name"),
        F("ISHIDDEN", BOOL, "hidden"),
        F("ISMIRRORED", BOOL, "mirrored"),
        F("READONLYSTATE", INT, "read_only_state"),
        F("OVERRIDENOTAUTOPOSITION", BOOL, "override_not_auto_position"),
    )

    @property
    def name(self) -> str:
        return self._text("NAME")

    @property
    def hidden(self) -> bool:
        return self._bool("ISHIDDEN")

    @property
    def mirrored(self) -> bool:
        return self._bool("ISMIRRORED")

    @property
    def read_only_state(self) -> int:
        return self._int("READONLYSTATE")

    @property
    def override_not_auto_position(self) -> bool:
        return self._bool("OVERRIDENOTAUTOPOSITION")


class Parameter(_Text):
    """Record 41: a parameter of its owner (a component, a directive, or the sheet when it has no owner)."""

    __slots__ = ()
    RECORD_ID = 41
    FIELDS = (
        *BASE_FIELDS,
        *TEXT_FIELDS,
        F("NAME", TEXT, "name"),
        F("ISHIDDEN", BOOL, "hidden"),
        F("ISMIRRORED", BOOL, "mirrored"),
        F("READONLYSTATE", INT, "read_only_state"),
        F("SHOWNAME", BOOL, "show_name"),
        F("NOTAUTOPOSITION", BOOL, "not_auto_position"),
    )

    @property
    def name(self) -> str:
        return self._text("NAME")

    @property
    def hidden(self) -> bool:
        return self._bool("ISHIDDEN")

    @property
    def mirrored(self) -> bool:
        return self._bool("ISMIRRORED")

    @property
    def read_only_state(self) -> int:
        return self._int("READONLYSTATE")

    @property
    def show_name(self) -> bool:
        return self._bool("SHOWNAME")

    @property
    def not_auto_position(self) -> bool:
        return self._bool("NOTAUTOPOSITION")


class ImplementationList(SchRecord):
    """Record 44: the list of a component's models."""

    __slots__ = ()
    RECORD_ID = 44
    FIELDS = BASE_FIELDS


class Implementation(SchRecord):
    """Record 45: one model (a footprint, a simulation model …) of a component."""

    __slots__ = ()
    RECORD_ID = 45
    FIELDS = (
        *BASE_FIELDS,
        F("MODELNAME", TEXT, "model_name"),
        F("MODELTYPE", TEXT, "model_type"),
        F("DESCRIPTION", TEXT, "description"),
        F("ISCURRENT", BOOL, "is_current"),
        F("USECOMPONENTLIBRARY", BOOL, "use_component_library"),
        F("DATAFILECOUNT", COUNT, "data_files"),
        F("MODELDATAFILEENTITY<i>", TEXT, "data_files"),
        F("MODELDATAFILEKIND<i>", TEXT, "data_files"),
        F("MODELDATAFILE<i>", TEXT, "data_files"),
        F("INTEGRATEDMODEL", BOOL, "integrated_model"),
        F("DATABASEMODEL", BOOL, "database_model"),
        F("DATALINKSLOCKED", BOOL, "data_links_locked"),
        F("DATABASEDATALINKSLOCKED", BOOL, "database_data_links_locked"),
    )

    @property
    def model_name(self) -> str:
        return self._text("MODELNAME")

    @property
    def model_type(self) -> str:
        return self._text("MODELTYPE")

    @property
    def description(self) -> str:
        return self._text("DESCRIPTION")

    @property
    def is_current(self) -> bool:
        return self._bool("ISCURRENT")

    @property
    def use_component_library(self) -> bool:
        return self._bool("USECOMPONENTLIBRARY")

    @property
    def integrated_model(self) -> bool:
        return self._bool("INTEGRATEDMODEL")

    @property
    def database_model(self) -> bool:
        return self._bool("DATABASEMODEL")

    @property
    def data_links_locked(self) -> bool:
        return self._bool("DATALINKSLOCKED")

    @property
    def database_data_links_locked(self) -> bool:
        return self._bool("DATABASEDATALINKSLOCKED")

    @property
    def data_files(self) -> tuple[DataFile, ...]:
        """The data files from the keys that exist (``DATAFILECOUNT`` is not trusted), by index."""
        numbers = sorted(
            set(self._indexes(r"MODELDATAFILEENTITY(\d+)"))
            | set(self._indexes(r"MODELDATAFILEKIND(\d+)"))
            | set(self._indexes(r"MODELDATAFILE(\d+)"))
        )
        return tuple(
            DataFile(
                n,
                self._text(f"MODELDATAFILEENTITY{n}"),
                self._text(f"MODELDATAFILEKIND{n}"),
                self._text(f"MODELDATAFILE{n}"),
            )
            for n in numbers
        )


class MapDefinerList(SchRecord):
    """Record 46: the pin-to-pad map list of an implementation."""

    __slots__ = ()
    RECORD_ID = 46
    FIELDS = BASE_FIELDS


class MapDefiner(SchRecord):
    """Record 47: one map from a pin designator to model designators."""

    __slots__ = ()
    RECORD_ID = 47
    FIELDS = (
        *BASE_FIELDS,
        F("DESINTF", TEXT, "interface"),
        F("DESIMPCOUNT", COUNT, "implementations"),
        F("DESIMP<i>", TEXT, "implementations"),
    )

    @property
    def interface(self) -> str:
        return self._text("DESINTF")

    @property
    def implementations(self) -> tuple[str, ...]:
        return tuple(self._text(f"DESIMP{n}") for n in self._indexes(r"DESIMP(\d+)"))


class ImplementationParameters(SchRecord):
    """Record 48: the parameter list of an implementation."""

    __slots__ = ()
    RECORD_ID = 48
    FIELDS = BASE_FIELDS


SHEET_FONT_FIELDS = (
    F("FONTIDCOUNT", COUNT, "fonts"),
    F("SIZE<i>", INT, "fonts"),
    F("FONTNAME<i>", TEXT, "fonts"),
    F("ITALIC<i>", BOOL, "fonts"),
    F("BOLD<i>", BOOL, "fonts"),
    F("UNDERLINE<i>", BOOL, "fonts"),
    F("ROTATION<i>", INT, "fonts"),
)


def read_fonts(props: PropertyList | None) -> tuple[Font, ...]:
    """The font table from the ``SIZE<i>`` and ``FONTNAME<i>`` keys that exist (``FONTIDCOUNT`` is not
    trusted)."""
    if props is None:
        return ()
    numbers: set[int] = set()
    for key in props.keys():
        match = re.match(r"^(?:SIZE|FONTNAME)(\d+)$", key)
        if match:
            numbers.add(int(match.group(1)))
    return tuple(
        Font(
            n,
            props.text(f"FONTNAME{n}"),
            props.int(f"SIZE{n}"),
            props.bool(f"ITALIC{n}"),
            props.bool(f"BOLD{n}"),
            props.bool(f"UNDERLINE{n}"),
            props.int(f"ROTATION{n}"),
        )
        for n in sorted(numbers)
    )


class Sheet(SchRecord):
    """Record 31: the sheet, record 0 of a schematic document."""

    __slots__ = ()
    RECORD_ID = 31
    FIELDS = (
        *BASE_FIELDS,
        *SHEET_FONT_FIELDS,
        F("SYSTEMFONT", INT, "system_font"),
        F("SHEETSTYLE", INT, "sheet_style"),
        F("USECUSTOMSHEET", BOOL, "custom_size"),
        F("CUSTOMX", LENGTH, "custom_size"),
        F("CUSTOMX_FRAC", FRAC, "custom_size"),
        F("CUSTOMY", LENGTH, "custom_size"),
        F("CUSTOMY_FRAC", FRAC, "custom_size"),
        F("WORKSPACEORIENTATION", INT, "portrait"),
        F("TITLEBLOCKON", BOOL, "title_block"),
        F("BORDERON", BOOL, "border"),
        F("AREACOLOR", COLOR, "area_color"),
        F("SNAPGRIDON", BOOL, "snap_grid_on"),
        F("SNAPGRIDSIZE", INT, "snap_grid_size"),
        F("VISIBLEGRIDON", BOOL, "visible_grid_on"),
        F("VISIBLEGRIDSIZE", INT, "visible_grid_size"),
        F("HOTSPOTGRIDON", BOOL, "hotspot_grid_on"),
        F("HOTSPOTGRIDSIZE", INT, "hotspot_grid_size"),
        F("DISPLAY_UNIT", INT, "display_unit"),
        F("USEMBCS", BOOL, "use_mbcs"),
        F("ISBOC", BOOL, "is_boc"),
        F("SHEETNUMBERSPACESIZE", INT, "sheet_number_space_size"),
        F("CUSTOMXZONES", INT, "custom_x_zones"),
        F("CUSTOMYZONES", INT, "custom_y_zones"),
        F("CUSTOMMARGINWIDTH", INT, "custom_margin_width"),
        F("REFERENCEZONESON", BOOL, "reference_zones_on"),
        F("SHOWTEMPLATEGRAPHICS", BOOL, "show_template_graphics"),
        F("TEMPLATEFILENAME", TEXT, "template_file_name"),
    )

    @property
    def fonts(self) -> tuple[Font, ...]:
        return read_fonts(self.props)

    @property
    def system_font(self) -> int:
        return self._int("SYSTEMFONT")

    @property
    def sheet_style(self) -> int:
        return self._int("SHEETSTYLE")

    @property
    def custom_size(self) -> Point | None:
        """``(CUSTOMX, CUSTOMY)`` when ``USECUSTOMSHEET=T``, else ``None``."""
        if not self._bool("USECUSTOMSHEET"):
            return None
        return (self._len("CUSTOMX"), self._len("CUSTOMY"))

    @property
    def portrait(self) -> bool:
        return self._int("WORKSPACEORIENTATION") == 1

    @property
    def title_block(self) -> bool:
        return self._bool("TITLEBLOCKON")

    @property
    def border(self) -> bool:
        return self._bool("BORDERON")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def snap_grid_on(self) -> bool:
        return self._bool("SNAPGRIDON")

    @property
    def snap_grid_size(self) -> int:
        return self._int("SNAPGRIDSIZE")

    @property
    def visible_grid_on(self) -> bool:
        return self._bool("VISIBLEGRIDON")

    @property
    def visible_grid_size(self) -> int:
        return self._int("VISIBLEGRIDSIZE")

    @property
    def hotspot_grid_on(self) -> bool:
        return self._bool("HOTSPOTGRIDON")

    @property
    def hotspot_grid_size(self) -> int:
        return self._int("HOTSPOTGRIDSIZE")

    @property
    def display_unit(self) -> int:
        return self._int("DISPLAY_UNIT")

    @property
    def use_mbcs(self) -> bool:
        return self._bool("USEMBCS")

    @property
    def is_boc(self) -> bool:
        return self._bool("ISBOC")

    @property
    def sheet_number_space_size(self) -> int:
        return self._int("SHEETNUMBERSPACESIZE")

    @property
    def custom_x_zones(self) -> int:
        return self._int("CUSTOMXZONES")

    @property
    def custom_y_zones(self) -> int:
        return self._int("CUSTOMYZONES")

    @property
    def custom_margin_width(self) -> int:
        return self._int("CUSTOMMARGINWIDTH")

    @property
    def reference_zones_on(self) -> bool:
        return self._bool("REFERENCEZONESON")

    @property
    def show_template_graphics(self) -> bool:
        return self._bool("SHOWTEMPLATEGRAPHICS")

    @property
    def template_file_name(self) -> str:
        """The template's file name as text; never opened."""
        return self._text("TEMPLATEFILENAME")


class Template(SchRecord):
    """Record 39: a sheet template, owning the template's lines and labels."""

    __slots__ = ()
    RECORD_ID = 39
    FIELDS = (*BASE_FIELDS, F("FILENAME", TEXT, "file_name"), F("ISNOTACCESIBLE", BOOL, "not_accessible"))

    @property
    def file_name(self) -> str:
        """The template's file name as text; never opened."""
        return self._text("FILENAME")

    @property
    def not_accessible(self) -> bool:
        return self._bool("ISNOTACCESIBLE")


class Image(_Graphic):
    """Record 30: an image, linked by file name or embedded in ``Storage``."""

    __slots__ = ()
    RECORD_ID = 30
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *_point_fields("CORNER", "corner"),
        F("EMBEDIMAGE", BOOL, "embedded"),
        F("FILENAME", TEXT, "file_name"),
        F("KEEPASPECT", BOOL, "keep_aspect"),
    )

    @property
    def embedded(self) -> bool:
        return self._bool("EMBEDIMAGE")

    @property
    def file_name(self) -> str:
        """The image's file name as text; never opened."""
        return self._text("FILENAME")

    @property
    def keep_aspect(self) -> bool:
        return self._bool("KEEPASPECT")


# --- connectivity and hierarchy -------------------------------------------------------------------------


POLY_FIELDS = (
    F("COLOR", COLOR, "color"),
    F("LINEWIDTH", INT, "line_width"),
    *POINTS_FIELDS,
)


class Wire(_Polyline):
    """Record 27: a wire, a polyline at sheet level."""

    __slots__ = ()
    RECORD_ID = 27
    FIELDS = (*BASE_FIELDS, *POLY_FIELDS)


class Bus(_Polyline):
    """Record 26: a bus polyline."""

    __slots__ = ()
    RECORD_ID = 26
    FIELDS = (*BASE_FIELDS, *POLY_FIELDS)


class SignalHarness(_Polyline):
    """Record 218: a signal harness line."""

    __slots__ = ()
    RECORD_ID = 218
    FIELDS = (*BASE_FIELDS, *POLY_FIELDS)


class BusEntry(_Graphic):
    """Record 37: a bus entry line from ``LOCATION`` to ``CORNER``."""

    __slots__ = ()
    RECORD_ID = 37
    FIELDS = (*BASE_FIELDS, *GRAPHIC_FIELDS, *_point_fields("CORNER", "corner"))


class Junction(_Located):
    """Record 29: a junction."""

    __slots__ = ()
    RECORD_ID = 29
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        F("COLOR", COLOR, "color"),
        F("LOCKED", BOOL, "locked"),
    )

    @property
    def locked(self) -> bool:
        return self._bool("LOCKED")


class NetLabel(_Text):
    """Record 25: a net label; its location is the connection point."""

    __slots__ = ()
    RECORD_ID = 25
    FIELDS = (*BASE_FIELDS, *TEXT_FIELDS)


class PowerPort(_Text):
    """Record 17: a power port; its location is the connection point."""

    __slots__ = ()
    RECORD_ID = 17
    FIELDS = (
        *BASE_FIELDS,
        *TEXT_FIELDS,
        F("STYLE", INT, "style"),
        F("SHOWNETNAME", BOOL, "show_net_name"),
        F("ISCROSSSHEETCONNECTOR", BOOL, "cross_sheet"),
    )

    @property
    def style(self) -> int:
        return self._int("STYLE")

    @property
    def show_net_name(self) -> bool:
        return self._bool("SHOWNETNAME")

    @property
    def cross_sheet(self) -> bool:
        return self._bool("ISCROSSSHEETCONNECTOR")


class Port(_Located):
    """Record 18: a port."""

    __slots__ = ()
    RECORD_ID = 18
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        F("NAME", TEXT, "name"),
        *_len_fields("WIDTH", "width"),
        *_len_fields("HEIGHT", "height"),
        F("IOTYPE", INT, "io_type"),
        F("STYLE", INT, "style"),
        F("ALIGNMENT", INT, "alignment"),
        F("HARNESSTYPE", TEXT, "harness_type"),
        F("COLOR", COLOR, "color"),
        F("AREACOLOR", COLOR, "area_color"),
        F("TEXTCOLOR", COLOR, "text_color"),
        F("FONTID", INT, "font_id"),
    )

    @property
    def name(self) -> str:
        return self._text("NAME")

    @property
    def width(self) -> SchLength:
        return self._len("WIDTH")

    @property
    def height(self) -> SchLength:
        return self._len("HEIGHT")

    @property
    def io_type(self) -> int:
        return self._int("IOTYPE")

    @property
    def style(self) -> int:
        return self._int("STYLE")

    @property
    def alignment(self) -> int:
        return self._int("ALIGNMENT")

    @property
    def harness_type(self) -> str:
        return self._text("HARNESSTYPE")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def text_color(self) -> Color:
        return self._color("TEXTCOLOR")

    @property
    def font_id(self) -> int:
        return self._int("FONTID")


class NoErc(_Located):
    """Record 22: a No ERC directive."""

    __slots__ = ()
    RECORD_ID = 22
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        F("COLOR", COLOR, "color"),
        F("ISACTIVE", BOOL, "active"),
        F("SUPPRESSALL", BOOL, "suppress_all"),
        F("SYMBOL", TEXT, "symbol"),
        F("ORIENTATION", QUARTER, "orientation"),
    )

    @property
    def active(self) -> bool:
        return self._bool("ISACTIVE")

    @property
    def suppress_all(self) -> bool:
        return self._bool("SUPPRESSALL")

    @property
    def symbol(self) -> str:
        return self._text("SYMBOL")

    @property
    def orientation(self) -> int:
        return self._int("ORIENTATION")


BOX_FIELDS = (
    *_point_fields("LOCATION", "location"),
    *_len_fields("XSIZE", "x_size"),
    *_len_fields("YSIZE", "y_size"),
    F("COLOR", COLOR, "color"),
    F("AREACOLOR", COLOR, "area_color"),
)


class _Box(_Located):
    __slots__ = ()

    @property
    def x_size(self) -> SchLength:
        return self._len("XSIZE")

    @property
    def y_size(self) -> SchLength:
        return self._len("YSIZE")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")


class SheetSymbol(_Box):
    """Record 15: a sheet symbol; its location is its top-left corner."""

    __slots__ = ()
    RECORD_ID = 15
    FIELDS = (
        *BASE_FIELDS,
        *BOX_FIELDS,
        F("ISSOLID", BOOL, "solid"),
        F("SYMBOLTYPE", TEXT, "symbol_type"),
    )

    @property
    def solid(self) -> bool:
        return self._bool("ISSOLID")

    @property
    def symbol_type(self) -> str:
        return self._text("SYMBOLTYPE")


class _Entry(SchRecord):
    __slots__ = ()

    @property
    def name(self) -> str:
        return self._text("NAME")

    @property
    def side(self) -> int:
        return self._int("SIDE")

    @property
    def distance(self) -> SchLength:
        """``DISTANCEFROMTOP × 1 000 000 + DISTANCEFROMTOP_FRAC1``: steps of 10 units and a fraction."""
        return SchLength(
            self._int("DISTANCEFROMTOP") * 10 * FRAC_PER_UNIT + self._int("DISTANCEFROMTOP_FRAC1")
        )

    @property
    def color(self) -> Color:
        return self._color("COLOR")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def text_color(self) -> Color:
        return self._color("TEXTCOLOR")

    @property
    def text_font_id(self) -> int:
        return self._int("TEXTFONTID")

    @property
    def text_style(self) -> str:
        return self._text("TEXTSTYLE")


ENTRY_FIELDS = (
    F("NAME", TEXT, "name"),
    F("SIDE", INT, "side"),
    F("DISTANCEFROMTOP", LENGTH, "distance"),
    F("DISTANCEFROMTOP_FRAC1", FRAC, "distance"),
    F("COLOR", COLOR, "color"),
    F("AREACOLOR", COLOR, "area_color"),
    F("TEXTCOLOR", COLOR, "text_color"),
    F("TEXTFONTID", INT, "text_font_id"),
    F("TEXTSTYLE", TEXT, "text_style"),
)


class SheetEntry(_Entry):
    """Record 16: a sheet entry of a sheet symbol."""

    __slots__ = ()
    RECORD_ID = 16
    FIELDS = (
        *BASE_FIELDS,
        *ENTRY_FIELDS,
        F("IOTYPE", INT, "io_type"),
        F("STYLE", INT, "style"),
        F("ARROWKIND", TEXT, "arrow_kind"),
        F("HARNESSTYPE", TEXT, "harness_type"),
    )

    @property
    def io_type(self) -> int:
        return self._int("IOTYPE")

    @property
    def style(self) -> int:
        return self._int("STYLE")

    @property
    def arrow_kind(self) -> str:
        return self._text("ARROWKIND")

    @property
    def harness_type(self) -> str:
        return self._text("HARNESSTYPE")


class SheetName(_Text):
    """Record 32: the sheet name of a sheet symbol."""

    __slots__ = ()
    RECORD_ID = 32
    FIELDS = (*BASE_FIELDS, *TEXT_FIELDS, F("ISHIDDEN", BOOL, "hidden"))

    @property
    def hidden(self) -> bool:
        return self._bool("ISHIDDEN")


class SheetFileName(_Text):
    """Record 33: the file name of a sheet symbol, as text; never opened."""

    __slots__ = ()
    RECORD_ID = 33
    FIELDS = (*BASE_FIELDS, *TEXT_FIELDS, F("ISHIDDEN", BOOL, "hidden"))

    @property
    def hidden(self) -> bool:
        return self._bool("ISHIDDEN")


class HarnessConnector(_Box):
    """Record 215: a harness connector; its location is its top-left corner."""

    __slots__ = ()
    RECORD_ID = 215
    FIELDS = (
        *BASE_FIELDS,
        *BOX_FIELDS,
        F("LINEWIDTH", INT, "line_width"),
        F("HARNESSCONNECTORSIDE", INT, "side"),
        F("SIDE", INT, "side"),
        F("PRIMARYCONNECTIONPOSITION", INT, "primary_position"),
    )

    @property
    def line_width(self) -> int:
        return self._int("LINEWIDTH")

    @property
    def side(self) -> int:
        """``HARNESSCONNECTORSIDE``, or ``SIDE`` when that key is absent."""
        if self.props is not None and self.props.has("HARNESSCONNECTORSIDE"):
            return self._int("HARNESSCONNECTORSIDE")
        return self._int("SIDE")

    @property
    def primary_position(self) -> SchLength:
        """``PRIMARYCONNECTIONPOSITION`` in units of 10 mil below the top-left corner."""
        return SchLength.of(self._int("PRIMARYCONNECTIONPOSITION"))


class HarnessEntry(_Entry):
    """Record 216: an entry of a harness connector."""

    __slots__ = ()
    RECORD_ID = 216
    FIELDS = (*BASE_FIELDS, *ENTRY_FIELDS)


class HarnessType(_Text):
    """Record 217: the type label of a harness connector."""

    __slots__ = ()
    RECORD_ID = 217
    FIELDS = (*BASE_FIELDS, *TEXT_FIELDS, F("ISHIDDEN", BOOL, "hidden"))

    @property
    def hidden(self) -> bool:
        return self._bool("ISHIDDEN")


# --- graphics -------------------------------------------------------------------------------------------


class IeeeSymbol(_Graphic):
    """Record 3: an IEEE symbol near a pin."""

    __slots__ = ()
    RECORD_ID = 3
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        F("SYMBOL", INT, "symbol"),
        F("SCALEFACTOR", INT, "scale_factor"),
        F("ORIENTATION", QUARTER, "orientation"),
        F("ISMIRRORED", BOOL, "mirrored"),
    )

    @property
    def symbol(self) -> int:
        return self._int("SYMBOL")

    @property
    def scale_factor(self) -> int:
        return self._int("SCALEFACTOR")

    @property
    def orientation(self) -> int:
        return self._int("ORIENTATION")

    @property
    def mirrored(self) -> bool:
        return self._bool("ISMIRRORED")


class Label(_Text):
    """Record 4: a text note."""

    __slots__ = ()
    RECORD_ID = 4
    FIELDS = (
        *BASE_FIELDS,
        *TEXT_FIELDS,
        F("JUSTIFICATION", INT, "justification"),
        F("ISMIRRORED", BOOL, "mirrored"),
        F("ISNOTACCESIBLE", BOOL, "not_accessible"),
        F("GRAPHICALLYLOCKED", BOOL, "locked"),
    )

    @property
    def justification(self) -> int:
        return self._int("JUSTIFICATION")

    @property
    def mirrored(self) -> bool:
        return self._bool("ISMIRRORED")

    @property
    def not_accessible(self) -> bool:
        return self._bool("ISNOTACCESIBLE")

    @property
    def locked(self) -> bool:
        return self._bool("GRAPHICALLYLOCKED")


LINE_SHAPE_FIELDS = (
    F("LINESTYLE", INT, "line_style"),
    F("STARTLINESHAPE", INT, "start_line_shape"),
    F("ENDLINESHAPE", INT, "end_line_shape"),
    F("LINESHAPESIZE", INT, "line_shape_size"),
)


class _Shaped(_Polyline):
    __slots__ = ()

    @property
    def line_style(self) -> int:
        return self._int("LINESTYLE")

    @property
    def start_line_shape(self) -> int:
        return self._int("STARTLINESHAPE")

    @property
    def end_line_shape(self) -> int:
        return self._int("ENDLINESHAPE")

    @property
    def line_shape_size(self) -> int:
        return self._int("LINESHAPESIZE")


class Bezier(_Polyline):
    """Record 5: a Bezier curve; its points are the control points."""

    __slots__ = ()
    RECORD_ID = 5
    FIELDS = (*BASE_FIELDS, *POLY_FIELDS, F("ISNOTACCESIBLE", BOOL, "not_accessible"))


class Polyline(_Shaped):
    """Record 6: a polyline."""

    __slots__ = ()
    RECORD_ID = 6
    FIELDS = (*BASE_FIELDS, *POLY_FIELDS, *LINE_SHAPE_FIELDS, F("ISNOTACCESIBLE", BOOL, "not_accessible"))


class Polygon(_Polyline):
    """Record 7: a polygon."""

    __slots__ = ()
    RECORD_ID = 7
    FIELDS = (
        *BASE_FIELDS,
        *POLY_FIELDS,
        *FILL_FIELDS,
        F("ISNOTACCESIBLE", BOOL, "not_accessible"),
        F("IGNOREONLOAD", BOOL, "ignore_on_load"),
    )

    @property
    def ignore_on_load(self) -> bool:
        return self._bool("IGNOREONLOAD")


class _Round(_Graphic):
    __slots__ = ()

    @property
    def radius(self) -> SchLength:
        return self._len("RADIUS")

    @property
    def secondary_radius(self) -> SchLength:
        return self._len("SECONDARYRADIUS")

    @property
    def start_angle(self) -> int:
        """Microdegrees."""
        return self._udeg("STARTANGLE")

    @property
    def end_angle(self) -> int:
        """Microdegrees."""
        return self._udeg("ENDANGLE")


RADIUS_FIELDS = _len_fields("RADIUS", "radius")
ANGLE_FIELDS = (F("STARTANGLE", REAL, "start_angle"), F("ENDANGLE", REAL, "end_angle"))


class Ellipse(_Round):
    """Record 8: an ellipse."""

    __slots__ = ()
    RECORD_ID = 8
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *FILL_FIELDS,
        *RADIUS_FIELDS,
        *_len_fields("SECONDARYRADIUS", "secondary_radius"),
    )


class PieChart(_Round):
    """Record 9: a pie chart."""

    __slots__ = ()
    RECORD_ID = 9
    FIELDS = (*BASE_FIELDS, *GRAPHIC_FIELDS, *FILL_FIELDS, *RADIUS_FIELDS, *ANGLE_FIELDS)


class RoundRectangle(_Graphic):
    """Record 10: a rectangle with round corners."""

    __slots__ = ()
    RECORD_ID = 10
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *FILL_FIELDS,
        *_point_fields("CORNER", "corner"),
        *_len_fields("CORNERXRADIUS", "corner_x_radius"),
        *_len_fields("CORNERYRADIUS", "corner_y_radius"),
    )

    @property
    def corner_x_radius(self) -> SchLength:
        return self._len("CORNERXRADIUS")

    @property
    def corner_y_radius(self) -> SchLength:
        return self._len("CORNERYRADIUS")


class EllipticalArc(_Round):
    """Record 11: an elliptical arc."""

    __slots__ = ()
    RECORD_ID = 11
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *RADIUS_FIELDS,
        *_len_fields("SECONDARYRADIUS", "secondary_radius"),
        *ANGLE_FIELDS,
    )


class Arc(_Round):
    """Record 12: a circle or an arc; angles in microdegrees."""

    __slots__ = ()
    RECORD_ID = 12
    FIELDS = (*BASE_FIELDS, *GRAPHIC_FIELDS, *RADIUS_FIELDS, *ANGLE_FIELDS)


class Line(_Graphic):
    """Record 13: a line from ``LOCATION`` to ``CORNER``."""

    __slots__ = ()
    RECORD_ID = 13
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *_point_fields("CORNER", "corner"),
        F("LINESTYLE", INT, "line_style"),
    )

    @property
    def line_style(self) -> int:
        return self._int("LINESTYLE")


class Rectangle(_Graphic):
    """Record 14: a rectangle from ``LOCATION`` (bottom left) to ``CORNER`` (top right)."""

    __slots__ = ()
    RECORD_ID = 14
    FIELDS = (
        *BASE_FIELDS,
        *GRAPHIC_FIELDS,
        *FILL_FIELDS,
        *_point_fields("CORNER", "corner"),
        F("TRANSPARENT", BOOL, "transparent"),
    )

    @property
    def transparent(self) -> bool:
        return self._bool("TRANSPARENT")


class TextFrame(_Text):
    """Record 28: a text box."""

    __slots__ = ()
    RECORD_ID = 28
    FIELDS = (
        *BASE_FIELDS,
        *TEXT_FIELDS,
        *_point_fields("CORNER", "corner"),
        F("AREACOLOR", COLOR, "area_color"),
        F("ALIGNMENT", INT, "alignment"),
        F("WORDWRAP", BOOL, "word_wrap"),
        F("SHOWBORDER", BOOL, "show_border"),
        F("ISSOLID", BOOL, "solid"),
        F("CLIPTORECT", BOOL, "clip_to_rect"),
        F("ISNOTACCESIBLE", BOOL, "not_accessible"),
        *_len_fields("TEXTMARGIN", "text_margin"),
    )

    @property
    def corner(self) -> Point:
        return self._point("CORNER")

    @property
    def area_color(self) -> Color:
        return self._color("AREACOLOR")

    @property
    def alignment(self) -> int:
        return self._int("ALIGNMENT")

    @property
    def word_wrap(self) -> bool:
        return self._bool("WORDWRAP")

    @property
    def show_border(self) -> bool:
        return self._bool("SHOWBORDER")

    @property
    def solid(self) -> bool:
        return self._bool("ISSOLID")

    @property
    def clip_to_rect(self) -> bool:
        return self._bool("CLIPTORECT")

    @property
    def not_accessible(self) -> bool:
        return self._bool("ISNOTACCESIBLE")

    @property
    def text_margin(self) -> SchLength:
        return self._len("TEXTMARGIN")


class WarningSign(_Located):
    """Record 43: a directive (a warning sign, or a Parameter Set owning parameters)."""

    __slots__ = ()
    RECORD_ID = 43
    FIELDS = (
        *BASE_FIELDS,
        *_point_fields("LOCATION", "location"),
        F("COLOR", COLOR, "color"),
        F("NAME", TEXT, "name"),
        F("ORIENTATION", QUARTER, "orientation"),
    )

    @property
    def name(self) -> str:
        return self._text("NAME")

    @property
    def orientation(self) -> int:
        return self._int("ORIENTATION")


class Hyperlink(_Text):
    """Record 226: a hyperlink text; its address is text and never followed."""

    __slots__ = ()
    RECORD_ID = 226
    FIELDS = (*BASE_FIELDS, *TEXT_FIELDS, F("URL", TEXT, "url"))

    @property
    def url(self) -> str:
        return self._text("URL")


RECORD_TYPES: dict[int, type[SchRecord]] = {
    cls.RECORD_ID: cls
    for cls in (
        Component,
        Pin,
        IeeeSymbol,
        Label,
        Bezier,
        Polyline,
        Polygon,
        Ellipse,
        PieChart,
        RoundRectangle,
        EllipticalArc,
        Arc,
        Line,
        Rectangle,
        SheetSymbol,
        SheetEntry,
        PowerPort,
        Port,
        NoErc,
        NetLabel,
        Bus,
        Wire,
        TextFrame,
        Junction,
        Image,
        Sheet,
        SheetName,
        SheetFileName,
        Designator,
        BusEntry,
        Template,
        Parameter,
        WarningSign,
        ImplementationList,
        Implementation,
        MapDefinerList,
        MapDefiner,
        ImplementationParameters,
        HarnessConnector,
        HarnessEntry,
        HarnessType,
        SignalHarness,
        Hyperlink,
    )
    if cls.RECORD_ID is not None
}
"""The closed table of record ids and their classes (43 entries)."""

COUNT_CHECKS: dict[str, str] = {
    "LOCATIONCOUNT": r"[XY](\d+)",
    "FONTIDCOUNT": r"(?:SIZE|FONTNAME)(\d+)",
    "DATAFILECOUNT": r"MODELDATAFILE(?:ENTITY|KIND)?(\d+)",
    "DESIMPCOUNT": r"DESIMP(\d+)",
}
"""Count keys and the key pattern whose distinct numbers they count; a count never drives a loop."""


def iter_modeled(cls: type[SchRecord]) -> Iterator[FieldSpec]:
    """Each modelled field of ``cls`` once, in declaration order."""
    seen: set[str] = set()
    for spec in cls.FIELDS:
        if spec.key not in seen:
            seen.add(spec.key)
            yield spec


__all__ = [
    "BASE_FIELDS",
    "COUNT_CHECKS",
    "DIRECTIONS",
    "RECORD_TYPES",
    "Arc",
    "Bezier",
    "Bus",
    "BusEntry",
    "Component",
    "DataFile",
    "Designator",
    "Ellipse",
    "EllipticalArc",
    "FieldSpec",
    "Font",
    "HarnessConnector",
    "HarnessEntry",
    "HarnessType",
    "Hyperlink",
    "IeeeSymbol",
    "Image",
    "Implementation",
    "ImplementationList",
    "ImplementationParameters",
    "Junction",
    "Label",
    "Line",
    "MapDefiner",
    "MapDefinerList",
    "NetLabel",
    "NoErc",
    "Parameter",
    "PieChart",
    "Pin",
    "PinFields",
    "Polygon",
    "Polyline",
    "Port",
    "PowerPort",
    "PropertyRecord",
    "RecordRef",
    "Rectangle",
    "RoundRectangle",
    "SchRecord",
    "Sheet",
    "SheetEntry",
    "SheetFileName",
    "SheetName",
    "SheetSymbol",
    "SignalHarness",
    "Template",
    "TextFrame",
    "UnknownRecord",
    "WarningSign",
    "Wire",
    "iter_modeled",
    "read_fonts",
]
