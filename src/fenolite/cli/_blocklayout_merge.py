# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A persistent three-way adapter for owned layout copper; no generic part edit/take grammar.

The root output snapshot has its own content hash and is also a protected planned build output.
Code is the asset's local geometry; output/CAD are measured back in that frame. Fills, native ids,
net ids and locks are not CAD geometry edits: nets follow the block map and copies remain locked.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

from fenolite.backends.kicad.copper import copper_uuid, is_copper_uuid
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.ids import derived_id
from fenolite.core.trig import ONE
from fenolite.core.units import round_half_even_div
from fenolite.geometry.transform import Transform
from fenolite.model import canonical
from fenolite.model.board import Arc, Track, Via, Zone
from fenolite.model.design import Design
from fenolite.reuse.blocklayout import BlockLayout, local_nets
from fenolite.reuse.codes import issue
from fenolite.reuse.copper import CopiedItem, Copper, CopperCopy, layer_map

BASE_FILE = "fenolite-layout-base.json"
SCHEMA = "fenolite.block-layout-base.v0"
EXCLUDED = {"id", "native_ids", "provenance", "ext", "net_id", "locked", "fills", "filled"}
KINDS: dict[str, type[Track] | type[Arc] | type[Via] | type[Zone]] = {
    "track": Track,
    "arc": Arc,
    "via": Via,
    "zone": Zone,
}


def _sha(data: object) -> str:
    return "sha256:" + hashlib.sha256(canonical.dumps(data).encode()).hexdigest()


def _validate_snapshot(raw: object) -> None:
    if raw is None:
        return
    if not isinstance(raw, dict):
        raise ValueError("a code/output observation is no geometry object")
    data = cast(dict[str, Any], raw)
    kind = data.get("kind")
    if not isinstance(kind, str) or kind not in KINDS:
        raise ValueError("an observation has an unknown copper kind")
    if any(key in EXCLUDED for key in data):
        raise ValueError("an observation contains identity or derived data")
    values = {key: value for key, value in data.items() if key != "kind"}
    values["id"] = derived_id(
        {"track": "trk", "arc": "arc", "via": "via", "zone": "zon"}[kind],
        "fenolite.layout-base",
        "validation",
    )
    try:
        item = canonical.loads(canonical.dumps(values), KINDS[kind], file=BASE_FILE)
        if isinstance(item, (Track, Arc)) and item.width <= 0:
            raise ValueError("an observation has a nonpositive width")
        if isinstance(item, Via) and not 0 < item.drill < item.diameter:
            raise ValueError("an observation has invalid via sizes")
        if isinstance(item, Zone) and len(item.outline) < 3:
            raise ValueError("an observation has no zone outline")
    except (FormatError, TypeError) as error:
        raise ValueError("an observation has malformed geometry") from error


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("expected an object")
    data = cast(dict[str, Any], raw)
    body = {key: value for key, value in data.items() if key != "sha256"}
    if data.get("schema") != SCHEMA or data.get("sha256") != _sha(body):
        raise ValueError("schema or body SHA-256 does not match")
    if set(body) != {"schema", "design", "layers", "frames", "assets", "copies"}:
        raise ValueError("unknown or missing snapshot fields")
    for key in ("frames", "assets", "copies"):
        if not isinstance(body[key], dict):
            raise ValueError(f"{key} is no table")
    for frame in data["frames"].values():
        _frame(frame)
    for block, rows in data["copies"].items():
        if not isinstance(block, str) or not isinstance(rows, dict):
            raise ValueError("invalid instance observations")
        for uid, raw_row in cast(dict[str, Any], rows).items():
            if not isinstance(raw_row, dict):
                raise ValueError("invalid owned copy observation")
            row = cast(dict[str, Any], raw_row)
            if set(row) != {"code", "out", "source", "net", "pads"}:
                raise ValueError("unknown or missing owned copy fields")
            if not isinstance(row["source"], str) or not isinstance(row["net"], str):
                raise ValueError("invalid source or local net")
            if uid != copper_uuid(f"block-layout:{block}", row["source"]):
                raise ValueError("owned UUID does not match its source")
            if not isinstance(row["pads"], list) or not all(
                isinstance(p, str) for p in cast(list[object], row["pads"])
            ):
                raise ValueError("invalid local pad contacts")
            _validate_snapshot(row["code"])
            _validate_snapshot(row["out"])
    return data


def frame_data(frame: Transform) -> list[Any]:
    return [
        round_half_even_div(frame.tx_fixed, ONE),
        round_half_even_div(frame.ty_fixed, ONE),
        frame.rot_udeg,
        "bottom" if frame.mirror else "top",
    ]


def _frame(value: Any) -> Transform:
    if not isinstance(value, list):
        raise ValueError("invalid frame")
    row = cast(list[Any], value)
    if len(row) != 4 or any(type(n) is not int for n in row[:3]) or row[3] not in ("top", "bottom"):
        raise ValueError("invalid frame")
    return Transform.placement(Point(row[0], row[1]), row[2], row[3] == "bottom")


def fallback_frames(out: Path) -> dict[str, tuple[int, int, int, str]]:
    """A clone keeps its pose observations in the persistent root base, even without cache files."""
    try:
        data = _read(out / BASE_FILE)
        if data is None:
            return {}
        return {path: (row[0], row[1], row[2], row[3]) for path, row in data["frames"].items()}
    except (OSError, ValueError, TypeError, KeyError):
        return {}  # the adapter reports a corrupt base before any write


def _move(item: Copper, frame: Transform, model: Design) -> Copper:
    board = model.board
    assert board is not None
    layers = layer_map(board, board, flipped=frame.mirror)
    order = {layer.name: index for index, layer in enumerate(board.layers) if layer.kind == "copper"}

    def image_layers(names: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(
            sorted((layers.get(name, name) for name in names), key=lambda name: order.get(name, len(order)))
        )

    if isinstance(item, (Track, Arc)):
        changes: dict[str, Any] = {
            "start": frame.apply(item.start),
            "end": frame.apply(item.end),
            "layer": layers.get(item.layer, item.layer),
        }
        if isinstance(item, Arc):
            changes["mid"] = frame.apply(item.mid)
        return dataclasses.replace(item, **changes)
    if isinstance(item, Via):
        return dataclasses.replace(
            item,
            position=frame.apply(item.position),
            layers=image_layers(item.layers),
        )
    return dataclasses.replace(
        item,
        outline=tuple(frame.apply(p) for p in item.outline),
        layers=image_layers(item.layers),
        fills=(),
        filled=False,
    )


def snapshot(item: Copper, *, frame: Transform | None = None, model: Design | None = None) -> dict[str, Any]:
    if frame is not None:
        assert model is not None
        item = _move(item, frame, model)
    data = cast(dict[str, Any], canonical.to_data(item))
    data = {key: value for key, value in data.items() if key not in EXCLUDED}
    data["kind"] = type(item).__name__.lower()
    if "layers" in data:
        data["layers"] = sorted(data["layers"])
    return data


def equal(first: dict[str, Any] | None, second: dict[str, Any] | None) -> bool:
    if first is None or second is None:
        return first is second
    if first.keys() != second.keys():
        return False
    for key, value in first.items():
        other = second[key]
        if key in ("start", "mid", "end", "position"):
            if any(abs(value[axis] - other[axis]) > 1 for axis in ("x", "y")):
                return False
        elif key == "outline":
            if len(value) != len(other) or any(
                abs(a[axis] - b[axis]) > 1 for a, b in zip(value, other, strict=True) for axis in ("x", "y")
            ):
                return False
        elif value != other:
            return False
    return True


def _copper(model: Design | None) -> dict[str, Copper]:
    if model is None or model.board is None:
        return {}
    return {
        item.native_ids.get("kicad", ""): item
        for item in (*model.board.tracks, *model.board.arcs, *model.board.vias, *model.board.zones)
        if item.native_ids.get("kicad")
    }


@dataclass
class CopyMerge:
    out: Path
    model: Design
    existing: Design | None
    worlds: Mapping[str, Transform]
    assets: Mapping[str, str]
    discard: bool = False
    previous: dict[str, Any] | None = None
    issues: list[Issue] = field(default_factory=lambda: [])
    rows: dict[str, dict[str, dict[str, Any]]] = field(default_factory=lambda: {})
    contacts: dict[str, tuple[str, ...]] = field(default_factory=lambda: {})
    owned: set[str] = field(default_factory=lambda: set())
    changed_kept: set[str] = field(default_factory=lambda: set())
    broken: bool = False
    had_file: bool = False
    absent_intent: set[tuple[str, str]] = field(default_factory=lambda: set())

    def __post_init__(self) -> None:
        self.had_file = (self.out / BASE_FILE).exists()
        if self.discard:
            return
        try:
            self.previous = _read(self.out / BASE_FILE)
            if self.previous is not None and self.previous["design"] != self.model.header.name:
                raise ValueError("the snapshot belongs to another design")
            if self.previous is not None and self.model.board is not None:
                layers = [layer.name for layer in self.model.board.layers if layer.kind == "copper"]
                if self.previous.get("layers") != layers:
                    raise ValueError("the copper stack changed; restore it, recapture, or discard layout")
            for block, rows in (self.previous or {}).get("copies", {}).items():
                if not isinstance(rows, dict):
                    raise ValueError(f"invalid rows of {block}")
                for uid, row in cast(dict[str, Any], rows).items():
                    if not isinstance(row, dict) or set(cast(dict[str, Any], row)) != {
                        "code",
                        "out",
                        "source",
                        "net",
                        "pads",
                    }:
                        raise ValueError("invalid owned copy row")
                    self.owned.add(uid)
        except (OSError, ValueError, TypeError, KeyError) as error:
            self.previous = None
            self.broken = True
            self.issues.append(
                issue(
                    "reuse.layout-conflict",
                    f"{BASE_FILE}: {error}; copper observations cannot be trusted",
                    where=BASE_FILE,
                    hint="restore the protected base, or review --discard-layout",
                )
            )

    @property
    def needed(self) -> bool:
        return bool(self.assets) or self.had_file or self.broken

    def frame(self, block: str) -> Transform:
        if block in self.worlds:
            return self.worlds[block]
        row = (self.previous or {}).get("frames", {}).get(block)
        return _frame(row) if row is not None else Transform()

    def merge(self, block: str, layout: BlockLayout | None, copy: CopperCopy) -> CopperCopy:
        """Choose local geometry before contact checks and settling. No --take grammar is consulted."""
        old = cast(dict[str, dict[str, Any]], (self.previous or {}).get("copies", {}).get(block, {}))
        frame = self.frame(block)
        cad_items = _copper(self.existing)
        source_items = {item.id: item for item in layout.copper} if layout is not None else {}
        wanted = {copper_uuid(f"block-layout:{block}", source): source for source in source_items}
        templates = {found.source: found for found in copy.items}
        chosen: list[CopiedItem] = []
        rows: dict[str, dict[str, Any]] = {}
        for uid in sorted(set(wanted) | set(old)):
            self.owned.add(uid)
            prior = old.get(uid)
            source = wanted.get(uid, str(prior["source"]) if prior else "")
            original = source_items.get(source) if uid in wanted else None
            code = snapshot(original) if original is not None else None
            current = cad_items.get(uid)
            cad = snapshot(current, frame=frame.inverse(), model=self.model) if current is not None else None
            local_net = original.net_id if original is not None else (prior or {}).get("net")
            pads = (
                layout.pads.get(source, ())
                if original is not None and layout is not None
                else tuple((prior or {}).get("pads", ()))
            )
            self.contacts[f"{block}:{source}"] = tuple(pads)
            use = code
            conflict = False
            if not self.discard and self.existing is not None and not self.broken:
                if prior is None and self.previous is None:
                    conflict = not equal(code, cad)
                    use = cad if conflict else code
                elif prior is not None:
                    code_changed, cad_changed = not equal(code, prior["code"]), not equal(cad, prior["out"])
                    if equal(code, cad):
                        use = code
                    elif code_changed and cad_changed:
                        conflict, use = True, cad
                    elif not code_changed:
                        use = cad
                elif current is not None and not equal(code, cad):
                    conflict, use = True, cad
            if conflict:
                missing = (
                    " without a persistent snapshot"
                    if self.previous is None
                    else " on both code and CAD sides"
                )
                self.issues.append(
                    issue(
                        "reuse.layout-conflict",
                        f"{block}: owned copper {source} differs{missing}; nothing is written",
                        where=f"{block}:{source}",
                        hint="recapture the CAD geometry into the asset, restore the chosen geometry, "
                        "or review --discard-layout; part --take does not choose copper",
                    )
                )
            if not equal(use, code) and (self.previous or {}).get("assets", {}).get(block) != self.assets.get(
                block
            ):
                self.changed_kept.add(block)
            row = {"code": code, "out": use, "source": source, "net": local_net, "pads": list(pads)}
            rows[uid] = row
            if use is None:
                if prior is not None and current is None:
                    self.absent_intent.add((block, uid))
                continue
            template = templates.get(source)
            if equal(use, code) and template is None:
                continue  # the normal layer/net copier already dropped this source
            target_net = next(
                (ident for ident, name in local_nets(self.model, block).items() if name == local_net), None
            )
            if target_net is None:
                self.issues.append(
                    issue(
                        "reuse.layout-conflict",
                        f"{block}: kept copper {source} has no surviving local net",
                        where=block,
                        hint="recapture against the current block nets or review --discard-layout",
                    )
                )
                continue
            data = {key: value for key, value in use.items() if key != "kind"}
            data.update(
                id=derived_id(
                    {"track": "trk", "arc": "arc", "via": "via", "zone": "zon"}[use["kind"]],
                    "fenolite.layout-base",
                    uid,
                ),
                native_ids={"kicad": uid},
                locked=True,
                net_id=target_net,
            )
            item = cast(Copper, canonical.loads(canonical.dumps(data), KINDS[use["kind"]], file=BASE_FILE))
            item = _move(item, frame, self.model)
            if current is not None and type(item) is type(current):
                if equal(use, cad):
                    item = dataclasses.replace(
                        current, id=item.id, native_ids=item.native_ids, net_id=target_net, locked=True
                    )
                else:
                    item = dataclasses.replace(item, ext=current.ext, provenance=current.provenance)
            chosen.append(CopiedItem(item, source, str(local_net)))
        self.rows[block] = rows
        return CopperCopy(tuple(chosen), copy.nets, copy.dropped)

    def complete_choices(self) -> None:
        if (
            self.previous is None
            and self.existing is not None
            and self.assets
            and not (self.discard or self.broken)
        ):
            unknown = set(_copper(self.existing)) - self.owned - set(_copper(self.model))
            if any(is_copper_uuid(uid) for uid in unknown):
                self.issues.append(
                    issue(
                        "reuse.layout-conflict",
                        "a missing layout copper snapshot leaves script-copy ownership ambiguous",
                        where=BASE_FILE,
                        hint="restore the protected base, or review --discard-layout",
                    )
                )

    def remaining(self) -> tuple[str, ...]:
        return tuple(sorted(set((self.previous or {}).get("copies", {})) - set(self.rows)))

    def strip(self, existing: Design | None) -> Design | None:
        if existing is None or existing.board is None:
            return existing
        board = existing.board
        return dataclasses.replace(
            existing,
            board=dataclasses.replace(
                board,
                tracks=tuple(i for i in board.tracks if i.native_ids.get("kicad") not in self.owned),
                arcs=tuple(i for i in board.arcs if i.native_ids.get("kicad") not in self.owned),
                vias=tuple(i for i in board.vias if i.native_ids.get("kicad") not in self.owned),
                zones=tuple(i for i in board.zones if i.native_ids.get("kicad") not in self.owned),
            ),
        )

    def output(self, written: Design) -> bytes:
        """Record the actual written model, including settled-away copies and CAD deletions."""
        actual = _copper(written)
        for block, rows in self.rows.items():
            for uid, row in list(rows.items()):
                item = actual.get(uid)
                if item is None and row["code"] is not None and (block, uid) not in self.absent_intent:
                    del rows[uid]  # a settled-away candidate was never a saved CAD deletion
                    continue
                row["out"] = (
                    snapshot(item, frame=self.frame(block).inverse(), model=self.model)
                    if item is not None
                    else None
                )
        frames = {
            **(self.previous or {}).get("frames", {}),
            **{block: frame_data(frame) for block, frame in sorted(self.worlds.items()) if block},
        }
        body: dict[str, Any] = {
            "schema": SCHEMA,
            "design": self.model.header.name,
            "frames": frames,
            "layers": [layer.name for layer in self.model.board.layers if layer.kind == "copper"]
            if self.model.board
            else [],
            "assets": dict(self.assets),
            "copies": self.rows,
        }
        return canonical.dumps({**body, "sha256": _sha(body)}).encode()
