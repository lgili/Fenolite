# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Edited Altium outputs are not overwritten (capability altium-build, "Edited Altium outputs are not
overwritten"; change c0032), in the binary form by default and in the ASCII form, and a rebuild that only
switches the form is not an edit (scenario "Switching the form is not an edit"; change c0033)."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
from pathlib import Path

import pytest
from _altium import SAMPLE

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
SCHDOC = "altium_sample.SchDoc"
PRJPCB = "altium_sample.PrjPcb"


def run(monkeypatch: pytest.MonkeyPatch, out: Path, *flags: str) -> tuple[int, dict[str, object], str]:
    stdout, stderr = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", stdout)
    monkeypatch.setattr("sys.stderr", stderr)
    args = ["build", str(SAMPLE), "--out", str(out), "--target", "altium", *flags, "--json"]
    code = cli_main.main(args)
    return code, json.loads(stdout.getvalue()) if stdout.getvalue() else {}, stderr.getvalue()


def files_under(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


@pytest.fixture
def built(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    out = tmp_path / "B"
    assert run(monkeypatch, out, "--confirm")[0] == 0
    return out


def _edit_one_byte(path: Path) -> bytes:
    data = path.read_bytes()
    assert data.count(b"|TEXT=330|") == 1
    edited = data.replace(b"|TEXT=330|", b"|TEXT=331|")
    path.write_bytes(edited)
    return edited


def test_edited_schematic_refused(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    schdoc = built / SCHDOC
    _edit_one_byte(schdoc)
    before = files_under(built)
    for flags in (["--confirm"], ["--dry-run"]):
        code, env, err = run(monkeypatch, built, *flags)
        assert code == 7 and json.loads(err)["code"] == "FEN-7001"
        issues = env["issues"]
        assert isinstance(issues, list) and [i["code"] for i in issues] == ["build.layout-exists"]
        assert issues[0]["where"] == str(schdoc)
        assert files_under(built) == before


def test_discarding_the_edited_schematic(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    schdoc = built / SCHDOC
    edited = _edit_one_byte(schdoc)
    code, _, _ = run(monkeypatch, built, "--discard-layout", "--confirm")
    assert code == 0
    assert schdoc.read_bytes() == (GOLDEN / "binary" / SCHDOC).read_bytes()
    assert (built / f"{SCHDOC}.bak").read_bytes() == edited


def test_edited_ascii_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    out = tmp_path / "A"
    assert run(monkeypatch, out, "--altium-format", "ascii", "--confirm")[0] == 0
    schdoc = out / SCHDOC
    edited = _edit_one_byte(schdoc)
    code, env, _ = run(monkeypatch, out, "--altium-format", "ascii", "--confirm")
    assert code == 7 and [i["code"] for i in env["issues"]] == ["build.layout-exists"]  # type: ignore[union-attr]
    assert schdoc.read_bytes() == edited
    assert run(monkeypatch, out, "--altium-format", "ascii", "--discard-layout", "--confirm")[0] == 0
    assert schdoc.read_bytes() == (GOLDEN / SCHDOC).read_bytes()


def test_switching_the_form_is_not_an_edit(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The edited-output rule compares the existing file with the build record, not with the new form."""
    out = tmp_path / "B"
    schdoc = out / SCHDOC
    assert run(monkeypatch, out, "--altium-format", "ascii", "--confirm")[0] == 0
    assert schdoc.read_bytes() == (GOLDEN / SCHDOC).read_bytes()
    code, env, _ = run(monkeypatch, out, "--confirm")
    assert code == 0 and env["result"]["schematic_format"] == "binary"  # type: ignore[index]
    binary = (GOLDEN / "binary" / SCHDOC).read_bytes()
    assert schdoc.read_bytes() == binary
    record = json.loads((out / ".fenolite" / "build.json").read_bytes())
    assert record["files"][SCHDOC] == hashlib.sha256(binary).hexdigest()
    assert run(monkeypatch, out, "--altium-format", "ascii", "--confirm")[0] == 0
    assert schdoc.read_bytes() == (GOLDEN / SCHDOC).read_bytes()


def test_discarding_without_a_backup(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    _edit_one_byte(built / SCHDOC)
    assert run(monkeypatch, built, "--discard-layout", "--confirm", "--no-backup")[0] == 0
    assert not (built / f"{SCHDOC}.bak").exists()


def test_a_schematic_saved_in_another_form_is_refused(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    (built / SCHDOC).write_bytes(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + bytes(504))
    code, env, _ = run(monkeypatch, built, "--confirm")
    assert code == 7 and [i["code"] for i in env["issues"]] == ["build.layout-exists"]  # type: ignore[union-attr]


def test_project_saved_by_altium_is_kept(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    prjpcb = built / PRJPCB
    edited = prjpcb.read_bytes() + b"[Document2]\r\nDocumentPath=altium_sample.PcbDoc\r\n"
    prjpcb.write_bytes(edited)
    for flags in (["--confirm"], ["--discard-layout", "--confirm"]):
        code, env, _ = run(monkeypatch, built, *flags)
        result, issues = env["result"], env["issues"]
        assert code == 0 and isinstance(result, dict) and isinstance(issues, list)
        assert prjpcb.read_bytes() == edited
        assert result["kept"] == [str(prjpcb)]
        assert str(prjpcb) not in result["files"]
        assert "altium.project-kept" in [i["code"] for i in issues]
        assert not (built / f"{PRJPCB}.bak").exists()


def test_unchanged_rebuild_and_lost_record(monkeypatch: pytest.MonkeyPatch, built: Path) -> None:
    """A rebuild keeps every output; its record names only the files it planned, so the kept project file
    drops out of ``build.json``. Without a record, only identical bytes pass."""
    before = files_under(built)
    assert run(monkeypatch, built, "--confirm")[0] == 0
    after = {k: v for k, v in files_under(built).items() if not k.endswith(".bak")}
    record = ".fenolite/build.json"
    assert {k: v for k, v in after.items() if k != record} == {k: v for k, v in before.items() if k != record}
    assert list(json.loads(before[record])["files"]) == [PRJPCB, SCHDOC]
    assert list(json.loads(after[record])["files"]) == [SCHDOC]
    shutil.rmtree(built / ".fenolite")
    assert run(monkeypatch, built, "--confirm")[0] == 0, "identical bytes pass without a record"
    shutil.rmtree(built / ".fenolite")
    _edit_one_byte(built / SCHDOC)
    assert run(monkeypatch, built, "--confirm")[0] == 7, "without a record only identical bytes pass"
