# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""An Altium build of an imported Altium project (change c0480): drawings on a user layer named after a
mechanical layer are written there, the script's own items are not reported as uncopied, and a script that
carries an Altium source's board records is written through the conversion writer, so the source's rule
records come back as they were read.

The source is authored here: the blink example, built for Altium by Fenolite and imported back."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _importcode import ROOT, STAMP

from fenolite.api import run
from fenolite.api.board import read_board
from fenolite.backends.altium import lower
from fenolite.cli.cmd_build import altium_carried
from fenolite.core.coords import Point, Size
from fenolite.dsl import Design as DslDesign
from fenolite.lens import altium_copper
from fenolite.lens.altium import _document_holds  # pyright: ignore[reportPrivateUsage]
from fenolite.model.board import Board, Graphic, Text
from fenolite.model.design import Design, DesignHeader
from fenolite.model.rules import Rule

EXAMPLE = ROOT / "examples" / "blink_2layer"
LINE = Graphic(
    id="gfx_00000000-0000-4000-8000-000000000001",
    kind="line",
    layer="User.10",
    points=(Point(0, 0), Point(1_000_000, 0)),
    width=100_000,
)
TEXT = Text(
    "NOTE",
    Point(0, 0),
    "User.10",
    Size(1_000_000, 1_000_000),
    150_000,
    id="txt_00000000-0000-4000-8000-000000000001",
)


def test_drawing_on_a_named_user_layer_is_written() -> None:
    """A line and a text on a user layer that the document holds as a mechanical layer are written."""
    board = Board(id="brd_x", graphics=(LINE,), texts=(TEXT,))
    found: list[object] = []
    items = altium_copper.lower_items(board, ("F.Cu", "B.Cu"), found, layer_ids={"User.10": 69})  # type: ignore[arg-type]
    assert items.graphics == (LINE,) and items.texts == (TEXT,) and found == []
    unmapped: list[object] = []
    items = altium_copper.lower_items(board, ("F.Cu", "B.Cu"), unmapped)  # type: ignore[arg-type]
    assert items.graphics == () and items.texts == () and len(unmapped) == 2


def test_footprint_drawing_on_a_named_user_layer_is_held() -> None:
    """A footprint line on User.11 named after Mechanical 15 is a component item of the document."""
    line = Graphic(id=LINE.id, kind="line", layer="User.11", points=LINE.points, width=LINE.width)
    assert _document_holds(line, {"User.11": 71})
    assert not _document_holds(line, lower.KICAD_MECHANICAL)


def test_script_items_of_a_script_copper_source_are_not_reported() -> None:
    """The items the design's board holds itself are written from there, not reported as uncopied."""
    header = DesignHeader(id="dsn_m", name="m", schema_version="0", fenolite_version="0")
    board = Board(id="brd_x", graphics=(LINE,), texts=(TEXT,))
    source = altium_copper.CopperSource(Design(header, board=board), "script")
    assert altium_copper.source_not_lowered(source, board) == []
    assert [i.message for i in altium_copper.source_not_lowered(source)] == [
        "script copper: 1 texts are not copied",
        "script copper: 1 graphics are not copied",
    ]


def _rules(path: Path) -> list[tuple[str, str, str, object, object, object]]:
    read = read_board(path).design.rules
    rules: tuple[Rule, ...] = read.rules if read is not None else ()
    return sorted((r.name, str(r.kind), str(r.selector_a), r.min, r.opt, r.max) for r in rules)


@pytest.mark.needs_kicad  # the KiCad schematic of the import needs kicad-cli for its netlist
def test_imported_altium_project_builds_through_the_conversion(tmp_path: Path) -> None:
    """Scenario "Altium build of an imported Altium project"."""
    source = tmp_path / "src"
    source.mkdir()
    (source / "design.py").write_text((EXAMPLE / "design.py").read_text(encoding="utf-8"))
    for name in ("fp-lib-table", "sym-lib-table"):
        text = (EXAMPLE / name).read_text(encoding="utf-8")
        (source / name).write_text(text.replace("${KIPRJMOD}/../..", ROOT.as_posix()))
    first = run(
        "build", "design.py", "--target", "altium", "--out", "alt", "--altium-pour", "outline", "--confirm",
        cwd=source, timestamp=STAMP,
    )  # fmt: skip
    assert first.exit_code == 0, first.error
    assert first.result is not None and "through" not in first.result
    imported = run(
        "import", str(source / "alt" / "blink.PrjPcb"), "--to", "python", "--out", "py", "--confirm",
        cwd=tmp_path, timestamp=STAMP,
    )  # fmt: skip
    assert imported.exit_code == 0, imported.error
    again = run(
        "build", "design.py", "--target", "altium", "--out", "alt", "--altium-pour", "outline", "--confirm",
        cwd=tmp_path / "py", timestamp=STAMP,
    )  # fmt: skip
    assert again.exit_code == 0, again.error
    assert again.result is not None and again.result["through"] == "conversion", json.dumps(again.result)[
        :400
    ]
    assert _rules(tmp_path / "py" / "alt" / "blink.PcbDoc") == _rules(source / "alt" / "blink.PcbDoc")


def test_a_script_without_carriers_is_not_carried() -> None:
    design = DslDesign("plain")
    assert not altium_carried(design)
    design.verbatim("property/1", '(property "Fenolite.Altium.Rules6" "x")')
    assert altium_carried(design)


def test_single_pad_unconnected_net_is_no_net() -> None:
    """A pad on a KiCad net ``unconnected-(…)`` of that one pad is on no net in an Altium conversion."""
    from fenolite.convert.to_altium import open_pads
    from fenolite.model.board import FootprintInstance, Pad
    from fenolite.model.circuit import Circuit, Net

    def pad(number: str, net: str | None) -> Pad:
        return Pad(number, "rect", Size(1, 1), Point(0, 0), id=f"pad_{number}", net_id=net)

    header = DesignHeader(id="dsn_m", name="m", schema_version="0", fenolite_version="0")
    nets = (Net(id="net_a", name="unconnected-(U1-NC-Pad2)"), Net(id="net_b", name="GND"))
    fp = FootprintInstance(
        "cmp_u1", "lib:U", Point(0, 0), pads=(pad("1", "net_b"), pad("2", "net_a")), id="fpi_u1"
    )
    design = Design(header, circuit=Circuit(nets=nets), board=Board(id="brd_x", footprints=(fp,)))
    opened = open_pads(design)
    assert opened.board is not None
    assert [p.net_id for p in opened.board.footprints[0].pads] == ["net_b", None]
    assert [net.name for net in opened.circuit.nets] == ["GND"]
