# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite restore`` (capability cli-contract, "Restore command"; change c0066). Hermetic."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Any

import pytest
from _checkcli import run
from _cliexamples import folder_snapshot

DESIGN = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"


def _overwrite(monkeypatch: pytest.MonkeyPatch, folder: Path) -> dict[str, Any]:
    """``out.txt`` holding ``one``, overwritten with ``two``; the envelope is saved as ``r.json``."""
    (folder / "out.txt").write_bytes(b"one")
    code, env, _, raw = run(
        monkeypatch, folder, "_echo", "--write", "out.txt", "--content", "two", "--confirm"
    )
    assert code == 0 and env["receipt"]["undo"] == "fenolite restore - --confirm"
    (folder / "r.json").write_text(raw, encoding="utf-8")
    return env


def test_undo_of_an_overwrite_and_undo_of_the_undo(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    written = _overwrite(monkeypatch, tmp_path)
    before = folder_snapshot(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "restore", "r.json")
    assert code == 4 and err["code"] == "FEN-4001" and folder_snapshot(tmp_path) == before
    assert [(p["path"], p["kind"], p["overwrite"]) for p in env["result"]["plan"]] == [
        ("out.txt", "restore", True)
    ]

    code, env, _, raw = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 0 and env["issues"] == []
    assert (tmp_path / "out.txt").read_bytes() == b"one" and (tmp_path / "out.txt.bak").read_bytes() == b"two"
    assert env["result"] == {"id": written["receipt"]["id"], "restored": ["out.txt"], "kept": []}
    assert env["receipt"]["backup"] == ["out.txt.bak"] and env["receipt"]["undo"]

    (tmp_path / "undo.json").write_text(raw, encoding="utf-8")
    code, _, _, _ = run(monkeypatch, tmp_path, "restore", "undo.json", "--confirm")
    assert code == 0
    assert (tmp_path / "out.txt").read_bytes() == b"two" and (tmp_path / "out.txt.bak").read_bytes() == b"one"


def test_changed_since_the_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _overwrite(monkeypatch, tmp_path)
    (tmp_path / "out.txt").write_bytes(b"edited by hand")
    before = folder_snapshot(tmp_path)
    code, env, err, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    assert [(i["code"], i["severity"], i["where"]) for i in env["issues"]] == [
        ("restore.changed-since", "error", "out.txt")
    ]
    assert env["result"]["changed"] == ["out.txt"] and env["result"]["restored"] == []
    assert "plan" not in env["result"] and env["receipt"] is None
    assert folder_snapshot(tmp_path) == before


def test_missing_backup_and_nothing_to_restore(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    _overwrite(monkeypatch, tmp_path)
    (tmp_path / "out.txt.bak").rename(tmp_path / "moved.bak")
    code, env, _, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["restore.backup-missing"]
    assert (tmp_path / "out.txt").read_bytes() == b"two"

    fresh = tmp_path / "fresh"
    fresh.mkdir()
    code, env, _, raw = run(monkeypatch, fresh, "_echo", "--write", "new.txt", "--confirm")
    assert code == 0 and env["receipt"]["undo"] is None
    (fresh / "r.json").write_text(raw, encoding="utf-8")
    code, env, _, _ = run(monkeypatch, fresh, "restore", "r.json", "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["restore.nothing"]
    assert (fresh / "new.txt").is_file() and env["result"]["kept"] == ["new.txt"]


def test_created_files_stay_after_a_rebuild_is_undone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A build into an empty folder, then a rebuild of a changed design: the restore gives every
    overwritten file its previous bytes, deletes nothing and reports the files without a backup."""
    work = tmp_path / "work"
    work.mkdir()
    script = work / "design.py"
    source = DESIGN.read_text(encoding="utf-8")
    script.write_text(source, encoding="utf-8", newline="\n")
    libs = (DESIGN.parents[2] / "tests" / "data" / "libs").as_posix()
    for table in ("fp-lib-table", "sym-lib-table"):  # the example's tables, with the library path spelled out
        text = (DESIGN.parent / table).read_text(encoding="utf-8")
        assert "${KIPRJMOD}/../../tests/data/libs" in text
        (work / table).write_text(
            text.replace("${KIPRJMOD}/../../tests/data/libs", libs), encoding="utf-8", newline="\n"
        )
    code, env, _, _ = run(monkeypatch, work, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0, env["issues"]
    first = folder_snapshot(work)
    assert source.count('"330"') >= 1
    script.write_text(source.replace('"330"', '"470"'), encoding="utf-8", newline="\n")
    code, env, _, raw = run(monkeypatch, work, "build", "design.py", "--out", "out", "--confirm")
    assert code == 0 and env["receipt"]["backup"], env["issues"]
    rebuilt = folder_snapshot(work)
    (tmp_path / "receipt.json").write_text(raw, encoding="utf-8")
    overwritten = {b[: -len(".bak")] for b in env["receipt"]["backup"]}
    without_backup = sorted(w["path"] for w in env["receipt"]["written"] if w["path"] not in overwritten)

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    code, env, _, _ = run(
        monkeypatch, elsewhere, "restore", str(tmp_path / "receipt.json"), "--in", str(work), "--confirm"
    )
    assert code == 0, env["issues"]
    after = folder_snapshot(work)
    assert set(after) >= set(rebuilt), "restore deleted a file"
    assert all(after[path] == first[path] for path in overwritten)
    assert sorted(i["where"] for i in env["issues"] if i["code"] == "restore.kept") == without_backup
    assert (
        sorted(env["result"]["restored"]) == sorted(overwritten) and env["result"]["kept"] == without_backup
    )
    assert list(elsewhere.iterdir()) == []


def test_receipt_from_stdin_and_bare_receipt(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    written = _overwrite(monkeypatch, tmp_path)
    monkeypatch.setattr("sys.stdin", io.StringIO((tmp_path / "r.json").read_text(encoding="utf-8")))
    code, env, _, _ = run(monkeypatch, tmp_path, "restore", "-", "--dry-run")
    assert code == 0 and [p["path"] for p in env["result"]["plan"]] == ["out.txt"]
    assert (tmp_path / "out.txt").read_bytes() == b"two"

    bare = {"written": written["receipt"]["written"], "backup": written["receipt"]["backup"]}
    (tmp_path / "bare.json").write_text(json.dumps(bare), encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "restore", "bare.json", "--dry-run")
    assert code == 0 and env["result"]["id"] == written["receipt"]["id"]


@pytest.mark.parametrize(
    "text",
    [
        "not json",
        "[1, 2]",
        '{"ok": true, "receipt": null}',
        '{"written": [], "backup": "x"}',
        '{"written": [{"path": "/etc/hosts", "sha256": "0"}], "backup": []}',
        '{"written": [{"path": "../x", "sha256": "0"}], "backup": []}',
        '{"written": [{"path": "a", "sha256": "0"}], "backup": ["b.bak"]}',
        '{"written": [{"path": "a"}], "backup": []}',
    ],
)
def test_anything_else_is_malformed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, text: str) -> None:
    (tmp_path / "r.json").write_text(text, encoding="utf-8")
    code, _, err, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--confirm")
    assert code == 3 and err["code"] == "FEN-3004"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["r.json"]


def test_missing_receipt_or_folder(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err, _ = run(monkeypatch, tmp_path, "restore", "none.json")
    assert code == 3 and err["code"] == "FEN-3001"
    _overwrite(monkeypatch, tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "restore", "r.json", "--in", "nowhere")
    assert code == 3 and err["code"] == "FEN-3001"
