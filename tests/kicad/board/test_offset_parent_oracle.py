# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native shifted copper body contacts on authored CC0 through-hole pads (c0340)."""

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
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse

pytestmark = pytest.mark.needs_kicad


def number(value: Fraction) -> str:
    nm = value * 1_000_000
    assert nm.denominator == 1
    return Atom.from_nm(nm.numerator).text


def turn(point: tuple[Fraction, Fraction], angle: int):
    x, y = point
    for _ in range(angle // 90):
        x, y = y, -x
    return x, y


@pytest.mark.parametrize("shape", ("rect", "roundrect"))
@pytest.mark.parametrize("angle", (0, 90, 180, 270))
@pytest.mark.parametrize("side", ("F.Cu", "B.Cu"))
def test_native_offset_moves_copper_in_raw_pad_frame_on_both_sides(
    tmp_path: Path, shape: str, angle: int, side: str
) -> None:
    version = _kicad.supported_version()
    if not version.startswith("10."):
        pytest.skip("native10 regeneration parent control; existing frame offsets cover native9")
    native = KicadCli(Path(_kicad.cli()))
    results = {}
    for shifted in (True, False):
        project = curve_project(tmp_path / str(shifted), 10, 10_000)
        path = project / "font_probe.kicad_pcb"
        root = parse(path.read_text())
        fp = root.nodes("footprint")[0]
        target = fp.nodes("pad")[0]
        at = fp.find("at")
        assert at is not None
        origin = (Fraction(at.atoms()[0].text), Fraction(at.atoms()[1].text))
        children = [
            Atom.symbol("thru_hole") if index == 1 else Atom.symbol(shape) if index == 2 else child
            for index, child in enumerate(target.children)
            if not isinstance(child, Node)
            or child.name not in {"at", "layers", "size", "drill", "roundrect_rratio"}
        ]
        children += [
            parse(f"(at 0 0 {angle})"),
            parse('(layers "*.Cu" "*.Mask")'),
            parse("(size 1 1)"),
            parse("(drill 0.3 (offset 1.2 0))"),
        ]
        if shape == "roundrect":
            children.append(parse("(roundrect_rratio 0.25)"))
        changed = target.with_children(children)
        moved_fp = fp.with_children(
            tuple(
                parse(f'(layer "{side}")') if isinstance(child, Node) and child.name == "layer" else child
                for child in fp.children
                if not isinstance(child, Node) or child.name != "pad"
            )
            + (changed,)
        )
        dx, dy = turn((Fraction(0), Fraction(4)), angle)
        other = (origin[0] + dx, origin[1] + dy)
        other_fp = parse(
            f'(footprint "AuthorialOther" (layer "F.Cu") (at {number(other[0])} {number(other[1])}) '
            '(uuid "00000000-0000-4000-8000-000000009606") '
            '(property "Reference" "R_OTHER" (at 0 0) (layer "F.SilkS") (effects (font (size 1 1)))) '
            '(pad "1" thru_hole circle (at 0 0) (size 1 1) (drill 0.3) (layers "*.Cu" "*.Mask") '
            '(net "FENOLITE_OFFSET_OTHER") (uuid "00000000-0000-4000-8000-000000009607")))'
        )
        delta = turn((Fraction(6, 5), Fraction(0)) if shifted else (Fraction(0), Fraction(2, 5)), angle)
        end = (origin[0] + delta[0], origin[1] + delta[1])
        probe = parse(
            f"(segment (start {number(other[0])} {number(other[1])}) (end {number(end[0])} {number(end[1])}) "
            '(width 0.2) (layer "F.Cu") (net "FENOLITE_OFFSET_OTHER") '
            '(uuid "00000000-0000-4000-8000-000000009608"))'
        )
        kept = tuple(
            moved_fp if child is fp else child
            for child in root.children
            if not isinstance(child, Node) or child.name not in {"segment", "arc", "via", "zone"}
        )
        path.write_text(dumps(root.with_children((*kept, other_fp, probe))))
        before = snapshot(project)
        run = native.run(
            ["pcb", "drc", "--format", "json", "--severity-all", "-o", "offset.json", path.name],
            files={p.name: p for p in project.iterdir() if p.is_file()},
        )
        assert run.ok, (run.stdout, run.stderr)
        report = json.loads(run.outputs["offset.json"])
        contacts = [v for v in report["violations"] if v["type"] == "shorting_items"]
        assert bool(contacts) is shifted, (shape, angle, side, shifted, report["violations"])
        assert snapshot(project) == before
        results[str(shifted)] = {
            "version": version,
            "shorting_items": len(contacts),
            "input_sha256": before,
            "report_sha256": hashlib.sha256(run.outputs["offset.json"]).hexdigest(),
        }
    (tmp_path / "offset-contact-receipt.json").write_text(
        json.dumps(results, indent=2, sort_keys=True) + "\n"
    )
