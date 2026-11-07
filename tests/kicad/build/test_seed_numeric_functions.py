# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0335: numeric-function normalization preserves an authored circuit's native partition."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from _kicad import cli, major
from _libs import isolated_kicad_env, kicad

import fenolite.library.seed as seed_module
from fenolite.api import run
from fenolite.backends.kicad.netlist import read_netlist
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.catalog.records import DeviceRecord, record_text
from fenolite.library.licences import normalised_digest
from fenolite.library.seed import convert

pytestmark = pytest.mark.needs_kicad
DEMO = Path(__file__).resolve().parents[3] / "tests/data/librepcb/demo"


def test_numeric_seed_preserves_native_partition(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    upstream = tmp_path / "upstream"
    shutil.copytree(DEMO, upstream)
    source = next((upstream / "cmp").glob("*/component.lp"))
    source.write_text(
        source.read_text().replace('(name "A")', '(name "1")').replace('(name "B")', '(name "2")')
    )
    source_symbol = next((upstream / "sym").glob("*/symbol.lp"))
    source_symbol.write_text(source_symbol.read_text().replace("(rotation 180)", "(rotation -90)"))
    monkeypatch.setattr(seed_module, "CC0_SHA256", normalised_digest((upstream / "LICENSE.txt").read_bytes()))
    converted = convert(
        upstream,
        library_name="Authored Demo",
        commit="1" * 40,
        namespace="Seed",
        source_id="D-0001",
        allocate=lambda kind, name, uid: f"Seed:{kind}",
    )
    assert not any(i.code == "library.seed-skipped" for i in converted.issues)
    device = next(i.record for i in converted.items if isinstance(i.record, DeviceRecord))
    assert tuple(p.pin_pads for p in device.device.pins) == ((("1", "1"),), (("2", "2"),))
    folder = tmp_path / "devices"
    folder.mkdir()
    for i in converted.items:
        (folder / f"{i.kind}.toml").write_text(record_text(i.record))
    script = tmp_path / "design.py"
    script.write_text("""from fenolite.dsl import Design, Net, connect, mm
design = Design("numeric_seed")
design.board(mm(20), mm(20))
r1 = design.part("R1", device="Seed:device")
r2 = design.part("R2", device="Seed:device")
connect(Net("JOIN"), r1["Pin_1"], r2["Pin_2"])
connect(Net("LEFT"), r1["Pin_2"])
connect(Net("RIGHT"), r2["Pin_1"])
r1.place(mm(5), mm(10))
r2.place(mm(15), mm(10))
""")
    built = run(
        "build", str(script), "--out", "out", "--confirm", "--kicad-version", str(major()), cwd=tmp_path
    )
    assert built.exit_code == 0, built.error
    symbol_library = next((tmp_path / "out").rglob("*.kicad_sym"))
    upgraded = tmp_path / "native.kicad_sym"
    save = kicad(
        cli(), isolated_kicad_env(tmp_path), "sym", "upgrade", "--force", symbol_library, "-o", upgraded
    )
    assert save.returncode == 0, save.stdout + save.stderr
    native_symbols = read_symbol_library(upgraded, library="Seed")
    assert any(p.number == "2" and p.rotation == 270_000_000 for s in native_symbols for p in s.pins)
    output = tmp_path / "native.net"
    native = kicad(
        cli(),
        isolated_kicad_env(tmp_path),
        "sch",
        "export",
        "netlist",
        "--format",
        "kicadsexpr",
        "-o",
        output,
        tmp_path / "out/numeric_seed.kicad_sch",
    )
    assert native.returncode == 0, native.stdout + native.stderr
    nets = read_netlist(output.read_text())
    assert {n.name: {(p.ref, p.pin) for p in n.nodes} for n in nets.nets} == {
        "JOIN": {("R1", "1"), ("R2", "2")},
        "LEFT": {("R1", "2")},
        "RIGHT": {("R2", "1")},
    }
