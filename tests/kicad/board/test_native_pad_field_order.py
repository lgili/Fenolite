# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native evidence for only unique known pad-field order; no runtime normalization (c0355)."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project

from fenolite.api.sides import read_side
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.derived_teardrops import regions
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse_bytes
from fenolite.cli._derived_cache import _raw_bindings, inputs

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("style", ("circle", "roundrect", "through-hole", "chamfered"))
def test_known_unique_net_field_order_keeps_exact_native_copper(tmp_path: Path, style: str) -> None:
    target = int(_kicad.supported_version().split(".")[0])
    source = curve_project(tmp_path / "source", target, 10_000)
    path = source / "font_probe.kicad_pcb"
    root = parse_bytes(path.read_bytes())
    if style != "circle":

        def make_round(n):
            if not isinstance(n, Node):
                return n
            if n.name == "pad":
                assert n.find("roundrect_rratio") is None
                if style in {"roundrect", "chamfered"}:
                    children = tuple(
                        Atom.symbol("roundrect") if i == 2 else c for i, c in enumerate(n.children)
                    )
                    extra = [parse_bytes(b"(roundrect_rratio 0.25)")]
                    if style == "chamfered":
                        extra += [
                            parse_bytes(b"(chamfer_ratio 0.2)"),
                            parse_bytes(b"(chamfer top_left bottom_right)"),
                            parse_bytes(b"(remove_unused_layers)"),
                        ]
                    return n.with_children((*children, *extra))
                children = tuple(
                    Atom.symbol("thru_hole")
                    if i == 1
                    else parse_bytes(b'(layers "*.Cu" "*.Mask")')
                    if isinstance(c, Node) and c.name == "layers"
                    else c
                    for i, c in enumerate(n.children)
                )
                return n.with_children(
                    (
                        *children,
                        parse_bytes(b"(drill 0.4)"),
                        parse_bytes(b"(remove_unused_layers)"),
                        parse_bytes(b"(keep_end_layers)"),
                    )
                )
            return n.with_children(tuple(make_round(c) for c in n.children))

        root = make_round(root)
        path.write_bytes(dumps(root).encode())
    original = path.read_bytes()
    changed = 0

    def permute(n):
        nonlocal changed
        if not isinstance(n, Node):
            return n
        if n.name == "pad":
            nets = n.nodes("net")
            assert len(nets) == 1
            assert all(len(n.nodes(name)) <= 1 for name in ("at", "size", "layers", "teardrops"))
            children = tuple(c for c in n.children if c is not nets[0])
            changed += 1
            return (
                n.with_children((*children, nets[0]))
                if style != "circle"
                else n.with_children((*children[:3], nets[0], *children[3:]))
            )
        return n.with_children(tuple(permute(c) for c in n.children))

    alternate = dumps(permute(root)).encode()
    assert changed > 0 and alternate != original
    native = KicadCli(Path(_kicad.cli()))
    other = tmp_path / "alternate"
    other.mkdir()
    other_path = other / path.name
    other_path.write_bytes(alternate)
    files = {p.name: p for p in source.iterdir() if p.is_file() and p != path}
    svg_a = native.export_layers_svg(path, ["F.Cu", "B.Cu"], files=files)
    svg_b = native.export_layers_svg(other_path, ["F.Cu", "B.Cu"], files=files)
    (tmp_path / "native-a.svg").write_text(svg_a)
    (tmp_path / "native-b.svg").write_text(svg_b)

    # KiCad writes its current clock in non-rendered SVG title metadata; preserve raw receipts.
    def stable_title(text):
        return re.sub(
            r"(<title>[^<]*?)\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}:\d{2}([^<]*</title>)",
            r"\1MEASURED_NATIVE_CLOCK\2",
            text,
        )

    assert stable_title(svg_a) == stable_title(svg_b)
    receipt = {
        "native_version": _kicad.supported_version(),
        "style": style,
        "input_sha256": hashlib.sha256(original).hexdigest(),
        "permuted_sha256": hashlib.sha256(alternate).hexdigest(),
        "pad_fields_permuted": changed,
        "exact_copper_svg_sha256": hashlib.sha256(stable_title(svg_a).encode()).hexdigest(),
        "raw_svg_sha256": [hashlib.sha256(text.encode()).hexdigest() for text in (svg_a, svg_b)],
        "only_svg_title_clock_normalized": True,
        "identity_or_geometry_mutation": False,
        "refill_claimed": target == 10,
    }
    if target == 10:
        ci = inputs(read_side(source))
        assert ci is not None
        a = native.refill(path, files=files)
        b = native.refill(other_path, files=files)
        assert a.run.ok and b.run.ok and a.board is not None and b.board is not None
        saved = [parse_bytes(body) for body in (a.board, b.board)]
        compared = [regions(n, _raw_bindings(n, frozenset(ci.bindings.values()))) for n in saved]
        assert compared[0] and compared[0] == compared[1]
        receipt["exact_derived_regions"] = len(compared[0])
        receipt["exact_derived_sha256"] = hashlib.sha256(repr(compared[0]).encode()).hexdigest()
        (tmp_path / "native-a.kicad_pcb").write_bytes(a.board)
        (tmp_path / "native-b.kicad_pcb").write_bytes(b.board)
    assert path.read_bytes() == original
    (tmp_path / "native-pad-field-order-proof.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    )
