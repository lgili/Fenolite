# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative LibrePCB-to-record conversion (c0266, docs/formats/librepcb/library.md).

Only library elements are read, all interpretations remain UNVERIFIED, and unsupported geometry
skips its element and dependants. No upstream program or third-party parser runs.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from fenolite.backends.librepcb import Element, Library, read_library
from fenolite.backends.librepcb.reader import CC0_SHA256, UUID
from fenolite.backends.librepcb.sexpr import Invalid, Node, parse, quantity
from fenolite.catalog.records import (
    DeviceRecord,
    GraphicEntry,
    Header,
    Origin,
    PackageRecord,
    PadEntry,
    PartEntry,
    PinEntry,
    PinPlacement,
    PinsRecord,
    Record,
    SymbolDrawing,
    parse_record,
    record_text,
)
from fenolite.core.coords import Point, Size
from fenolite.core.errors import FormatError, Issue
from fenolite.library.codes import issue
from fenolite.library.items import Depend
from fenolite.library.licences import normalised_digest
from fenolite.model.library import DeviceDef, DevicePin, SymbolGraphic, SymbolUnit

ROLES = {
    "input": "input",
    "output": "output",
    "inout": "bidirectional",
    "passive": "passive",
    "power": "power_in",
    "opendrain": "open_collector",
}
LAYERS = {
    "top_courtyard": "F.CrtYd",
    "top_documentation": "F.Fab",
    "top_legend": "F.SilkS",
    "top_placement": "F.SilkS",
}


@dataclass(frozen=True)
class SeedItem:
    kind: str
    record: Record
    element: str
    depends: tuple[Depend, ...] = ()


@dataclass(frozen=True)
class Converted:
    items: tuple[SeedItem, ...]
    issues: tuple[Issue, ...]
    licence: bytes
    upstream: str
    inputs: tuple[Path, ...]


def _uuid(node: Node) -> str:
    if len(node.atoms) != 1 or not UUID.fullmatch(node.atoms[0]):
        raise Invalid(f"{node.head}: expected one UUID")
    return node.atoms[0]


def _indexed(nodes: tuple[Node, ...]) -> dict[str, Node]:
    found: dict[str, Node] = {}
    for node in nodes:
        key = _uuid(node)
        if key in found:
            raise Invalid(f"duplicate {node.head} UUID {key}")
        found[key] = node
    return found


def _point(node: Node, field: str = "position") -> Point:
    child = node.child(field)
    if child is None or len(child.atoms) != 2:
        raise Invalid(f"{node.head}.{field}: expected two lengths")
    return Point(*(quantity(value) for value in child.atoms))


def _supported(node: Node, heads: set[str]) -> None:
    unknown = sorted({v.head for v in node.values if isinstance(v, Node)} - heads)
    if unknown:
        raise Invalid(f"unsupported {node.head} fields: {', '.join(unknown)}")


def _vertices(node: Node) -> tuple[Point, ...]:
    vertices = node.children("vertex")
    if any(quantity(v.text("angle", "0"), angle=True) != 0 for v in vertices):
        raise Invalid("curved polygon segment")
    if len(vertices) < 2:
        raise Invalid("polygon has fewer than two vertices")
    return tuple(_point(v) for v in vertices)


def _graphics(node: Node, *, unit: int = 0) -> tuple[GraphicEntry | SymbolGraphic, ...]:
    out: list[GraphicEntry | SymbolGraphic] = []
    for drawing in (
        v
        for v in node.values
        if isinstance(v, Node) and v.head in {"polygon", "circle", "text", "stroke_text"}
    ):
        if drawing.head in {"text", "stroke_text"}:
            if drawing.text("value") not in {"{{NAME}}", "{{VALUE}}"}:
                raise Invalid("custom text is not representable by records")
            continue
        layer = drawing.text("layer")
        if unit and layer not in {"sym_outlines", "sym_hidden_grab_areas"}:
            raise Invalid(f"unsupported symbol layer {layer!r}")
        if not unit and layer not in LAYERS:
            raise Invalid(f"unsupported footprint layer {layer!r}")
        if drawing.head == "polygon":
            _supported(drawing, {"layer", "width", "fill", "grab_area", "vertex"})
            points = _vertices(drawing)
            kind = "line" if len(points) == 2 else "polygon"
        else:
            _supported(drawing, {"layer", "width", "fill", "grab_area", "position", "diameter"})
            center = _point(drawing)
            diameter = quantity(drawing.text("diameter"))
            if diameter <= 0 or diameter % 2:
                raise Invalid("circle needs a positive whole-nm radius")
            points = (center, Point(center.x + diameter // 2, center.y))
            kind = "circle"
        width = quantity(drawing.text("width", "0"))
        filled = drawing.text("fill", "false") == "true"
        if unit:
            out.append(SymbolGraphic(cast("object", kind), points, width, filled, unit, 1))  # type: ignore[arg-type]
        else:
            out.append(GraphicEntry(kind, LAYERS[layer], points, width, filled, _uuid(drawing)))
    return tuple(out)


def _package(element: Element, footprint: Node, header: Header) -> PackageRecord:
    _supported(footprint, {"name", "description", "pad", "polygon", "circle", "stroke_text", "text"})
    package_pads = {key: p.text("name") for key, p in _indexed(element.node.children("pad")).items()}
    pads: list[PadEntry] = []
    for pad in footprint.children("pad"):
        _supported(pad, {"package_pad", "side", "shape", "position", "rotation", "size", "hole"})
        shape = pad.text("shape")
        if shape not in {"rect", "round"}:
            raise Invalid(f"custom or unsupported pad shape {shape!r}")
        if pad.text("side", "top") != "top":
            raise Invalid("unsupported pad side")
        size = _point(pad, "size")
        holes = pad.children("hole")
        if len(holes) > 1:
            raise Invalid("multiple pad holes")
        drill = None
        if holes:
            _supported(holes[0], {"diameter", "vertex"})
            vertices = holes[0].children("vertex")
            if len(vertices) > 1 or (vertices and _point(vertices[0]) != Point(0, 0)):
                raise Invalid("slot or offset pad hole")
            drill = quantity(holes[0].text("diameter"))
        pad_ref = pad.text("package_pad")
        if pad_ref not in package_pads:
            raise Invalid(f"unmapped package pad {pad_ref!r}")
        pads.append(
            PadEntry(
                package_pads[pad_ref],
                "circle" if shape == "round" and size.x == size.y else "oval" if shape == "round" else "rect",
                Size(size.x, size.y),
                _point(pad),
                key=_uuid(pad),
                kind="thru_hole" if drill else "smd",
                rotation=quantity(pad.text("rotation", "0"), angle=True),
                drill=drill,
                layers=("*.Cu", "*.Mask") if drill else ("F.Cu", "F.Paste", "F.Mask"),
            )
        )
    if not pads:
        raise Invalid("footprint has no supported pads")
    return PackageRecord(
        header,
        kind="through_hole" if any(p.drill for p in pads) else "smd",
        pads=tuple(pads),
        graphics=cast(tuple[GraphicEntry, ...], _graphics(footprint)),
    )


def _component(
    element: Element, library: Library, header: Header
) -> tuple[PinsRecord, dict[str, tuple[str, ...]]]:
    variants = element.node.children("variant")
    if not variants:
        raise Invalid("component has no symbol variant")
    symbols = {e.uuid: e for e in library.of_kind("symbol")}
    signals = _indexed(element.node.children("signal"))
    if len({signal.text("name") for signal in signals.values()}) != len(signals):
        raise Invalid("distinct component signals share one function name")
    pins: list[PinEntry] = []
    placements: list[PinPlacement] = []
    graphics: list[SymbolGraphic] = []
    units: list[SymbolUnit] = []
    mapped: dict[str, list[str]] = {}
    for unit, gate in enumerate(variants[0].children("gate"), 1):
        source = symbols.get(gate.text("symbol"))
        if source is None:
            raise Invalid(f"missing/unsupported gate symbol {gate.text('symbol')}")
        _supported(
            source.node,
            {
                "name",
                "description",
                "keywords",
                "author",
                "version",
                "created",
                "deprecated",
                "category",
                "pin",
                "polygon",
                "circle",
                "text",
            },
        )
        by_pin = {key: p.text("signal") for key, p in _indexed(gate.children("pin")).items()}
        for pin in source.node.children("pin"):
            _supported(pin, {"name", "position", "rotation", "length"})
            signal_id = by_pin.get(_uuid(pin), "")
            if signal_id not in signals:
                raise Invalid(f"unmapped symbol pin {_uuid(pin)}")
            signal = signals[signal_id]
            number = str(len(pins) + 1)
            pins.append(
                PinEntry(
                    number, signal.text("name"), ROLES.get(signal.text("role"), "unspecified"), unit=unit
                )
            )
            placements.append(
                PinPlacement(
                    number,
                    _point(pin),
                    quantity(pin.text("rotation", "0"), angle=True),
                    quantity(pin.text("length")),
                )
            )
            mapped.setdefault(signal_id, []).append(number)
        units.append(SymbolUnit(unit, 1, gate.text("name", str(unit))))
        graphics.extend(cast(tuple[SymbolGraphic, ...], _graphics(source.node, unit=unit)))
    if not pins:
        raise Invalid("component has no gate pins")
    return PinsRecord(
        header,
        tuple(pins),
        SymbolDrawing("U", units=tuple(units), placements=tuple(placements), graphics=tuple(graphics)),
    ), {key: tuple(values) for key, values in mapped.items()}


def _device(
    element: Element,
    component: Element,
    pins: PinsRecord,
    mapping: dict[str, tuple[str, ...]],
    package: Element,
    footprint: PackageRecord,
    header: Header,
) -> DeviceRecord:
    pads = {key: p.text("name") for key, p in _indexed(package.node.children("pad")).items()}
    names = {_uuid(s): s.text("name") for s in component.node.children("signal")}
    functions: dict[str, list[tuple[str, str]]] = {}
    covered: set[str] = set()
    for pad in element.node.children("pad"):
        signal = pad.text("signal")
        if signal not in mapping or _uuid(pad) not in pads:
            raise Invalid("device maps an unknown or unrepresented signal/pad")
        covered.add(signal)
        for pin in mapping[signal]:
            functions.setdefault(names[signal], []).append((pin, pads[_uuid(pad)]))
    if covered != set(mapping):
        raise Invalid("component signals lack a representable device pad mapping")
    parts: list[PartEntry] = []
    for part in element.node.children("part"):
        if len(part.atoms) != 1:
            raise Invalid("part needs one MPN")
        parts.append(PartEntry(part.atoms[0], manufacturer=part.text("manufacturer")))
    device = DeviceDef(
        header.id,
        summary=header.summary,
        symbol=pins.header.id,
        footprint=footprint.header.id,
        ref_prefix="U",
        evidence="UNVERIFIED",
        sources=header.sources,
        pins=tuple(DevicePin(name, tuple(values)) for name, values in sorted(functions.items())),
    )
    return DeviceRecord(header, device, tuple(parts))


def _licence(root: Path) -> tuple[Path, bytes]:
    found: list[tuple[Path, bytes]] = []
    for name in ("LICENSE.txt", "LICENSE", "LICENSE.md"):
        path = root / name
        if path.is_file() and not path.is_symlink():
            data = path.read_bytes()
            if normalised_digest(data) != CC0_SHA256:
                raise FormatError("not a CC0-1.0 library: a licence file differs from the pinned legal code")
            found.append((path, data))
    if found:
        return found[0]
    raise FormatError(
        "not a CC0-1.0 library: the full legal code does not match the pinned normalized SHA-256"
    )


def convert(
    root: Path, *, library_name: str, commit: str, namespace: str, source_id: str, allocate: object
) -> Converted:
    """Convert the supported subset; allocate(kind, proposed_name, UUID) supplies stable item ids."""
    from collections.abc import Callable

    allocator = cast(Callable[[str, str, str], str], allocate)
    if (
        not re.fullmatch(r"[A-Za-z0-9_.+-]+", namespace)
        or namespace in {"Fenolite", "."}
        or ".." in namespace
    ):
        raise FormatError("invalid or reserved seed namespace")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise FormatError("--commit must be a full 40-hex commit")
    licence_path, licence = _licence(root)
    if (root / ".git").exists():
        proc = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], text=True, capture_output=True, check=False
        )
        if proc.returncode or proc.stdout.strip() != commit:
            raise FormatError("LibrePCB checkout HEAD does not equal --commit")
    try:
        library = read_library(root)
        metadata = parse((root / "library.lp").read_text(encoding="utf-8"))
    except (Invalid, OSError, UnicodeError) as exc:
        raise FormatError(str(exc)) from None
    upstream = metadata.text(
        "url",
        "https://github.com/LibrePCB-Libraries/LibrePCB_Base.lplib"
        if library_name in {"LibrePCB Base", "LibrePCB_Base.lplib"}
        else "",
    )
    if not upstream.startswith("https://"):
        raise FormatError(
            "library.lp needs a public https url for the source register; "
            "only LibrePCB Base has a known default URL"
        )
    issues = [issue("library.seed-skipped", f"{s.uuid}: {s.reason}", where=s.uuid) for s in library.skipped]
    items: list[SeedItem] = []
    packages: dict[str, tuple[Element, PackageRecord]] = {}
    components: dict[str, tuple[Element, PinsRecord, dict[str, tuple[str, ...]]]] = {}

    def header(kind: str, name: str, element_id: str) -> Header:
        record_id = allocator(kind, name, element_id)
        schema = {"symbol": "pins", "footprint": "package", "device": "device"}[kind]
        return Header(
            f"fenolite.{schema}.v{'1' if kind == 'device' else '0'}",
            record_id,
            "1.0.0",
            f"Seeded from {library_name}: {name}",
            "CC0-1.0",
            "UNVERIFIED",
            sources=(source_id,),
            origin=Origin(library_name, commit, element_id, "CC0-1.0"),
        )

    def skipped(element: Element, error: Exception) -> None:
        issues.append(issue("library.seed-skipped", f"{element.uuid}: {error}", where=element.uuid))

    for element in library.of_kind("package"):
        for index, fp in enumerate(element.node.children("footprint")):
            try:
                name = element.name if index == 0 else f"{element.name}_{fp.text('name')}"
                record = _package(element, fp, header("footprint", name, _uuid(fp)))
                parse_record(record_text(record))
                items.append(SeedItem("footprint", record, _uuid(fp)))
                if index == 0:
                    packages[element.uuid] = element, record
            except (Invalid, FormatError, ValueError) as exc:
                skipped(element, exc)
    for element in library.of_kind("component"):
        try:
            record, mapping = _component(element, library, header("symbol", element.name, element.uuid))
            parse_record(record_text(record))
            items.append(SeedItem("symbol", record, element.uuid))
            components[element.uuid] = element, record, mapping
        except (Invalid, FormatError, ValueError) as exc:
            skipped(element, exc)
    for element in library.of_kind("device"):
        try:
            component_id, package_id = element.node.text("component"), element.node.text("package")
            if component_id not in components or package_id not in packages:
                raise Invalid("missing or skipped component/package dependency")
            component, symbol, mapping = components[component_id]
            package, footprint = packages[package_id]
            record = _device(
                element,
                component,
                symbol,
                mapping,
                package,
                footprint,
                header("device", element.name, element.uuid),
            )
            parse_record(record_text(record))
            depends = (
                Depend("symbol", symbol.header.id, "1.0.0"),
                Depend("footprint", footprint.header.id, "1.0.0"),
            )
            items.append(SeedItem("device", record, element.uuid, depends))
        except (Invalid, FormatError, ValueError) as exc:
            skipped(element, exc)
    inputs = (root / ".librepcb-lib", root / "library.lp", licence_path)
    for folder, filename in (
        ("sym", "symbol.lp"),
        ("pkg", "package.lp"),
        ("cmp", "component.lp"),
        ("dev", "device.lp"),
    ):
        inputs += tuple(sorted((root / folder).glob(f"*/{filename}")))
        inputs += tuple(sorted((root / folder).glob(f"*/.librepcb-{folder}")))
    if (root / ".git").is_dir():
        inputs += tuple(
            p
            for p in (root / ".git").rglob("*")
            if p.is_file() and (p.name in {"HEAD", "packed-refs"} or "refs" in p.parts)
        )
    return Converted(tuple(items), tuple(issues), licence, upstream, tuple(sorted({*inputs, licence_path})))
