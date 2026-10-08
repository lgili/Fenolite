# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog's default pin-to-pad map (capability fenolite-component-catalog, "Default pin-to-pad map of
the cathode-first lands", and design-dsl, "Default pin-to-pad map is reported"; change c0147).

A part of an anode-first catalog symbol on a catalog land whose pad 1 is the cathode, without a ``pad_map``,
gets the anode pin on the anode pad and the cathode pin on the cathode pad, in the KiCad and the Altium
build alike, and each such part is reported once with ``build.pad-map-default``. An explicit map wins."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from _altium_built import LIBRARY_VARIABLES
from _altium_padmap import pad_nets as altium_pad_nets

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.catalog import CATHODE_FIRST_PAD_MAP
from fenolite.cli._padmap import apply_default_pad_maps
from fenolite.dsl import Design, Net, Part, connect, to_model

CODE = "build.pad-map-default"
SCRIPT = """\
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("polarity")
design.board(mm(40), mm(20))
d1 = Part("D1", "Fenolite:LED", footprint="Fenolite:LED0603_Kingbright_APT1608SURCK", value="red"{d1})
d2 = Part("D2", "Fenolite:Schottky_Diode", footprint="Fenolite:SOD128_Nexperia_CFP5", value="1A"{d2})
d3 = Part("D3", "Fenolite:Diode", footprint="Fenolite:SOD123_Diodes", value="1A")
r1 = Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="1k")
design.add(d1, d2, d3, r1)
connect(Net("VA"), r1[1], d1["A"], d2["A"], d3["A"])
connect(Net("GND"), r1[2], d1["K"], d2["K"], d3["K"])
d1.place(mm(6), mm(10))
d2.place(mm(16), mm(10))
d3.place(mm(26), mm(10))
r1.place(mm(34), mm(10))
"""
TARGETS = ("kicad", "altium")
LANDS = {
    "Fenolite:LED0603_Kingbright_APT1608SURCK": "D1",
    "Fenolite:SOD128_Nexperia_CFP5": "D2",
    "Fenolite:SOD123_Diodes": "D3",
    "Fenolite:Chip_0603": "R1",
}
"""Land → reference in the script; the board file's reader gives the footprints, each land used once."""
ANODE_ON_PAD_2 = {"1": "GND", "2": "VA"}
"""The pad nets of a cathode-first land with its anode on ``VA``: pad 1 is the cathode."""


def script(folder: Path, d1: str = "", d2: str = "") -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "design.py"
    path.write_text(SCRIPT.format(d1=d1, d2=d2), encoding="utf-8")
    return path


def build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str, path: Path
) -> tuple[dict[str, dict[str, str]], list[dict[str, str]]]:
    """``(reference → pad → net name, issues)`` of the ``--confirm`` build of ``path`` for ``target``."""
    config = tmp_path / "kicad-config"
    config.mkdir(exist_ok=True)
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in LIBRARY_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    folder = tmp_path / f"built-{target}"
    stdout, stderr = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr("sys.stdout", stdout)
        patch.setattr("sys.stderr", stderr)
        code = cli_main.main(
            ["build", str(path), "--out", str(folder), "--target", target, "--confirm", "--json"]
        )
    assert code == 0, stderr.getvalue()
    issues = json.loads(stdout.getvalue())["issues"]
    nets: dict[str, dict[str, str]] = {}
    if target == "altium":
        for (ref, pad), name in altium_pad_nets(folder).items():
            nets.setdefault(ref, {})[pad] = name
        return nets, issues
    restored = read_board((folder / "polarity.kicad_pcb").read_text(encoding="utf-8"))
    assert restored.board is not None
    names = {net.id: net.name for net in restored.circuit.nets}
    for footprint in restored.board.footprints:
        for pad in footprint.pads:
            nets.setdefault(LANDS[footprint.lib_ref], {})[pad.number] = names.get(pad.net_id or "", "")
    return nets, issues


def defaults(issues: list[dict[str, str]]) -> list[dict[str, str]]:
    return [found for found in issues if found["code"] == CODE]


@pytest.mark.parametrize("target", TARGETS)
def test_the_default_map_puts_the_anode_on_the_anode_pad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str
) -> None:
    """Scenario "Part without a map": both cathode-first parts get the map; the others keep their pads."""
    nets, _issues = build(monkeypatch, tmp_path, target, script(tmp_path / "script"))
    assert nets["D1"] == ANODE_ON_PAD_2 and nets["D2"] == ANODE_ON_PAD_2
    assert nets["D3"] == {"1": "VA", "2": "GND"}  # SOD123: pad 1 is the anode, no map
    assert nets["R1"] == {"1": "VA", "2": "GND"}


@pytest.mark.parametrize("target", TARGETS)
def test_one_warning_per_defaulted_part(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str) -> None:
    """Scenario "The default is reported": one warning per part, naming the part, the land and the map."""
    _nets, issues = build(monkeypatch, tmp_path, target, script(tmp_path / "script"))
    found = defaults(issues)
    assert [(i["where"], i["severity"]) for i in found] == [("D1", "warning"), ("D2", "warning")]
    first = found[0]
    assert first["message"] == (
        "D1 (Fenolite:LED on Fenolite:LED0603_Kingbright_APT1608SURCK) gives no pad_map; the build applies "
        'the catalog\'s map pad_map={"1": "2", "2": "1"} (pin 1 on pad 2, pin 2 on pad 1): pad 1 of this '
        "land is the cathode"
    )
    assert first["hint"] == (
        'write pad_map={"1": "2", "2": "1"} on the part to keep this map and silence the warning, and '
        "connect it by pin name (A, K); a design that wired it by pin number for the pad order of earlier "
        'builds keeps that order with pad_map={"1": "1", "2": "2"}'
    )
    assert "Fenolite:SOD128_Nexperia_CFP5" in found[1]["message"]


@pytest.mark.parametrize("target", TARGETS)
def test_an_explicit_map_wins_and_is_not_reported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: str
) -> None:
    """Scenario "Explicit map": the identity map keeps the pad order of earlier builds; the written default
    map gives the default's pads; neither part is reported."""
    path = script(
        tmp_path / "script", d1=', pad_map={"1": "1", "2": "2"}', d2=', pad_map={"1": "2", "2": "1"}'
    )
    nets, issues = build(monkeypatch, tmp_path, target, path)
    assert nets["D1"] == {"1": "VA", "2": "GND"}
    assert nets["D2"] == ANODE_ON_PAD_2
    assert defaults(issues) == []


def _design(**pad_map: dict[str, str]) -> Design:
    design = Design("polarity")
    for ref, symbol, footprint in (
        ("D1", "Fenolite:LED", "Fenolite:LED0805_Kingbright_APT2012SURCK"),
        ("D2", "Fenolite:Zener_Diode", "Fenolite:SOD128_Nexperia_CFP5"),
        ("D3", "Fenolite:LED", "Fenolite:Chip_0603"),
        ("D4", "Fenolite:Diode", "Fenolite:DO41_P10.16_Diodes"),
        ("C1", "Fenolite:Capacitor_Polarized", "Fenolite:SOD128_Nexperia_CFP5"),
    ):
        design.add(Part(ref, symbol, footprint=footprint, pad_map=pad_map.get(ref)))
    connect(Net("GND"), *(design.parts[ref][2] for ref in ("D1", "D2", "D3", "D4", "C1")))
    return design


def _maps(
    design: Design, **authored: tuple[str, ...]
) -> tuple[dict[str, tuple[tuple[str, str], ...]], list[str]]:
    model, applied = apply_default_pad_maps(to_model(design), **authored)
    return {c.ref: c.pin_pad_map for c in model.circuit.components}, [a.ref for a in applied]


def test_only_anode_first_symbols_on_cathode_first_lands_get_the_map() -> None:
    """Scenario "Other lands and symbols": a land without polarity, a land with pad 1 the anode, and a
    symbol that is not anode-first keep the identity map."""
    maps, applied = _maps(_design())
    assert applied == ["D1", "D2"]
    assert maps == {"C1": (), "D1": CATHODE_FIRST_PAD_MAP, "D2": CATHODE_FIRST_PAD_MAP, "D3": (), "D4": ()}


def test_an_explicit_map_is_kept_as_written() -> None:
    maps, applied = _maps(_design(D1={"1": "1", "2": "2"}))
    assert maps["D1"] == (("1", "1"), ("2", "2")) and applied == ["D2"]


def test_an_authored_symbol_or_land_of_the_same_lib_id_gets_no_default() -> None:
    """A design that authors ``Fenolite:LED`` or the land itself does not use the catalog's definition."""
    maps, applied = _maps(_design(), authored_symbols=("Fenolite:LED",))
    assert applied == ["D2"] and maps["D1"] == ()
    maps, applied = _maps(_design(), authored_footprints=("Fenolite:SOD128_Nexperia_CFP5",))
    assert applied == ["D1"] and maps["D2"] == ()


def test_a_model_without_such_a_part_is_returned_as_it_is() -> None:
    model = to_model(_design(D1={"1": "2", "2": "1"}, D2={"1": "2", "2": "1"}))
    assert apply_default_pad_maps(model) == (model, ())


def test_the_kit_samples_are_not_reported() -> None:
    """The four kit samples carry their map (change c0144): the default leaves their model unchanged."""
    from fenolite.cli._script import run_design_script

    root = Path(__file__).resolve().parents[3] / "examples" / "kit"
    for sample in ("board6", "flat", "libs", "routed", "tree"):
        design = run_design_script(root / sample / "design.py").design
        model = to_model(design)
        assert apply_default_pad_maps(
            model, authored_symbols=design.symbols, authored_footprints=design.footprints
        ) == (model, ()), sample
