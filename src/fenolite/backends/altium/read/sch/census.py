# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Counts of what a reading found, for the census of public files (``tools/altium_census.py``).

A census holds key names, record ids, class names, stream names, issue codes and numbers only, never a value
of a record: the header text is given by its kind (``schematic-binary``, ``schematic-ascii``, ``library``),
and a library's storage names, which are component names, are replaced by ``<component>``.
"""

# evidence: see read.sch

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Protocol

from fenolite.backends.altium.read.sch.props import UTF8_PREFIX, decode_value, parse_int
from fenolite.backends.altium.read.sch.records import LENGTH, Pin, PropertyRecord, SchRecord, UnknownRecord
from fenolite.backends.altium.read.sch.units import FRAC_PER_UNIT, SchLength

if TYPE_CHECKING:
    from fenolite.backends.altium.read.sch.document import EmbeddedFile, SchDocument

Census = dict[str, object]
HEADER_KINDS = {
    "protel for windows - schematic capture binary file version 5.0": "schematic-binary",
    "protel for windows - schematic capture ascii file version 5.0": "schematic-ascii",
    "protel for windows - schematic library editor binary file version 5.0": "library",
}


LABELS = frozenset(
    {
        "COMPCOUNT absent", "COMPCOUNT agrees", "COMPCOUNT differs", "OWNERINDEX not followed",
        "WEIGHT absent", "WEIGHT agrees", "WEIGHT differs", "Additional: WEIGHT absent",
        "Additional: WEIGHT agrees", "Additional: WEIGHT differs", "absent", "at root",
        "binary pin strings", "binary pin tails", "bytes", "components", "count", "duplicated keys by id",
        "embedded file", "files", "form", "fraction signs", "fractions out of range", "header", "issues",
        "key case", "lengths not exact in nm", "lengths with a fraction", "lengths", "library",
        "lower-case", "mixed-case", "upper-case", "name list", "no header", "none", "opaque", "other",
        "owners by id", "pins with PinFrac", "present", "records by class", "records by id", "section keys",
        "side streams", "storage", "streams", "text", "twin different", "twin equal",
        "twin without plain key", "non-ASCII value", "undecodable value", "unknown keys by id",
        "unknown record ids", "weight", "with owner", "with tail", "without tail", "with OWNERINDEX",
        "without OWNERINDEX", "schematic-binary", "schematic-ascii", "binary", "ascii",
    }
)  # fmt: skip
"""The fixed labels a census uses besides key names, ids, class names, stream names and issue codes."""


def _sign(value: int) -> str:
    return "+" if value > 0 else "-" if value < 0 else "0"


def _id(record: SchRecord) -> str:
    record_id = record.record_id
    return "none" if record_id is None else str(record_id)


def _header_kind(header: PropertyRecord | None) -> str:
    if header is None or header.props is None:
        return "none"
    return HEADER_KINDS.get(header.props.text("HEADER").casefold(), "other")


class _Tally:
    def __init__(self) -> None:
        self.records: Counter[str] = Counter()
        self.classes: Counter[str] = Counter()
        self.unknown_ids: Counter[str] = Counter()
        self.unknown_keys: dict[str, Counter[str]] = {}
        self.duplicates: dict[str, Counter[str]] = {}
        self.key_case: Counter[str] = Counter()
        self.lengths: Counter[str] = Counter()
        self.frac_signs: Counter[str] = Counter()
        self.twins: Counter[str] = Counter()
        self.owners: dict[str, Counter[str]] = {}
        self.pin_strings: Counter[str] = Counter()
        self.pin_tails: Counter[str] = Counter()

    def add(self, record: SchRecord) -> None:
        ident = _id(record)
        self.records[ident] += 1
        self.classes[type(record).__name__] += 1
        if isinstance(record, UnknownRecord):
            self.unknown_ids[ident] += 1
        for key in record.unknown_keys:
            self.unknown_keys.setdefault(ident, Counter())[key] += 1
        owners = self.owners.setdefault(ident, Counter())
        owners["with owner" if record.owner is not None else "at root"] += 1
        owners["with OWNERINDEX" if record.owner_index is not None else "without OWNERINDEX"] += 1
        index = record.owner_index
        if index is not None and (record.owner is None or record.owner.index != index):
            owners["OWNERINDEX not followed"] += 1
        if isinstance(record, Pin) and record.binary:
            self.pin_strings[str(record.strings_read)] += 1
            self.pin_tails["with tail" if record.tail else "without tail"] += 1
            if record.pin_fracs is not None:
                self.lengths["pins with PinFrac"] += 1
        props = record.props
        if props is None:
            return
        for key in props.duplicates:
            self.duplicates.setdefault(ident, Counter())[key] += 1
        for item in props.items:
            if item.raw is None or not item.key:
                continue
            self.key_case["upper-case" if item.key == item.key.upper() else "mixed-case"] += 1
            folded = item.folded
            if folded.startswith(UTF8_PREFIX):
                plain = props.raw(folded[len(UTF8_PREFIX) :])
                if plain is None:
                    self.twins["twin without plain key"] += 1
                else:
                    twin_text = decode_value(item.raw, props.codepage, utf8=True)[0].strip()
                    plain_text = decode_value(plain, props.codepage)[0].strip()
                    self.twins["twin equal" if twin_text == plain_text else "twin different"] += 1
            elif any(byte > 0x7F for byte in item.raw):
                self.twins["non-ASCII value"] += 1
                if not decode_value(item.raw, props.codepage, utf8=props.utf8)[1]:
                    self.twins["undecodable value"] += 1
        if isinstance(record, (UnknownRecord, PropertyRecord)):
            return
        for key in props.keys():
            spec = record.spec_for(key)
            if spec is None or spec.kind != LENGTH:
                continue
            units = parse_int(props.raw(key))
            if units is None:
                continue
            frac_key = f"{key}_FRAC1" if key == "DISTANCEFROMTOP" else f"{key}_FRAC"
            frac_raw = props.raw(frac_key)
            frac = parse_int(frac_raw)
            self.lengths["lengths"] += 1
            if frac_raw is None:
                continue
            self.lengths["lengths with a fraction"] += 1
            if frac is None:
                continue
            limit = 10 * FRAC_PER_UNIT if key == "DISTANCEFROMTOP" else FRAC_PER_UNIT
            if not -limit < frac < limit:
                self.lengths["fractions out of range"] += 1
            self.frac_signs[f"{_sign(units)}/{_sign(frac)}"] += 1
            scale = 10 * FRAC_PER_UNIT if key == "DISTANCEFROMTOP" else FRAC_PER_UNIT
            if not SchLength(units * scale + frac).exact:
                self.lengths["lengths not exact in nm"] += 1

    def result(self) -> Census:
        return {
            "records by id": dict(sorted(self.records.items())),
            "records by class": dict(sorted(self.classes.items())),
            "unknown record ids": dict(sorted(self.unknown_ids.items())),
            "unknown keys by id": {k: dict(sorted(v.items())) for k, v in sorted(self.unknown_keys.items())},
            "duplicated keys by id": {k: dict(sorted(v.items())) for k, v in sorted(self.duplicates.items())},
            "key case": dict(sorted(self.key_case.items())),
            "lengths": dict(sorted(self.lengths.items())),
            "fraction signs": dict(sorted(self.frac_signs.items())),
            "text": dict(sorted(self.twins.items())),
            "owners by id": {k: dict(sorted(v.items())) for k, v in sorted(self.owners.items())},
            "binary pin strings": dict(sorted(self.pin_strings.items())),
            "binary pin tails": dict(sorted(self.pin_tails.items())),
        }


def _weight(header: PropertyRecord | None, count: int) -> str:
    if header is None or header.props is None:
        return "no header"
    weight = parse_int(header.props.raw("WEIGHT"))
    if weight is None:
        return "WEIGHT absent"
    return "WEIGHT agrees" if weight == count else "WEIGHT differs"


def _issues(issues: Iterable[object]) -> dict[str, int]:
    counts: Counter[str] = Counter(str(getattr(issue, "code", "")) for issue in issues)
    return dict(sorted(counts.items()))


class ComponentLike(Protocol):
    """What the census reads of a library component (``read.schlib.SchLibComponent``)."""

    @property
    def records(self) -> tuple[SchRecord, ...]: ...
    @property
    def data(self) -> bytes: ...
    @property
    def side_streams(self) -> dict[str, bytes]: ...
    @property
    def extra_streams(self) -> dict[str, bytes]: ...


class LibraryLike(Protocol):
    """What the census reads of a library (``read.schlib.SchLibrary``); ``read.sch`` never imports
    ``read.schlib``."""

    @property
    def header(self) -> PropertyRecord: ...
    @property
    def components(self) -> tuple[ComponentLike, ...]: ...
    @property
    def streams(self) -> dict[str, bytes]: ...
    @property
    def listed_names(self) -> tuple[str, ...]: ...
    @property
    def section_keys(self) -> dict[str, str]: ...
    @property
    def embedded(self) -> tuple[EmbeddedFile, ...]: ...
    @property
    def issues(self) -> tuple[object, ...]: ...


def document_census(document: SchDocument) -> Census:
    """The census of one schematic document."""
    tally = _Tally()
    for record in document.all_records():
        tally.add(record)
    weights: Counter[str] = Counter({_weight(document.header, len(document.records)): 1})
    if document.additional_header is not None:
        weights["Additional: " + _weight(document.additional_header, len(document.additional))] += 1
    embedded = Counter("opaque" if item.opaque else "embedded file" for item in document.embedded)
    names = [*document.streams, *document.extra_streams]
    sizes = {name: len(document.streams.get(name, document.extra_streams.get(name, b""))) for name in names}
    return {
        "files": 1,
        "form": {document.form: 1},
        "header": {_header_kind(document.header): 1},
        "weight": dict(sorted(weights.items())),
        "storage": dict(sorted(embedded.items())),
        "streams": {name: {"count": 1, "bytes": size} for name, size in sizes.items()},
        "issues": _issues(document.issues),
        **tally.result(),
    }


def library_census(library: LibraryLike) -> Census:
    """The census of one schematic library (a ``read.schlib.SchLibrary``)."""
    tally = _Tally()
    side: Counter[str] = Counter()
    sizes: list[tuple[str, int]] = []
    for name in ("FileHeader", "SectionKeys", "Storage"):
        for path, data in library.streams.items():
            if path.upper() == name.upper():
                sizes.append((name, len(data)))
    for component in library.components:
        for record in component.records:
            tally.add(record)
        sizes.append(("<component>/Data", len(component.data)))
        for name, data in component.side_streams.items():
            sizes.append((f"<component>/{name}", len(data)))
            side[name] += 1
        for name, data in component.extra_streams.items():
            sizes.append((f"<component>/{name}", len(data)))
    out: dict[str, dict[str, int]] = {}
    for name, size in sizes:
        entry = out.setdefault(name, {"count": 0, "bytes": 0})
        entry["count"] += 1
        entry["bytes"] += size
    total = sum(len(component.records) for component in library.components) + 1
    props = library.header.props
    stated = None if props is None else parse_int(props.raw("COMPCOUNT"))
    compcount = "COMPCOUNT absent" if stated is None else (
        "COMPCOUNT agrees" if stated == len(library.components) else "COMPCOUNT differs"
    )  # fmt: skip
    return {
        "files": 1,
        "form": {"library": 1},
        "header": {_header_kind(library.header): 1},
        "components": len(library.components),
        "weight": {_weight(library.header, total): 1, compcount: 1},
        "name list": {"present" if library.listed_names else "absent": 1},
        "section keys": len(library.section_keys),
        "storage": dict(
            sorted(Counter("opaque" if i.opaque else "embedded file" for i in library.embedded).items())
        ),
        "streams": out,
        "side streams": dict(sorted(side.items())),
        "issues": _issues(library.issues),
        **tally.result(),
    }


def merge(items: Iterable[Mapping[str, object]]) -> Census:
    """The sum of several censuses: numbers add up and mappings merge key by key."""
    total: Census = {}
    for item in items:
        _merge_into(total, item)
    return total


def _merge_into(total: dict[str, object], item: Mapping[str, object]) -> None:
    for key, value in item.items():
        if isinstance(value, Mapping):
            existing = total.setdefault(key, {})
            assert isinstance(existing, dict)
            _merge_into(existing, value)  # type: ignore[arg-type]
        elif isinstance(value, int):
            current = total.get(key, 0)
            assert isinstance(current, int)
            total[key] = current + value
        else:
            raise TypeError(f"a census holds numbers and mappings only, not {type(value).__name__}")


__all__ = [
    "HEADER_KINDS",
    "Census",
    "ComponentLike",
    "LibraryLike",
    "document_census",
    "library_census",
    "merge",
]
