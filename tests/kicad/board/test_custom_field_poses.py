# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native SVG ink of an authored visible property before/after code import (c0345)."""

from collections import Counter
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from _custom_fields import original
from _probes import runner

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Atom, dumps, parse

pytestmark = pytest.mark.needs_kicad


def ink(svg: str) -> Counter:
    """Exact native primitives and inherited styles; only native object IDs are irrelevant."""
    values = []

    def visit(node, parents):
        tag = node.tag.rsplit("}", 1)[-1]
        attributes = tuple(sorted((k, v) for k, v in node.attrib.items() if k != "id"))
        if tag in {"path", "line", "polyline", "polygon", "rect", "circle", "ellipse", "text"}:
            values.append((tag, attributes, node.text if tag == "text" else "", parents))
        inherited = (*parents, attributes) if tag == "g" and attributes else parents
        for child in node:
            visit(child, inherited)

    visit(ET.fromstring(svg), ())
    assert values
    return Counter(values)


@pytest.mark.parametrize("styled", [False, True])
def test_native_custom_field_ink_matches_imported_code(tmp_path: Path, styled: bool) -> None:
    cli = runner()
    source = original(tmp_path / "original", 180, cli.major(), visible=True, styled=styled)
    args = ("import", str(source), "--to", "python", "--out", "code", "--licence", "CC0-1.0")
    planned = run(*args, "--dry-run", cwd=tmp_path)
    assert planned.exit_code == 0, planned.error
    confirmed = run(*args, "--confirm", "--plan", planned.result["plan_id"], cwd=tmp_path)
    assert confirmed.exit_code == 0, confirmed.error
    built = run(
        "build",
        "code/design.py",
        "--out",
        "built",
        "--kicad-version",
        str(cli.major()),
        "--confirm",
        cwd=tmp_path,
    )
    assert built.exit_code == 0, built.error
    before_svg = cli.export_layers_svg(source.with_suffix(".kicad_pcb"), ["F.Fab"])
    after_svg = cli.export_layers_svg(tmp_path / "built/font_probe.kicad_pcb", ["F.Fab"])
    (tmp_path / "native-before.svg").write_text(before_svg)
    (tmp_path / "native-after.svg").write_text(after_svg)
    a, b = ink(before_svg), ink(after_svg)
    assert a == b, (a - b, b - a)
    # The oracle must actually see this custom field, rather than comparing only the library artwork.
    board = parse((tmp_path / "built/font_probe.kicad_pcb").read_text())
    (fp,) = board.nodes("footprint")
    prop = next(p for p in fp.nodes("property") if p.atoms()[0].value == "Author")
    at = prop.find("at")
    assert at is not None
    moved = at.with_children((Atom.from_nm(20_000_000), *at.atoms()[1:]))
    changed = prop.with_children(tuple(moved if c is at else c for c in prop.children))
    fp2 = fp.with_children(tuple(changed if c is prop else c for c in fp.children))
    planted = tmp_path / "planted.kicad_pcb"
    planted.write_text(dumps(board.with_children(tuple(fp2 if c is fp else c for c in board.children))))
    planted_svg = cli.export_layers_svg(planted, ["F.Fab"])
    (tmp_path / "native-planted.svg").write_text(planted_svg)
    assert ink(planted_svg) != a
