# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native custom anchor contacts on wholly authored CC0 pads (c0340)."""

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
from fenolite.backends.kicad.derived_teardrops import _parents, native_net
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse

pytestmark = pytest.mark.needs_kicad


def _number(value: Fraction) -> str:
    nm = value * 1_000_000
    assert nm.denominator == 1
    return Atom.from_nm(nm.numerator).text


@pytest.mark.parametrize("anchor", ("rect", "circle"))
def test_explicit_custom_anchor_has_copper_outside_its_contained_primitive(
    tmp_path: Path, anchor: str
) -> None:
    version = _kicad.supported_version()
    if not version.startswith("10."):
        pytest.skip("native10 anchor control; native9 does not supply this cache regeneration feature")
    native = KicadCli(Path(_kicad.cli()))
    receipts = {}
    for mode, inside in (("ordinary", True), ("custom", True), ("custom-outside", False)):
        project = curve_project(tmp_path / mode, 10, 10_000)
        path = project / "font_probe.kicad_pcb"
        root = parse(path.read_text())
        parents = _parents(root)
        parent = parents[0]
        footprint = root.nodes("footprint")[0]
        target = footprint.nodes("pad")[0]
        other_net = "FENOLITE_ANCHOR_OTHER"
        assert native_net(target, root) != other_net
        children = tuple(
            Atom.symbol(anchor if mode == "ordinary" else "custom") if index == 2 else child
            for index, child in enumerate(target.children)
        )
        if mode != "ordinary":
            children += (
                parse(f"(options (clearance outline) (anchor {anchor}))"),
                parse("(primitives (gr_circle (center 0 0) (end 0.1 0) (width 0) (fill yes)))"),
            )
        changed = target.with_children(children)
        second = footprint.nodes("pad")[1]
        other_pad = second.with_children(
            tuple(child for child in second.children if not isinstance(child, Node) or child.name != "net")
            + (parse(f'(net "{other_net}")'),)
        )
        fp = footprint.with_children(
            tuple(
                changed if child is target else other_pad if child is second else child
                for child in footprint.children
            )
        )
        x, y = parent.center
        # This point is strictly inside the nominal anchor and outside the added radius0.1 primitive.
        x += Fraction(2, 5) if inside else Fraction(0)
        y += Fraction(0) if inside else Fraction(2)
        probe = parse(
            f"(segment (start {_number(parents[1].center[0])} {_number(parents[1].center[1])}) "
            f"(end {_number(x)} {_number(y)}) "
            f'(width 0.2) (layer "F.Cu") (net "{other_net}") '
            '(uuid "00000000-0000-4000-8000-000000009605"))'
        )
        kept = tuple(
            fp if child is footprint else child
            for child in root.children
            if not isinstance(child, Node) or child.name not in {"segment", "arc", "via", "zone"}
        )
        path.write_text(dumps(root.with_children((*kept, probe))))
        before = snapshot(project)
        run = native.run(
            ["pcb", "drc", "--format", "json", "--severity-all", "-o", "anchor.json", path.name],
            files={p.name: p for p in project.iterdir() if p.is_file()},
        )
        assert run.ok, (run.stdout, run.stderr)
        report = json.loads(run.outputs["anchor.json"])
        contacts = [v for v in report["violations"] if v["type"] == "shorting_items"]
        assert bool(contacts) is inside, (mode, report["violations"])
        assert snapshot(project) == before
        receipts[mode] = {
            "version": version,
            "exit": run.returncode,
            "shorting_items": len(contacts),
            "input_sha256": before,
            "native_report_sha256": hashlib.sha256(run.outputs["anchor.json"]).hexdigest(),
        }
    assert receipts["ordinary"]["shorting_items"] == receipts["custom"]["shorting_items"]
    (tmp_path / "custom-anchor-receipt.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n"
    )
