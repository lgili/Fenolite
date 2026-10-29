# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design lock in ``fenolite build`` (capability design-dsl, "Design lock in a build", "Lock entries
follow path aliases", "Lock issue codes", "Lock in the build result", "Lock reading" and MODIFIED
"Reproducible builds"; cli-contract, "Lock option of the build command"; change c0249)."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / "examples" / "lock"
BLINK = ROOT / "examples" / "blink_2layer"


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
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue()) if out.getvalue() else {}, err.getvalue()


def copy(tmp_path: Path, *, lock: bool = False, name: str = "ex") -> Path:
    folder = tmp_path / name
    folder.mkdir()
    shutil.copy(EXAMPLE / "design.py", folder / "design.py")
    if lock:
        shutil.copy(EXAMPLE / "design.lock", folder / "design.lock")
    return folder


def lock_of(env: dict[str, object]) -> dict[str, object]:
    return env["result"]["lock"]  # type: ignore[index,return-value]


def codes(env: dict[str, object]) -> list[str]:
    return [i["code"] for i in env.get("issues", [])]  # type: ignore[union-attr]


def written(env: dict[str, object]) -> list[str]:
    return [w["path"] for w in env["receipt"]["written"]]  # type: ignore[index]


def planned_lock(env: dict[str, object]) -> list[dict[str, object]]:
    return [w for w in env["result"].get("plan", []) if w["kind"] == "lock"]  # type: ignore[union-attr]


def snapshot(folder: Path) -> dict[str, str]:
    return {
        p.relative_to(folder).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(folder.rglob("*"))
        if p.is_file()
    }


def test_first_build_writes_the_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    code, env, err = run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")
    assert code == 0, err
    assert "ex/design.lock" in written(env)
    receipt = next(w for w in env["receipt"]["written"] if w["path"] == "ex/design.lock")  # type: ignore[index]
    data = (folder / "design.lock").read_bytes()
    assert receipt["sha256"] == hashlib.sha256(data).hexdigest()
    assert data == (EXAMPLE / "design.lock").read_bytes()
    assert lock_of(env)["written"] is True and lock_of(env)["exists"] is False
    assert lock_of(env)["file"] == "design.lock" and lock_of(env)["frozen"] is False


def test_rebuild_leaves_the_lock_alone(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    assert run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")[0] == 0
    before = snapshot(folder)
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")
    assert code == 0 and "ex/design.lock" not in written(env)
    assert (
        lock_of(env)["written"] is False and lock_of(env)["exists"] is True and lock_of(env)["changes"] == []
    )
    assert snapshot(folder) == before
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0 and planned_lock(env) == []


def test_explicit_refs_get_no_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = BLINK
    before = snapshot(folder)
    code, env, err = run(monkeypatch, str(BLINK / "design.py"), "--out", "B", "--confirm")
    assert code == 0, err
    assert env["result"]["lock"] is None  # type: ignore[index]
    assert not (folder / "design.lock").exists() and snapshot(folder) == before


def test_first_build_is_quiet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    copy(tmp_path)
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0
    assert not [c for c in codes(env) if c.startswith("lock.")]
    changes = lock_of(env)["changes"]
    assert changes and {c["reason"] for c in changes} == {"assigned"}  # type: ignore[union-attr,index]
    assert [w["path"] for w in planned_lock(env)] == ["ex/design.lock"]
    assert not (tmp_path / "ex" / "design.lock").exists()


def test_a_hand_edit_renumbers(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    path = folder / "design.lock"
    path.write_text(path.read_text(encoding="utf-8").replace('"reg/C" = "C1"', '"reg/C" = "C7"'), "utf-8")
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0 and lock_of(env)["changes"] == [] and planned_lock(env) == []
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")
    text = (tmp_path / "B" / "lock_demo.kicad_pcb").read_text(encoding="utf-8")
    assert code == 0 and '"Reference" "C7"' in text and '"Reference" "C1"' not in text


def test_hand_formatted_lock_is_rewritten_once(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    path = folder / "design.lock"
    path.write_text(
        path.read_text(encoding="utf-8").replace("# Design lock", "# my notes\n# Design lock"), "utf-8"
    )
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")
    assert code == 0 and "ex/design.lock" in written(env) and lock_of(env)["changes"] == []
    assert path.read_bytes() == (EXAMPLE / "design.lock").read_bytes()


def test_changes_listed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    path = folder / "design.lock"
    path.write_text(path.read_text(encoding="utf-8") + '"old/R" = "R9"\n', "utf-8")
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0
    assert lock_of(env)["changes"] == [
        {"section": "refs", "key": "old/R", "before": "R9", "after": None, "reason": "released"}
    ]
    assert "lock.ref-released" in codes(env)


def test_lock_elsewhere(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    code, env, err = run(monkeypatch, "ex/design.py", "--out", "B", "--lock", "B/release.lock", "--confirm")
    assert code == 0, err
    assert "B/release.lock" in written(env) and not (folder / "design.lock").exists()
    assert lock_of(env)["file"] == "release.lock"
    assert (tmp_path / "B" / "release.lock").read_bytes() == (EXAMPLE / "design.lock").read_bytes()
    inside = copy(tmp_path, name="in")
    code, env, _ = run(monkeypatch, "in/design.py", "--out", "B2", "--lock", "in/locks/x.lock", "--dry-run")
    assert code == 0 and lock_of(env)["file"] == "locks/x.lock" and inside.is_dir()


def test_malformed_lock_is_refused(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    path = folder / "design.lock"
    path.write_text(path.read_text(encoding="utf-8") + '"other/C" = "C1"\n', "utf-8")
    code, _, err = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3004" and "reg/C" in err and "other/C" in err
    path.write_text(path.read_text(encoding="utf-8").replace("lock.v0", "lock.v3"), "utf-8")
    code, _, err = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 3 and json.loads(err)["code"] == "FEN-3002"


def test_design_renamed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    path = folder / "design.lock"
    path.write_text(
        path.read_text(encoding="utf-8").replace('design = "lock_demo"', 'design = "old"'), "utf-8"
    )
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0 and "lock.design-renamed" in codes(env) and planned_lock(env)
    assert lock_of(env)["changes"] == [
        {
            "section": "design",
            "key": "design",
            "before": "old",
            "after": "lock_demo",
            "reason": "design-renamed",
        }
    ]


def test_error_findings_plan_no_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path)
    script = folder / "design.py"
    script.write_text(
        script.read_text(encoding="utf-8") + '\nconnect(Net("BAD"), u["NOPE"])\n', encoding="utf-8"
    )
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 5 and planned_lock(env) == [] and lock_of(env)["written"] is False


RENAMED = (
    'reg = Module("reg")',
    'reg = Module("regulator")',
)


def test_module_renamed_with_moved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    script = folder / "design.py"
    text = script.read_text(encoding="utf-8").replace(*RENAMED)
    script.write_text(text + '\ndesign.moved("reg", "regulator")\n', encoding="utf-8")
    code, env, err = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0, err
    assert "lock.ref-moved" in codes(env) and "lock.ref-released" not in codes(env)
    moved = [c for c in lock_of(env)["changes"] if c["reason"] == "moved"]  # type: ignore[union-attr,index]
    assert {c["key"]: c["after"] for c in moved} == {
        "regulator/C": "C1",
        "regulator/U": "U1",
        "regulator/c_in": "C2",
    }
    assert not [c for c in lock_of(env)["changes"] if c["reason"] != "moved"]  # type: ignore[union-attr,index]
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--confirm")
    lock = (folder / "design.lock").read_text(encoding="utf-8")
    assert code == 0 and '"regulator/U" = "U1"' in lock and "reg/U" not in lock


def test_renamed_without_moved(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    script = folder / "design.py"
    script.write_text(script.read_text(encoding="utf-8").replace(*RENAMED), encoding="utf-8")
    code, env, _ = run(monkeypatch, "ex/design.py", "--out", "B", "--dry-run")
    assert code == 0
    released = [i for i in env["issues"] if i["code"] == "lock.ref-released"]  # type: ignore[union-attr]
    assert {i["where"] for i in released} == {"reg/C", "reg/U", "reg/c_in"}
    assert any("U1" in i["message"] for i in released if i["where"] == "reg/U")


def test_altium_target_uses_the_lock(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = copy(tmp_path, lock=True)
    lock = folder / "design.lock"
    lock.write_text(lock.read_text(encoding="utf-8").replace('"reg/U" = "U1"', '"reg/U" = "U5"'), "utf-8")
    code, env, err = run(monkeypatch, "ex/design.py", "--out", "A", "--target", "altium", "--dry-run")
    assert code == 0, err
    assert lock_of(env)["changes"] == [] and planned_lock(env) == []
