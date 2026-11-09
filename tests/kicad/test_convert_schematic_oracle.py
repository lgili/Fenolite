# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The converted drawing against kicad-cli (change c0470, tasks 4.2 and 5.5; capability design-conversion,
"Sheet carriers" and "Schematic conversion verified at level S").

Every run happens in ``tmp_path``: the authored projects ``tests/data/altium/blink`` and the one built from
``examples/altium_hier_board`` are converted to KiCad and written there."""

from __future__ import annotations

from pathlib import Path

import pytest
from _drawings import BLINK, hier_board
from _kicad import cli, run

from fenolite.backends.kicad import sheet_carrier
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.netlist import KicadNetlist
from fenolite.backends.kicad.oracle import export_netlist_of
from fenolite.convert import convert_project
from fenolite.model.circuit import Circuit

pytestmark = pytest.mark.needs_kicad


def _written(project: Path, folder: Path) -> dict[str, Path]:
    conversion = convert_project(project, to="kicad", allow_lossy=True)
    out: dict[str, Path] = {}
    for name, data in conversion.files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        out[name] = target
    return out


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_a_resave_keeps_the_carrier(name: str, tmp_path: Path) -> None:
    """Task 4.2, scenario "KiCad keeps the carrier on a save": ``kicad-cli sch upgrade --force`` rewrites
    each sheet, and the carrier in its title block's comment 9 is the one written."""
    project = BLINK if name == "blink" else hier_board(tmp_path / "source")
    files = _written(project, tmp_path / "kicad")
    sheets = {name: path for name, path in files.items() if name.endswith(".kicad_sch")}
    assert sheets
    for path in sheets.values():
        before = sheet_carrier.take(path.read_text(encoding="utf-8"))
        assert before is not None
        run("sch", "upgrade", "--force", path)
        after = sheet_carrier.take(path.read_text(encoding="utf-8"))
        assert after == before, path.name
        sheet_carrier.AltiumSheet.parse(after)


def _groups_of_netlist(found: KicadNetlist) -> set[frozenset[tuple[str, str]]]:
    return {frozenset((n.ref, n.pin) for n in net.nodes) for net in found.nets if len(net.nodes) > 1}


def _groups_of_circuit(circuit: Circuit) -> set[frozenset[tuple[str, str]]]:
    components = {c.id: c for c in circuit.components}
    groups: set[frozenset[tuple[str, str]]] = set()
    for net in circuit.nets:
        members = {
            (components[m.component_id].ref, pad)
            for m in net.members
            if m.component_id in components
            for pad in components[m.component_id].pads_of(m.pin)
        }
        if len(members) > 1:
            groups.add(frozenset(members))
    return groups


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_netlist_of_the_written_sheets(name: str, tmp_path: Path) -> None:
    """Task 5.5: ``kicad-cli`` loads every written sheet, and the netlist it exports joins the pins as the
    circuit of the source does."""
    project = BLINK if name == "blink" else hier_board(tmp_path / "source")
    conversion = convert_project(project, to="kicad", allow_lossy=True)
    files = _written(project, tmp_path / "kicad")
    root = next(n for n in files if n.endswith(".kicad_sch") and "/" not in n)
    export = export_netlist_of(KicadCli(Path(cli())), root, files)
    assert export.netlist is not None, export.message
    assert _groups_of_netlist(export.netlist) == _groups_of_circuit(conversion.design.circuit)


@pytest.mark.kicad_min_major(10)
@pytest.mark.parametrize("name", ["blink", "altium_hier_board"])
def test_erc_there_and_back(name: str, tmp_path: Path) -> None:
    """Task 5.5: the ERC violations by type of the written KiCad sheets equal those of the same drawing
    converted to Altium and back to KiCad."""
    from collections import Counter

    from fenolite.api import convert

    project = BLINK if name == "blink" else hier_board(tmp_path / "source")
    first = _written(project, tmp_path / "kicad")
    altium = convert(
        next(p for n, p in first.items() if n.endswith(".kicad_pro")), to="altium", allow_lossy=True
    )
    assert altium.unexplained == ()
    for key, data in altium.conversion.files.items():
        (tmp_path / "altium" / key).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / "altium" / key).write_bytes(data)
    again = _written(next((tmp_path / "altium").glob("*.PrjPcb")), tmp_path / "again")
    tool = KicadCli(Path(cli()))

    def types(files: dict[str, Path]) -> Counter[str]:
        root = next(n for n in files if n.endswith(".kicad_sch") and "/" not in n)
        found = tool.erc(files[root], files={n: p for n, p in files.items() if n != root})
        assert found.report is not None
        return Counter(v.type for v in found.report.violations if not v.excluded)

    assert types(again) == types(first)
