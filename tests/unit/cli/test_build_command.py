# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``build`` command (capability design-dsl, "Build command" and "Edited outputs are not
overwritten"; change c0011)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
FOOTPRINTS = ("Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603")


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


def blink_copy(tmp_path: Path) -> Path:
    """The blink folder copied next to the test libraries' relative location."""
    target = tmp_path / "repo" / "examples" / "blink_2layer"
    shutil.copytree(BLINK_DIR, target)
    shutil.copytree(ROOT / "tests" / "data" / "libs", tmp_path / "repo" / "tests" / "data" / "libs")
    return target / "design.py"


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, err = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out))
    assert code == 4 and env["result"]["plan"] and not out.exists()  # type: ignore[index]
    assert json.loads(err)["code"] == "FEN-4001"


def test_fields_project_the_plan(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """``--fields`` restricts ``result``, the dispatcher's ``plan`` included (living cli-contract)."""
    script, out = str(BLINK_DIR / "design.py"), str(tmp_path / "B")
    code, env, _ = run(monkeypatch, script, "--out", out, "--dry-run", "--fields", "design")
    assert code == 0 and env["result"] == {"design": "blink"}
    code, env, _ = run(monkeypatch, script, "--out", out, "--dry-run", "--fields", "plan")
    assert code == 0 and list(env["result"]) == ["plan"] and env["result"]["plan"]  # type: ignore[index]


def test_confirmed_build_and_rebuild(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out), "--confirm")
    assert code == 0
    written = sorted(Path(w["path"]).relative_to(out).as_posix() for w in env["receipt"]["written"])  # type: ignore[index]
    assert written == sorted(
        [
            "blink.kicad_dru", "blink.kicad_pcb", "blink.kicad_pro", "fp-lib-table",
            *(f"lib/Mini.pretty/{n}.kicad_mod" for n in FOOTPRINTS),
            *(f".fenolite/{n}.json" for n in ("board", "build", "circuit", "findings", "manufacturing")),
            ".fenolite/meta.json", ".fenolite/rules.json",
        ]
    )  # fmt: skip
    before = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    code, _, _ = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(out), "--confirm")
    assert code == 0
    after = {p: p.read_bytes() for p in out.rglob("*") if p.is_file()}
    assert {p: d for p, d in after.items() if p.suffix != ".bak"} == before
    result = env["result"]
    assert (
        result["design"] == "blink"
        and result["target"] == 10
        and result["libraries"]["Mini:Mini_R_0603"] == "project"
    )  # type: ignore[index]
    assert env["input"]["kind"] == "fenolite-dsl" and len(env["input"]["sha256"]) == 64  # type: ignore[index]


def test_output_folder_is_the_script_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    code, _, err = run(monkeypatch, str(BLINK_DIR / "design.py"), "--out", str(BLINK_DIR), "--dry-run")
    assert code == 2 and json.loads(err)["code"] == "FEN-2001"


def test_edited_board_refused_and_discarded(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "B"
    design = str(BLINK_DIR / "design.py")
    assert run(monkeypatch, design, "--out", str(out), "--confirm")[0] == 0
    board = out / "blink.kicad_pcb"
    edited = board.read_bytes() + b" "
    board.write_bytes(edited)
    for flags in (["--confirm"], ["--dry-run"], ["--allow-lossy", "--confirm"]):
        code, env, err = run(monkeypatch, design, "--out", str(out), *flags)
        assert code == 7 and json.loads(err)["code"] == "FEN-7001"
        assert [i["code"] for i in env["issues"]] == ["build.layout-exists"]  # type: ignore[index]
        assert board.read_bytes() == edited
    code, _, _ = run(monkeypatch, design, "--out", str(out), "--discard-layout", "--confirm")
    assert code == 0 and (out / "blink.kicad_pcb.bak").read_bytes() == edited


def test_dsl_edit_needs_no_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    out = tmp_path / "B"
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    script.write_text(script.read_text().replace("r1.place(mm(32), mm(9))", "r1.place(mm(33), mm(9))"))
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    assert "(at 133 109" in (out / "blink.kicad_pcb").read_text()


def test_lost_record(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    out = tmp_path / "B"
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    shutil.rmtree(out / ".fenolite")
    assert run(monkeypatch, str(script), "--out", str(out), "--confirm")[0] == 0
    shutil.rmtree(out / ".fenolite")
    script.write_text(script.read_text().replace("r1.place(mm(32), mm(9))", "r1.place(mm(33), mm(9))"))
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert code == 7 and any("blink.kicad_pcb" in i["where"] for i in env["issues"])  # type: ignore[index]


def test_errors_write_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = blink_copy(tmp_path)
    script.write_text(script.read_text() + '\ndesign.add(Net("gnd"))\n')
    out = tmp_path / "B"
    code, env, _ = run(monkeypatch, str(script), "--out", str(out), "--confirm")
    assert (
        code == 5 and "build.name-case-collision" in [i["code"] for i in env["issues"]] and not out.exists()
    )  # type: ignore[index]


def test_help_warns_about_untrusted_scripts(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli_main.main(["build", "--help"]) == 0
    assert "untrusted script" in capsys.readouterr().out
