# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact, versioned block-local layout assets (c0271; docs/formats/fenolite/block-layout.md).

Pure model operations except reading the named TOML file. Copper stores its local net in ``net_id``;
``apply_block_layout`` maps it to model ids. The CLI supplies group selection, pad checking and settling
without adding those package edges to reuse.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import tomllib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Any, cast

from fenolite.backends.base import BoardPad
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.trig import ONE
from fenolite.core.units import (
    format_angle,
    format_length,
    parse_angle,
    parse_area,
    parse_length,
    round_half_even_div,
)
from fenolite.geometry.thick import Thick, thick_touch
from fenolite.geometry.transform import Transform
from fenolite.model import canonical
from fenolite.model.board import Arc, Track, Via, ViaProtection, Zone, ZoneHatch, ZoneSettings
from fenolite.model.circuit import Component
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse.codes import issue
from fenolite.reuse.copper import Copper, CopperCopy, copy_block, layer_map

IDENTITY = Transform()
SCHEMA = "fenolite.block-layout.v0"
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
VERSION = re.compile(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)")
LOCAL_NET = re.compile(r"(?:port|net|global):[^\s:]+")


class BlockLayoutError(FormatError):
    """Malformed v0 (FEN-3004), or an unsupported schema (FEN-3002)."""

    def __init__(self, message: str, *, file: str, key: str = "", code: str = "FEN-3004") -> None:
        self.code = code
        super().__init__(message, file=file, locator=key)


@dataclass(frozen=True, slots=True)
class LayoutPart:
    at: Point
    rotation: int
    side: str
    footprint: str


@dataclass(frozen=True)
class BlockLayout:
    block: str
    block_version: str
    parts_digest: str
    nets_digest: str
    licence: str
    evidence: str
    parts: Mapping[str, LayoutPart]
    tracks: tuple[Track, ...] = ()
    arcs: tuple[Arc, ...] = ()
    vias: tuple[Via, ...] = ()
    zones: tuple[Zone, ...] = ()
    pads: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: MappingProxyType({}))
    captured_from: str | None = None

    @property
    def copper(self) -> tuple[Copper, ...]:
        return (*self.tracks, *self.arcs, *self.vias, *self.zones)


class _Reader:
    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, key: str, message: str) -> Any:
        raise BlockLayoutError(message, file=self.file, key=key)

    def table(self, value: object, key: str, allowed: set[str]) -> dict[str, Any]:
        if not isinstance(value, dict):
            self.fail(key, "expected a table")
        data = cast(dict[str, Any], value)
        for name in data:
            if name not in allowed:
                self.fail(f"{key}.{name}".lstrip("."), f"unknown key {name}")
        return data

    def text(self, value: object, key: str) -> str:
        if not isinstance(value, str) or not value:
            self.fail(key, "expected nonempty text")
        return cast(str, value)

    def integer(self, value: object, key: str) -> int:
        if type(value) is not int:
            self.fail(key, "expected an integer")
        return cast(int, value)

    def quantity(self, value: object, key: str, kind: str = "length") -> int:
        text = self.text(value, key)
        try:
            return {"length": parse_length, "angle": parse_angle, "area": parse_area}[kind](text)
        except ValueError as error:
            self.fail(key, str(error))
        raise AssertionError("unreachable")

    def point(self, value: object, key: str) -> Point:
        if not isinstance(value, list) or len(cast(list[object], value)) != 2:
            self.fail(key, "expected two exact lengths")
        pair = cast(list[object], value)
        return Point(self.quantity(pair[0], key), self.quantity(pair[1], key))

    def texts(self, value: object, key: str) -> tuple[str, ...]:
        if not isinstance(value, list):
            self.fail(key, "expected an array of text")
        return tuple(self.text(entry, key) for entry in cast(list[object], value))

    def settings(self, value: object, key: str, *, hatch: bool = False) -> ZoneSettings | ZoneHatch:
        cls = ZoneHatch if hatch else ZoneSettings
        data = self.table(value, key, {f.name for f in dataclasses.fields(cls)})
        default = cls()
        out: dict[str, Any] = {}
        for name, entry in data.items():
            where = f"{key}.{name}"
            current = getattr(default, name)
            if name == "hatch":
                out[name] = self.settings(entry, where, hatch=True)
            elif name in ("min_island_area",):
                out[name] = self.quantity(entry, where, "area")
            elif name == "orientation":
                out[name] = self.quantity(entry, where, "angle")
            elif name in ("smoothing_level",):
                out[name] = self.integer(entry, where)
            elif isinstance(current, int):
                out[name] = self.quantity(entry, where)
            else:
                out[name] = self.text(entry, where)
        return cls(**out)


def read_block_layout(path: str | Path) -> BlockLayout:
    """Read v0 with exact units; the file and offending key locate every malformed value."""
    path = Path(path)
    r = _Reader(path.as_posix())
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as error:
        raise BlockLayoutError(str(error), file=r.file) from error
    data = r.table(
        raw,
        "",
        {
            "schema",
            "block",
            "block_version",
            "parts_digest",
            "nets_digest",
            "licence",
            "evidence",
            "captured_from",
            "parts",
            "tracks",
            "arcs",
            "vias",
            "zones",
        },
    )
    if data.get("schema") != SCHEMA:
        raise BlockLayoutError("unsupported block layout schema", file=r.file, key="schema", code="FEN-3002")
    header = {
        name: r.text(data.get(name), name)
        for name in (
            "block",
            "block_version",
            "parts_digest",
            "nets_digest",
            "licence",
            "evidence",
        )
    }
    if not VERSION.fullmatch(header["block_version"]):
        r.fail("block_version", "expected MAJOR.MINOR.PATCH")
    for name in ("parts_digest", "nets_digest"):
        if not DIGEST.fullmatch(header[name]):
            r.fail(name, "expected sha256: and 64 lower-case hexadecimal digits")
    if header["block"].startswith("Fenolite:") and header["licence"] != "Apache-2.0":
        r.fail("licence", "a Fenolite: layout uses Apache-2.0")
    captured = data.get("captured_from")
    if captured is not None:
        captured = r.text(captured, "captured_from")
        if PurePosixPath(captured).is_absolute() or ".." in PurePosixPath(captured).parts:
            r.fail("captured_from", "expected a relative path without parent traversal")
    raw_parts = data.get("parts", {})
    if not isinstance(raw_parts, dict):
        r.fail("parts", "expected parts tables")
    parts: dict[str, LayoutPart] = {}
    for name, value in cast(dict[str, object], raw_parts).items():
        if name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/")):
            r.fail(f"parts.{name}", "expected a local part path")
        key = f"parts.{name}"
        part = r.table(value, key, {"at", "rotation", "side", "footprint"})
        side = r.text(part.get("side"), f"{key}.side")
        if side not in ("top", "bottom"):
            r.fail(f"{key}.side", "expected top or bottom")
        parts[name] = LayoutPart(
            r.point(part.get("at"), f"{key}.at"),
            r.quantity(part.get("rotation"), f"{key}.rotation", "angle"),
            side,
            r.text(part.get("footprint"), f"{key}.footprint"),
        )
    copper: dict[str, list[Any]] = {kind: [] for kind in ("tracks", "arcs", "vias", "zones")}
    pads: dict[str, tuple[str, ...]] = {}
    for kind in copper:
        entries = data.get(kind, [])
        if not isinstance(entries, list):
            r.fail(kind, "expected an array of tables")
        for index, entry in enumerate(cast(list[object], entries)):
            key = f"{kind}[{index}]"
            allowed = {"net", "pads"} | {
                "tracks": {"start", "end", "width", "layer"},
                "arcs": {"start", "mid", "end", "width", "layer"},
                "vias": {"at", "size", "drill", "layers", "via_type"},
                "zones": {"outline", "layers", "name", "priority", "settings"},
            }[kind]
            table = r.table(entry, key, allowed)
            net = r.text(table.get("net"), f"{key}.net")
            if not LOCAL_NET.fullmatch(net):
                r.fail(f"{key}.net", "expected port:NAME, net:NAME or global:NAME")
            ident = f"{kind}:{index}"
            kwargs: dict[str, Any] = {"id": ident, "net_id": net}
            if kind in ("tracks", "arcs"):
                for name in ("start", "end") if kind == "tracks" else ("start", "mid", "end"):
                    kwargs[name] = r.point(table.get(name), f"{key}.{name}")
                kwargs.update(
                    width=r.quantity(table.get("width"), f"{key}.width"),
                    layer=r.text(table.get("layer"), f"{key}.layer"),
                )
                item = (Track if kind == "tracks" else Arc)(**kwargs)
            elif kind == "vias":
                kwargs.update(
                    position=r.point(table.get("at"), f"{key}.at"),
                    diameter=r.quantity(table.get("size"), f"{key}.size"),
                    drill=r.quantity(table.get("drill"), f"{key}.drill"),
                    layers=r.texts(table.get("layers"), f"{key}.layers"),
                    via_type=r.text(table.get("via_type", "through"), f"{key}.via_type"),
                )
                item = Via(**kwargs)
            else:
                outline = table.get("outline")
                if not isinstance(outline, list) or len(cast(list[object], outline)) < 3:
                    r.fail(f"{key}.outline", "expected at least three points")
                kwargs.update(
                    outline=tuple(r.point(p, f"{key}.outline") for p in cast(list[object], outline)),
                    layers=r.texts(table.get("layers"), f"{key}.layers"),
                    name=table.get("name", ""),
                    priority=r.integer(table.get("priority", 0), f"{key}.priority"),
                    settings=r.settings(table.get("settings", {}), f"{key}.settings"),
                )
                item = Zone(**kwargs)
            if "pads" in table:
                pads[ident] = r.texts(table["pads"], f"{key}.pads")
                for contact in pads[ident]:
                    local, dot, number = contact.rpartition(".")
                    if not dot or local not in parts or not number:
                        r.fail(f"{key}.pads", f"unknown local pad {contact}")
            copper[kind].append(item)
    return BlockLayout(
        header["block"],
        header["block_version"],
        header["parts_digest"],
        header["nets_digest"],
        header["licence"],
        header["evidence"],
        parts=MappingProxyType(dict(sorted(parts.items()))),
        pads=MappingProxyType(pads),
        captured_from=captured,
        **{kind: tuple(items) for kind, items in copper.items()},
    )


def _quote(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def _point(point: Point) -> str:
    return _quote([format_length(point.x), format_length(point.y)])


def _settings(settings: ZoneSettings | ZoneHatch) -> str:
    fields: list[str] = []
    for f in dataclasses.fields(settings):
        value = getattr(settings, f.name)
        if isinstance(value, ZoneHatch):
            shown = _settings(value)
        elif f.name == "min_island_area":
            shown = _quote(f"{value}nm2")
        elif f.name == "orientation":
            shown = _quote(format_angle(value))
        elif f.name == "smoothing_level":
            shown = str(value)
        elif isinstance(value, int):
            shown = _quote(format_length(value))
        else:
            shown = _quote(value)
        fields.append(f"{f.name} = {shown}")
    return "{ " + ", ".join(fields) + " }"


def _item_key(item: Copper) -> tuple[Any, ...]:
    layers = (item.layer,) if isinstance(item, (Track, Arc)) else item.layers
    points = (
        (item.start, item.end)
        if isinstance(item, Track)
        else (
            (item.start, item.mid, item.end)
            if isinstance(item, Arc)
            else ((item.position,) if isinstance(item, Via) else item.outline)
        )
    )
    return (layers, item.net_id or "", tuple((p.x, p.y) for p in points), canonical.dumps(item))


def write_block_layout(layout: BlockLayout) -> bytes:
    """Canonical key, part and geometry order; exact decimal millimetres and degrees."""
    lines = [
        "# SPDX-License-Identifier: CC0-1.0",
        "# Authored for Fenolite; captured block-local placement and copper.",
        f"schema = {_quote(SCHEMA)}",
    ]
    for name in ("block", "block_version", "parts_digest", "nets_digest", "licence", "evidence"):
        lines.append(f"{name} = {_quote(getattr(layout, name))}")
    if layout.captured_from is not None:
        lines.append(f"captured_from = {_quote(layout.captured_from)}")
    for name, part in sorted(layout.parts.items()):
        lines += [
            "",
            f"[parts.{_quote(name)}]",
            f"at = {_point(part.at)}",
            f"rotation = {_quote(format_angle(part.rotation))}",
            f"side = {_quote(part.side)}",
            f"footprint = {_quote(part.footprint)}",
        ]
    for kind in ("tracks", "arcs", "vias", "zones"):
        for item in sorted(getattr(layout, kind), key=_item_key):
            lines += ["", f"[[{kind}]]", f"net = {_quote(item.net_id)}"]
            if isinstance(item, (Track, Arc)):
                lines += [
                    f"layer = {_quote(item.layer)}",
                    f"width = {_quote(format_length(item.width))}",
                    f"start = {_point(item.start)}",
                ]
                if isinstance(item, Arc):
                    lines.append(f"mid = {_point(item.mid)}")
                lines.append(f"end = {_point(item.end)}")
            elif isinstance(item, Via):
                lines += [
                    f"at = {_point(item.position)}",
                    f"size = {_quote(format_length(item.diameter))}",
                    f"drill = {_quote(format_length(item.drill))}",
                    f"layers = {_quote(item.layers)}",
                ]
                if item.via_type != "through":
                    lines.append(f"via_type = {_quote(item.via_type)}")
            else:
                lines += [
                    f"layers = {_quote(item.layers)}",
                    "outline = [" + ", ".join(_point(p) for p in item.outline) + "]",
                    f"name = {_quote(item.name)}",
                    f"priority = {item.priority}",
                    f"settings = {_settings(item.settings)}",
                ]
            if layout.pads.get(item.id):
                lines.append(f"pads = {_quote(sorted(layout.pads[item.id]))}")
    return ("\n".join(lines) + "\n").encode("utf-8")


def pad_contains(pad: BoardPad, point: Point, layers: Sequence[str] = ()) -> bool:
    """An endpoint lies in exact pad copper on a participating layer, boundary included."""
    return any(
        entry.exact
        and (not layers or entry.layer in layers)
        and thick_touch(Thick(entry.core, entry.width, entry.filled), Thick((point, point), 0))
        for entry in pad.copper
    )


def component_path(component: Component) -> str:
    return component.properties.get("fenolite.path", component.path or component.ref)


def instance_parts(design: Design, instance: str) -> dict[str, Component]:
    prefix = f"{instance}/"
    return {
        component_path(c)[len(prefix) :]: c
        for c in design.circuit.components
        if component_path(c).startswith(prefix)
    }


def local_nets(design: Design, instance: str) -> dict[str, str]:
    """Model net id -> stable local spelling; ports take precedence over local net names."""
    names = {net.id: net.name for net in design.circuit.nets}
    module = next((m for m in design.circuit.modules if m.path == instance), None)
    found = {
        ident: f"net:{name[len(instance) + 1 :]}" if name.startswith(f"{instance}/") else f"global:{name}"
        for ident, name in names.items()
    }
    if module is not None:
        for port in sorted(design.circuit.ports, key=lambda p: p.name, reverse=True):
            if port.owner != module.id:
                continue
            for member, net in sorted(port.members.items(), reverse=True):
                found[net] = f"port:{port.name}" + (f".{member}" if len(port.members) > 1 else "")
    return found


def part_rows(
    design: Design, instance: str, definitions: Mapping[str, FootprintDef] | None = None
) -> list[list[Any]]:
    footprints = {fp.component_id: fp for fp in design.board.footprints} if design.board else {}
    rows: list[list[Any]] = []
    for path, c in sorted(instance_parts(design, instance).items()):
        defn = (definitions or {}).get(f"{instance}/{path}") or (definitions or {}).get(c.lib_footprint_ref)
        pads = defn.pads if defn is not None else (footprints[c.id].pads if c.id in footprints else ())
        numbers = sorted(pad.number for pad in pads)
        rows.append([path, c.lib_footprint_ref, numbers])
    return rows


def _sha(value: object) -> str:
    return "sha256:" + hashlib.sha256(canonical.dumps(value).encode("utf-8")).hexdigest()


def parts_digest(design: Design, instance: str, definitions: Mapping[str, FootprintDef] | None = None) -> str:
    return _sha(part_rows(design, instance, definitions))


def nets_digest(design: Design, instance: str, definitions: Mapping[str, FootprintDef] | None = None) -> str:
    local = local_nets(design, instance)
    members = {
        (p.component_id, pad): local[net.id]
        for net in design.circuit.nets
        for p in net.members
        for c in design.circuit.components
        if c.id == p.component_id
        for pad in c.pads_of(p.pin)
    }
    components = instance_parts(design, instance)
    return _sha(
        sorted(
            [path, pad, members.get((components[path].id, pad), "nc")]
            for path, _fp, pads in part_rows(design, instance, definitions)
            for pad in pads
        )
    )


@dataclass(frozen=True)
class LayoutApplication:
    status: str
    parts: Mapping[str, LayoutPart]
    copper: CopperCopy = CopperCopy()
    issues: tuple[Issue, ...] = ()


def apply_block_layout(
    layout: BlockLayout,
    design: Design,
    instance: str,
    pose: Transform,
    definitions: Mapping[str, FootprintDef] | None = None,
    *,
    copper: bool = False,
) -> LayoutApplication:
    """Validate identity/digests and compose positions without fitting or moving geometry to pads."""
    module = next((m for m in design.circuit.modules if m.path == instance), None)
    if module is None:
        raise ValueError(f"no module {instance}")
    issues: list[Issue] = []
    if (
        layout.block != module.block
        or layout.block_version.split(".")[0] != module.block_version.split(".")[0]
    ):
        return LayoutApplication(
            "refused",
            {},
            issues=(
                issue(
                    "reuse.layout-block",
                    f"{instance}: layout {layout.block}@{layout.block_version} differs from "
                    f"{module.block}@{module.block_version}",
                    where=instance,
                ),
            ),
        )
    parts_sha = parts_digest(design, instance, definitions)
    actual_rows = part_rows(design, instance, definitions)
    actual_parts = {row[0]: row[1] for row in actual_rows}
    inconsistent = set(actual_parts) != set(layout.parts) or any(
        part.footprint != actual_parts.get(path) for path, part in layout.parts.items()
    )
    if layout.parts_digest != parts_sha or inconsistent:
        actual = {row[0]: row[1] for row in part_rows(design, instance, definitions)}
        difference = next(
            (
                f"{path}: layout {layout.parts[path].footprint if path in layout.parts else 'absent'}, "
                f"built {actual.get(path, 'absent')}"
                for path in sorted(set(actual) | set(layout.parts))
                if path not in layout.parts or actual.get(path) != layout.parts[path].footprint
            ),
            "pad numbers changed",
        )
        return LayoutApplication(
            "stale",
            {},
            issues=(
                issue(
                    "reuse.layout-stale",
                    f"{instance}: parts digest {layout.parts_digest} differs from {parts_sha}; "
                    f"{difference}; staged",
                    where=instance,
                ),
            ),
        )
    status = "applied"
    if layout.nets_digest != nets_digest(design, instance, definitions):
        status = "nets-differ"
        issues.append(
            issue(
                "reuse.layout-nets",
                f"{instance}: nets digest {layout.nets_digest} differs from "
                f"{nets_digest(design, instance, definitions)}; placement kept, no copper copied",
                where=instance,
            )
        )
    elif tuple(map(int, layout.block_version.split("."))) < tuple(map(int, module.block_version.split("."))):
        status = "older"
        issues.append(
            issue(
                "reuse.layout-older",
                f"{instance}: layout {layout.block_version} applies to block {module.block_version}",
                where=instance,
            )
        )
    placed: dict[str, LayoutPart] = {}
    for path, part in layout.parts.items():
        transform = pose.compose(Transform.placement(part.at, part.rotation, part.side == "bottom"))
        at = Point(round_half_even_div(transform.tx_fixed, ONE), round_half_even_div(transform.ty_fixed, ONE))
        placed[path] = LayoutPart(
            at, transform.rot_udeg, "bottom" if transform.mirror else "top", part.footprint
        )
    copied = CopperCopy()
    if copper and status != "nets-differ" and design.board is not None:
        local = local_nets(design, instance)
        nets = {name: ident for ident, name in local.items()}
        reference = dataclasses.replace(
            design,
            board=dataclasses.replace(
                design.board, tracks=layout.tracks, arcs=layout.arcs, vias=layout.vias, zones=layout.zones
            ),
        )
        copied = copy_block(
            reference,
            pose,
            nets,
            layer_map(design.board, design.board, flipped=pose.mirror),
            key=f"block-layout:{instance}",
        )  # type: ignore[arg-type]
    return LayoutApplication(status, MappingProxyType(placed), copied, tuple(issues))


@dataclass(frozen=True)
class Capture:
    layout: BlockLayout | None
    issues: tuple[Issue, ...] = ()
    left: tuple[str, ...] = ()


def capture_block_layout(
    design: Design,
    instance: str,
    *,
    pose: Transform = IDENTITY,
    origin: str = "pose",
    anchor: str | None = None,
    pads: Sequence[BoardPad] = (),
    selected: frozenset[str] = frozenset(),
    copper: bool = True,
    licence: str = "Apache-2.0",
) -> Capture:
    """Capture a model's instance. The caller supplies c0227's selected joined copper group ids."""
    module = next((m for m in design.circuit.modules if m.path == instance), None)
    if module is None or not module.block_version:
        raise ValueError(f"{instance} is no recorded block instance")
    components = instance_parts(design, instance)
    footprints = {fp.component_id: fp for fp in design.board.footprints} if design.board else {}
    missing = [f"{instance}/{p}" for p, c in components.items() if c.id not in footprints]
    if missing:
        return Capture(
            None,
            (
                Issue(
                    "blocks.capture-unplaced",
                    "error",
                    f"parts not on the board: {', '.join(missing)}",
                    where=", ".join(missing),
                ),
            ),
        )
    if not components:
        return Capture(
            None,
            (Issue("blocks.capture-unplaced", "error", f"{instance} has no placed parts", where=instance),),
        )
    if origin == "anchor":
        name = anchor or min(components)
        if name not in components:
            raise ValueError(f"unknown anchor {name}; choose {', '.join(sorted(components))}")
        fp = footprints[components[name].id]
        pose = Transform.translation(fp.position.x, fp.position.y)
    inverse = pose.inverse()
    parts: dict[str, LayoutPart] = {}
    for name, c in sorted(components.items()):
        fp = footprints[c.id]
        frame = inverse.compose(Transform.placement(fp.position, fp.rotation, fp.side == "bottom"))
        at = Point(round_half_even_div(frame.tx_fixed, ONE), round_half_even_div(frame.ty_fixed, ONE))
        parts[name] = LayoutPart(at, frame.rot_udeg, "bottom" if frame.mirror else "top", c.lib_footprint_ref)
    local = local_nets(design, instance)
    issues: list[Issue] = []
    for name in sorted({value for value in local.values() if value.startswith("global:")}):
        net = next(n for n in design.circuit.nets if local[n.id] == name)
        if any(member.component_id in {c.id for c in components.values()} for member in net.members):
            issues.append(
                Issue(
                    "blocks.capture-escape", "warning", f"{instance}: pad on escaped {name}", where=instance
                )
            )
    board = design.board
    assert board is not None
    all_copper = (*board.tracks, *board.arcs, *board.vias, *board.zones)
    chosen = [item for item in all_copper if item.id in selected and copper and item.net_id is not None]
    unsupported = [item.id for item in chosen if isinstance(item, Via) and item.protection != ViaProtection()]
    if unsupported:
        return Capture(
            None,
            (
                *issues,
                Issue(
                    "blocks.capture-check-failed",
                    "error",
                    "v0 cannot round trip nondefault via protection: " + ", ".join(unsupported),
                    where=instance,
                ),
            ),
        )
    reference = dataclasses.replace(
        design,
        board=dataclasses.replace(
            board,
            tracks=tuple(i for i in chosen if isinstance(i, Track)),
            arcs=tuple(i for i in chosen if isinstance(i, Arc)),
            vias=tuple(i for i in chosen if isinstance(i, Via)),
            zones=tuple(i for i in chosen if isinstance(i, Zone)),
        ),
    )
    names = {name: name for layer in board.layers for name in (layer.name,)}
    if inverse.mirror:
        names = layer_map(board, board, flipped=True)
    copied = copy_block(reference, inverse, local, names, key="capture")
    items = [
        dataclasses.replace(found.item, fills=(), filled=False)
        if isinstance(found.item, Zone)
        else found.item
        for found in copied.items
    ]
    contacts: dict[str, tuple[str, ...]] = {}
    fp_paths = {fp.id: p for p, c in components.items() for fp in (footprints[c.id],)}
    # Exact pad containment is supplied by the CLI; local contacts are pad centres at an item's ends.
    for found in copied.items:
        source = next(item for item in chosen if item.id == found.source)
        ends = (
            (source.start, source.end)
            if isinstance(source, (Track, Arc))
            else ((source.position,) if isinstance(source, Via) else ())
        )
        contacts[found.item.id] = tuple(
            sorted(
                {
                    f"{fp_paths[p.footprint_id]}.{p.number}"
                    for p in pads
                    if p.footprint_id in fp_paths
                    and p.net_id == source.net_id
                    and any(pad_contains(p, end) for end in ends)
                }
            )
        )
    layout = BlockLayout(
        module.block,
        module.block_version,
        parts_digest(design, instance),
        nets_digest(design, instance),
        licence,
        "INFERRED",
        MappingProxyType(parts),
        tuple(i for i in items if isinstance(i, Track)),
        tuple(i for i in items if isinstance(i, Arc)),
        tuple(i for i in items if isinstance(i, Via)),
        tuple(i for i in items if isinstance(i, Zone)),
        MappingProxyType(contacts),
    )
    return Capture(layout, tuple(issues))


__all__ = [
    "SCHEMA",
    "BlockLayout",
    "BlockLayoutError",
    "LayoutPart",
    "LayoutApplication",
    "Capture",
    "read_block_layout",
    "write_block_layout",
    "parts_digest",
    "nets_digest",
    "part_rows",
    "local_nets",
    "instance_parts",
    "component_path",
    "apply_block_layout",
    "capture_block_layout",
]
