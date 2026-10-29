# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A build of parts placed from devices passes the KiCad oracle (change c0248; capability design-dsl, scenario
"Device build passes the KiCad oracle"; hypothesis H-K-BUILD-DEVICE).

``examples/devices/design.py`` is built for each target the running ``kicad-cli`` reads, and so is the same
design written with plain ``Part`` calls (symbol, footprint and pad map spelled out), below. Each folder is
given to the whole ``fenolite check`` (ERC and DRC with ``kicad-cli``): the device build must report no
finding that the plain build does not report, and the device's ``Datasheet`` must read back from the board.
"""

from __future__ import annotations

import io
import json
import shutil
from collections import Counter
from pathlib import Path
from typing import Any

import pytest
from _kicad import cli, supported_version

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board

pytestmark = pytest.mark.needs_kicad
ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "devices"
TARGETS = [pytest.param(10, marks=pytest.mark.kicad_min_major(10), id="t10"), pytest.param(9, id="t9")]
PLAIN = '''\
# Authored for Fenolite as test data: examples/devices/design.py with plain Part calls.
from fenolite.dsl import Design, Net, Part, Symbol, connect, farad, henry, mm, ohm

design = Design("devices")
design.board(mm(40), mm(25))
buck = Symbol("Example", "Buck_6pin", reference="U", value="EXB6202")
for number, name, y in (("1", "BST", -2.54), ("2", "GND", 0), ("3", "FB", 2.54)):
    buck.pin(number, name, at=(mm(-7.62), mm(y)), length=mm(2.54))
for number, name, y in (("4", "EN", 2.54), ("5", "VIN", 0), ("6", "SW", -2.54)):
    buck.pin(number, name, at=(mm(7.62), mm(y)), length=mm(2.54), rotation=180)
buck.rect((mm(-5.08), mm(-5.08)), (mm(5.08), mm(5.08)))
design.add(buck)
vin, gnd, sw, bst, fb, v33, led = (Net(n) for n in ("VIN", "GND", "SW", "BST", "FB", "V3V3", "LED_A"))
IDENTITY = {"1": "1", "2": "2"}
j1 = design.part("J1", "Fenolite:Connector_2", "Fenolite:Header_1x2_P2.54", "5V IN", pad_map=IDENTITY)
u1 = design.part(
    "U1", "Example:Buck_6pin", "Fenolite:SOT23_6_TI_DBV0006A", "EXB6202",
    properties={"MPN": "EXB6202", "Manufacturer": "Example Semi"},
    pad_map={str(n): str(n) for n in range(1, 7)},
)
c1 = design.part("C1", "Fenolite:Capacitor", "Fenolite:Chip_0805", farad("10u"), pad_map=IDENTITY)
c2 = design.part("C2", "Fenolite:Capacitor", "Fenolite:Chip_0603", farad("100n"), pad_map=IDENTITY)
c3 = design.part("C3", "Fenolite:Capacitor", "Fenolite:Chip_0805", farad("22u"), pad_map=IDENTITY)
l1 = design.part("L1", "Fenolite:Inductor", footprint="Fenolite:Chip_0805", value=henry("4u7"))
r1 = design.part("R1", "Fenolite:Resistor", "Fenolite:Chip_0603", ohm("31k6"), pad_map=IDENTITY)
r2 = design.part("R2", "Fenolite:Resistor", "Fenolite:Chip_0603", ohm("10k"), pad_map=IDENTITY)
r3 = design.part("R3", "Fenolite:Resistor", "Fenolite:Chip_0603", ohm("1k"), pad_map=IDENTITY)
d1 = design.part(
    "D1", "Fenolite:LED", "Fenolite:LED0603_Kingbright_APT1608SURCK", "LED_0603", pad_map={"1": "2", "2": "1"}
)
connect(vin, j1[1], c1[1], u1[5], u1[4])
connect(gnd, j1[2], c1[2], u1[2], c3[2], r2[2], d1[2])
connect(bst, u1[1], c2[1])
connect(sw, u1[6], c2[2], l1[1])
connect(v33, l1[2], c3[1], r1[1], r3[1])
connect(fb, u1[3], r1[2], r2[1])
connect(led, r3[2], d1[1])
j1.place(mm(5), mm(12.5), rot=90, locked=True)
c1.place(mm(12), mm(8))
u1.place(mm(18), mm(12.5))
c2.place(mm(18), mm(7))
l1.place(mm(25), mm(12.5))
c3.place(mm(31), mm(8))
r1.place(mm(25), mm(18))
r2.place(mm(20), mm(18))
r3.place(mm(31), mm(17))
d1.place(mm(35), mm(17))
'''  # fmt: skip


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main([*args, "--json"])
    return code, json.loads(stdout.getvalue() or "{}"), stderr.getvalue()


def build_and_check(monkeypatch: pytest.MonkeyPatch, script: Path, out: Path, target: int) -> Counter[str]:
    code, _, err = run(
        monkeypatch, "--kicad-version", str(target), "build", str(script), "--out", str(out), "--confirm"
    )
    assert code == 0, err
    _, envelope, _ = run(monkeypatch, "check", str(out), "--kicad-cli", cli())
    return Counter(issue["code"] for issue in envelope["issues"])


@pytest.mark.parametrize("target", TARGETS)
def test_device_build_passes_the_kicad_oracle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int
) -> None:
    version = supported_version()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    devices = tmp_path / "devices"
    shutil.copytree(EXAMPLE, devices)
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "design.py").write_text(PLAIN, encoding="utf-8")
    found = build_and_check(monkeypatch, devices / "design.py", tmp_path / "out_devices", target)
    control = build_and_check(monkeypatch, plain / "design.py", tmp_path / "out_plain", target)
    print(f"kicad-cli {version}, target {target}: devices {dict(found)}, plain {dict(control)}")
    assert not found - control, found - control
    board = read_board((tmp_path / "out_devices" / "devices.kicad_pcb").read_text(encoding="utf-8"))
    u1 = next(component for component in board.circuit.components if component.ref == "U1")
    assert u1.properties["Datasheet"] == "https://example.invalid/exb6202.pdf"
    assert u1.properties["fenolite.device"] == "Example:BUCK_6V_2A"
