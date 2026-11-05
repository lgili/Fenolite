# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A board built beside a drawn hierarchy carries KiCad's net names (capability kicad-file-backend, "Net
names in KiCad's stored form"; capability kicad-schematic, "Names of unconnected-pin nets"; hypotheses
``H-K-SCH-SLASH`` and ``H-K-SCH-UNCONNECTED``; change c0408).

The authored case has the shape that failed on the public ``flat_hierarchy`` demo: nets named by a local and
a hierarchical label on a child sheet, whose code names are the sheet-path names (``/child/FB``), and a part
whose pins are named like their numbers, left open. ``pcb drc --schematic-parity`` of the built board
against its own sheets reports nothing; the control respells one net as a label text and the same run
reports it, so the run reads net names."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import _drawn
import _erc
import _probes
import pytest
from _buildhelp import build as build_design

from fenolite.dsl import Design, Part
from fenolite.lens.drawn import read_drawn

pytestmark = pytest.mark.needs_kicad

OPEN_PART = """
[[sheet.symbol]]
part = "J1"
unit = 1
at = [152.4, 63.5]
rotation = 0
"""
"""J1 on the root sheet, with no wire: both pins open."""
CHILD = '\n[[sheet]]\nkey = "child"'
"""Where the child sheet of the fixture's drawing starts; J1 is drawn on the root sheet before it."""


def _numbered_pins(library: str) -> str:
    """The mini library with the pins of ``Mini_R`` named like their numbers (``1`` and ``2``)."""
    start = library.index('(symbol "Mini_R"')
    end = library.find('\n\t(symbol "', start + 1)
    end = library.rindex("\n)") if end < 0 else end  # the last symbol ends where the library does
    block = library[start:end]
    count = iter(("1", "2"))
    named = re.sub(r'\(name ""', lambda _: f'(name "{next(count)}"', block)
    assert next(count, None) is None, "Mini_R has two unnamed pins"
    return library[:start] + named + library[end:]


def _case(tmp_path: Path) -> tuple[Design, Path, str]:
    """The design, the project folder and the drawn text of the authored case."""
    libs = _drawn.ROOT / "tests" / "data" / "libs"
    (tmp_path / "libs").mkdir()
    (tmp_path / "libs" / "Mini_v9.kicad_sym").write_text(
        _numbered_pins((libs / "Mini_v9.kicad_sym").read_text(encoding="utf-8")), encoding="utf-8"
    )
    shutil.copytree(libs / "Mini_v9.pretty", tmp_path / "libs" / "Mini_v9.pretty")
    folder = tmp_path / "drawn" / "case"
    folder.mkdir(parents=True)
    for table in ("sym-lib-table", "fp-lib-table"):
        shutil.copy(_drawn.folder("hier") / table, folder / table)
    code = _drawn.design("hier")
    for old, new in (("IN", "/child/IN"), ("FB", "/child/FB")):
        net = code.nets.pop(old)
        net.name = new
        code.nets[new] = net
    code.add(Part("J1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="open"))
    drawing = _drawn.text("hier")
    assert drawing.count(CHILD) == 1
    return code, folder, drawing.replace(CHILD, OPEN_PART + CHILD)


def test_sheet_path_and_numbered_pin_nets_pass_parity(tmp_path: Path) -> None:
    code, folder, text = _case(tmp_path)
    output = build_design(
        code, _probes.major(), project_dir=folder, drawn=read_drawn(text, file="schematic.toml"),
        drawn_file="schematic.toml", schematic_layout="wired",
    )  # fmt: skip
    assert output.files and not any(i.severity == "error" for i in output.issues), output.issues
    files = dict(output.files)
    board = "drawn_hier.kicad_pcb"
    written = files[board].decode("utf-8")
    for name in ("/child/FB", "/child/IN", "unconnected-(J1-Pad1)", "unconnected-(J1-Pad2)"):
        assert f'"{name}"' in written, name
    assert "{slash}child" not in written
    report = _erc.run_parity(_probes.runner(), board, files)
    found = _erc.parity(report)
    assert found == [], [(v["type"], v["description"]) for v in found]
    # control: the label-text spelling of one sheet-path net is reported
    files[board] = written.replace('"/child/FB"', '"{slash}child{slash}FB"').encode("utf-8")
    control = _erc.types(_erc.parity(_erc.run_parity(_probes.runner(), board, files)))
    assert control["net_conflict"] > 0, control
    print(f"c0408 parity: 0 issues, control {dict(control)} on kicad-cli {_probes.version()}")
