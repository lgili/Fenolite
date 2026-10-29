# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite snapshot`` (change c0201; capability file-safety, "Stable snapshot")."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _checkcli import run
from _safetyproject import project

from fenolite.cli import cmd_snapshot
from fenolite.core.io import sha256_bytes, sha256_of
from fenolite.safety.files import RETRIES, companions, project_files, read_stable


def test_companions_of_a_board(tmp_path: Path) -> None:
    """The documents of the stem, the table beside it and the library folder it names; not the other
    board, not the notes."""
    board = project(tmp_path)
    assert [rel.as_posix() for rel in companions(board)] == [
        "Local.pretty/R.kicad_mod", "board.kicad_pcb", "board.kicad_pro", "fp-lib-table",
    ]  # fmt: skip
    assert "other.kicad_pcb" in {rel.as_posix() for rel in project_files(board.parent)}


def test_a_file_saved_during_the_copy(tmp_path: Path) -> None:
    """Scenario "A file saved during the copy": the board is saved once after its first read."""
    board = project(tmp_path)
    saved = b"(kicad_pcb (version 20240108))\n"

    def save_once(path: Path, attempt: int) -> None:
        if path == board and attempt == 0:
            path.write_bytes(saved)

    read = read_stable(board.parent, companions(board), hook=save_once)
    held = {item.path: item for item in read.files}
    assert read.retries == 1 and read.unstable == () and held["board.kicad_pcb"].data == saved


def test_a_file_that_never_settles(tmp_path: Path) -> None:
    board = project(tmp_path)
    count = iter(range(100))

    def keep_saving(path: Path, attempt: int) -> None:
        if path == board:
            path.write_bytes(f"(kicad_pcb {next(count)})\n".encode())

    read = read_stable(board.parent, companions(board), hook=keep_saving)
    assert read.unstable == ("board.kicad_pcb",) and read.retries == RETRIES


def test_snapshot_command(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    code, env, err, _ = run(
        monkeypatch, tmp_path, "snapshot", "proj/board.kicad_pcb", "--out", "snap", "--confirm"
    )
    assert code == 0, err
    manifest = json.loads((tmp_path / "snap" / "snapshot.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "fenolite.snapshot.v0" and manifest["source"] == "proj"
    assert {row["path"]: row["sha256"] for row in manifest["files"]}["board.kicad_pcb"] == sha256_of(board)
    assert (tmp_path / "snap" / "Local.pretty" / "R.kicad_mod").is_file()
    assert env["result"]["count"] == 4 and env["result"]["retries"] == 0


def test_unstable_writes_nothing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    count = iter(range(100))

    def keep_saving(path: Path, attempt: int) -> None:
        if path == board:
            path.write_bytes(f"(kicad_pcb {next(count)})\n".encode())

    monkeypatch.setattr(cmd_snapshot, "HOOK", keep_saving)
    code, env, _, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--confirm")
    assert code == 5 and [i["code"] for i in env["issues"]] == ["safety.unstable"]
    assert not (tmp_path / "snap").exists()


def test_out_inside_the_project(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    project(tmp_path)
    code, _, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "proj/snap", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_online_only_stops_before_reading(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    board = project(tmp_path)
    monkeypatch.setattr(cmd_snapshot, "online_only", lambda paths: tuple(p for p in paths if p == board))
    code, _, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3007" and err["retryable"] is True


@pytest.mark.parametrize("count", (0, 1, 2))
def test_unchanged_set_needs_no_retry(tmp_path: Path, count: int) -> None:
    paths = [Path(name) for name in ("b.kicad_sch", "a.kicad_pcb")[:count]]
    observed: list[tuple[str, int]] = []
    for path in paths:
        (tmp_path / path).write_bytes(path.name.encode())

    read = read_stable(tmp_path, paths, hook=lambda path, attempt: observed.append((path.name, attempt)))

    assert read.retries == 0 and read.unstable == ()
    assert observed == [(path.name, 0) for path in paths]
    assert [item.path for item in read.files] == sorted(path.name for path in paths)
    for item in read.files:
        assert item.data == (tmp_path / item.path).read_bytes()
        assert item.sha256 == sha256_bytes(item.data)


def test_saved_file_changes_an_earlier_file_during_retry(tmp_path: Path) -> None:
    """A0/B2 never coexist: a retry of B must invalidate the previously settled A0."""
    a, b = tmp_path / "a.kicad_pcb", tmp_path / "b.kicad_sch"
    a.write_bytes(b"A0")
    b.write_bytes(b"B0")
    observed: list[tuple[str, int]] = []

    def save(path: Path, attempt: int) -> None:
        observed.append((path.name, attempt))
        if path == b and attempt == 0:
            b.write_bytes(b"B1")
        elif path == b and attempt == 1:
            a.write_bytes(b"A1")
            b.write_bytes(b"B2")

    read = read_stable(tmp_path, [Path(a.name), Path(b.name)], hook=save)

    assert read.unstable == () and read.retries == 3
    assert {item.path: item.data for item in read.files} == {a.name: b"A1", b.name: b"B2"}
    assert observed == [(a.name, 0), (b.name, 0), (b.name, 1), (a.name, 2), (b.name, 2)]


def test_cross_file_saves_use_successive_retry_rounds(tmp_path: Path) -> None:
    """A file can become stale on any round after its first successful validation."""
    paths = [Path(name) for name in ("a.kicad_pcb", "b.kicad_sch", "c.kicad_pro")]
    for path in paths:
        (tmp_path / path).write_bytes(b"old")

    def save(path: Path, attempt: int) -> None:
        if path.name == "c.kicad_pro" and attempt == 0:
            path.write_bytes(b"new")
        elif path.name == "c.kicad_pro" and attempt == 1:
            (tmp_path / paths[1]).write_bytes(b"new")
        elif path.name == "b.kicad_sch" and attempt == 2:
            (tmp_path / paths[0]).write_bytes(b"new")

    read = read_stable(tmp_path, paths, hook=save)

    assert read.unstable == () and read.retries == 3
    assert [item.data for item in read.files] == [b"new", b"new", b"new"]


def test_all_files_kept_changing_exhaust_the_shared_budget(tmp_path: Path) -> None:
    paths = [Path("a.kicad_pcb"), Path("b.kicad_sch")]
    observed: list[tuple[str, int]] = []
    for path in paths:
        (tmp_path / path).write_bytes(b"initial")

    def save(path: Path, attempt: int) -> None:
        observed.append((path.name, attempt))
        if path.name == paths[-1].name:
            for rel in paths:
                (tmp_path / rel).write_bytes(f"saved {attempt}".encode())

    read = read_stable(tmp_path, paths, hook=save)

    assert read.retries == len(paths) * RETRIES
    assert read.unstable == tuple(path.name for path in paths)
    assert observed == [(path.name, attempt) for attempt in range(RETRIES + 1) for path in paths]


def test_previously_settled_file_changes_on_the_last_round(tmp_path: Path) -> None:
    a, b = tmp_path / "a.kicad_pcb", tmp_path / "b.kicad_sch"
    a.write_bytes(b"A0")
    b.write_bytes(b"B0")

    def save(path: Path, attempt: int) -> None:
        if path == b:
            if attempt < RETRIES:
                b.write_bytes(f"B{attempt + 1}".encode())
            else:
                a.write_bytes(b"A1")

    read = read_stable(tmp_path, [Path(a.name), Path(b.name)], hook=save)

    assert read.retries == RETRIES
    assert read.unstable == (a.name,)
    assert {item.path: item.data for item in read.files}[a.name] == b"A0"
    assert a.read_bytes() == b"A1"


def test_snapshot_manifest_after_cross_file_saves(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    a, b = root / "a.kicad_pcb", root / "b.kicad_sch"
    a.write_bytes(b"A0")
    b.write_bytes(b"B0")

    def save(path: Path, attempt: int) -> None:
        if path == b and attempt == 0:
            b.write_bytes(b"B1")
        elif path == b and attempt == 1:
            a.write_bytes(b"A1")
            b.write_bytes(b"B2")

    monkeypatch.setattr(cmd_snapshot, "HOOK", save)
    code, env, err, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--confirm")

    assert code == 0, err
    assert env["result"]["retries"] == 3
    manifest = json.loads((tmp_path / "snap" / "snapshot.json").read_text(encoding="utf-8"))
    expected = {a.name: b"A1", b.name: b"B2"}
    for row in manifest["files"]:
        data = (tmp_path / "snap" / row["path"]).read_bytes()
        assert data == expected[row["path"]]
        assert row["sha256"] == sha256_bytes(data)
        assert row["size"] == len(data)
    assert {row["path"] for row in manifest["files"]} == set(expected)


def test_snapshot_refuses_a_new_mismatch_on_the_final_round(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    root = tmp_path / "proj"
    root.mkdir()
    a, b = root / "a.kicad_pcb", root / "b.kicad_sch"
    a.write_bytes(b"A0")
    b.write_bytes(b"B0")
    reads: list[str] = []

    def save(path: Path, attempt: int) -> None:
        reads.append(path.name)
        if path == b:
            if attempt < RETRIES:
                b.write_bytes(f"B{attempt + 1}".encode())
            else:
                a.write_bytes(b"A1")

    monkeypatch.setattr(cmd_snapshot, "HOOK", save)
    code, env, _, _ = run(monkeypatch, tmp_path, "snapshot", "proj", "--out", "snap", "--confirm")

    assert code == 5 and env["result"]["retries"] == RETRIES
    assert [issue["code"] for issue in env["issues"]] == ["safety.unstable"]
    issue = env["issues"][0]
    assert issue["where"] == a.name
    assert f"{RETRIES} retry rounds" in issue["message"]
    assert "each of" not in issue["message"]
    assert reads.count(a.name) == 1 and reads.count(b.name) == RETRIES + 1
    assert not (tmp_path / "snap").exists()
