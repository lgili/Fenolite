# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Placement in code for ``fenolite build`` (change c0255; capability placement-in-code; ``docs/dsl.md``,
"Relative placement" and "Block layout"; ``docs/lens.md``, "Placement precedence").

The build injects what ``lens`` may not import: ``plan_layout`` measures every part's footprint (the box of
``footprint_extent`` and the pad boxes), reads the reference boards of the block reuses, and makes the
resolver that ``lens.preserve.prepare`` calls (``fenolite.placement.relative.resolve``). It also moves the
kept parts and copper of a block whose pose changed since the last build (``adjust``), copies the copper of
a block reuse with ``copper=True`` into the model, and gives ``result.placement.relative`` and
``result.placement.blocks`` and the record of ``.fenolite/build.json``.
"""

from __future__ import annotations

import dataclasses
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.embed import PATH_PROPERTY, footprint_extent
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.liberrors import LibraryError
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver
from fenolite.backends.kicad.outline import outline_box
from fenolite.backends.kicad.replace import PlacementError, move_footprint
from fenolite.cli import _blocklayouts, place_group
from fenolite.cli._blocklayout_merge import BASE_FILE as COPPER_BASE_FILE
from fenolite.cli._blocklayout_merge import CopyMerge, fallback_frames
from fenolite.cli._boardview import load_board
from fenolite.cli._script import DesignScriptError
from fenolite.cli.api import Context
from fenolite.cli.errors import CliError
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.trig import ONE
from fenolite.core.units import round_half_even_div
from fenolite.dsl import relative as dsl_relative
from fenolite.dsl.block import Block
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.dsl.design import Design as DslDesign
from fenolite.geometry.shapes import BBox
from fenolite.geometry.transform import Transform
from fenolite.lens.build import CACHE_DIR, RECORD_FILE, STAGING_OFFSET
from fenolite.lens.preserve import CodePlacement, PlacementLike
from fenolite.model.board import Arc, Track, Via, Zone
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.placement import relative
from fenolite.placement.codes import layout_issue
from fenolite.reuse import codes as reuse_codes
from fenolite.reuse.copper import CopiedItem, CopperCopy, copy_block, layer_map, with_copper
from fenolite.reuse.fit import DEFAULT_TOLERANCE

LAYOUT_KEY = "layout"
"""The key of the resolved block poses and the digest of the resolved placements in the build record."""


def _pad_box(pad: Any) -> BBox:
    w, h = pad.size.w, pad.size.h
    local = BBox(-(w - w // 2), -(h - h // 2), (w + 1) // 2, (h + 1) // 2)
    return Transform.placement(pad.position, pad.rotation).apply_bbox(local)


def measure(defn: FootprintDef) -> relative.Footprint:
    """What the resolution measures of a footprint definition: the box of ``footprint_extent`` and every
    pad's position and box, in the footprint's frame."""
    pads = tuple(relative.PadBox(pad.number, pad.position, _pad_box(pad)) for pad in defn.pads if pad.number)
    return relative.Footprint(footprint_extent(defn), pads)


def _component_path(component: Any) -> str:
    return cast(str, component.properties.get(PATH_PROPERTY, component.ref))


def footprint_definitions(
    model: Design,
    authored: Mapping[str, FootprintDef],
    *,
    script_path: Path,
    ctx: Context,
) -> dict[str, FootprintDef]:
    """Component path → the definition of its footprint: an authored or catalog one, else the project's
    libraries. A footprint that does not resolve is left out; the build reports it."""
    found: dict[str, FootprintDef] = {}
    resolver: LibraryResolver | None = None
    for component in sorted(model.circuit.components, key=_component_path):
        lib_ref = component.lib_footprint_ref
        if not lib_ref:
            continue
        defn = authored.get(lib_ref)
        if defn is None:
            if resolver is None:
                resolver = LibraryResolver(
                    LibraryConfig(target_major=ctx.kicad_target, project_dir=script_path.resolve().parent)
                )
            try:
                defn = resolver.footprint(lib_ref)
            except (LibraryError, OSError, ValueError):
                continue
        found[_component_path(component)] = defn
    return found


@dataclass(frozen=True)
class ReuseBoard:
    """A reference board of a block reuse: the block, the board as read, its pad records, the origin of its
    ``place()`` frame, the block-local path of each footprint id and the prefix stripped from the paths and
    net names of a board built from an instance of the block."""

    block: str
    copper: bool
    design: Design
    pads: tuple[BoardPad, ...]
    origin: Point
    paths: Mapping[str, str]
    prefix: str = ""


def _read_reuse(
    layout: dsl_relative.BlockLayout, reuse: dsl_relative.Reuse, *, script_path: Path, ctx: Context
) -> ReuseBoard:
    base = Path(reuse.root) if reuse.root is not None else script_path.resolve().parent
    path = Path(reuse.path)
    full = path if path.is_absolute() else base / path
    if not full.is_file():
        raise DesignScriptError(
            f"block {layout.path}: layout(reuse={reuse.path!r}) names no board file", file=str(script_path)
        )
    try:
        view = load_board(str(full), ctx)
    except CliError as error:
        raise DesignScriptError(
            f"block {layout.path}: layout(reuse={reuse.path!r}): {error}", file=str(script_path)
        ) from error
    design = view.design
    assert design.board is not None
    components = {c.id: c for c in design.circuit.components}
    paths: dict[str, str] = {}
    for fp in design.board.footprints:
        component = components.get(fp.component_id)
        paths[fp.id] = _component_path(component) if component is not None else fp.id
    heads = {p.split("/", 1)[0] for p in paths.values()}
    prefix = ""
    if len(heads) == 1 and all("/" in p for p in paths.values()):
        prefix = f"{next(iter(heads))}/"
        paths = {key: value[len(prefix) :] for key, value in paths.items()}
    box = outline_box(design)
    origin = Point(box[0], box[1]) if box is not None else BOARD_ORIGIN
    return ReuseBoard(layout.path, reuse.copper, design, view.pads, origin, paths, prefix)


def _placed(transform: Transform) -> tuple[Point, int, str]:
    at = Point(round_half_even_div(transform.tx_fixed, ONE), round_half_even_div(transform.ty_fixed, ONE))
    return at, transform.rot_udeg, "bottom" if transform.mirror else "top"


PoseRecord = tuple[int, int, int] | tuple[int, int, int, str]
NO_POSES: Mapping[str, PoseRecord] = MappingProxyType({})
"""No recorded block pose."""


def read_layout_record(out_dir: Path, *, owned: Sequence[str] = ()) -> Mapping[str, PoseRecord]:
    """The block poses of the last build (block path → x, y, rotation of its frame in the written frame),
    empty without a record."""
    persistent = fallback_frames(out_dir)
    if persistent:
        return MappingProxyType(persistent)
    try:
        data = json.loads((out_dir / RECORD_FILE).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return MappingProxyType(fallback_frames(out_dir))
    held = cast(dict[str, object], data).get(LAYOUT_KEY) if isinstance(data, dict) else None
    poses = cast(dict[str, object], held).get("poses") if isinstance(held, dict) else None
    if not isinstance(poses, dict):
        return MappingProxyType(fallback_frames(out_dir))
    found: dict[str, PoseRecord] = {}
    for key, value in cast(dict[object, object], poses).items():
        if isinstance(key, str) and any(
            key == block or key.startswith(f"{block}/") or block.startswith(f"{key}/") for block in owned
        ):
            continue  # a missing persistent observation never lets the cache move an owned copy
        if not isinstance(value, list):
            continue
        numbers = cast(list[object], value)
        if isinstance(key, str) and len(numbers) in (3, 4):
            if all(isinstance(n, int) and not isinstance(n, bool) for n in numbers[:3]):
                x, y, turn = cast(list[int], numbers[:3])
                if len(numbers) == 3:
                    found[key] = (x, y, turn)
                elif numbers[3] in ("top", "bottom"):
                    found[key] = (x, y, turn, cast(str, numbers[3]))
    return MappingProxyType(found)


@dataclass
class LayoutPlan:
    """The placement in code of one build: the scene, the script's absolute placements, the text of each
    relative request, the code resolution, the last resolution the lens asked for, the issues of the reuses
    and moves, the reference boards and the footprint definitions by lib id."""

    scene: relative.Scene
    requested: Mapping[str, PlacementLike]
    code: relative.Resolution
    reuse: Mapping[str, ReuseBoard] = field(default_factory=lambda: {})
    definitions: Mapping[str, FootprintDef] = field(default_factory=lambda: {})
    issues: list[Issue] = field(default_factory=lambda: [])
    last: relative.Resolution | None = None
    moved: dict[str, tuple[int, int, int]] = field(default_factory=lambda: {})
    files: Mapping[str, _blocklayouts.LayoutFile] = field(default_factory=lambda: {})
    sources: Mapping[str, object] = field(default_factory=lambda: {})

    def resolver(self, fixed: Mapping[str, PlacementLike]) -> Mapping[str, PlacementLike]:
        """The code placements for ``lens.preserve.resolving``: the script's own ``Placement`` where the
        resolution gives it unchanged, else a ``CodePlacement``."""
        held = {path: relative.Placed(p.at, p.rotation, p.side) for path, p in fixed.items()}
        resolution = relative.resolve(self.scene, held) if held else self.code
        self.last = resolution
        texts = {record.path: record.request for record in resolution.records}
        out: dict[str, PlacementLike] = {}
        for path, found in resolution.placements.items():
            given = self.requested.get(path)
            same = given is not None and (given.at, given.rotation, given.side, given.locked) == (
                found.at,
                found.rotation,
                found.side,
                found.locked,
            )
            if same and not found.staged:
                assert given is not None
                out[path] = given
                continue
            out[path] = CodePlacement(
                found.at,
                found.rotation,
                cast(Any, found.side),
                found.locked,
                texts.get(path, ""),
                found.staged,
                resolution.staging_end if found.staged else None,
            )
        return MappingProxyType(out)

    def placements(self) -> Mapping[str, PlacementLike]:
        """The code placements without a board (a build with ``--discard-layout``)."""
        return self.resolver(MappingProxyType({}))

    def moves(self, old: Mapping[str, PoseRecord]) -> dict[str, Transform]:
        """Each block whose resolved pose differs from the pose ``old`` records (the last build's), with the
        move ``new ∘ old⁻¹`` of its frame. A block staged as one box never moves its kept parts."""
        found: dict[str, Transform] = {}
        for path in sorted(old):
            new = self.code.worlds.get(path)
            held = self.code.blocks.get(path)
            if new is None or held is None or held.staged:
                continue
            previous = old[path]
            x, y, turn = previous[:3]
            before = Transform.placement(Point(x, y), turn, len(previous) == 4 and previous[3] == "bottom")
            if (new.rot_udeg, new.mirror, _placed(new)[0]) == (before.rot_udeg, before.mirror, Point(x, y)):
                continue
            found[path] = new.compose(before.inverse())
        return found

    @staticmethod
    def _owner(path: str, moves: Mapping[str, Transform]) -> str | None:
        """The innermost moved block that holds the component ``path``."""
        best: str | None = None
        for block in moves:
            if path.startswith(f"{block}/") and (best is None or len(block) > len(best)):
                best = block
        return best

    def adjust_base(self, base: Any, old: Mapping[str, PoseRecord]) -> Any:
        """The base record with the position and rotation of every part of a moved block moved with it:
        the code and the board moved the block together, so the three-way merge sees no change of its own
        (``lens.edits``, "Three-way merge")."""
        from fenolite.lens.edits import BaseEntry, BaseRecord

        moves = self.moves(old)
        if not moves or not isinstance(base, BaseRecord) or not base.present:
            return base
        parts: dict[str, Mapping[str, BaseEntry]] = {}
        for path, values in base.parts.items():
            owner = self._owner(path, moves)
            if owner is None:
                parts[path] = values
                continue
            move = moves[owner]
            changed = dict(values)
            for key in ("code", "out"):
                position = getattr(values.get("position"), key, None)
                rotation = getattr(values.get("rotation"), key, None)
                if not isinstance(position, tuple):
                    continue
                turn, side = cast(tuple[int, str], rotation) if isinstance(rotation, tuple) else (0, "top")
                pair = cast(tuple[int, int], position)
                at = Point(pair[0], pair[1])
                placed = _placed(move.compose(Transform.placement(at, turn, side == "bottom")))
                for prop, value in (
                    ("position", (placed[0].x, placed[0].y)),
                    ("rotation", (placed[1], placed[2])),
                ):
                    entry = changed.get(prop)
                    if entry is None or (prop == "rotation" and not isinstance(rotation, tuple)):
                        continue
                    changed[prop] = dataclasses.replace(entry, **{key: value})
            parts[path] = MappingProxyType(changed)
        return dataclasses.replace(base, parts=MappingProxyType(parts))

    def adjust(self, old: Mapping[str, PoseRecord]) -> Any:
        """The board change of ``lens.preserve.prepare``: each part of a block whose resolved pose differs
        from the one ``old`` records moves by ``new ∘ old⁻¹`` of its innermost moved block, with the copper
        joined only to the moved parts' pads (c0227's group move); each block whose own pose changed gives
        one ``layout.block-moved``, and a moved part with copper to parts that stay ``place.copper-left``."""

        def change(board: Design) -> tuple[Design, Sequence[Issue]]:
            return self._move_blocks(board, old)

        return change

    def _move_blocks(self, board: Design, old: Mapping[str, PoseRecord]) -> tuple[Design, Sequence[Issue]]:
        issues: list[Issue] = []
        moves = self.moves(old)
        if board.board is None or not moves:
            return board, issues
        backend = KicadBackend()
        components = {c.id: c for c in board.circuit.components}
        groups: dict[str, list[str]] = {}
        for fp in board.board.footprints:
            component = components.get(fp.component_id)
            if component is None:
                continue
            owner = self._owner(_component_path(component), moves)
            if owner is not None:
                groups.setdefault(owner, []).append(fp.id)
        pads = backend.board_pads(board)
        everyone = {fp_id for members in groups.values() for fp_id in members}
        moved_board: Design = board
        moved_copper: set[str] = set()
        from fenolite.backends.kicad.mod import prepare_authored_definition

        definitions = {key: prepare_authored_definition(defn) for key, defn in self.definitions.items()}
        for owner in sorted(groups):
            move, members = moves[owner], groups[owner]
            copper = place_group.moving_copper(board, pads, members)
            moved_copper |= copper
            for fp_id in members:
                held_board = moved_board.board
                assert held_board is not None
                fp = next(f for f in held_board.footprints if f.id == fp_id)
                target = Transform.placement(fp.position, fp.rotation, fp.side == "bottom")
                at, rotation, side = _placed(move.compose(target))
                try:
                    moved_board = move_footprint(
                        moved_board,
                        fp_id,
                        at=at,
                        rotation=rotation,
                        side=cast(Any, side),
                        definitions=definitions,
                        force=True,
                    )
                except PlacementError as error:
                    issues.extend(error.issues)
            held = moved_board.board
            assert held is not None
            layers = layer_map(held, held, flipped=move.mirror)
            layer_order = {layer.name: index for index, layer in enumerate(held.layers)}

            def moved(
                item: Any,
                move: Transform = move,
                layers: Mapping[str, str] = layers,
                layer_order: Mapping[str, int] = layer_order,
            ) -> Any:
                image = place_group.moved_item(item, move)
                if not move.mirror:
                    return image
                if isinstance(image, (Track, Arc)):
                    return dataclasses.replace(image, layer=layers.get(image.layer, image.layer))
                return dataclasses.replace(
                    image,
                    layers=tuple(
                        sorted(
                            (layers.get(name, name) for name in image.layers),
                            key=lambda name: layer_order.get(name, len(layer_order)),
                        )
                    ),
                    **(
                        {
                            "fills": tuple(
                                dataclasses.replace(fill, layer=layers.get(fill.layer, fill.layer))
                                for fill in image.fills
                            )
                        }
                        if isinstance(image, Zone)
                        else {}
                    ),
                )

            moved_board = dataclasses.replace(
                moved_board,
                board=dataclasses.replace(
                    held,
                    tracks=tuple(moved(t) if t.id in copper else t for t in held.tracks),  # type: ignore[misc]
                    arcs=tuple(moved(a) if a.id in copper else a for a in held.arcs),  # type: ignore[misc]
                    vias=tuple(moved(v) if v.id in copper else v for v in held.vias),  # type: ignore[misc]
                    zones=tuple(moved(z) if z.id in copper else z for z in held.zones),  # type: ignore[misc]
                ),
            )
            shift = _placed(move)[0]
            self.moved[owner] = (shift.x, shift.y, move.rot_udeg)
        for owner in sorted(moves):
            parent = self._owner(owner, moves)
            if parent is not None and moves[parent] == moves[owner]:
                continue  # carried by its moved parent block
            count = sum(
                len(members)
                for block, members in groups.items()
                if block == owner or block.startswith(f"{owner}/")
            )
            issues.append(
                layout_issue(
                    "layout.block-moved",
                    f"block {owner} has a new pose; its {count} kept part(s) moved with it, with the copper "
                    "joined only to their pads",
                    owner,
                )
            )
        names = {c.id: c.ref for c in board.circuit.components}
        assert board.board is not None
        for fp_id in _copper_left(board, pads, everyone, frozenset(moved_copper)):
            fp = next(f for f in board.board.footprints if f.id == fp_id)
            issues.append(_copper_left_issue(names.get(fp.component_id, fp_id)))
        return moved_board, issues

    def summary(self) -> dict[str, object]:
        """``result.placement.relative`` and ``result.placement.blocks``."""
        resolution = self.last or self.code
        origin = self.scene.origin
        records = [
            {
                "path": record.path,
                "request": record.request,
                "frame": record.frame,
                "refs": [
                    {
                        "ref": used.ref,
                        "box": [used.box.x0, used.box.y0, used.box.x1, used.box.y1],
                        "center": [used.center.x, used.center.y],
                    }
                    for used in record.refs
                ],
                "at": [record.at.x - origin.x, record.at.y - origin.y],
                "rotation": record.rotation,
                "side": record.side,
            }
            for record in resolution.records
        ]
        blocks = [
            {
                "path": held.path,
                "at": [held.at.x - origin.x, held.at.y - origin.y],
                "rotation": held.rotation,
                **({"side": held.side} if held.side != "top" else {}),
                "layout": self.files[held.path].summary() if held.path in self.files else held.layout,
                "source": held.source,
                "staged": held.staged,
            }
            for held in resolution.blocks.values()
        ]
        top = self.scene.top
        return {
            "relative": records,
            "blocks": blocks,
            "top": None if top is None else cast(Any, top).text(),
            "digest": resolution.digest(),
        }

    def layout_notices(self, out_dir: Path, placements: Mapping[str, PlacementLike]) -> list[Issue]:
        try:
            previous = (
                json.loads((out_dir / RECORD_FILE).read_text(encoding="utf-8"))
                .get("layout", {})
                .get("files", {})
            )
        except (OSError, ValueError):
            return []
        issues: list[Issue] = []
        for path, file in self.files.items():
            old = previous.get(path, {})
            if not old or old.get("sha256") == file.sha256:
                continue
            kept = [
                name
                for name, code in self.code.placements.items()
                if name.startswith(f"{path}/")
                and name in placements
                and (placements[name].at, placements[name].rotation, placements[name].side)
                != (code.at, code.rotation, code.side)
            ]
            if kept:
                issues.append(
                    reuse_codes.issue(
                        "reuse.layout-changed",
                        f"{path}: layout file changed; kept parts do not follow it: {', '.join(kept)}",
                        where=path,
                    )
                )
        return issues

    def record(self) -> dict[str, object]:
        """What ``.fenolite/build.json`` keeps: the resolved block poses and the digest."""
        resolution = self.last or self.code
        poses = {
            path: [held.at.x, held.at.y, held.rotation, *([held.side] if held.side != "top" else [])]
            for path, held in resolution.blocks.items()
        }
        return {
            "poses": poses,
            **({"sources": dict(self.sources)} if self.sources else {}),
            "digest": resolution.digest(),
            **({"files": {path: file.summary() for path, file in self.files.items()}} if self.files else {}),
        }


def _copper_left_issue(ref: str) -> Issue:
    from fenolite.placement.codes import issue as place_issue

    return place_issue(
        "place.copper-left",
        f"{ref} had copper to parts outside its block; those tracks and vias stay where they were",
        ref,
        "route the part again, or move the copper in KiCad",
    )


def _copper_left(
    board: Design, pads: Sequence[BoardPad], members: set[str], moving: frozenset[str]
) -> list[str]:
    """The moved footprints with a track end or a via on a pad that does not move with them."""
    held = board.board
    assert held is not None
    ends: list[tuple[Point, tuple[str, ...]]] = []
    for track in held.tracks:
        if track.id not in moving:
            ends += [(track.start, (track.layer,)), (track.end, (track.layer,))]
    for arc in held.arcs:
        if arc.id not in moving:
            ends += [(arc.start, (arc.layer,)), (arc.end, (arc.layer,))]
    for via in held.vias:
        if via.id not in moving:
            ends.append((via.position, tuple(via.layers)))
    found: list[str] = []
    for pad in pads:
        if pad.footprint_id not in members or pad.footprint_id in found:
            continue
        for entry in pad.copper:
            box = BBox.of_points(entry.core).inflate(-(-entry.width // 2))
            if any(entry.layer in layers and box.contains_point(point) for point, layers in ends):
                found.append(pad.footprint_id)
                break
    return sorted(found)


def _reuse_placements(
    scene_blocks: Mapping[str, dsl_relative.BlockLayout], boards: Mapping[str, ReuseBoard]
) -> dict[str, dict[str, relative.Placed]]:
    found: dict[str, dict[str, relative.Placed]] = {}
    for path, board in boards.items():
        assert path in scene_blocks
        held = board.design.board
        assert held is not None
        local: dict[str, relative.Placed] = {}
        for fp in held.footprints:
            name = board.paths.get(fp.id)
            if name is None or name in local:
                continue
            at = Point(fp.position.x - board.origin.x, fp.position.y - board.origin.y)
            local[name] = relative.Placed(at, fp.rotation, fp.side)
        found[path] = local
    return found


def _check_pads(
    plan: LayoutPlan, footprints: Mapping[str, FootprintDef], resolution: relative.Resolution
) -> list[Issue]:
    """``reuse.no-fit`` for each part placed by a reuse whose pads differ from its reference part's: every
    pad number found once in both lies within ``DEFAULT_TOLERANCE`` of the reference pad once the part's
    definition is placed where the reference part lies."""
    issues: list[Issue] = []
    for block, board in sorted(plan.reuse.items()):
        held = board.design.board
        assert held is not None
        by_name = {name: fp_id for fp_id, name in board.paths.items()}
        records: dict[str, list[BoardPad]] = {}
        for record in board.pads:
            records.setdefault(record.footprint_id, []).append(record)
        for path, placed in sorted(resolution.placements.items()):
            if not path.startswith(f"{block}/") or placed.source not in ("reuse", "group"):
                continue
            fp_id = by_name.get(path[len(block) + 1 :])
            defn = footprints.get(path)
            if fp_id is None or defn is None:
                continue
            fp = next(f for f in held.footprints if f.id == fp_id)
            frame = Transform.placement(fp.position, fp.rotation, fp.side == "bottom")
            ours = {pad.number: frame.apply(pad.position) for pad in defn.pads if pad.number}
            counts: dict[str, int] = {}
            for pad in defn.pads:
                counts[pad.number] = counts.get(pad.number, 0) + 1
            theirs: dict[str, list[Point]] = {}
            for record in records.get(fp_id, []):
                theirs.setdefault(record.number, []).append(record.position)
            far = 0
            missing = sorted(set(ours) ^ set(theirs))
            for number, point in ours.items():
                goal = theirs.get(number)
                if counts.get(number) != 1 or goal is None or len(goal) != 1:
                    continue
                far = max(far, abs(point.x - goal[0].x), abs(point.y - goal[0].y))
            if missing or far > DEFAULT_TOLERANCE:
                detail = (
                    f"pads {', '.join(missing)} are on one side only"
                    if missing
                    else f"a pad lies {far} nm away"
                )
                issues.append(
                    reuse_codes.issue(
                        "reuse.no-fit",
                        f"{path} does not fit its reference part in the board of block {block}: {detail}",
                        where=path,
                        hint="lay the block out again with the same footprints",
                    )
                )
    return issues


def plan_layout(
    design: DslDesign,
    model: Design,
    *,
    requested: Mapping[str, PlacementLike],
    authored: Mapping[str, FootprintDef],
    script_path: Path,
    ctx: Context,
) -> LayoutPlan | None:
    """The placement in code of ``design``, or ``None`` when it asks for none (the build is then that of
    before change c0255, byte for byte). A ``DslError`` of a locked reference or a frame rule raises."""
    if not dsl_relative.has_layout(design):
        return None
    relatives = dsl_relative.relative_requests(design)
    layouts = dsl_relative.block_layouts(design)
    defs = footprint_definitions(model, authored, script_path=script_path, ctx=ctx)
    boards: dict[str, ReuseBoard] = {}
    files: dict[str, _blocklayouts.LayoutFile] = {}
    for path, layout in layouts.items():
        if isinstance(layout.layout, dsl_relative.Reuse):
            reuse = layout.layout
            if Path(reuse.path).suffix.lower() == ".toml":
                base = Path(reuse.root) if reuse.root is not None else script_path.resolve().parent
                full = Path(reuse.path) if Path(reuse.path).is_absolute() else base / reuse.path
                files[path] = _blocklayouts.read_layout(
                    reuse.path, full, model, path, defs, copper=reuse.copper
                )
            else:
                boards[path] = _read_reuse(layout, reuse, script_path=script_path, ctx=ctx)
    absolute = {
        path: relative.Absolute(
            part.request.x, part.request.y, part.request.rotation, part.request.side, part.request.locked
        )
        for path, part in sorted(design.parts.items())
        if part.request is not None
    }
    box = outline_box(model)
    board_box = BBox(*box) if box is not None else None
    staging = Point(box[2] + STAGING_OFFSET, box[1]) if box is not None else None
    reuse_positions = _reuse_placements(layouts, boards)
    for path, file in files.items():
        if file.application.status not in ("stale", "refused"):
            reuse_positions[path] = {
                name: relative.Placed(part.at, part.rotation, part.side)
                for name, part in file.application.parts.items()
            }
    scene = relative.Scene(
        footprints=MappingProxyType({path: measure(defn) for path, defn in defs.items()}),
        frames=MappingProxyType({key: items.items for key, items in dsl_relative.frames(design).items()}),
        absolute=MappingProxyType(absolute),
        relative=relatives,
        turns=dsl_relative.turns(design),
        blocks=layouts,
        origin=BOARD_ORIGIN,
        top=dsl_relative.top_layout(design),
        board=board_box,
        staging=staging,
        reuse=MappingProxyType(reuse_positions),
    )
    code = relative.resolve(scene)
    by_lib: dict[str, FootprintDef] = {}
    components = {_component_path(c): c for c in model.circuit.components}
    for path, defn in defs.items():
        component = components.get(path)
        if component is not None and component.lib_footprint_ref:
            by_lib.setdefault(component.lib_footprint_ref, defn)
    sources: dict[str, object] = {}
    for path in layouts:
        made = design.modules[path]
        if not isinstance(made, Block) or not made.definition.version:
            continue
        if made.definition.name.startswith("Fenolite:"):
            continue  # shipped package blocks always require an explicit capture output
        root = dsl_relative.block_root(made)
        if root is not None and any(part in ("site-packages", "dist-packages") for part in Path(root).parts):
            continue
        try:
            folder = Path(root).relative_to(ctx.cwd.resolve()).as_posix() if root else None
        except ValueError:
            folder = None
        if folder is not None:
            sources[path] = {"folder": folder, "name": made.definition.function.__name__}
    plan = LayoutPlan(scene, requested, code, boards, by_lib, files=files, sources=sources)
    plan.issues += [issue for file in files.values() for issue in file.application.issues]
    plan.issues += code_issues(plan, defs)
    return plan


def code_issues(plan: LayoutPlan, footprints: Mapping[str, FootprintDef]) -> list[Issue]:
    """The issues of the reuses: a block-local part that the reference board lacks (``reuse.unknown-part``,
    a warning here: the rest of the block is placed) and the pad check."""
    issues: list[Issue] = []
    for block, local in plan.code.missing:
        issues.append(
            Issue(
                "reuse.unknown-part",
                "warning",
                f"the reference board of block {block} has no part {local}; {block}/{local} is staged",
                where=f"{block}/{local}",
                hint="lay the part out in the reference board, or place it with place()",
            )
        )
    issues += _check_pads(plan, footprints, plan.code)
    return issues


def reuse_copper(plan: LayoutPlan, design: DslDesign, model: Design) -> tuple[Design, list[Issue], int]:
    """The model with the copper of every block reuse of ``copper=True`` copied onto the block's pose, its
    nets mapped by port (``dsl.relative.port_nets``), each copy locked and marked as script copper so a
    rebuild regenerates it; a reference net that is neither a port nor a local net is
    ``reuse.port-unmapped`` (error). Also the number of copied items."""
    issues: list[Issue] = []
    items: list[Track | Arc | Via | Zone] = []
    names = {net.name: net.id for net in model.circuit.nets}
    for block, board in sorted(plan.reuse.items()):
        if not board.copper:
            continue
        world = plan.code.worlds.get(block)
        if world is None:
            continue
        ports = dsl_relative.port_nets(design, block)
        net_map: dict[str, str] = {}
        for net in board.design.circuit.nets:
            name = net.name
            if board.prefix and name.startswith(board.prefix):
                name = name[len(board.prefix) :]
            target = ports.get(name)
            if target is None or target not in names:
                used = any(
                    item.net_id == net.id
                    for item in (
                        *(board.design.board.tracks if board.design.board else ()),
                        *(board.design.board.arcs if board.design.board else ()),
                        *(board.design.board.vias if board.design.board else ()),
                        *(board.design.board.zones if board.design.board else ()),
                    )
                )
                if used:
                    issues.append(
                        reuse_codes.issue(
                            "reuse.port-unmapped",
                            f"net {net.name} of the reference board of block {block} is neither a port nor a "
                            "local net of the block; its copper cannot be mapped",
                            where=net.name,
                            hint="name the net after a port or a local net of the block, or reuse without "
                            "copper=True",
                        )
                    )
                continue
            net_map[net.id] = names[target]
        held = board.design.board
        assert held is not None
        target_layers = dataclasses.replace(held, layers=created_layers(design.copper))
        layers = layer_map(held, target_layers, flipped=world.mirror)
        transform = world.compose(Transform.translation(-board.origin.x, -board.origin.y))
        copied = copy_block(board.design, transform, net_map, layers, key=f"reuse:{block}")
        for found in copied.items:
            items.append(_locked(found, block))
    if any(found.severity == "error" for found in issues):
        return model, issues, 0
    return with_copper(model, items), issues, len(items)


def copy_merge(
    out: Path,
    plan: LayoutPlan | None,
    design: DslDesign,
    model: Design,
    existing: Design | None,
    *,
    discard: bool,
) -> CopyMerge | None:
    assets = {
        path: file.sha256
        for path, file in (plan.files.items() if plan is not None else ())
        if file.copper and file.application.status not in ("stale", "refused", "nets-differ")
    }
    if not assets and not (out / COPPER_BASE_FILE).exists():
        return None
    if model.board is None:
        return None
    shaped = dataclasses.replace(
        model, board=dataclasses.replace(model.board, layers=created_layers(design.copper))
    )
    return CopyMerge(out, shaped, existing, plan.code.worlds if plan is not None else {}, assets, discard)


def layout_file_copper(
    plan: LayoutPlan | None,
    design: DslDesign,
    model: Design,
    placements: Mapping[str, PlacementLike],
    merge: CopyMerge | None = None,
    definitions: Mapping[str, FootprintDef] | None = None,
) -> tuple[Design, list[Issue], int]:
    """Copy after the per-property merge, so pad contacts use each winning placement."""
    issues: list[Issue] = []
    items: list[Track | Arc | Via | Zone] = []
    layout_model = (
        dataclasses.replace(
            model, board=dataclasses.replace(model.board, layers=created_layers(design.copper))
        )
        if model.board is not None
        else model
    )
    defs = plan.definitions if plan is not None else (definitions or {})
    for block, file in sorted(plan.files.items() if plan is not None else ()):
        assert plan is not None
        if not file.copper or file.application.status in ("stale", "refused", "nets-differ"):
            continue
        world = plan.code.worlds.get(block)
        if world is None:
            continue
        copied, findings = _blocklayouts.layout_copper(
            file, layout_model, block, world, defs, placements, merge
        )
        items.extend(copied)
        issues.extend(findings)
    if merge is not None:
        for block in merge.remaining():
            copied = merge.merge(block, None, CopperCopy())
            contacts = {
                source: pads
                for key, pads in merge.contacts.items()
                for owner, separator, source in (key.partition(":"),)
                if separator and owner == block
            }
            kept, found = _blocklayouts.settle_copy(copied, layout_model, block, defs, placements, contacts)
            items.extend(kept)
            issues.extend(found)
        merge.complete_choices()
        issues.extend(merge.issues)
        issues.extend(
            reuse_codes.issue(
                "reuse.layout-changed", f"{block}: changed asset keeps CAD-edited copper", where=block
            )
            for block in sorted(merge.changed_kept)
        )
    if any(found.severity == "error" for found in issues):
        return model, issues, 0
    return with_copper(model, items), issues, len(items)


def _locked(found: CopiedItem, block: str) -> Track | Arc | Via | Zone:
    item = found.item
    native = {"kicad": copper_uuid(f"reuse:{block}", found.source)}
    return dataclasses.replace(item, native_ids=native, locked=True)  # type: ignore[return-value]


__all__ = [
    "CACHE_DIR",
    "LAYOUT_KEY",
    "LayoutPlan",
    "ReuseBoard",
    "footprint_definitions",
    "measure",
    "plan_layout",
    "read_layout_record",
    "reuse_copper",
]
