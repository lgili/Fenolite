# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native contact controls for turned and custom teardrop parents on authored CC0 pads (c0413).

Each case writes one target pad, a far pad of another net and a probe track of that net from the far
pad to a chosen point. KiCad's DRC reports `shorting_items` exactly when the probe meets the target's
copper. Every case asserts that native report and the contact `derived_teardrops._parents` predicts for
the same point.
"""

from __future__ import annotations

import hashlib
import json
from fractions import Fraction
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project
from _fidelity import snapshot

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.derived_teardrops import _parents
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.core.trig import ONE, cos_sin_fixed

pytestmark = pytest.mark.needs_kicad

OTHER = "FENOLITE_PARENT_OTHER"
LINE = "(primitives (gr_line (start 0 0) (end 3 0) (width 1)))"
HULL = "(options (clearance convexhull) (anchor rect))"
# name: (footprint angle, pad angle, shape, size, extra pad children, local point, contact expected)
CASES = {
    # A 4 x 0.4 rectangle at 30°: inside the turned body but outside the unturned one, and the reverse.
    "rect-30-turned": (30, 30, "rect", "4 0.4", "", (Fraction(3, 2), Fraction(1, 2000)), True),
    "rect-30-unturned": (30, 30, "rect", "4 0.4", "", (Fraction(13, 10), Fraction(3, 4)), False),
    # A custom pad's line primitive turns with the pad and has round caps of half its width.
    "line-90-cap": (90, 90, "custom", "0.5 0.5", LINE, (Fraction(33, 10), Fraction(3, 10)), True),
    "line-90-past-cap": (90, 90, "custom", "0.5 0.5", LINE, (Fraction(36, 10), Fraction(3, 10)), False),
    "line-30-cap": (30, 30, "custom", "0.5 0.5", LINE, (Fraction(33, 10), Fraction(3, 10)), True),
    "line-30-past-cap": (30, 30, "custom", "0.5 0.5", LINE, (Fraction(36, 10), Fraction(3, 10)), False),
    # The anchor stays copper when the clearance outline is the convex hull.
    "hull-anchor": (0, 0, "custom", "1 1", "", (Fraction(1, 5), Fraction(1, 5)), True),
    "hull-outside": (0, 0, "custom", "1 1", "", (Fraction(9, 10), Fraction(0)), False),
}


def _mm(value: Fraction) -> str:
    """Whole nanometres, rounded half-even; the case points keep >= 0.1 mm from every edge."""
    return Atom.from_nm(round(value * 1_000_000)).text


def _board_point(origin: tuple[Fraction, Fraction], degrees: int, local: tuple[Fraction, Fraction]):
    c, s = (Fraction(v, ONE) for v in cos_sin_fixed(degrees * 1_000_000))
    x, y = local
    return origin[0] + x * c + y * s, origin[1] - x * s + y * c


def _case(root: Node, name: str) -> tuple[Node, tuple[Fraction, Fraction]]:
    angle, pad_angle, shape, size, extra, local, _ = CASES[name]
    footprint = root.nodes("footprint")[0]
    at = footprint.find("at")
    assert at is not None
    origin = (Fraction(at.atoms()[0].text), Fraction(at.atoms()[1].text))
    target, far = footprint.nodes("pad")[:2]
    options = HULL if name.startswith("hull") else "(options (clearance outline) (anchor circle))"

    # A target-9 board declares nets by number; a target-10 board names them on each item.
    numbered = bool(root.nodes("net"))
    pad_net = f'(net 2 "{OTHER}")' if numbered else f'(net "{OTHER}")'
    track_net = "(net 2)" if numbered else f'(net "{OTHER}")'

    def pad(node: Node, offset: str, body: str, kind: str, net: str | None) -> Node:
        dropped = {"at", "size", "roundrect_rratio", *(("net",) if net else ())}
        kept = tuple(
            Atom.symbol(kind) if index == 2 else child
            for index, child in enumerate(node.children)
            if not isinstance(child, Node) or child.name not in dropped
        )
        added = (parse(f"(at {offset})"), parse(f"(size {body})"), *((parse(net),) if net else ()))
        if kind == "custom":
            added += (parse(options), *((parse(extra),) if extra else ()))
        return node.with_children((*kept, *added))

    changed = footprint.with_children(
        tuple(
            parse(f"(at {at.atoms()[0].text} {at.atoms()[1].text} {angle})")
            if child is at
            else pad(target, f"0 0 {pad_angle}", size, shape, None)
            if child is target
            else pad(far, f"0 8 {angle}", "1 1", "circle", pad_net)
            if child is far
            else child
            for child in footprint.children
        )
    )
    x, y = _board_point(origin, pad_angle, local)
    # The probe runs from the far pad: a track touching only the target would take the target's net
    # when KiCad loads the board, as a via does (H-K-VIA-RENET). Each path meets the target only at its end.
    fx, fy = _board_point(origin, angle, (Fraction(0), Fraction(8)))
    probe = parse(
        f"(segment (start {_mm(fx)} {_mm(fy)}) (end {_mm(x)} {_mm(y)}) "
        f'(width 0.1) (layer "F.Cu") {track_net} (uuid "00000000-0000-4000-8000-000000041300"))'
    )
    nets = root.nodes("net")
    kept: list[Node | Atom] = []
    for child in root.children:
        if isinstance(child, Node) and child.name in {"segment", "arc", "via", "zone"}:
            continue
        kept.append(changed if child is footprint else child)
        if numbered and child is nets[-1]:
            kept.append(parse(f'(net 2 "{OTHER}")'))
    point = (Fraction(round(x * 1_000_000), 1_000_000), Fraction(round(y * 1_000_000), 1_000_000))
    return root.with_children((*kept, probe)), point


@pytest.mark.parametrize("name", sorted(CASES))
def test_turned_and_custom_parent_contact_matches_native_drc(tmp_path: Path, name: str) -> None:
    version = _kicad.supported_version()
    native = KicadCli(Path(_kicad.cli()))
    project = curve_project(tmp_path / name, int(version.split(".")[0]), 10_000)
    path = project / "font_probe.kicad_pcb"
    board, point = _case(parse(path.read_text()), name)
    path.write_text(dumps(board))
    expected = CASES[name][-1]
    [parent] = [p for p in _parents(parse(path.read_text())) if p.net != OTHER]
    assert parent.contains(point) is expected, name
    before = snapshot(project)
    run = native.run(
        ["pcb", "drc", "--format", "json", "--severity-all", "-o", "parent.json", path.name],
        files={p.name: p for p in project.iterdir() if p.is_file()},
    )
    assert run.ok, (run.stdout, run.stderr)
    report = json.loads(run.outputs["parent.json"])
    contacts = [v for v in report["violations"] if v["type"] == "shorting_items"]
    assert bool(contacts) is expected, (name, version, report["violations"])
    assert snapshot(project) == before
    receipt = {
        "case": name,
        "version": version,
        "exit": run.returncode,
        "shorting_items": len(contacts),
        "input_sha256": before,
        "native_report_sha256": hashlib.sha256(run.outputs["parent.json"]).hexdigest(),
    }
    (tmp_path / "parent-receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
