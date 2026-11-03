# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public TOML record shapes before dimension, rating and grammar normalization."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, make_dataclass
from functools import reduce
from typing import Any

from fenolite.catalog import records
from fenolite.catalog.footprints.record import FAMILY_KEYS, LAND_KEYS, Key
from fenolite.model.circuit import INTERFACE_PARAMS
from fenolite.model.library import DeviceProvenance, SymbolUnit


@dataclass(frozen=True, kw_only=True)
class Header:
    schema: str
    id: str
    summary: str
    evidence: str
    version: str = ""
    licence: str = ""
    category: str = ""
    sources: list[str] | dict[str, list[str]] = field(default_factory=lambda: [])
    origin: records.Origin | ImportOrigin | ProposalOrigin = field(metadata={"optional": True})
    replaces: str = ""
    deprecated: records.Deprecation = field(metadata={"optional": True})
    reviewed_by: list[records.Review] = field(default_factory=lambda: [])
    waiver: list[records.Waiver] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class ImportOrigin:
    tool: str
    date: str
    shippable: bool
    source: list[OriginSource] = field(default_factory=lambda: [])
    output: list[records.ImportOutput] = field(default_factory=lambda: [])
    content_sha256: str = ""


@dataclass(frozen=True, kw_only=True)
class ProposalOrigin:
    tool: str
    date: str
    datasheet: str
    datasheet_sha256: str
    source: list[OriginSource]
    proposer: list[records.ProposalAuthor]
    content_sha256: str = ""
    output: list[records.ImportOutput] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class OriginSource:
    file: str
    sha256: str
    member: str = ""


@dataclass(frozen=True, kw_only=True)
class Pin:
    number: str
    name: str
    type: str
    shape: str = "line"
    hidden: bool = False
    unit: int = 1
    group: str = ""
    alternates: list[GeneratedAlternate] = field(default_factory=lambda: [])
    side: str = ""
    bus: str = ""
    stacked: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class GeneratedAlternate:
    name: str
    type: str = ""
    shape: str = ""


@dataclass(frozen=True, kw_only=True)
class PinPlacement:
    number: str
    at: tuple[str, str]
    rotation: str = ""
    length: str = ""
    body_style: int = 1


@dataclass(frozen=True, kw_only=True)
class SymbolGraphic:
    kind: str
    points: list[tuple[str, str]]
    width: str = ""
    filled: bool = False
    unit: int = 0
    body_style: int = 0


@dataclass(frozen=True, kw_only=True)
class Symbol:
    reference: str = ""
    value: str = ""
    pin_names_hidden: bool = False
    pin_numbers_hidden: bool = False
    pin_name_offset: str = ""
    units: list[SymbolUnit] = field(default_factory=lambda: [])
    pins: list[PinPlacement] = field(default_factory=lambda: [])
    graphic: list[SymbolGraphic] = field(default_factory=lambda: [])
    description: str = ""
    keywords: list[str] = field(default_factory=lambda: [])
    split_above: int = field(metadata={"optional": True})
    unit_pins: int = field(metadata={"optional": True})
    auto_bus: bool = True
    unit: list[GeneratedUnit] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class GeneratedUnit:
    number: int
    name: str = ""


@dataclass(frozen=True, kw_only=True)
class PinVariant:
    name: str
    value: str
    description: str = ""
    datasheet: str = ""
    footprint: str = ""
    keywords: list[str] = field(default_factory=lambda: [])
    fp_filters: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class PinsFile(Header):
    pin: list[Pin]
    symbol: Symbol = field(metadata={"optional": True})
    polarity: str = ""
    symbol_file: str = ""
    variant: list[PinVariant] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class PadstackLayer:
    layer: str
    shape: str
    size: tuple[str, str]
    offset: tuple[str, str] = ("0nm", "0nm")
    corner_ratio: int = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class Padstack:
    hole_shape: str
    hole_length: str = ""
    hole_rotation: str = ""
    layers: list[PadstackLayer] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class Pad:
    number: str
    shape: str
    size: tuple[str, str]
    at: tuple[str, str]
    key: str = ""
    kind: str = "smd"
    rotation: str = ""
    drill: str = ""
    layers: list[str] = field(default_factory=lambda: [])
    corner_ratio: int = field(metadata={"optional": True})
    mask_margin: str = ""
    padstack: Padstack = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class Graphic:
    kind: str
    layer: str
    points: list[tuple[str, str]]
    width: str = ""
    filled: bool = False
    key: str = ""


@dataclass(frozen=True, kw_only=True)
class Body:
    kind: str
    height: str
    outline: list[tuple[str, str]] = field(default_factory=lambda: [])
    standoff: str = ""
    layer: str = ""
    model: str = ""
    name: str = ""
    z_min: str = ""
    z_max: str = ""
    projection_unknown: bool = False


@dataclass(frozen=True, kw_only=True)
class PackageEnvelope(Header):
    name: str = ""
    generator: str = ""
    family: str = ""
    kind: str = ""
    flags: list[str] = field(default_factory=lambda: [])
    pad1: str = ""
    derived: str = ""
    footprint: str = ""
    pad: list[Pad] = field(default_factory=lambda: [])
    graphic: list[Graphic] = field(default_factory=lambda: [])
    component_body: list[Body] = field(default_factory=lambda: [])
    generate: GenerateOptions = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class GenerateOptions:
    drawing: int
    lands: int = field(metadata={"optional": True})
    density: str = "nominal"


@dataclass(frozen=True, kw_only=True)
class Depopulated:
    center: str


@dataclass(frozen=True, kw_only=True)
class Citation:
    page: int
    table: str = ""
    figure: str = ""


@dataclass(frozen=True, kw_only=True)
class QuantityRange:
    min: str = ""
    nominal: str = ""
    max: str = ""


def _parameters(name: str, keys: Mapping[str, Key], *, cites: bool = False) -> type:
    """Use the reader's finite dimension language; a new kind requires an explicit adapter here."""
    rows = [
        (
            key,
            _key_type(name + key.title(), spec, cites=cites),
            field(metadata={"optional": not spec.required}),
        )
        for key, spec in keys.items()
    ]
    if cites:
        rows.append(("cite", Citation, field(metadata={"optional": True})))
    return make_dataclass(name, rows, frozen=True, kw_only=True, namespace={"__module__": __name__})


def _key_type(name: str, spec: Key, *, cites: bool = False) -> Any:
    kind = spec.kind
    if kind in {"length", "span", "text"}:
        return str | QuantityRange if cites and kind == "length" else str
    if kind == "count":
        return int
    if kind in {"counts", "texts"}:
        return list[int] if kind == "counts" else list[str]
    if kind in {"table", "tables", "lengths"}:
        table = _parameters(name, spec.table, cites=cites)
        return list[table] if kind == "tables" else str | table if kind == "lengths" else table
    if kind == "depopulated":
        return list[str] | Depopulated
    raise ValueError(f"unadapted public dimension kind: {kind}")


def _union_type(left: Any, right: Any) -> Any:
    return left | right


def _package_file() -> type:
    shapes: dict[str, list[Any]] = {}
    for keys in FAMILY_KEYS.values():
        for key, spec in keys.items():
            shapes.setdefault(key, []).append(_key_type("Package" + key.title(), spec))
    for key in ("body", "span", "lead", "land"):
        shapes.setdefault(key, []).append(dict[str, str])  # explicit-record dimension names
    shapes.setdefault("pitch", []).append(str)
    shapes.setdefault("pins", []).append(int)
    shapes.setdefault("pad", []).append(list[Pad])
    shapes.setdefault("land", []).extend(
        _parameters("PackageLand" + name.title(), keys) for name, keys in LAND_KEYS.items()
    )
    rows = [
        (key, reduce(_union_type, dict.fromkeys(choices)), field(metadata={"optional": True}))
        for key, choices in shapes.items()
    ]
    return make_dataclass(
        "PackageFile",
        rows,
        bases=(PackageEnvelope,),
        frozen=True,
        kw_only=True,
        namespace={"__module__": __name__},
    )


PackageFile = _package_file()


@dataclass(frozen=True, kw_only=True)
class Bounds:
    min: str = ""
    max: str = ""


@dataclass(frozen=True, kw_only=True)
class Rating:
    abs_max: str | Bounds = field(metadata={"optional": True})
    operating: str | Bounds = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class DevicePin:
    pins: list[str] = field(default_factory=lambda: [])
    map: dict[str, str | list[str]] = field(default_factory=lambda: {})
    voltage: Rating = field(metadata={"optional": True})
    current: Rating = field(metadata={"optional": True})
    input_high_min: str = ""
    input_low_max: str = ""
    output_current_max: str = ""
    output_high_min: str = ""
    output_low_max: str = ""
    must_connect: bool = False


@dataclass(frozen=True, kw_only=True)
class PairLimit:
    between: tuple[str, str]
    voltage: Rating


@dataclass(frozen=True, kw_only=True)
class Interface:
    name: str
    kind: str
    direction: str
    members: dict[str, str | list[str]]
    reference: str = ""
    requires: list[str] = field(default_factory=lambda: [])
    evidence: str = ""


_interface_fields = sorted({key for table in INTERFACE_PARAMS.values() for key in table})
DeviceInterface = make_dataclass(
    "DeviceInterface",
    [(key, str | Bounds, field(metadata={"optional": True})) for key in _interface_fields],
    bases=(Interface,),
    frozen=True,
    kw_only=True,
    namespace={"__module__": __name__},
)


@dataclass(frozen=True, kw_only=True)
class Option:
    kind: str
    name: str
    alternatives: list[dict[str, str]]
    evidence: str = ""


@dataclass(frozen=True, kw_only=True)
class Bridge:
    between: tuple[str, str]
    delay_fs: int = 0
    loss_mdb: int = 0


@dataclass(frozen=True, kw_only=True)
class DeviceBody:
    symbol: str
    footprint: str
    pins: dict[str, str | list[str] | DevicePin]
    manufacturer: str = ""
    mpn: str = ""
    datasheet: str = ""
    ref_prefix: str = ""
    class_: str = field(default="", metadata={"name": "class"})
    value: str = ""
    kind: str = ""
    case: str = ""
    tolerance: str = ""
    dielectric: str = ""
    ground: str = ""
    unused_pads: list[str] = field(default_factory=lambda: [])
    ends: list[str] = field(default_factory=lambda: [])
    properties: dict[str, str] = field(default_factory=lambda: {})
    ratings: dict[str, Rating] = field(default_factory=lambda: {})
    limits: list[PairLimit] = field(default_factory=lambda: [])
    options: list[Option] = field(default_factory=lambda: [])
    bridges: list[Bridge] = field(default_factory=lambda: [])
    provenance: DeviceProvenance = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class PartBody:
    mpn: str
    extends: str = ""
    summary: str = ""
    manufacturer: str = ""
    packing: str = ""
    lifecycle: str = ""
    grade: str = ""
    datasheet: str = ""
    properties: dict[str, str] = field(default_factory=lambda: {})
    ratings: dict[str, Rating] = field(default_factory=lambda: {})


LegacyDeviceFile = make_dataclass(
    "LegacyDeviceFile",
    [("interfaces", list[DeviceInterface], field(default_factory=lambda: []))],
    bases=(Header, DeviceBody),
    frozen=True,
    kw_only=True,
    namespace={"__module__": __name__},
)
DeviceFile = make_dataclass(
    "DeviceFile",
    [("part", list[PartBody], field(default_factory=lambda: []))],
    bases=(LegacyDeviceFile,),
    frozen=True,
    kw_only=True,
    namespace={"__module__": __name__},
)


@dataclass(frozen=True, kw_only=True)
class PartFile(Header, PartBody):
    device: str


@dataclass(frozen=True, kw_only=True)
class FamilyValues:
    min: str
    max: str


@dataclass(frozen=True, kw_only=True)
class FamilyRowsFile:
    schema: str
    id: str
    kind: str
    summary: str
    symbol: str
    footprint: str
    case: str
    series: str
    values: FamilyValues
    tolerance: str
    evidence: str
    sources: dict[str, list[str]] = field(default_factory=lambda: {})
    power: str = ""
    voltage: str = ""
    rating: str = ""
    current: str = ""
    saturation: str = ""
    dcr: str = ""
    tempco: str = ""
    dielectric: str = ""


@dataclass(frozen=True, kw_only=True)
class GrammarSpan:
    min: str = ""
    max: str = ""
    series: str = ""
    values: list[str] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class GrammarField:
    role: str
    prefer: str = ""
    codes: dict[str, str | dict[str, str]] = field(default_factory=lambda: {})
    scheme: str = ""
    unit: str = ""
    series: str = ""


@dataclass(frozen=True, kw_only=True)
class FamilyGrammarFile:
    schema: str
    id: str
    kind: str
    summary: str
    manufacturer: str
    version: str
    licence: str
    evidence: str
    sources: list[str] | dict[str, list[str]]
    pattern: str
    fields: dict[str, GrammarField]
    valid: dict[str, str | list[str] | GrammarSpan]
    exclude: list[dict[str, str | list[str]]] = field(default_factory=lambda: [])
    datasheet: str = ""
    symbol: str = ""
    footprint: str = ""
    pins: dict[str, str] = field(default_factory=lambda: {})
    tail: str = "none"
    reviewed_by: list[records.Review] = field(default_factory=lambda: [])


@dataclass(frozen=True, kw_only=True)
class Datasheet:
    file: str
    sha256: str
    revision: str = ""
    title: str = ""


@dataclass(frozen=True, kw_only=True)
class ProposedDevice:
    id: str
    manufacturer: str = ""
    mpn: str = ""
    summary: str = ""
    ref_prefix: str = "U"
    cite: Citation = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposedPin:
    number: str
    name: str
    type: str
    group: str = ""
    side: str = ""
    bus: str = ""
    unit: int = 1
    shape: str = "line"
    hidden: bool = False
    stacked: bool = False
    alternates: list[GeneratedAlternate] = field(default_factory=lambda: [])
    cite: Citation = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class ProposedRating(Bounds):
    cite: Citation = field(metadata={"optional": True})
    limit: str = ""


@dataclass(frozen=True, kw_only=True)
class ProposedPart(PartBody):
    cite: Citation = field(metadata={"optional": True})


@dataclass(frozen=True, kw_only=True)
class Doubt:
    field: str
    reason: str


def _proposal_package() -> type:
    shapes: dict[str, list[Any]] = {
        "family": [str],
        "pins": [int],
        "row_labels": [list[str]],
        "cite": [Citation],
    }
    for keys in FAMILY_KEYS.values():
        for key, spec in keys.items():
            shapes.setdefault(key, []).append(_key_type("Proposal" + key.title(), spec, cites=True))
    land = [
        _parameters(
            "ProposalLand" + name.title(),
            {key: value for key, value in keys.items() if key != "source"},
            cites=True,
        )
        for name, keys in LAND_KEYS.items()
    ]
    shapes["land"] = land
    return make_dataclass(
        "ProposalPackage",
        [
            (key, reduce(_union_type, dict.fromkeys(choices)), field(metadata={"optional": True}))
            for key, choices in shapes.items()
        ],
        frozen=True,
        kw_only=True,
        namespace={"__module__": __name__},
    )


ProposalPackage = _proposal_package()
ProposalFile = make_dataclass(
    "ProposalFile",
    [
        ("schema", str),
        ("datasheet", Datasheet),
        ("proposer", records.ProposalAuthor),
        ("device", ProposedDevice),
        ("package", ProposalPackage),
        ("pin", list[ProposedPin], field(default_factory=lambda: [])),
        ("ratings", dict[str, ProposedRating], field(default_factory=dict[str, ProposedRating])),
        ("part", list[ProposedPart], field(default_factory=lambda: [])),
        ("doubt", list[Doubt], field(default_factory=lambda: [])),
    ],
    frozen=True,
    kw_only=True,
    namespace={"__module__": __name__},
)
