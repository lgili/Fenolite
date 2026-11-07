# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Canonical project records and their local-import provenance (c0264)."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, replace

from fenolite.backends.kicad import embed, slots
from fenolite.backends.kicad.mod import prepare_authored_definition, write_footprint
from fenolite.backends.kicad.sexpr import Atom, Node, dumps
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog.devices import ID, device_text, parse_device, stamped
from fenolite.catalog.records import (
    BodyEntry,
    DeviceRecord,
    GraphicEntry,
    Header,
    ImportOrigin,
    ImportOutput,
    ImportSource,
    PackageRecord,
    PadEntry,
    PadstackEntry,
    PinEntry,
    PinPlacement,
    PinsRecord,
    Record,
    SymbolDrawing,
    record_text,
)
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.library.importer.sources import ImportUsageError, Selection
from fenolite.library.importer.templates import pin_template
from fenolite.model.base import Modeled, Opaque, Slot
from fenolite.model.library import DeviceDef, DevicePin, FootprintDef, ModelPlacement, SymbolDef

TOOL = "fenolite library import"
LICENCE = "see source terms"
BACKEND = "fenolite.catalog"


@dataclass(frozen=True, slots=True)
class Imported:
    device: DeviceRecord
    records: tuple[Record, ...]
    files: dict[str, bytes]
    symbol: SymbolDef
    footprint: FootprintDef
    issues: tuple[Issue, ...]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def seal(record: Record) -> Record:
    """Stamp the complete canonical record, with its own checksum omitted to avoid a cycle."""
    origin = record.header.origin
    assert isinstance(origin, ImportOrigin)
    blank = replace(record, header=replace(record.header, origin=replace(origin, content_sha256="")))
    digest = _sha(record_text(blank).encode())
    return replace(record, header=replace(record.header, origin=replace(origin, content_sha256=digest)))


def record_edited(record: Record) -> bool:
    origin = record.header.origin
    if not isinstance(origin, ImportOrigin) or not origin.content_sha256:
        return True
    return seal(record).header.origin != origin


def with_model_path(footprint: FootprintDef, path: str) -> tuple[FootprintDef, bool]:
    """Rewrite only model paths; opaque KiCad placement children keep their existing transforms."""
    had_model = bool(footprint.models or footprint.placements)
    bag = footprint.ext.get("kicad")
    root = list(slots.from_ext(bag)) if bag is not None else []
    rewritten: list[Slot] = []
    for slot in root:
        if isinstance(slot, Opaque):
            node = slots.opaque_child(slot)
            if isinstance(node, Node) and node.name == "model":
                node = replace(node, children=(Atom.string(path), *node.children[1:]))
                slot = replace(slot, fragment=dumps(node, style="compact"))
        rewritten.append(slot)
    placements = tuple(replace(p, path=path) for p in footprint.placements)
    if not had_model:
        placements = (ModelPlacement(path),)
        if root:
            rewritten.append(Modeled("placements"))
    return replace(
        footprint,
        models=tuple(path for _ in footprint.models),
        placements=placements,
        bodies=tuple(replace(body, model=path) if body.model else body for body in footprint.bodies),
        ext={**footprint.ext, "kicad": slots.to_ext(rewritten, base=bag)} if root else footprint.ext,
    ), not had_model


def make_records(
    selection: Selection,
    *,
    device_id: str | None,
    date: str,
    target: int = 10,
    family: str = "imported",
    nominal: dict[str, tuple[int, ...]] | None = None,
    pins: tuple[DevicePin, ...] | None = None,
    manufacturer: str = "",
    mpn: str = "",
    datasheet: str = "",
    ref_prefix: str = "",
) -> Imported:
    """Plan record and native file bytes; source member names can never select an output path."""
    device_id = device_id or f"Imported:{selection.symbol.name}"
    if not ID.fullmatch(device_id) or device_id.startswith("Fenolite:"):
        raise ImportUsageError("--id must be a project NS:NAME, each matching [A-Za-z0-9_.+-]+")
    namespace, name = device_id.split(":", 1)
    origin = ImportOrigin(
        TOOL, date, tuple(ImportSource(s.file, s.member, s.sha256) for s in selection.sources)
    )
    summary = f"imported from {', '.join(sorted({s.file for s in selection.sources}))}"

    def header(kind: str) -> Header:
        return Header(
            f"fenolite.{kind}.v{'1' if kind == 'device' else '0'}",
            device_id,
            "0.1.0",
            summary,
            LICENCE,
            "UNVERIFIED",
            origin=origin,
        )

    symbol = replace(
        selection.symbol,
        id=derived_id("sym", BACKEND, device_id),
        library=namespace,
        name=name,
        extends="",
        native_ids={"fenolite": device_id},
        properties={**selection.symbol.properties, "Footprint": device_id},
    )
    footprint = replace(
        selection.footprint,
        id=derived_id("fpd", BACKEND, device_id),
        library=namespace,
        name=name,
        native_ids={"fenolite": device_id},
        pads=tuple(
            replace(p, id=derived_id("pad", BACKEND, f"{name}:pad-{index}"))
            for index, p in enumerate(selection.footprint.pads)
        ),
        graphics=tuple(
            replace(g, id=derived_id("gfx", BACKEND, f"{name}:graphic-{index}"))
            for index, g in enumerate(selection.footprint.graphics)
        ),
    )
    if not selection.steps and any(
        path.startswith(("/", "\\")) or re.match(r"^[A-Za-z]:", path)
        for path in (
            *footprint.models,
            *(p.path for p in footprint.placements),
            *(b.model for b in footprint.bodies),
        )
    ):
        raise ImportUsageError(
            "an absolute model path cannot be written into an imported record",
            hint="supply the STEP source so its model path can be rewritten locally",
        )
    issues = list(selection.issues)
    files: dict[str, bytes] = {}
    if selection.steps:
        step_name = f"{name}.step"
        files[step_name] = selection.steps[0].data
        footprint, new_placement = with_model_path(footprint, step_name)
        issues.append(
            Issue("library.import-step-unchecked", "info", "STEP bytes copied; geometry has not been read")
        )
        if new_placement:
            issues.append(
                Issue(
                    "library.import-step-placement",
                    "info",
                    "STEP added at offset 0 and rotation 0; check its rendered placement",
                )
            )
    if not selection.footprint.ext.get("kicad"):
        properties = dict(footprint.properties)
        footprint = prepare_authored_definition(
            replace(
                footprint, properties={k: v for k, v in properties.items() if k in {"Reference", "Value"}}
            )
        )
        for key, value in sorted(properties.items()):
            if key not in {"Reference", "Value"}:
                footprint = embed.with_property(footprint, name=key, value=value)
    files[f"{name}.kicad_sym"] = write_symbol_library([symbol], target=target).encode()
    files[f"{name}.kicad_mod"] = write_footprint(
        prepare_authored_definition(footprint), target=target, issues=issues
    ).encode()
    unique_pins = tuple(dict((pin.number, pin) for pin in symbol.pins).values())
    pins_record = PinsRecord(
        header("pins"),
        tuple(
            PinEntry(p.number, p.name, p.etype, p.shape, p.hidden, max(p.unit, 1), alternates=p.alternates)
            for p in unique_pins
        ),
        SymbolDrawing(
            symbol.reference or "U",
            symbol.value,
            symbol.pin_names_hidden,
            symbol.pin_numbers_hidden,
            symbol.pin_name_offset,
            symbol.units,
            tuple(
                PinPlacement(p.number, p.position, p.rotation, p.length, p.body_style or 1)
                for p in unique_pins
            ),
            symbol.graphics,
        ),
        symbol_file=f"{name}.kicad_sym",
    )
    package = PackageRecord(
        header("package"),
        kind=footprint.kind,
        flags=footprint.flags,
        dimensions=nominal or {},
        family=family,
        derived="imported footprint" if family != "imported" else "",
        footprint=f"{name}.kicad_mod",
        pads=tuple(
            PadEntry(
                p.number,
                p.shape,
                p.size,
                p.position,
                key=f"pad-{index}",
                kind=p.kind,
                rotation=p.rotation,
                drill=p.drill,
                layers=p.layers,
                corner_ratio=p.corner_ratio,
                mask_margin=p.mask_margin,
                padstack=None
                if p.padstack is None
                else PadstackEntry(
                    p.padstack.hole_shape, p.padstack.hole_length, p.padstack.hole_rotation, p.padstack.layers
                ),
            )
            for index, p in enumerate(footprint.pads)
        ),
        graphics=tuple(
            GraphicEntry(g.kind, g.layer, g.points, g.width, g.filled, f"graphic-{index}")
            for index, g in enumerate(footprint.graphics)
        ),
        bodies=tuple(
            BodyEntry(
                body.kind,
                body.height,
                body.standoff,
                body.outline,
                body.layer,
                body.model,
                body.name,
                body.z_min,
                body.z_max,
                body.projection_unknown,
            )
            for body in footprint.bodies
        ),
    )
    if pins is None:
        device_pins, pin_issues = pin_template(symbol, footprint, [])
        issues.extend(pin_issues)
    else:
        device_pins = pins
    device = parse_device(
        device_text(
            DeviceDef(
                device_id,
                summary,
                symbol=device_id,
                footprint=device_id,
                ref_prefix=ref_prefix or symbol.reference or "U",
                manufacturer=manufacturer,
                mpn=mpn,
                datasheet=datasheet,
                evidence="UNVERIFIED",
                pins=device_pins,
            )
        )
    )
    device = stamped(
        device, tool=TOOL, source=", ".join(sorted({s.file for s in selection.sources})), date=date
    )
    records = tuple(seal(r) for r in (pins_record, package))
    for filename, record in zip(("pins.toml", "package.toml"), records, strict=True):
        files[filename] = record_text(record).encode()
    outputs = tuple(ImportOutput(filename, _sha(data)) for filename, data in sorted(files.items()))
    device_record = seal(
        DeviceRecord(replace(header("device"), origin=replace(origin, output=outputs)), device)
    )
    assert isinstance(device_record, DeviceRecord)
    files["device.toml"] = record_text(device_record).encode()
    issues.append(
        Issue(
            "library.import-terms",
            "info",
            "Source terms may limit sharing this project; the imported device remains UNVERIFIED",
        )
    )
    return Imported(device_record, (device_record, *records), files, symbol, footprint, tuple(issues))


__all__ = ["Imported", "LICENCE", "TOOL", "make_records", "record_edited", "seal", "with_model_path"]
