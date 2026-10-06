# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build --target altium`` (capability altium-build: "Altium build target", "Altium build
issue codes", "Altium build evidence" and "Altium sample project"; change c0032; "Altium schematic format
option"; change c0033)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from _altium import HIER, SAMPLE, variant_script

import fenolite.cli.main as cli_main
from fenolite.backends.altium import cfb

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"
CACHE = (".fenolite/board.json", ".fenolite/build.json", ".fenolite/circuit.json", ".fenolite/findings.json",
         ".fenolite/manufacturing.json", ".fenolite/meta.json", ".fenolite/rules.json")  # fmt: skip
PLANNED = ("altium_sample.PrjPcb", "altium_sample.SchDoc", "FenoliteSample.SchLib", *CACHE)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def files_under(folder: Path) -> list[str]:
    return sorted(p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file())


def test_dry_run_of_the_sample(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    out.mkdir()
    code, env, _ = run(monkeypatch, str(SAMPLE), "--out", str(out), "--target", "altium", "--dry-run")
    assert code == 0
    result = env["result"]
    assert isinstance(result, dict)
    plan = sorted(Path(p["path"]).relative_to(out).as_posix() for p in result["plan"])
    assert plan == sorted(PLANNED)
    assert result["target"] == "altium" and result["experimental"] is True
    assert list(out.iterdir()) == []
    kinds = {Path(p["path"]).name: p["kind"] for p in result["plan"]}
    assert kinds["altium_sample.PrjPcb"] == "altium_prjpcb"
    assert kinds["altium_sample.SchDoc"] == "altium_schdoc_binary"
    assert kinds["FenoliteSample.SchLib"] == "altium_schlib"
    assert result["schematic_format"] == "binary"
    assert {kinds[Path(c).name] for c in CACHE} == {"fenolite"}
    assert result["footprints"] == 0 and result["pcb_document"] is None
    assert not [p for p in plan if p.endswith((".PcbLib", ".PcbDoc"))]
    assert list(result) == [
        "design", "target", "out", "files", "components", "nets", "labels", "power_ports", "no_connects",
        "sheet", "kept", "schematic_format", "sheet_mode", "sheets", "ports", "sheet_entries", "harnesses",
        "libraries", "symbols", "footprints", "pcb_document", "copper", "outjob", "drawing_sheet",
        "experimental", "script_output", "plan",
    ]  # fmt: skip


def test_binary_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(SAMPLE), "--out", str(out), "--target", "altium", "--confirm")
    result = env["result"]
    assert code == 0 and isinstance(result, dict) and result["schematic_format"] == "binary"
    assert (out / "altium_sample.SchDoc").read_bytes() == (
        GOLDEN / "binary" / "altium_sample.SchDoc"
    ).read_bytes()
    assert (out / "altium_sample.PrjPcb").read_bytes() == (GOLDEN / "altium_sample.PrjPcb").read_bytes()


def test_ascii_on_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    args = ("--out", str(out), "--target", "altium", "--altium-format", "ascii")
    code, env, _ = run(monkeypatch, str(SAMPLE), *args, "--dry-run")
    result = env["result"]
    assert code == 0 and isinstance(result, dict) and result["schematic_format"] == "ascii"
    kinds = {Path(p["path"]).name: p["kind"] for p in result["plan"]}
    assert kinds["altium_sample.SchDoc"] == "altium_schdoc_ascii"
    code, env, _ = run(monkeypatch, str(SAMPLE), *args, "--confirm")
    assert code == 0
    assert (out / "altium_sample.SchDoc").read_bytes() == (GOLDEN / "altium_sample.SchDoc").read_bytes()


@pytest.mark.parametrize("target", [(), ("--target", "kicad")], ids=["default-target", "kicad"])
def test_option_without_the_altium_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: tuple[str, ...]
) -> None:
    out = tmp_path / "B"
    code, env, err = run(
        monkeypatch, str(BLINK), "--out", str(out), *target, "--altium-format", "binary", "--dry-run"
    )
    error = json.loads(err)
    assert code == 2 and error["code"] == "FEN-2001" and error["where"] == "--altium-format"
    assert env["ok"] is False
    assert not out.exists()


def test_unknown_altium_format(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    args = ("--out", str(out), "--target", "altium", "--altium-format", "utf8", "--dry-run")
    code, _, err = run(monkeypatch, str(SAMPLE), *args)
    assert code == 2 and json.loads(err)["code"] == "FEN-2001" and not out.exists()


def test_too_large_exits_5(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cfb, "MAX_FAT_SECTORS", 0)
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(SAMPLE), "--out", str(out), "--target", "altium", "--confirm")
    issues = env["issues"]
    assert code == 5 and json.loads(err)["code"] == "FEN-5001" and isinstance(issues, list)
    assert "altium.schematic-too-large" in [i["code"] for i in issues]
    assert not out.exists() or files_under(out) == []
    ascii_args = ("--out", str(out), "--target", "altium", "--altium-format", "ascii", "--confirm")
    code, env, _ = run(monkeypatch, str(SAMPLE), *ascii_args)
    codes = [i["code"] for i in env["issues"]]  # type: ignore[union-attr]
    assert code == 5 and "altium.library-too-large" in codes and "altium.schematic-too-large" not in codes


def test_confirmed_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(SAMPLE), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0
    receipt = env["receipt"]
    assert isinstance(receipt, dict)
    written = {Path(w["path"]).relative_to(out).as_posix(): w["sha256"] for w in receipt["written"]}
    assert sorted(written) == sorted(PLANNED) == files_under(out)
    for rel, digest in written.items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == digest


def test_sample_builds_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = run(
        monkeypatch, str(SAMPLE), "--out", str(tmp_path / "B"), "--target", "altium", "--confirm"
    )
    result, issues = env["result"], env["issues"]
    assert isinstance(result, dict) and isinstance(issues, list)
    assert code == 0 and (result["components"], result["nets"], result["power_ports"], result["labels"]) == (
        8,
        6,
        13,
        6,
    )
    assert result["sheet"] == "A4" and all(i["severity"] == "info" for i in issues)


def test_sample_envelope(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _, env, _ = run(monkeypatch, str(SAMPLE), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run")
    evidence = env["evidence"]
    assert isinstance(evidence, dict) and evidence["level"] == "INFERRED"
    assert {"H-A-SCH-OPEN", "H-A-SCH-NETS", "H-A-PRJ-OPEN"} <= set(evidence["hypotheses"])
    assert env["input"] == {
        "path": str(SAMPLE),
        "sha256": hashlib.sha256(SAMPLE.read_bytes()).hexdigest(),
        "kind": "fenolite-dsl",
        "format_version": None,
    }


def test_unknown_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, _, err = run(monkeypatch, str(SAMPLE), "--out", str(out), "--target", "eagle", "--dry-run")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001" and not out.exists()


def test_default_target_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = str(tmp_path / "B")
    code, default, _ = run(monkeypatch, str(BLINK), "--out", out, "--dry-run")
    code2, explicit, _ = run(monkeypatch, str(BLINK), "--out", out, "--dry-run", "--target", "kicad")
    assert code == code2 == 0
    assert default["result"] == explicit["result"]
    result = default["result"]
    assert isinstance(result, dict) and result["target"] == 10
    assert not [p for p in result["plan"] if p["path"].endswith((".SchDoc", ".PrjPcb"))]


def test_no_library_is_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = run(
        monkeypatch, str(SAMPLE), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run"
    )
    issues = env["issues"]
    assert code == 0 and isinstance(issues, list)
    assert not [i for i in issues if i["code"].startswith("kicad.lib.")]


def test_kicad_options_change_no_byte(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = str(tmp_path / "B")
    base = ["--out", out, "--target", "altium", "--dry-run"]
    plans = []
    for extra in (
        [],
        ["--kicad-version", "9"],
        ["--allow-lossy"],
        ["--seed", "7", "--timestamp", "2027-01-01"],
    ):
        code, env, _ = run(monkeypatch, str(SAMPLE), *base, *extra)
        result = env["result"]
        assert code == 0 and isinstance(result, dict)
        plans.append([(p["path"], p["sha256"]) for p in result["plan"]])
    assert all(plan == plans[0] for plan in plans)


def test_malformed_lib_id_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = variant_script(tmp_path / "V", 'f"{SCHLIB}:HDR2"', '"HDR2"')
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--confirm")
    issues = env["issues"]
    assert code == 5 and isinstance(issues, list) and json.loads(err)["code"] == "FEN-5001"
    assert "altium.lib-id-form" in [i["code"] for i in issues]
    assert not out.exists() or files_under(out) == []


def test_items_not_lowered_are_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    extra = (
        "\nfrom fenolite.dsl import mm\n"
        "design.board(mm(50), mm(30))\n"
        "j1.place(mm(5), mm(5))\n"
        'design.rules.netclass("PWR", clearance=mm(0.3), nets=(vin, gnd))\n'
    )
    script = variant_script(tmp_path / "V", append=extra)
    code, env, _ = run(
        monkeypatch, str(script), "--out", str(tmp_path / "B"), "--target", "altium", "--confirm"
    )
    issues = env["issues"]
    assert code == 0 and isinstance(issues, list)
    found = [i for i in issues if i["code"] == "altium.not-lowered"]
    assert [i["where"] for i in found] == ["board", "placements", "rules"]
    assert all(i["severity"] == "info" for i in found)


BLINK = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def test_dry_run_with_kicad_footprints(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``altium-build`` "Altium build target", "Dry run with KiCad footprints" (change c0035)."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    out = tmp_path / "B"
    out.mkdir()
    code, env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--target", "altium", "--dry-run")
    assert code == 0
    result = env["result"]
    assert isinstance(result, dict)
    kinds = {Path(p["path"]).name: p["kind"] for p in result["plan"]}
    assert kinds["blink.PcbLib"] == "altium_pcblib" and kinds["blink.PcbDoc"] == "altium_pcbdoc"
    assert {"blink.PrjPcb", "blink.SchDoc", "blink.SchLib"} <= set(kinds)
    assert result["footprints"] == 3 and result["pcb_document"] == str(out / "blink.PcbDoc")
    assert list(out.iterdir()) == []


def test_edited_library_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``altium-build`` "PCB library outputs", "Edited library refused" (change c0035)."""
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    out = tmp_path / "B"
    code, _env, _ = run(monkeypatch, str(BLINK), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0
    library = out / "blink.PcbLib"
    data = bytearray(library.read_bytes())
    data[-1] ^= 0xFF
    library.write_bytes(bytes(data))
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    code, _env, err = run(monkeypatch, str(BLINK), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 7 and "FEN-7001" in err and "blink.PcbLib" in err
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before


# --- the sheets option (change c0037, "Altium sheets option") ----------------------------------------

HIER_SHEETS = ["altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"]
HIER_HARNESSES = ["altium_hier_flash.Harness", "altium_hier_mcu.Harness"]
MODULES = ("--target", "altium", "--altium-sheets", "modules")


def hier_variant(folder: Path, old: str = "", new: str = "", *, append: str = "") -> Path:
    """A copy of the hierarchy sample script under ``folder`` with one edit."""
    text = HIER.read_text(encoding="utf-8")
    if old:
        assert old in text, old
        text = text.replace(old, new)
    folder.mkdir(parents=True, exist_ok=True)
    script = folder / "design.py"
    script.write_text(text + append, encoding="utf-8")
    return script


def test_flat_by_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Flat by default"."""
    out = tmp_path / "B"
    out.mkdir()
    code, env, _ = run(monkeypatch, str(HIER), "--out", str(out), "--target", "altium", "--dry-run")
    result = env["result"]
    assert code == 0 and isinstance(result, dict)
    assert result["sheet_mode"] == "flat" and result["sheets"] == ["altium_hier.SchDoc"]
    assert (result["ports"], result["sheet_entries"], result["harnesses"]) == (0, 0, 0)
    assert list(out.iterdir()) == []
    flat = ("--target", "altium", "--altium-sheets", "flat")
    code, explicit, _ = run(monkeypatch, str(HIER), "--out", str(out), *flat, "--dry-run")
    assert code == 0 and explicit["result"] == result


def test_modules_on_request(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenarios "Modules on request" and "Sample builds without warnings"."""
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(HIER), "--out", str(out), *MODULES, "--confirm")
    result, receipt, issues = env["result"], env["receipt"], env["issues"]
    assert code == 0 and isinstance(result, dict) and isinstance(receipt, dict) and isinstance(issues, list)
    assert result["sheet_mode"] == "modules" and result["sheets"] == HIER_SHEETS
    assert (result["ports"], result["sheet_entries"], result["harnesses"]) == (5, 5, 1)
    assert (result["components"], result["nets"]) == (6, 9)
    assert not [i for i in issues if i["severity"] in ("warning", "error")]
    assert len(receipt["written"]) == len([p for p in out.rglob("*") if p.is_file()])
    dry = ("--out", str(tmp_path / "P"), *MODULES, "--dry-run")
    _, planned, _ = run(monkeypatch, str(HIER), *dry)
    kinds = {Path(p["path"]).name: p["kind"] for p in planned["result"]["plan"]}  # type: ignore[index]
    assert {kinds[name] for name in HIER_HARNESSES} == {"altium_harness"}
    assert {kinds[name] for name in HIER_SHEETS} == {"altium_schdoc_binary"}
    assert all((out / name).read_bytes() == b"SPI=CS,MISO,MOSI,SCK\r\n" for name in HIER_HARNESSES)
    expected = [*HIER_SHEETS, *HIER_HARNESSES, "altium_hier.PrjPcb", "FenoliteHier.SchLib", *CACHE]
    assert files_under(out) == sorted(expected)
    record = json.loads((out / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert sorted(record["files"]) == sorted(
        [*HIER_SHEETS, *HIER_HARNESSES, "altium_hier.PrjPcb", "FenoliteHier.SchLib"]
    )
    ascii_args = ("--out", str(tmp_path / "A"), *MODULES, "--altium-format", "ascii", "--dry-run")
    code, env, _ = run(monkeypatch, str(HIER), *ascii_args)
    plan = {Path(p["path"]).name: p["kind"] for p in env["result"]["plan"]}  # type: ignore[index]
    assert code == 0 and {plan[name] for name in HIER_SHEETS} == {"altium_schdoc_ascii"}
    assert not [name for name in plan if name.endswith(".Harness")]


def test_result_keys_of_the_sheets_option(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = run(monkeypatch, str(HIER), "--out", str(tmp_path / "B"), *MODULES, "--dry-run")
    result = env["result"]
    assert code == 0 and isinstance(result, dict)
    keys = list(result)
    at = keys.index("schematic_format")
    assert keys[at + 1 : at + 6] == ["sheet_mode", "sheets", "ports", "sheet_entries", "harnesses"]


@pytest.mark.parametrize("target", [(), ("--target", "kicad")], ids=["default-target", "kicad"])
def test_sheets_option_without_the_altium_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: tuple[str, ...]
) -> None:
    """Scenario "Option without the Altium target"."""
    out = tmp_path / "B"
    code, env, err = run(
        monkeypatch, str(BLINK), "--out", str(out), *target, "--altium-sheets", "modules", "--dry-run"
    )
    error = json.loads(err)
    assert code == 2 and error["code"] == "FEN-2001" and error["where"] == "--altium-sheets"
    assert env["ok"] is False and not out.exists()


def test_unknown_altium_sheets_value(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    args = ("--out", str(out), "--target", "altium", "--altium-sheets", "pages", "--dry-run")
    code, _, err = run(monkeypatch, str(HIER), *args)
    assert code == 2 and json.loads(err)["code"] == "FEN-2001" and not out.exists()


def test_switching_the_mode_is_not_an_edit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Switching the mode is not an edit"; a sheet the new plan no longer holds is left in place
    and is not in the new build record."""
    out = tmp_path / "B"
    code, _, _ = run(monkeypatch, str(HIER), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0
    flat_top = (out / "altium_hier.SchDoc").read_bytes()
    code, env, _ = run(monkeypatch, str(HIER), "--out", str(out), *MODULES, "--confirm")
    assert code == 0
    top = (out / "altium_hier.SchDoc").read_bytes()
    reference = tmp_path / "R"
    assert run(monkeypatch, str(HIER), "--out", str(reference), *MODULES, "--confirm")[0] == 0
    assert top == (reference / "altium_hier.SchDoc").read_bytes() != flat_top
    codes = [i["code"] for i in env["issues"]]  # type: ignore[union-attr]
    assert "altium.project-kept" in codes and "altium.sheets-not-in-project" in codes
    module_sheet = (out / "altium_hier_flash.SchDoc").read_bytes()
    code, _, _ = run(monkeypatch, str(HIER), "--out", str(out), "--target", "altium", "--confirm")
    assert code == 0 and (out / "altium_hier.SchDoc").read_bytes() == flat_top
    assert (out / "altium_hier_flash.SchDoc").read_bytes() == module_sheet, "left in place"
    record = json.loads((out / ".fenolite" / "build.json").read_text(encoding="utf-8"))
    assert sorted(record["files"]) == ["FenoliteHier.SchLib", "altium_hier.SchDoc"]


@pytest.mark.parametrize("name", ["altium_hier_mcu.SchDoc", "altium_hier_flash.Harness"])
def test_edited_module_sheet_or_harness_file_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    """Every planned sheet and harness file follows the edited-output rule on its own."""
    out = tmp_path / "B"
    assert run(monkeypatch, str(HIER), "--out", str(out), *MODULES, "--confirm")[0] == 0
    target = out / name
    original = target.read_bytes()
    edited = original + b"\r\n"
    target.write_bytes(edited)
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    code, _, err = run(monkeypatch, str(HIER), "--out", str(out), *MODULES, "--confirm")
    assert code == 7 and "FEN-7001" in err and name in err
    assert {p: p.read_bytes() for p in out.rglob("*") if p.is_file()} == before
    code, _, _ = run(monkeypatch, str(HIER), "--out", str(out), *MODULES, "--discard-layout", "--confirm")
    assert code == 0 and target.read_bytes() == original
    assert target.with_name(name + ".bak").read_bytes() == edited


def test_net_in_two_harnesses_exits_5(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Net in two harnesses"."""
    script = hier_variant(tmp_path / "V", append='\ndesign.add(Harness("DBG", {"CLK": spi_sck}))\n')
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(script), "--out", str(out), "--target", "altium", "--confirm")
    issues = env["issues"]
    assert code == 5 and isinstance(issues, list) and json.loads(err)["code"] == "FEN-5001"
    (found,) = [i for i in issues if i["code"] == "altium.harness-net-shared"]
    assert all(text in found["message"] for text in ("SPI_SCK", "SPI", "DBG"))
    assert not out.exists() or files_under(out) == []


def test_hierarchy_envelope_evidence(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Envelope evidence"."""
    _, env, _ = run(monkeypatch, str(HIER), "--out", str(tmp_path / "B"), *MODULES, "--dry-run")
    evidence = env["evidence"]
    assert isinstance(evidence, dict) and evidence["level"] == "INFERRED"
    assert {"H-A-SCH-HIER-OPEN", "H-A-SCH-HIER-ECO", "H-A-SCH-HARN-OPEN"} <= set(evidence["hypotheses"])


def test_layer_count_from_the_script(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``altium-build`` "Copper in an Altium build", "Layer count from the script" (change c0038)."""
    from _altium import blink_tree

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    project = blink_tree(tmp_path / "tree")
    script = project / "design.py"
    text = script.read_text(encoding="utf-8")
    assert "design.board(mm(50), mm(30))" in text
    script.write_text(text.replace("design.board(mm(50), mm(30))", "design.board(mm(50), mm(30), copper=4)"))
    code, env, _ = run(
        monkeypatch, str(script), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run"
    )
    assert code == 0
    result = env["result"]
    assert isinstance(result, dict)
    copper = result["copper"]
    assert copper["layers"] == 4 and copper["source"] == "none" and copper["from"] is None
    assert copper["planes"] == {} and copper["placements_from_board"] == 0
    assert [copper[key] for key in ("tracks", "arcs", "vias", "zones")] == [0, 0, 0, 0]


def test_plane_in_an_altium_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``design-dsl`` "Planes in a build", "Plane in an Altium build" (change c0038)."""
    from _altium import blink_tree

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    script = blink_tree(tmp_path / "tree") / "design.py"
    lines = script.read_text(encoding="utf-8").splitlines()
    nets = next(line for line in lines if line.startswith("vin, gnd, led_drv, led_a = "))
    lines.remove(nets)
    board = lines.index("design.board(mm(50), mm(30))")
    lines[board] = nets + '\ndesign.board(mm(50), mm(30), copper=4, planes={"In1.Cu": gnd})'
    script.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, env, _ = run(
        monkeypatch, str(script), "--out", str(tmp_path / "B"), "--target", "altium", "--dry-run"
    )
    assert code == 0
    result = env["result"]
    assert isinstance(result, dict) and result["copper"]["planes"] == {"In1.Cu": "GND"}
    issues = env["issues"]
    assert isinstance(issues, list) and "build.plane-not-lowered" not in [i["code"] for i in issues]
