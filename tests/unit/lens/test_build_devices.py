# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Device parts in a build (change c0248; capability design-dsl, "Device functions in a build", "Device
agreement in a build" and "Device fields on built parts"). The devices, symbols and footprints are authored
for Fenolite as test data."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.model import canonical
from fenolite.model.circuit import Circuit, PinRef

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "devices"

SCRIPT = """\
# Authored for Fenolite as test data.
from fenolite.dsl import Design, Footprint, Net, Symbol, connect, mm

design = Design("grounds")
design.board(mm(30), mm(20))
symbol = Symbol("Example", "Reg_9pin", reference="U")
for index in range(1, {pins} + 1):
    name = "GND" if index in (2, 9) else f"P{{index}}"
    symbol.pin(str(index), name, at=(mm(-7.62), mm(2.54 * index)), length=mm(2.54))
symbol.rect((mm(-5.08), mm(0)), (mm(5.08), mm(25.4)))
design.add(symbol)
land = Footprint("Example", "Pads_9", kind="smd")
for index in range(1, 10):
    land.pad(str(index), at=(mm(0), mm(1.27 * index)), size=(mm(0.6), mm(0.6)))
land.pad("MP", at=(mm(3), mm(6)), size=(mm(1.5), mm(1.5)))
design.add_footprint(land)
u1 = design.part("U1", device="Example:LDO_GROUNDS")
gnd, vin = Net("GND"), Net("VIN")
connect(gnd, u1.GND)
connect(vin, u1.VIN, u1.EN)
u1.place(mm(15), mm(5))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def project(tmp_path: Path, *, pins: int = 9) -> Path:
    folder = tmp_path / "proj"
    (folder / "devices").mkdir(parents=True)
    shutil.copy(DATA / "grouped_ground.toml", folder / "devices" / "grounds.toml")
    script = folder / "design.py"
    script.write_text(SCRIPT.format(pins=pins), encoding="utf-8")
    return script


def codes(envelope: dict[str, object]) -> list[str]:
    return [issue["code"] for issue in envelope["issues"]]  # type: ignore[index, union-attr]


def test_function_joins_its_pins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = project(tmp_path)
    out = tmp_path / "out"
    code, envelope, err = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 0, err
    circuit = canonical.loads((out / ".fenolite" / "circuit.json").read_text(encoding="utf-8"), Circuit)
    u1 = next(component for component in circuit.components if component.ref == "U1")
    gnd = next(net for net in circuit.nets if net.name == "GND")
    assert PinRef(u1.id, "2") in gnd.members and PinRef(u1.id, "9") in gnd.members
    assert u1.properties["fenolite.device"] == "Example:LDO_GROUNDS"
    board = read_board((out / "grounds.kicad_pcb").read_text(encoding="utf-8"))
    names = {net.id: net.name for net in board.circuit.nets}
    footprint = board.board.footprints[0]  # type: ignore[union-attr]
    pads = {pad.number: names.get(pad.net_id or "") for pad in footprint.pads}
    assert pads["2"] == pads["9"] == "GND" and pads["1"] == pads["4"] == "VIN"
    # scenario "Unused pad declared": MP is listed in unused_pads
    assert not any(
        issue["code"] == "build.pad-without-pin" and "MP" in issue["message"]  # type: ignore[index]
        for issue in envelope["issues"]  # type: ignore[union-attr]
    )
    assert "build.unknown-pin" not in codes(envelope)


def test_device_disagrees_with_its_symbol(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = project(tmp_path, pins=10)  # the symbol has a pin 10 that the device does not list
    out = tmp_path / "out"
    code, envelope, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 5
    found = [issue for issue in envelope["issues"] if issue["code"] == "build.device-mismatch"]  # type: ignore[union-attr, index]
    assert len(found) == 1 and "pin 10" in found[0]["message"]  # type: ignore[index]
    assert not out.exists() or not any(out.iterdir())


def test_datasheet_field(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "devices_example"
    shutil.copytree(ROOT / "examples" / "devices", folder)
    out = tmp_path / "out"
    code, _, err = run(monkeypatch, str(folder / "design.py"), "--out", str(out), "--confirm")
    assert code == 0, err
    board = read_board((out / "devices.kicad_pcb").read_text(encoding="utf-8"))
    refs = {component.id: component for component in board.circuit.components}
    u1 = next(c for c in refs.values() if c.ref == "U1")
    assert u1.properties["Datasheet"] == "https://example.invalid/exb6202.pdf"
    assert u1.properties["fenolite.device"] == "Example:BUCK_6V_2A"
    assert "https://example.invalid/exb6202.pdf" in (out / "devices.kicad_sch").read_text(encoding="utf-8")
    # scenario "Devices stay out of the layer files"
    for path in sorted((out / ".fenolite").glob("*.json")):
        assert "EXB6202" not in path.read_text(encoding="utf-8") or path.name in (
            "circuit.json",
            "board.json",
        )
        assert '"pins"' not in path.read_text(encoding="utf-8") or path.name != "meta.json"
    circuit = (out / ".fenolite" / "circuit.json").read_text(encoding="utf-8")
    assert '"fenolite.device": "Example:BUCK_6V_2A"' in circuit and '"ratings"' not in circuit


def test_override_and_edit_are_reported_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Override of a shipped device" and "A hand edit is detected" in a build."""
    folder = tmp_path / "proj"
    (folder / "devices").mkdir(parents=True)
    stamped = (DATA / "stamped.toml").read_text(encoding="utf-8")
    edited = stamped.replace('id = "Proj:R_0603"', 'id = "Fenolite:R_0603"\nsources = ["S-0314"]')
    (folder / "devices" / "r0603.toml").write_text(edited, encoding="utf-8")
    (folder / "design.py").write_text(
        "from fenolite.dsl import Design, mm\n"
        'design = Design("over")\n'
        "design.board(mm(20), mm(10))\n"
        'design.part("R1", device="Fenolite:R_0603", value="1k").place(mm(5), mm(5))\n'
        'design.part("R2", device="Fenolite:R_0603", value="2k").place(mm(10), mm(5))\n',
        encoding="utf-8",
    )
    code, envelope, err = run(
        monkeypatch, str(folder / "design.py"), "--out", str(tmp_path / "out"), "--dry-run"
    )
    assert code == 0, err
    found = codes(envelope)
    assert found.count("device.overrides-builtin") == 1 and found.count("device.edited") == 1
    (row,) = envelope["result"]["devices"]  # type: ignore[index]
    assert row["origin"] == "authored" and row["edited"] is True and row["parts"] == ["R1", "R2"]
