# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pins and package records give symbols and footprints (change c0259; capability library-records, "Pins
records" and "Package records"). The records are authored for Fenolite as test data."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.catalog import get_footprint, get_symbol
from fenolite.catalog.records import (
    GeneratorMissingError,
    PackageRecord,
    PinsRecord,
    footprint_def,
    parse_record,
    shipped_tree,
    symbol_def,
)
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "tests" / "data" / "library"
TWO_PIN = (LIBRARY / "pins" / "two_pin.toml").read_text(encoding="utf-8")
TWO_PAD = (LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8")
SCRIPT = """\
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("records")
design.board(mm(20), mm(10))
x1 = Part("X1", "{symbol}", footprint="{footprint}", value="1")
design.add(x1)
connect(Net("A"), x1[1])
connect(Net("B"), x1[2])
x1.place(mm(10), mm(5))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def build(monkeypatch: pytest.MonkeyPatch, folder: Path, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(
        ["build", str(folder / "design.py"), "--out", str(folder.parent / "out"), *args, "--json"]
    )
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def project(tmp_path: Path, symbol: str, footprint: str, records: dict[str, str]) -> Path:
    folder = tmp_path / "proj"
    for name, text in records.items():
        path = folder / "devices" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    folder.mkdir(exist_ok=True)
    (folder / "design.py").write_text(SCRIPT.format(symbol=symbol, footprint=footprint), encoding="utf-8")
    return folder


def test_pin_placed_twice() -> None:
    text = TWO_PIN.replace('{ number = "2", at = ["5.08mm", "0mm"]', '{ number = "1", at = ["5.08mm", "0mm"]')
    with pytest.raises(FormatError) as caught:
        parse_record(text, file="pins/two_pin.toml")
    assert "pin 1" in str(caught.value) and getattr(caught.value, "code", "") == "FEN-3004"


def test_symbol_from_a_pins_record() -> None:
    record = parse_record(TWO_PIN)
    assert isinstance(record, PinsRecord)
    symbol = symbol_def(record)
    assert symbol.id == derived_id("sym", "fenolite.catalog", "Proj:Two_Pin")
    assert symbol.properties == {"Reference": "X", "Value": "Two_Pin", "Description": "Two-pin test symbol"}
    assert [(pin.number, pin.name, pin.position.x) for pin in symbol.pins] == [
        ("1", "A", -5_080_000),
        ("2", "B", 5_080_000),
    ]


def test_explicit_footprint() -> None:
    record = parse_record(TWO_PAD)
    assert isinstance(record, PackageRecord)
    footprint = footprint_def(record)
    assert [pad.id for pad in footprint.pads] == [
        derived_id("pad", "fenolite.catalog", "Two_Pad:1"),
        derived_id("pad", "fenolite.catalog", "Two_Pad:2"),
    ]
    assert footprint.kind == "smd" and footprint.graphics[0].id == derived_id(
        "gfx", "fenolite.catalog", "Two_Pad:F.CrtYd"
    )


def test_records_give_todays_catalog() -> None:
    tree = shipped_tree()
    chip = tree.get("package", "Fenolite:Chip_0603")
    resistor = tree.get("pins", "Fenolite:Resistor")
    assert isinstance(chip, PackageRecord) and isinstance(resistor, PinsRecord)
    assert footprint_def(chip) == get_footprint("Fenolite:Chip_0603")
    assert symbol_def(resistor) == get_symbol("Fenolite:Resistor")
    assert get_footprint("Fenolite:Chip_0603").description.endswith(
        "; land pattern remains INFERRED and requires part-specific review"
    )


def test_no_drawing_and_no_generator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    bare = TWO_PIN[: TWO_PIN.index("[symbol]")]
    record = parse_record(bare)
    assert isinstance(record, PinsRecord)
    with pytest.raises(GeneratorMissingError):
        symbol_def(record)
    folder = project(
        tmp_path,
        "Proj:Two_Pin",
        "Proj:Two_Pad",
        {"pins/two_pin.toml": bare, "packages/two_pad.toml": TWO_PAD},
    )
    code, envelope, _ = build(monkeypatch, folder, "--confirm")
    assert code == 5
    found = [issue for issue in envelope["issues"] if issue["code"] == "library.generator-missing"]  # type: ignore[union-attr, index]
    assert len(found) == 1 and found[0]["severity"] == "error" and "Proj:Two_Pin" in found[0]["message"]  # type: ignore[index]
    assert not (tmp_path / "out").exists()


def test_family_package_before_its_generator(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    family = TWO_PAD.replace('generator = "explicit"', 'generator = "gullwing"')
    folder = project(
        tmp_path,
        "Proj:Two_Pin",
        "Proj:Two_Pad",
        {"pins/two_pin.toml": TWO_PIN, "packages/two_pad.toml": family},
    )
    code, envelope, _ = build(monkeypatch, folder, "--dry-run")
    found = [issue for issue in envelope["issues"] if issue["code"] == "library.generator-missing"]  # type: ignore[union-attr, index]
    assert code == 5 and len(found) == 1
    assert "Proj:Two_Pad" in found[0]["message"] and "gullwing" in found[0]["message"]  # type: ignore[index]


def test_project_records_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = project(
        tmp_path,
        "Proj:Two_Pin",
        "Proj:Two_Pad",
        {"pins/two_pin.toml": TWO_PIN, "packages/two_pad.toml": TWO_PAD},
    )
    code, envelope, err = build(monkeypatch, folder, "--dry-run")
    assert code == 0, err
    libraries = envelope["result"]["libraries"]  # type: ignore[index]
    assert libraries["Proj:Two_Pin"] == "authored" and libraries["Proj:Two_Pad"] == "authored"
    files = [row["path"] for row in envelope["result"]["device_files"]]  # type: ignore[index]
    assert files == ["devices/packages/two_pad.toml", "devices/pins/two_pin.toml"]
    shutil.rmtree(folder / "devices")
