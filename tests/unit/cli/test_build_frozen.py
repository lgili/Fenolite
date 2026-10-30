# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite build --frozen`` (capability cli-contract, "Frozen builds" and "Frozen error code"; change
c0249)."""

from __future__ import annotations

import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.cli.errors import REGISTRY
from fenolite.cli.exitcodes import ExitCode

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "lock"
NEW_PART = '\nextra = led.part(name="r_extra", lib_id="Fenolite:Resistor", footprint="Fenolite:Chip_0603")\n'


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, object], str]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def copy(tmp_path: Path, *, lock: bool = True, extra: str = "") -> Path:
    folder = tmp_path / "ex"
    folder.mkdir()
    (folder / "design.py").write_text((EXAMPLE / "design.py").read_text(encoding="utf-8") + extra, "utf-8")
    if lock:
        shutil.copy(EXAMPLE / "design.lock", folder / "design.lock")
    return folder


def test_frozen_build_with_a_new_part(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, extra=NEW_PART)
    before = (folder / "design.lock").read_bytes()
    code, env, err = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--dry-run")
    assert code == 7
    error = json.loads(err)
    assert error["code"] == "FEN-7004" and error["retryable"] is False and "--frozen" in error["hint"]
    changed = [i for i in env["issues"] if i["code"] == "lock.changed"]  # type: ignore[union-attr]
    assert len(changed) == 1 and changed[0]["severity"] == "error"
    assert "led/r_extra" in changed[0]["where"] and "assigned" in changed[0]["message"]
    assert not (tmp_path / "B").exists() and (folder / "design.lock").read_bytes() == before
    code, _, err = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--confirm")
    assert code == 7 and not (tmp_path / "B").exists() and (folder / "design.lock").read_bytes() == before


def test_frozen_build_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy(tmp_path)
    code, env, err = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--confirm")
    assert code == 0, err
    assert env["result"]["lock"]["frozen"] is True  # type: ignore[index]
    assert not [w for w in env["receipt"]["written"] if w["path"].endswith(".lock")]  # type: ignore[index]


def test_frozen_build_of_the_example_in_place(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, err = run(
        monkeypatch, "build", str(EXAMPLE / "design.py"), "--out", "B", "--frozen", "--dry-run"
    )
    assert code == 0, err
    assert env["result"]["lock"] == {  # type: ignore[index]
        "file": "design.lock",
        "exists": True,
        "written": False,
        "frozen": True,
        "changes": [],
    }


def test_missing_lock_under_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=False)
    code, env, err = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--dry-run")
    assert code == 7 and json.loads(err)["code"] == "FEN-7004"
    assert len([i for i in env["issues"] if i["code"] == "lock.changed"]) == 6  # type: ignore[union-attr]
    assert not (folder / "design.lock").exists()


def test_formatting_only_is_no_change(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    path = folder / "design.lock"
    text = path.read_text(encoding="utf-8").replace('"J1" = "J1"', '  J1   =   "J1"  # the connector')
    path.write_text(text, encoding="utf-8")
    code, env, err = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--confirm")
    assert code == 0, err
    assert path.read_text(encoding="utf-8") == text
    assert not [w for w in env["receipt"]["written"] if w["path"].endswith(".lock")]  # type: ignore[index]


def test_frozen_refuses_a_released_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    path = folder / "design.lock"
    path.write_text(path.read_text(encoding="utf-8") + '"gone/R" = "R4"\n', encoding="utf-8")
    code, env, _ = run(monkeypatch, "build", "ex/design.py", "--out", "B", "--frozen", "--dry-run")
    assert code == 7
    changed = [i for i in env["issues"] if i["code"] == "lock.changed"]  # type: ignore[union-attr]
    assert [i["where"] for i in changed] == ["refs:gone/R"] and "released" in changed[0]["message"]


def test_explicit_design_is_free_under_frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    blink = ROOT / "examples" / "blink_2layer" / "design.py"
    code, env, err = run(monkeypatch, "build", str(blink), "--out", "B", "--frozen", "--dry-run")
    assert code == 0, err
    assert env["result"]["lock"] is None  # type: ignore[index]


def test_code_registered() -> None:
    spec = REGISTRY["FEN-7004"]
    assert spec.exit_code is ExitCode.LOSSY and spec.retryable is False
    assert spec.message == "the design lock would change under --frozen; nothing was written"
    assert (
        spec.hint == "build without --frozen, review result.lock.changes, commit the lock, then build frozen"
    )


def test_code_explained(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, _ = run(monkeypatch, "explain", "FEN-7004")
    assert code == 0
    result = env["result"]
    assert result["exit_code"] == 7 and "--frozen" in result["fix"]  # type: ignore[index]
