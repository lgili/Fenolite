# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block layout reuse in a build (change c0255; capability layout-reuse, "Block layout reuse in a build",
"Nets mapped by port" and "Block reuse codes"). The reference board is
``examples/relative/channel.kicad_pcb``, authored for Fenolite from ``examples/relative/bench/channel.py``."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from _relbench import Bench

from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.pcb import read_board
from fenolite.core.coords import Point

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "relative"
MM = 1_000_000
BLOCK = """from fenolite.dsl import Design, Net, Power, block, connect, mm, row

design = Design("reuse")
design.board(mm(50), mm(30))


@block
def channel(b):
    vin = b.port("VIN", direction="in")
    gnd = b.port("GND", direction="in")
    a = b.net("A")
    c = b.part("C", "Fenolite:Capacitor", footprint="Fenolite:Chip_0805", value="100n")
    r = b.part("R", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
    d = b.part(
        "D", "Fenolite:LED", footprint="Fenolite:LED0603_Kingbright_APT1608SURCK", value="green",
        pad_map={"1": "2", "2": "1"},
    )
    connect(vin, c["A"], r[1])
    connect(a, r[2], d["A"])
    connect(gnd, c["B"], d["K"])
    EXTRA


v12, gnd = Net("V12"), Net("GND")
j1 = design.part("J1", "Fenolite:Connector_2", footprint="Fenolite:Header_1x2_P2.54", value="PWR")
connect(v12, j1[1])
connect(gnd, j1[2])
design.add(Power(v12, gnd))
p3 = design.use(channel, "buck3")
connect(v12, p3.VIN)
connect(gnd, p3.GND)
j1.place(mm(3), mm(15))
p3.layout(reuse="channel.kicad_pcb", COPPER)
p3.place(mm(20), mm(5))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _bench(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    copper: bool,
    extra: str = "",
    reference: str | None = None,
) -> Bench:
    text = BLOCK.replace("EXTRA", extra or "pass").replace("COPPER", f"copper={copper}")
    bench = Bench(tmp_path, monkeypatch, text, "reuse")
    target = bench.folder / "channel.kicad_pcb"
    if reference is None:
        shutil.copy(EXAMPLE / "channel.kicad_pcb", target)
    else:
        target.write_text(reference, encoding="utf-8")
    return bench


def _pads(text: str) -> dict[tuple[str, str], Point]:
    design = read_board(text)
    paths = {c.id: c.properties.get("fenolite.path", c.ref) for c in design.circuit.components}
    assert design.board is not None
    fps = {fp.id: paths[fp.component_id] for fp in design.board.footprints}
    return {(fps[p.footprint_id], p.number): p.position for p in KicadBackend().board_pads(design)}


def test_a_block_placed_from_its_own_board(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = _bench(tmp_path, monkeypatch, copper=False)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    reference = _pads((EXAMPLE / "channel.kicad_pcb").read_text(encoding="utf-8"))
    built = _pads(bench.board.read_text(encoding="utf-8"))
    # the reference positions are taken in the place() frame of the reference board and composed with the
    # pose (20 mm, 5 mm)
    shift = Point(20 * MM, 5 * MM)
    for (path, number), at in reference.items():
        local = path.removeprefix("ch/")
        mine = built[(f"buck3/{local}", number)]
        assert abs(mine.x - at.x - shift.x) <= 1000 and abs(mine.y - at.y - shift.y) <= 1000, (path, number)
    (held,) = env["result"]["placement"]["blocks"]
    assert held["layout"] == "reuse=channel.kicad_pcb" and held["source"] == "instance"
    board = bench.read().board
    assert board is not None and not board.tracks


def test_copper_follows_the_ports(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = _bench(tmp_path, monkeypatch, copper=True)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    design = bench.read()
    assert design.board is not None
    names = {net.id: net.name for net in design.circuit.nets}
    tracks = design.board.tracks
    assert len(tracks) == 6 and all(track.locked for track in tracks)
    assert sorted({names[t.net_id or ""] for t in tracks}) == ["V12", "buck3/A"]
    assert not [i for i in env["issues"] if i["code"].startswith("copper.")]
    first = bench.files()
    assert bench.build("--confirm")[0] == 0
    assert bench.files() == first


def test_a_net_without_a_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    text = (EXAMPLE / "channel.kicad_pcb").read_text(encoding="utf-8")
    text = re.sub(r'\(net "ch\{slash\}A"\)', '(net "TEST")', text)
    bench = _bench(tmp_path, monkeypatch, copper=True, reference=text)
    code, env, _ = bench.build("--confirm")
    assert code == 5
    (found,) = [i for i in env["issues"] if i["code"] == "reuse.port-unmapped"]
    assert found["where"] == "TEST" and found["severity"] == "error"
    assert not bench.board.exists()
    # without copper the net is ignored
    other = _bench(tmp_path / "plain", monkeypatch, copper=False, reference=text)
    assert other.build("--confirm")[0] == 0


def test_a_part_without_reference_is_staged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extra = 'b.part("X", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="10k")'
    bench = _bench(tmp_path, monkeypatch, copper=False, extra=extra)
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    (found,) = [i for i in env["issues"] if i["code"] == "reuse.unknown-part"]
    assert found["where"] == "buck3/X" and found["severity"] == "warning"
    assert [i["where"] for i in env["issues"] if i["code"] == "layout.unplaced"] == ["buck3/X"]


def test_a_footprint_that_differs_does_not_fit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = _bench(tmp_path, monkeypatch, copper=False)
    bench.edit_script('footprint="Fenolite:Chip_0603"', 'footprint="Fenolite:Chip_1206"')
    code, env, _ = bench.build("--confirm")
    assert code == 5
    (found,) = [i for i in env["issues"] if i["code"] == "reuse.no-fit"]
    assert found["where"] == "buck3/R"


def test_the_example_builds_with_its_copper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    bench = Bench(
        tmp_path, monkeypatch, (EXAMPLE / "blocks.py").read_text(encoding="utf-8"), "relative_blocks"
    )
    shutil.copy(EXAMPLE / "channel.kicad_pcb", bench.folder / "channel.kicad_pcb")
    code, env, err = bench.build("--confirm")
    assert code == 0, err
    assert not [i for i in env["issues"] if i["severity"] != "info"]
    design = bench.read()
    assert design.board is not None and len(design.board.tracks) == 6
