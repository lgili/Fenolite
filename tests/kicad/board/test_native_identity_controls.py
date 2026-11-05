# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 native identity controls for derived teardrop fills (c0384 1.1); no runtime rewrite."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project
from _native_identity_pairing import apply_identities, pair_identities

from fenolite.backends.kicad import derived_teardrops as dt
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_bytes

pytestmark = pytest.mark.needs_kicad

HALF = 0.4  # two 0.5 mm circular pads 0.3 mm apart, on two nets
CENTER = (115.0, 110.0)


def _close_pads(root: Node) -> Node:
    def pad(node: Node) -> Node:
        number = node.atoms()[0].value
        children = []
        for child in node.children:
            if isinstance(child, Node) and child.name == "at":
                child = parse(f"(at {-HALF if number == '1' else HALF} 0)")
            elif isinstance(child, Node) and child.name == "size":
                child = parse("(size 0.5 0.5)")
            elif isinstance(child, Node) and child.name == "net" and number == "2":
                child = parse('(net 2 "SECOND")')
            children.append(child)
        return node.with_children(tuple(children))

    body = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "segment":
            continue
        if isinstance(child, Node) and child.name == "footprint":
            child = child.with_children(
                tuple(pad(c) if isinstance(c, Node) and c.name == "pad" else c for c in child.children)
            )
        body.append(child)
        if isinstance(child, Node) and child.name == "net" and child.atoms()[0].value == "1":
            body.append(parse('(net 2 "SECOND")'))
    return root.with_children(tuple(body))


def _tracks(order, ids) -> tuple[Node, ...]:
    x, y = CENTER
    ends = (
        ((x - HALF, y), (x - HALF - 0.3, y - 1.5), 1),
        ((x + HALF, y), (x + HALF + 0.3, y - 1.5), 2),
        ((x - HALF, y), (x - HALF - 0.3, y + 1.5), 1),
        ((x + HALF, y), (x + HALF + 0.3, y + 1.5), 2),
    )
    return tuple(
        parse(
            f"(segment (start {ends[i][0][0]} {ends[i][0][1]}) (end {ends[i][1][0]} {ends[i][1][1]}) "
            f'(width 0.2) (layer "F.Cu") (net {ends[i][2]}) (uuid "{ids[i]}"))'
        )
        for i in order
    )


def _swap_pad_ids(root: Node) -> Node:
    fp = root.nodes("footprint")[0]
    pads = fp.nodes("pad")
    ids = [p.nodes("uuid")[0] for p in pads]

    def swapped(p: Node, new: Node) -> Node:
        return p.with_children(
            tuple(new if isinstance(c, Node) and c.name == "uuid" else c for c in p.children)
        )

    table = {id(pads[0]): swapped(pads[0], ids[1]), id(pads[1]): swapped(pads[1], ids[0])}
    changed = fp.with_children(tuple(table.get(id(c), c) for c in fp.children))
    return root.with_children(tuple(changed if c is fp else c for c in root.children))


def test_track_and_pad_identities_change_derived_fills_and_pairing_restores_them(tmp_path: Path) -> None:
    if not _kicad.supported_version().startswith("10."):
        pytest.skip("actual native10 refill control only")
    source = curve_project(tmp_path / "source", 9, 10_000)
    base = _close_pads(parse_bytes((source / "font_probe.kicad_pcb").read_bytes()))
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"Fenolite c0384 1.1 close {i}")) for i in range(4)]
    swapped_ids = [ids[1], ids[0], ids[3], ids[2]]
    baseline = base.with_children((*base.children, *_tracks(range(4), ids)))
    track_ids = base.with_children((*base.children, *_tracks(range(4), swapped_ids)))
    pad_ids = _swap_pad_ids(baseline)
    order = base.with_children((*base.children, *_tracks(range(3, -1, -1), ids)))
    paired = apply_identities(track_ids, pair_identities(baseline, track_ids))
    paired_pads = apply_identities(pad_ids, pair_identities(baseline, pad_ids))
    assert paired == baseline and paired_pads == baseline
    project = json.loads((source / "font_probe.kicad_pro").read_text())
    for netclass in project["net_settings"]["classes"]:
        netclass["clearance"] = 0.25  # wider than the 0.3 mm pad gap minus the teardrop growth
    files = {"font_probe.kicad_pro": (json.dumps(project, indent=2) + "\n").encode()}
    native = KicadCli(Path(_kicad.cli()))
    observed: dict[str, tuple[str, str, int]] = {}
    cases = (
        ("baseline", baseline),
        ("baseline-repeat", baseline),
        ("track-uuids-swapped", track_ids),
        ("pad-uuids-swapped", pad_ids),
        ("track-order-reversed", order),
        ("track-uuids-paired", paired),
    )
    for label, root in cases:
        folder = tmp_path / label
        folder.mkdir()
        board = folder / "font_probe.kicad_pcb"
        board.write_bytes(dumps(root).encode())
        run = native.refill(board, files=files)
        assert run.run.ok and run.board is not None
        saved = parse_bytes(run.board)
        zones = [z for z in saved.nodes("zone") if dt._derived(z)]
        outlines = sorted(repr(dt._tree(z.nodes("polygon")[0])) for z in zones)
        fills = sorted(
            repr((dt.native_net(z, saved), tuple(dt._tree(f) for f in z.nodes("filled_polygon"))))
            for z in zones
        )
        observed[label] = (
            hashlib.sha256(repr(outlines).encode()).hexdigest(),
            hashlib.sha256(repr(fills).encode()).hexdigest(),
            len(zones),
        )
    outline = {value[0] for value in observed.values()}
    assert len(outline) == 1 and observed["baseline"][2] == 4  # identities never move an outline here
    assert observed["baseline-repeat"] == observed["baseline"]  # one run per input is deterministic
    assert observed["track-uuids-swapped"][1] != observed["baseline"][1]  # UUID-only: fills differ
    assert observed["pad-uuids-swapped"][1] != observed["baseline"][1]
    assert observed["track-order-reversed"] == observed["baseline"]  # order-only: no effect in this geometry
    assert observed["track-uuids-paired"] == observed["baseline"]  # paired identities restore the fills
    (tmp_path / "native-identity-controls.json").write_text(
        json.dumps(
            {"native_version": _kicad.supported_version(), "cases": observed}, indent=2, sort_keys=True
        )
        + "\n"
    )


TEARDROPS = (
    "(teardrops (best_length_ratio 0.5) (max_length 1) (best_width_ratio 1) (max_width 2) (curved_edges no) "
    "(filter_ratio 0.9) (enabled yes) (allow_two_segments yes) (prefer_zone_connections no))"
)


def test_via_identities_change_derived_fills_and_pairing_restores_them(tmp_path: Path) -> None:
    if not _kicad.supported_version().startswith("10."):
        pytest.skip("actual native10 refill control only")
    source = curve_project(tmp_path / "source", 9, 10_000)
    root = parse_bytes((source / "font_probe.kicad_pcb").read_bytes())
    body = []
    for child in root.children:
        body.append(child)
        if isinstance(child, Node) and child.name == "net" and child.atoms()[0].value == "1":
            body.append(parse('(net 2 "SECOND")'))
    root = root.with_children(tuple(body))
    x, y, half = 122.0, 110.0, 0.375  # two 0.45 mm vias of two nets, 0.3 mm apart
    via_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"Fenolite c0384 via {i}")) for i in range(2)]
    track_ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"Fenolite c0384 via track {i}")) for i in range(4)]

    def board(ids: list[str]) -> Node:
        items = [
            f'(via (at {x - half} {y}) (size 0.45) (drill 0.2) (layers "F.Cu" "B.Cu") {TEARDROPS} '
            f'(net 1) (uuid "{ids[0]}"))',
            f'(via (at {x + half} {y}) (size 0.45) (drill 0.2) (layers "F.Cu" "B.Cu") {TEARDROPS} '
            f'(net 2) (uuid "{ids[1]}"))',
        ]
        for index, (sx, dx, dy, net) in enumerate(
            (
                (x - half, -0.3, -1.5, 1),
                (x + half, 0.3, -1.5, 2),
                (x - half, -0.3, 1.5, 1),
                (x + half, 0.3, 1.5, 2),
            )
        ):
            items.append(
                f'(segment (start {sx} {y}) (end {sx + dx} {y + dy}) (width 0.2) (layer "F.Cu") '
                f'(net {net}) (uuid "{track_ids[index]}"))'
            )
        return root.with_children((*root.children, *(parse(item) for item in items)))

    baseline, swapped = board(via_ids), board(via_ids[::-1])
    paired = apply_identities(swapped, pair_identities(baseline, swapped))
    assert paired == baseline
    project = json.loads((source / "font_probe.kicad_pro").read_text())
    for netclass in project["net_settings"]["classes"]:
        netclass["clearance"] = 0.25
    files = {"font_probe.kicad_pro": (json.dumps(project, indent=2) + "\n").encode()}
    native = KicadCli(Path(_kicad.cli()))
    observed = {}
    for label, case in (("baseline", baseline), ("via-uuids-swapped", swapped), ("via-uuids-paired", paired)):
        folder = tmp_path / label
        folder.mkdir()
        path = folder / "font_probe.kicad_pcb"
        path.write_bytes(dumps(case).encode())
        run = native.refill(path, files=files)
        assert run.run.ok and run.board is not None
        saved = parse_bytes(run.board)
        zones = [z for z in saved.nodes("zone") if dt._derived(z)]
        observed[label] = (
            sorted(repr(dt._tree(z.nodes("polygon")[0])) for z in zones),
            sorted(
                repr((dt.native_net(z, saved), tuple(dt._tree(f) for f in z.nodes("filled_polygon"))))
                for z in zones
            ),
        )
    assert observed["via-uuids-swapped"][0] == observed["baseline"][0]  # outlines equal
    assert observed["via-uuids-swapped"][1] != observed["baseline"][1]  # UUID-only: fills differ
    assert observed["via-uuids-paired"] == observed["baseline"]


PAD_IDS = (
    "10000000-0000-4000-8000-000000000001",  # pad 1, net 1
    "20000000-0000-4000-8000-000000000002",  # pad 2, net 2: sorts between the two identical pads
    "30000000-0000-4000-8000-000000000003",  # the stacked twin of pad 1, identical but for this field
)


def _stacked_twin(root: Node, ids: tuple[str, str, str]) -> Node:
    """Pad 1, pad 2 and an exact copy of pad 1 after them, with the three given pad identities."""
    fp = root.nodes("footprint")[0]
    pads = fp.nodes("pad")

    def with_id(pad: Node, value: str) -> Node:
        return pad.with_children(
            tuple(
                parse(f'(uuid "{value}")') if isinstance(c, Node) and c.name == "uuid" else c
                for c in pad.children
            )
        )

    first, second = with_id(pads[0], ids[0]), with_id(pads[1], ids[1])
    twin = with_id(pads[0], ids[2])
    body: list[Node | object] = []
    for child in fp.children:
        if child is pads[0]:
            body.append(first)
        elif child is pads[1]:
            body.extend((second, twin))
        else:
            body.append(child)
    changed = fp.with_children(tuple(body))  # type: ignore[arg-type]
    return root.with_children(tuple(changed if c is fp else c for c in root.children))


def test_fully_identical_pads_exchange_their_identities_without_changing_fills(tmp_path: Path) -> None:
    """c0384 2.1(c): the exchange of two fully identical pads is fill-neutral; a non-identical swap is not."""
    version = _kicad.supported_version()
    if not version.startswith("10."):
        # kicad-cli 9 has no `pcb drc --refill-zones`; the level-7 proof itself requires KiCad 10 (FEN-6002).
        pytest.skip("actual native10 refill control only")
    source = curve_project(tmp_path / "source", 9, 10_000)
    ids = [str(uuid.uuid5(uuid.NAMESPACE_URL, f"Fenolite c0384 1.1 close {i}")) for i in range(4)]
    base = _close_pads(parse_bytes((source / "font_probe.kicad_pcb").read_bytes()))
    base = base.with_children((*base.children, *_tracks(range(4), ids)))
    a, b, twin = PAD_IDS
    cases = (
        ("baseline", _stacked_twin(base, (a, b, twin))),
        ("baseline-repeat", _stacked_twin(base, (a, b, twin))),
        ("identical-pads-exchanged", _stacked_twin(base, (twin, b, a))),
        ("different-pads-exchanged", _stacked_twin(base, (b, a, twin))),  # positive control
    )
    first = cases[0][1].nodes("footprint")[0].nodes("pad")
    assert dumps(first[0]).replace(a, twin) == dumps(first[2])  # the twin differs only in its identity
    project = json.loads((source / "font_probe.kicad_pro").read_text())
    for netclass in project["net_settings"]["classes"]:
        netclass["clearance"] = 0.25
    files = {"font_probe.kicad_pro": (json.dumps(project, indent=2) + "\n").encode()}
    native = KicadCli(Path(_kicad.cli()))
    observed: dict[str, tuple[str, str, int]] = {}
    for label, root in cases:
        folder = tmp_path / label
        folder.mkdir()
        board = folder / "font_probe.kicad_pcb"
        board.write_bytes(dumps(root).encode())
        run = native.refill(board, files=files)
        assert run.run.ok and run.board is not None
        saved = parse_bytes(run.board)
        # Every zone's fill and outline in native file order, identities and priorities excluded: exact bytes.
        native_order = [
            dumps(
                z.with_children(
                    tuple(
                        c for c in z.children if not (isinstance(c, Node) and c.name in ("uuid", "priority"))
                    )
                ),
                style="compact",
            )
            for z in saved.nodes("zone")
        ]
        zones = [z for z in saved.nodes("zone") if dt._derived(z)]
        fills = sorted(
            repr((dt.native_net(z, saved), tuple(dt._tree(f) for f in z.nodes("filled_polygon"))))
            for z in zones
        )
        observed[label] = (
            hashlib.sha256("\n".join(native_order).encode()).hexdigest(),
            hashlib.sha256(repr(fills).encode()).hexdigest(),
            len(zones),
        )
    assert observed["baseline"][2] > 0
    assert observed["baseline-repeat"] == observed["baseline"]
    assert observed["different-pads-exchanged"][1] != observed["baseline"][1]  # identities matter here
    assert observed["identical-pads-exchanged"] == observed["baseline"]  # byte-identical zones and fills
    (tmp_path / "identical-pad-exchange.json").write_text(
        json.dumps(
            {"native_version": version, "pad_ids": PAD_IDS, "cases": observed}, indent=2, sort_keys=True
        )
        + "\n"
    )
