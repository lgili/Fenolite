# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``template build --target altium`` (capability sheet-templates, "Template build for Altium"; change
c0087)."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pytest
from _altium_job import A4, example_sheet

import fenolite.cli.main as cli_main
from fenolite.backends.altium.read.sheet import import_sheet
from fenolite.backends.altium.schdot import written_scope
from fenolite.backends.kicad import wks
from fenolite.model.presentation import PAPER_SIZES
from fenolite.templates import example_path

EXAMPLE = str(example_path("iso5457_generic"))
ALTIUM = ("build", EXAMPLE, "--target", "altium", "--out", "t.SchDot")
COMPOUND = bytes.fromhex("d0cf11e0a1b11ae1")


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict, dict]:  # type: ignore[type-arg]
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["template", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def test_both_targets_from_one_specification(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Both targets from one specification"."""
    code, env, _ = run(monkeypatch, tmp_path, *ALTIUM, "--confirm")
    assert code == 0
    data = (tmp_path / "t.SchDot").read_bytes()
    assert data.startswith(COMPOUND)
    assert env["receipt"]["written"][0]["sha256"] == hashlib.sha256(data).hexdigest()
    result = env["result"]
    assert result["target"] == "altium" and "kicad_version" not in result and "plan" not in result
    assert result["altium"] == {
        "format": "binary",
        "size": "A4",
        "width": A4[0],
        "height": A4[1],
        "lines": 36,
        "texts": 36,
        "parameters": [],
        "strings": ["=ApprovedBy", "=Date", "=DocumentNumber", "=DrawnBy", "=Organization", "=Revision",
                    "=SheetNumber", "=Title"],
    }  # fmt: skip
    assert set(result["drawn"]) == {"A4"} and result["drawn"]["A4"]["texts"] == 36
    assert result["sheet"]["sizes"] == ["A4", "A3"]
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-A-SCHDOT-OPEN", "H-A-SCHDOT-READBACK", "H-A-SCHDOT-STRINGS"],
    }
    kicad = ("build", EXAMPLE, "--target", "kicad", "--out", "t.kicad_wks", "--confirm")
    code, _, _ = run(monkeypatch, tmp_path, *kicad)
    assert code == 0
    from_kicad = wks.read_drawing_sheet((tmp_path / "t.kicad_wks").read_text(encoding="utf-8"), file="t")
    from_altium = import_sheet(data).sheet
    page = {"width": A4[0], "height": A4[1], "paper": "A4"}
    assert written_scope(from_altium, **page) == written_scope(from_kicad, **page)
    assert written_scope(from_altium, **page) == written_scope(example_sheet(), **page)


def test_dry_run_confirmation_and_determinism(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The rules of the template build command hold for the Altium target."""
    code, _, err = run(monkeypatch, tmp_path, *ALTIUM)
    assert code == 4 and err["code"] == "FEN-4001" and not (tmp_path / "t.SchDot").exists()
    code, env, _ = run(monkeypatch, tmp_path, *ALTIUM, "--dry-run")
    assert code == 0 and not (tmp_path / "t.SchDot").exists()
    assert [(w["path"], w["kind"]) for w in env["result"]["plan"]] == [("t.SchDot", "altium_schdot")]
    first, second = tmp_path / "a", tmp_path / "b"
    for folder in (first, second):
        folder.mkdir()
        assert run(monkeypatch, folder, *ALTIUM, "--confirm")[0] == 0
    assert (first / "t.SchDot").read_bytes() == (second / "t.SchDot").read_bytes()


def test_a_listed_size(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A listed size"."""
    code, env, _ = run(monkeypatch, tmp_path, *ALTIUM, "--size", "A3", "--dry-run")
    a3 = PAPER_SIZES["A3"]
    assert code == 0 and env["result"]["altium"]["size"] == "A3"
    assert (env["result"]["altium"]["width"], env["result"]["altium"]["height"]) == (a3[1], a3[0])
    assert set(env["result"]["drawn"]) == {"A3"}
    code, _, err = run(monkeypatch, tmp_path, *ALTIUM, "--size", "A0", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"


def test_ascii_form(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, env, _ = run(monkeypatch, tmp_path, *ALTIUM, "--altium-format", "ascii", "--confirm")
    assert code == 0 and env["result"]["altium"]["format"] == "ascii"
    data = (tmp_path / "t.SchDot").read_bytes()
    assert data.startswith(b"|HEADER=Protel for Windows - Schematic Capture Ascii File")
    assert import_sheet(data).source.form == "ascii"


@pytest.mark.parametrize(
    "args",
    [
        ("build", EXAMPLE, "--target", "kicad", "--out", "o", "--size", "A4", "--dry-run"),
        ("build", EXAMPLE, "--target", "kicad", "--out", "o", "--altium-format", "ascii", "--dry-run"),
        ("import", "x.SchDot", "--target", "altium", "--out", "o", "--dry-run"),
        ("build", EXAMPLE, "--target", "altium", "--out", "o", "--altium-format", "xml", "--dry-run"),
    ],
)
def test_usage_errors(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, args: tuple[str, ...]) -> None:
    (tmp_path / "x.SchDot").write_bytes(b"")
    code, _, _ = run(monkeypatch, tmp_path, *args)
    assert code == 2


def test_a_loss_needs_allow_lossy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A specification whose title block mixes a token with other text is refused without the option."""
    text = example_path("iso5457_generic").read_text(encoding="utf-8")
    lossy = text.replace('label = "Title"\ntoken = "title"', 'label = "{title} of {sheets}"\ntoken = "title"')
    assert lossy != text
    (tmp_path / "s.sheet.toml").write_text(lossy, encoding="utf-8", newline="\n")
    args = ("build", "s.sheet.toml", "--target", "altium", "--out", "t.SchDot", "--confirm")
    code, _, err = run(monkeypatch, tmp_path, *args)
    assert code == 7 and err["code"] == "FEN-7001" and not (tmp_path / "t.SchDot").exists()
    code, env, _ = run(monkeypatch, tmp_path, *args, "--allow-lossy")
    assert code == 0 and "altium.sheet.not-representable" in {i["code"] for i in env["issues"]}
    assert env["result"]["altium"]["texts"] == 35
