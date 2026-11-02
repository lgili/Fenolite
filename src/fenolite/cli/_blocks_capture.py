# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Capture one recorded block instance through the standard plan/confirm protocol (c0271)."""

from __future__ import annotations

import argparse
import dataclasses
import difflib
import json
import os
from pathlib import Path
from typing import Any, cast

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.outline import outline_box
from fenolite.backends.kicad.projectset import resolve_board
from fenolite.cli import _blocklayouts, _layout, place_group
from fenolite.cli._boardview import load_board
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.errors import CliError
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl.convert import BOARD_ORIGIN
from fenolite.geometry.transform import Transform
from fenolite.model import canonical
from fenolite.model.design import Design
from fenolite.reuse.blocklayout import (
    capture_block_layout,
    component_path,
    instance_parts,
    write_block_layout,
)
from fenolite.reuse.fit import Layout, fit_block
from fenolite.tidy.graph import groups, net_pieces

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-BLOCK-LAYOUT",))


def register_capture(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--instance", metavar="PATH", help="capture: block instance path in the built board")
    parser.add_argument(
        "-o", dest="capture_output", metavar="FILE", help="capture: write the block layout here"
    )
    parser.add_argument(
        "--origin",
        choices=("pose", "anchor"),
        help="capture frame; default recorded nonidentity pose, else anchor",
    )
    parser.add_argument("--anchor", metavar="LOCAL", help="capture: local part path used by --origin anchor")
    parser.add_argument(
        "--copper",
        dest="capture_copper",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="capture: include copper joined only to the block's pads (default yes)",
    )


def current_model(cached: Design, actual: Design) -> Design:
    """Keep recorded hierarchy and circuit ids, using geometry read from the user's current board."""
    board = actual.board
    assert board is not None
    names = {component.id: component_path(component) for component in actual.circuit.components}
    components = {component_path(c): c.id for c in cached.circuit.components}
    net_names = {net.id: net.name for net in actual.circuit.nets}
    nets = {net.name: net.id for net in cached.circuit.nets}
    nets.update({net.name: net.id for net in actual.circuit.nets if net.name not in nets})
    extra = tuple(c for c in actual.circuit.components if component_path(c) not in components)
    component_ids = {c.id: components.get(component_path(c), c.id) for c in actual.circuit.components}
    components.update({component_path(c): c.id for c in extra})

    def net_id(ident: str | None) -> str | None:
        return nets.get(net_names.get(ident or "", ""))

    footprints = tuple(
        dataclasses.replace(
            fp,
            component_id=components[names[fp.component_id]],
            pads=tuple(dataclasses.replace(pad, net_id=net_id(pad.net_id)) for pad in fp.pads),
        )
        for fp in board.footprints
        if names.get(fp.component_id) in components
    )
    extra_ids = {c.id for c in extra}
    actual_nets = {net.name: net for net in actual.circuit.nets}
    circuit = dataclasses.replace(
        cached.circuit,
        components=(*cached.circuit.components, *extra),
        nets=tuple(
            dataclasses.replace(
                net,
                members=(
                    *net.members,
                    *(
                        dataclasses.replace(member, component_id=component_ids[member.component_id])
                        for member in actual_nets.get(net.name, net).members
                        if member.component_id in extra_ids
                    ),
                ),
            )
            for net in cached.circuit.nets
        )
        + tuple(net for net in actual.circuit.nets if net.name not in {n.name for n in cached.circuit.nets}),
    )
    return dataclasses.replace(
        cached,
        circuit=circuit,
        board=dataclasses.replace(
            board,
            footprints=footprints,
            tracks=tuple(dataclasses.replace(i, net_id=net_id(i.net_id)) for i in board.tracks),
            arcs=tuple(dataclasses.replace(i, net_id=net_id(i.net_id)) for i in board.arcs),
            vias=tuple(dataclasses.replace(i, net_id=net_id(i.net_id)) for i in board.vias),
            zones=tuple(dataclasses.replace(i, net_id=net_id(i.net_id)) for i in board.zones),
        ),
    )


def copper_left(model: Design, pads: tuple[BoardPad, ...], members: set[str]) -> set[str]:
    """Names of joined copper groups containing both inside and outside pads."""
    shaped = net_pieces(model, pads)
    owners = {pad.pad_id: pad.footprint_id for pad in pads}
    left: set[str] = set()
    for net, held in shaped.pieces.items():
        for fills in (False, True):
            pieces = tuple(piece for piece in held if fills or piece.kind != "fill")
            roots = groups(pieces)
            joined: dict[int, set[str]] = {}
            for piece in pieces:
                if piece.kind == "pad":
                    joined.setdefault(roots[piece.ident], set()).add(owners[piece.ident])
            for piece in pieces:
                owners_here = joined.get(roots[piece.ident], set())
                if (
                    piece.kind in ("track", "arc", "via", "fill")
                    and owners_here & members
                    and owners_here - members
                ):
                    left.add(net)
    return {net.name for net in model.circuit.nets if net.id in left}


def _pose(record: dict[str, Any], instance: str) -> Transform:
    raw_layout: object = record.get("layout", {})
    if not isinstance(raw_layout, dict):
        raise CliError("FEN-3004", "build.json has no valid layout table", where="build.json")
    layout = cast(dict[str, Any], raw_layout)
    raw_poses: object = layout.get("poses", {})
    if not isinstance(raw_poses, dict):
        raise CliError("FEN-3004", "build.json has no valid pose table", where="build.json")
    raw_numbers: object = cast(dict[str, Any], raw_poses).get(instance, [0, 0, 0])
    if not isinstance(raw_numbers, list):
        raise CliError("FEN-3004", f"build.json has an invalid pose for {instance}", where="build.json")
    numbers = cast(list[Any], raw_numbers)
    if (
        len(numbers) not in (3, 4)
        or any(type(n) is not int for n in numbers[:3])
        or (len(numbers) == 4 and numbers[3] not in ("top", "bottom"))
    ):
        raise CliError("FEN-3004", f"build.json has an invalid pose for {instance}", where="build.json")
    return Transform.placement(
        Point(numbers[0], numbers[1]), numbers[2], len(numbers) > 3 and numbers[3] == "bottom"
    )


def run_capture(args: argparse.Namespace, ctx: Context) -> Result:
    if len(args.target) != 1 or not args.instance:
        raise CliError(
            "FEN-2001",
            "blocks capture takes BOARD and --instance PATH",
            hint="fenolite blocks capture out --instance dut -o layouts/divider.toml --dry-run",
        )
    if args.files or args.category or args.out:
        raise CliError("FEN-2001", "blocks capture takes no --from, --category or --out; use -o FILE")
    copper = args.capture_copper is not False
    given = Path(args.target[0])
    full = given if given.is_absolute() else ctx.cwd / given
    board_path = resolve_board(full)
    out = board_path.parent
    cache = out / ".fenolite"
    if not (cache / "circuit.json").is_file():
        raise CliError(
            "FEN-2001", "capture needs a built output folder with .fenolite/circuit.json", where=str(given)
        )
    cached = canonical.load_dir(cache)
    instances = {m.path: m for m in cached.circuit.modules if m.block_version}
    instance = str(args.instance)
    if instance not in instances:
        closest = difflib.get_close_matches(instance, sorted(instances), n=4, cutoff=0.0)
        raise CliError(
            "FEN-2001",
            f"{instance} is no recorded block instance",
            where=instance,
            hint="closest instances: " + ", ".join(closest),
        )
    view = load_board(str(board_path), ctx)
    model = current_model(cached, view.design)
    record_path = cache / "build.json"
    try:
        raw_record: object = json.loads(record_path.read_text(encoding="utf-8"))
        if not isinstance(raw_record, dict):
            raise ValueError("expected a build record object")
    except (OSError, ValueError) as error:
        raise CliError("FEN-3004", f"cannot read build record: {error}", where=record_path.name) from error
    record = cast(dict[str, Any], raw_record)
    held_pose = _layout.read_layout_record(out).get(instance)
    pose = (
        Transform.placement(
            Point(held_pose[0], held_pose[1]), held_pose[2], len(held_pose) == 4 and held_pose[3] == "bottom"
        )
        if held_pose is not None
        else _pose(record, instance)
    )
    identities = (Transform(), Transform.translation(BOARD_ORIGIN.x, BOARD_ORIGIN.y))
    origin = args.origin or ("pose" if pose not in identities else "anchor")
    if args.anchor and origin != "anchor":
        raise CliError("FEN-2001", "--anchor belongs to --origin anchor", where="--anchor")
    source_raw: object = record.get("layout", {}).get("sources", {}).get(instance)
    if source_raw is not None and not isinstance(source_raw, dict):
        raise CliError("FEN-3004", "build.json has an invalid block source", where="build.json")
    source = cast(dict[str, Any] | None, source_raw)
    target = args.capture_output
    if target is None:
        if not source:
            raise CliError("FEN-2001", "a block outside the working directory needs -o FILE", where="-o")
        folder = Path(source["folder"])
        target = (folder / "layouts" / f"{source['name']}.toml").as_posix()
    output = Path(target)
    if output.is_absolute():
        try:
            output = output.resolve().relative_to(ctx.cwd.resolve())
        except ValueError as error:
            raise CliError("FEN-2001", "-o must be under the working directory", where="-o") from error
    if ".." in output.parts:
        raise CliError("FEN-2001", "-o must be under the working directory", where="-o")
    backend = KicadBackend()
    pads = backend.board_pads(model)
    components = instance_parts(model, instance)
    held = {c.id for c in components.values()}
    assert model.board is not None
    members = {fp.id for fp in model.board.footprints if fp.component_id in held}
    box = outline_box(model)
    unplaced = [
        f"{instance}/{name}"
        for name, c in components.items()
        for fp in model.board.footprints
        if fp.component_id == c.id
        and box is not None
        and not (box[0] <= fp.position.x <= box[2] and box[1] <= fp.position.y <= box[3])
    ]
    if unplaced:
        return Result(
            result={"capture": {"instance": instance}},
            issues=(
                Issue(
                    "blocks.capture-unplaced",
                    "error",
                    f"parts outside the board: {', '.join(unplaced)}",
                    where=", ".join(unplaced),
                ),
            ),
            evidence=EVIDENCE,
        )
    selected: frozenset[str] = place_group.moving_copper(model, pads, members) if copper else frozenset()
    try:
        capture = capture_block_layout(
            model,
            instance,
            pose=pose,
            origin=origin,
            anchor=args.anchor,
            pads=pads,
            selected=selected,
            copper=copper,
        )
    except ValueError as error:
        raise CliError("FEN-2001", str(error), where="--anchor") from error
    issues = list(capture.issues)
    if capture.layout is None:
        return Result(result={"capture": {"instance": instance}}, issues=tuple(issues), evidence=EVIDENCE)
    left = sorted(copper_left(model, pads, members)) if copper else []
    issues += [
        Issue(
            "blocks.capture-copper-left",
            "info",
            f"{instance}: copper on {name} joins outside pads and stayed out",
            where=name,
        )
        for name in left
    ]
    if origin == "anchor":
        name = args.anchor or min(components)
        fp = next(fp for fp in model.board.footprints if fp.component_id == components[name].id)
        pose = Transform.translation(fp.position.x, fp.position.y)
    definitions_by_path = _layout.footprint_definitions(model, {}, script_path=board_path, ctx=ctx)
    definitions = {
        c.footprint_definition_ref or c.lib_footprint_ref: definitions_by_path[component_path(c)]
        for c in model.circuit.components
        if component_path(c) in definitions_by_path
    }
    from fenolite.reuse.blocklayout import apply_block_layout

    applied = apply_block_layout(capture.layout, model, instance, pose)
    placements = {f"{instance}/{name}": p for name, p in applied.parts.items()}
    virtual = _blocklayouts.placed_model(model, definitions, placements)
    refs = [c.ref for c in components.values()]
    fit = fit_block(
        Layout(model, pads),
        Layout(virtual, backend.board_pads(virtual)),
        refs,
        tolerance=1_000,
        transform=Transform(),
    )
    failed = len(fit.placed) != len(refs) or any(
        part.placement is None
        or part.placement.side != part.before.side
        or part.placement.rotation != part.before.rotation
        or abs(part.placement.at.x - part.before.at.x) > 1_000
        or abs(part.placement.at.y - part.before.at.y) > 1_000
        for part in fit.parts
    )
    if not failed and selected:
        bare = place_group.without(model, selected)
        file = _blocklayouts.LayoutFile(str(output), output, "", capture.layout, applied, True)
        items, drops = _blocklayouts.layout_copper(file, bare, instance, pose, definitions, placements)
        failed = bool(drops) or len(items) != len(capture.layout.copper)
    if failed:
        issues.append(
            Issue(
                "blocks.capture-check-failed",
                "error",
                f"{instance}: capture round trip did not keep every pad within 1000 nm and every copper item",
                where=instance,
            )
        )
    data = write_block_layout(capture.layout)
    hint_path = os.path.relpath(ctx.cwd / output, ctx.cwd / source["folder"]) if source else output.as_posix()
    result = {
        "instance": instance,
        "block": capture.layout.block,
        "version": capture.layout.block_version,
        "file": output.as_posix(),
        "parts": len(capture.layout.parts),
        "left": left,
        **{kind: len(getattr(capture.layout, kind)) for kind in ("tracks", "arcs", "vias", "zones")},
        "hint": f"add b.layout(reuse={Path(hint_path).as_posix()!r}, copper=True) to the block",
    }
    return Result(
        result={"capture": result},
        issues=tuple(issues),
        evidence=EVIDENCE,
        writes=() if failed else (PlannedWrite(output.as_posix(), data, "block-layout"),),
        depends=depends_on(
            ctx.cwd, board_path, record_path, *(cache / name for name in ("circuit.json", "board.json"))
        ),
    )
