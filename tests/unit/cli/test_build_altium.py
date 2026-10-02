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
from _altium import SAMPLE, variant_script

import fenolite.cli.main as cli_main
from fenolite.backends.altium import cfb

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
BLINK = ROOT / "examples" / "blink_2layer" / "design.py"
CACHE = (".fenolite/board.json", ".fenolite/build.json", ".fenolite/circuit.json", ".fenolite/findings.json",
         ".fenolite/manufacturing.json", ".fenolite/meta.json", ".fenolite/rules.json")  # fmt: skip
PLANNED = ("altium_sample.PrjPcb", "altium_sample.SchDoc", *CACHE)


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
    assert result["schematic_format"] == "binary"
    assert {kinds[Path(c).name] for c in CACHE} == {"fenolite"}
    assert list(result) == [
        "design", "target", "out", "files", "components", "nets", "labels", "power_ports", "sheet", "kept",
        "schematic_format", "experimental", "script_output", "plan",
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
    assert run(monkeypatch, str(SAMPLE), *ascii_args)[0] == 0


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
