# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite catalog import``: a device template from a symbol and a footprint (change c0248; capability
fenolite-component-catalog, "Device import", "Device import pins and pads", "Device import keeps hand
edits" and "Device provenance and edits")."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.catalog.devices import device_digest, is_edited, parse_device

IMPORT = (
    "catalog",
    "import",
    "--symbol",
    "Fenolite:Resistor",
    "--footprint",
    "Fenolite:Chip_0603",
    "--id",
    "Proj:R_0603",
    "--out",
    "devices/r.toml",
    "--timestamp",
    "2026-10-29T00:00:00Z",
)


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.chdir(cwd)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def test_import_a_template(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, err = run(monkeypatch, tmp_path, *IMPORT, "--confirm")
    assert code == 0, err
    written = [entry["path"] for entry in envelope["receipt"]["written"]]  # type: ignore[index]
    assert written == ["devices/r.toml"]
    text = (tmp_path / "devices" / "r.toml").read_text(encoding="utf-8")
    device = parse_device(text)
    assert device.evidence == "UNVERIFIED" and device.provenance is not None
    assert device.provenance.date == "2026-10-29" and device.provenance.tool == "fenolite catalog import"
    assert device.provenance.source == "Fenolite:Resistor Fenolite:Chip_0603"
    assert device.provenance.sha256 == device_digest(device) and not is_edited(device)
    assert [pin.function for pin in device.pins] == ["A", "B"] and device.pad_map == (("1", "1"), ("2", "2"))
    code, _, err = run(monkeypatch, tmp_path, *IMPORT, "--confirm")
    assert code == 0, err
    assert (tmp_path / "devices" / "r.toml").read_text(encoding="utf-8") == text


def test_import_plans_before_it_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, envelope, _ = run(monkeypatch, tmp_path, *IMPORT, "--dry-run")
    assert code == 0 and envelope["result"]["plan"] and not (tmp_path / "devices").exists()  # type: ignore[index]
    assert envelope["result"]["functions"] == ["A", "B"]  # type: ignore[index]


def test_a_pin_without_a_pad(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = list(IMPORT)
    args[args.index("Fenolite:Resistor")] = "Fenolite:Linear_Regulator"
    code, envelope, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 5
    found = [issue for issue in envelope["issues"] if issue["code"] == "catalog.pin-without-pad"]  # type: ignore[union-attr, index]
    assert len(found) == 1 and "pin 3" in found[0]["message"]  # type: ignore[index]
    assert not (tmp_path / "devices").exists()
    # --pin maps it: pin 3 joins pad 2 with pin 2 moved off it
    code, envelope, err = run(
        monkeypatch, tmp_path, *args, "--pin", "OUT=3:2", "--pin", "GND=2:1", "--pin", "IN=1:EPX"
    )
    assert code == 5 and "pad EPX" in json.dumps(envelope["issues"])


def test_pin_options_map_pads(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = list(IMPORT)
    args[args.index("Fenolite:Resistor")] = "Fenolite:LED"
    args[args.index("Fenolite:Chip_0603")] = "Fenolite:LED0603_Kingbright_APT1608SURCK"
    code, _, err = run(monkeypatch, tmp_path, *args, "--pin", "A=1:2", "--pin", "K=2:1", "--confirm")
    assert code == 0, err
    device = parse_device((tmp_path / "devices" / "r.toml").read_text(encoding="utf-8"))
    assert device.pin("A").pin_pads == (("1", "2"),) and device.pin("K").pin_pads == (("2", "1"),)
    assert device.ref_prefix == "D"


def test_pad_unmapped_is_a_warning(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    args = list(IMPORT)
    args[args.index("Fenolite:Chip_0603")] = "Fenolite:SOT23_6_TI_DBV0006A"
    code, envelope, err = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, err
    unmapped = [i for i in envelope["issues"] if i["code"] == "catalog.pad-unmapped"]  # type: ignore[union-attr, index]
    assert [i["severity"] for i in unmapped] == ["warning"] * 4  # type: ignore[index]


def test_grouped_names(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An authored symbol whose pins 2 and 9 are both named GND, through a project symbol library."""
    from fenolite.backends.kicad.sym import write_symbol_library
    from fenolite.dsl import Symbol, mm

    symbol = Symbol("Proj", "Reg9", reference="U")
    for index in range(1, 10):
        symbol.pin(
            str(index),
            "GND" if index in (2, 9) else f"IO{index}",
            at=(mm(0), mm(2.54 * index)),
            length=mm(2.54),
        )
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "Proj.kicad_sym").write_text(
        write_symbol_library([symbol.definition]), encoding="utf-8"
    )
    (tmp_path / "sym-lib-table").write_text(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "Proj") (type "KiCad") '
        '(uri "${KIPRJMOD}/lib/Proj.kicad_sym") (options "") (descr ""))\n)\n',
        encoding="utf-8",
    )
    args = list(IMPORT)
    args[args.index("Fenolite:Resistor")] = "Proj:Reg9"
    args[args.index("Fenolite:Chip_0603")] = "Fenolite:Header_1x10_P2.54"
    args[args.index("devices/r.toml")] = "u.toml"
    code, envelope, err = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, (err, envelope.get("issues"))
    device = parse_device((tmp_path / "u.toml").read_text(encoding="utf-8"))
    assert device.pin("GND").pin_pads == (("2", "2"), ("9", "9"))


def test_reimport_over_a_hand_edit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    path = tmp_path / "devices" / "r.toml"
    edited = path.read_text(encoding="utf-8").replace("(imported template, not reviewed)", "(reviewed)")
    path.write_text(edited, encoding="utf-8")
    assert is_edited(parse_device(edited))
    code, _, err = run(monkeypatch, tmp_path, *IMPORT, "--confirm")
    assert code == 7 and json.loads(err.strip().splitlines()[-1])["code"] == "FEN-7001"
    assert path.read_text(encoding="utf-8") == edited
    code, _, err = run(monkeypatch, tmp_path, *IMPORT, "--confirm", "--allow-lossy")
    assert code == 0, err
    assert not is_edited(parse_device(path.read_text(encoding="utf-8")))


def test_reimport_of_an_unedited_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    path = tmp_path / "devices" / "r.toml"
    before = parse_device(path.read_text(encoding="utf-8"))
    code, envelope, err = run(monkeypatch, tmp_path, *IMPORT, "--mpn", "X-1", "--confirm")
    assert code == 0, err
    after = parse_device(path.read_text(encoding="utf-8"))
    assert after.mpn == "X-1" and after.provenance is not None and before.provenance is not None
    assert after.provenance.sha256 != before.provenance.sha256 and 'mpn = "X-1"' in path.read_text(
        encoding="utf-8"
    )


def test_a_hand_edit_is_detected_by_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    assert run(monkeypatch, tmp_path, *IMPORT, "--confirm")[0] == 0
    path = tmp_path / "devices" / "r.toml"
    path.write_text(
        path.read_text(encoding="utf-8").replace("[pins]", 'mpn = "X-2"\n\n[pins]'), encoding="utf-8"
    )
    (tmp_path / "design.py").write_text(
        "from fenolite.dsl import Design, mm\n"
        'design = Design("edit")\n'
        "design.board(mm(20), mm(10))\n"
        'design.part("R1", device="Proj:R_0603", value="1k").place(mm(5), mm(5))\n',
        encoding="utf-8",
    )
    code, envelope, err = run(monkeypatch, tmp_path, "build", "design.py", "--out", "out", "--dry-run")
    assert code == 0, err
    assert [i["where"] for i in envelope["issues"] if i["code"] == "device.edited"] == ["Proj:R_0603"]  # type: ignore[union-attr, index]
    assert envelope["result"]["devices"][0]["edited"] is True  # type: ignore[index]


def test_import_usage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, tmp_path, "catalog", "import", "--symbol", "Fenolite:Resistor")
    assert code == 2 and "--footprint" in err
    code, _, err = run(monkeypatch, tmp_path, *IMPORT, "--pin", "bad")
    assert code == 2
