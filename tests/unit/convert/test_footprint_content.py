# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Everything a footprint draws survives an Altium to KiCad conversion (capability design-conversion,
"Footprint texts of an imported footprint"; change c0422). The Altium source is the authored document of
``tests/_fpcontent.py``."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from _fpcontent import GRAPHICS, TEXTS, altium_document, by_ref, converted, drawn
from _importcode import imported

from fenolite.api import convert
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.kicad import fpitems
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.sexpr import Node, parse


def _named(pcb: Node) -> dict[str, str]:
    """User name → layer name for the named rows of a board's layer table."""
    table = pcb.find("layers")
    assert table is not None
    rows = [[atom.value for atom in row.atoms()] for row in table.nodes()]  # name, type[, user name]
    return {row[2]: row[0] for row in rows if len(row) > 2}


def test_the_altium_source_holds_every_drawing(tmp_path: Path) -> None:
    board = AltiumBackend().read(altium_document(tmp_path)).design.board
    assert board is not None
    resistor, led = board.footprints
    kinds = Counter((g.layer, g.kind, g.filled) for g in resistor.graphics)
    assert kinds[("F.SilkS", "arc", False)] == 1 and kinds[("F.SilkS", "polygon", True)] == 1
    assert kinds[("F.SilkS", "rect", True)] == 1
    assert {("Mech.5", "line", False), ("Mech.13", "line", False), ("Mech.10", "circle", False)} <= set(kinds)
    assert [(t.text, t.layer) for t in resistor.texts] == [("NOTE A", "F.SilkS"), ("ASSY", "Mech.13")]
    assert [(t.text, t.layer) for t in led.texts] == [("NOTE B", "B.SilkS")]
    assert Counter(g.layer for g in led.graphics) == {"B.SilkS": 3}
    assert sum(len(fp.graphics) for fp in board.footprints) == GRAPHICS


def test_conversion_writes_footprint_texts_and_graphics(tmp_path: Path) -> None:
    conversion = convert(altium_document(tmp_path), to="kicad", allow_lossy=True).conversion
    rows = {row.kind: row for row in conversion.report.rows}
    text, graphic = rows["footprint-text"], rows["footprint-graphic"]
    assert (text.source, text.written, text.lost) == (TEXTS, TEXTS, 0)
    assert (graphic.source, graphic.written, graphic.lost) == (GRAPHICS, GRAPHICS, 0)
    lossy = [i for i in conversion.issues if i.code == "convert.lossy" and i.where.startswith("footprint-")]
    assert not lossy
    pcb = parse(conversion.files[conversion.read_back].decode())
    named = _named(pcb)
    resistor, led = by_ref(pcb, "R1"), by_ref(pcb, "D1")
    expected = {
        ("fp_arc", "F.SilkS"): 1,
        ("fp_poly", "F.SilkS"): 1,
        ("fp_rect", "F.SilkS"): 1,
        ("fp_line", named["Mech.5"]): 1,
        ("fp_line", named["Mech.13"]): 1,
        ("fp_circle", named["Mech.10"]): 1,
        ("fp_text", "F.SilkS"): 1,
        ("fp_text", named["Mech.13"]): 1,
    }
    assert drawn(resistor) >= Counter(expected)
    on_bottom = {("fp_circle", "B.SilkS"): 1, ("fp_arc", "B.SilkS"): 1, ("fp_poly", "B.SilkS"): 1}
    assert drawn(led) == Counter({**on_bottom, ("fp_text", "B.SilkS"): 1})
    # the text keeps its string, size and stroke; on a bottom layer it is mirrored, as KiCad holds it
    note = next(t for t in led.nodes("fp_text") if t.atoms()[1].value == "NOTE B")
    effects = note.find("effects")
    assert effects is not None and effects.find("justify") is not None
    font = effects.find("font")
    size = font.find("size") if font is not None else None
    # 0.8 mm is 314 961 Altium units of 0.0001 mil, which read back 1 nm larger
    assert size is not None and [a.to_nm() for a in size.atoms()] == [800_001, 800_001]
    # the texts come after the graphics and before the pads, as KiCad 10.0.6 saves a footprint (S-0058)
    heads = [child.name for child in resistor.nodes() if child.name in ("fp_line", "fp_text", "pad")]
    assert heads.index("fp_text") > max(i for i, h in enumerate(heads) if h == "fp_line")
    assert heads.index("pad") > max(i for i, h in enumerate(heads) if h == "fp_text")
    libraries = [parse(data.decode()) for key, data in conversion.files.items() if key.endswith(".kicad_mod")]
    assert sum(len(mod.nodes("fp_text")) for mod in libraries) == TEXTS


def test_the_kicad_side_projects_every_footprint_item(tmp_path: Path) -> None:
    """What a cross-backend comparison of the two sides sees on the KiCad side (``fpitems``, change c0126):
    every drawing and text of the source, each on the user layer named after its mechanical layer."""
    board = converted(altium_document(tmp_path), tmp_path / "back")
    named = _named(parse(board.read_text(encoding="utf-8")))
    projected = fpitems.with_footprint_items(KicadBackend().read(board).design).design.board
    assert projected is not None
    free = ("NOTE A", "ASSY", "NOTE B")
    texts = Counter((t.text, t.layer) for fp in projected.footprints for t in fp.texts if t.text in free)
    assert texts == Counter(
        {("NOTE A", "F.SilkS"): 1, ("ASSY", named["Mech.13"]): 1, ("NOTE B", "B.SilkS"): 1}
    )
    layers = Counter(g.layer for fp in projected.footprints for g in fp.graphics)
    assert layers >= Counter(
        {"F.SilkS": 3, "B.SilkS": 3, named["Mech.5"]: 1, named["Mech.13"]: 1, named["Mech.10"]: 1}
    )


def test_import_to_python_vendors_the_footprint_texts(tmp_path: Path) -> None:
    (tmp_path / "import").mkdir()
    reply = imported(tmp_path / "import", altium_document(tmp_path / "src"), "--confirm", "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    layers: Counter[str] = Counter()
    for path in sorted((tmp_path / "import" / "out").rglob("*.kicad_mod")):
        for child in parse(path.read_text(encoding="utf-8")).nodes("fp_text"):
            layer = child.find("layer")
            assert layer is not None
            layers[layer.atoms()[0].value] += 1
    # the bottom LED lies on the front in the library, its text with it
    assert sum(layers.values()) == TEXTS and layers["F.SilkS"] == 2
