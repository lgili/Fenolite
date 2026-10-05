# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``template import`` command (capability sheet-templates, "Template import command"; change c0046).
The templates are authored in ``tests/_altium_sheet.py`` and written under ``tmp_path`` only."""

from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _altium_sheet import build, label, sheet, template

import fenolite.cli.main as cli_main
from fenolite.backends.altium.read.sheet import import_sheet
from fenolite.backends.kicad.wks import read_drawing_sheet
from fenolite.cli.cmd_template import ACTIONS, IMPORT_EVIDENCE

HEADER = '(kicad_wks\n\t(version 20231118)\n\t(generator "fenolite")\n'
LOSSES = ["altium.sheet.not-representable", "altium.sheet.not-template-content"]


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["template", "import", *args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")


def write(folder: Path, file: str, name: str, form: str = "binary") -> None:
    (folder / file).write_bytes(template(name, form=form))  # type: ignore[arg-type]


def test_dry_run_reports_the_import(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write(tmp_path, "t.SchDot", "title_block")
    code, env, _ = run(
        monkeypatch, tmp_path, "t.SchDot", "--target", "kicad", "--out", "t.kicad_wks", "--dry-run"
    )
    assert code == 0 and not (tmp_path / "t.kicad_wks").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["t.SchDot"]
    result = env["result"]
    assert [w["path"] for w in result["plan"]] == ["t.kicad_wks"]
    assert result["source"] == {
        "form": "binary",
        "style": 0,
        "paper": "A4",
        "portrait": False,
        "width": 292_100_000,
        "height": 193_040_000,
    }
    assert result["sheet"]["name"] == "t" and result["sheet"]["items"] == 26
    assert {"title", "doc_id"} <= set(result["sheet"]["tokens"])
    assert set(result["drawn"]) == {"A4"}
    assert result["drawn"]["A4"]["texts"] == 19 and result["drawn"]["A4"]["lines"] == 5 + 2 * 4
    assert "Title" in result["drawn"]["A4"]["resolved"] and "1" in result["drawn"]["A4"]["resolved"]
    assert result["imported"] == {"4": 19, "13": 5, "14": 2} and result["reported"] == []
    assert result["strings"]["=Title"] == "{title}" and result["parameters"] == []
    assert result["target"] == "kicad" and result["kicad_version"] == 10 and result["output"] == "t.kicad_wks"
    keys = "sheet source imported reported strings parameters target kicad_version drawn output plan"
    assert set(result) == set(keys.split())
    assert env["input"]["kind"] == "altium-sheet"
    assert env["input"]["sha256"] == hashlib.sha256((tmp_path / "t.SchDot").read_bytes()).hexdigest()
    assert env["evidence"] == {
        "level": "INFERRED",
        "oracle": None,
        "hypotheses": ["H-A-RD-SHT-SAME", "H-K-WKS-CORNER"],
    }
    assert env["issues"] == []


def test_confirmation_required(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write(tmp_path, "t.SchDot", "title_block")
    code, _, err = run(monkeypatch, tmp_path, "t.SchDot", "--target", "kicad", "--out", "t.kicad_wks")
    assert code == 4 and err["code"] == "FEN-4001" and not (tmp_path / "t.kicad_wks").exists()


def test_confirmed_write(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    data = template("title_block")
    outputs: list[bytes] = []
    for name in ("a", "b"):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "t.SchDot").write_bytes(data)
        code, env, _ = run(
            monkeypatch, folder, "t.SchDot", "--target", "kicad", "--out", "t.kicad_wks", "--confirm"
        )
        assert code == 0 and "plan" not in env["result"]
        written = (folder / "t.kicad_wks").read_bytes()
        assert env["receipt"]["written"][0]["sha256"] == hashlib.sha256(written).hexdigest()
        assert sorted(p.name for p in folder.iterdir()) == ["t.SchDot", "t.kicad_wks"]
        outputs.append(written)
    assert outputs[0] == outputs[1] and outputs[0].decode("utf-8").startswith(HEADER)
    back = read_drawing_sheet(outputs[0].decode("utf-8"))
    imported = import_sheet(data, name="t").sheet
    assert back.setup == imported.setup and back.items == imported.items


def test_ascii_source_and_schdoc_extension(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write(tmp_path, "applied.SchDoc", "applied", "ascii")
    code, env, _ = run(
        monkeypatch, tmp_path, "applied.SchDoc", "--target", "kicad", "-o", "o.kicad_wks", "--dry-run"
    )
    assert code == 0 and env["result"]["source"]["form"] == "ascii"
    assert env["result"]["imported"] == {"4": 1, "13": 2} and env["result"]["sheet"]["name"] == "applied"


def test_loss_refused_without_the_flag(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write(tmp_path, "m.SchDot", "mixed")
    args = ("m.SchDot", "--target", "kicad", "--out", "m.kicad_wks", "--dry-run")
    code, env, err = run(monkeypatch, tmp_path, *args)
    assert code == 7 and err["code"] == "FEN-7001" and "--allow-lossy" in err["hint"]
    assert [i["code"] for i in env["issues"]] == LOSSES
    code, env, _ = run(monkeypatch, tmp_path, *args, "--allow-lossy")
    assert code == 0 and [i["code"] for i in env["issues"]] == LOSSES
    assert [(i["severity"], i["where"]) for i in env["issues"]] == [
        ("warning", "record[4]"),
        ("warning", "record[5]"),
    ]
    assert [w["path"] for w in env["result"]["plan"]] == ["m.kicad_wks"]
    assert env["result"]["reported"] == ["record[4]", "record[5]"] and env["result"]["parameters"] == [
        "Title"
    ]
    assert not (tmp_path / "m.kicad_wks").exists()


def test_custom_sheet_is_drawn_on_its_own_page(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    write(tmp_path, "c.SchDot", "border_zones")
    code, env, _ = run(
        monkeypatch, tmp_path, "c.SchDot", "--target", "kicad", "--out", "c.kicad_wks", "--dry-run"
    )
    assert code == 0 and set(env["result"]["drawn"]) == {"custom"}
    assert env["result"]["source"]["style"] is None
    assert env["result"]["drawn"]["custom"] == {
        "texts": 12,
        "lines": 16,
        "resolved": [*"1234", *"1234", *"AB", *"AB"],
    }
    assert [i["code"] for i in env["issues"]] == ["altium.sheet.builtin-drawn"]


def test_writer_refusal_keeps_the_importers_issues(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    records = [sheet(SHEETSTYLE=0), label(10, 10, "=CurrentDate"), label(10, 30, "50%Rev")]
    (tmp_path / "w.SchDot").write_bytes(build(records, form="ascii"))
    code, env, err = run(
        monkeypatch,
        tmp_path,
        "w.SchDot",
        "--target",
        "kicad",
        "--out",
        "w.kicad_wks",
        "--dry-run",
        "--allow-lossy",
    )
    assert code == 7 and err["code"] == "FEN-7001"
    assert [i["code"] for i in env["issues"]] == ["altium.sheet.dynamic-string", "kicad.wks.literal-variable"]


def test_not_an_altium_schematic(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    (tmp_path / "x.SchDot").write_text("hello")
    code, _, err = run(
        monkeypatch, tmp_path, "x.SchDot", "--target", "kicad", "--out", "x.kicad_wks", "--dry-run"
    )
    assert code == 3 and err["code"] == "FEN-3004"
    write(tmp_path, "n.SchDot", "no_sheet", "ascii")
    code, _, err = run(
        monkeypatch, tmp_path, "n.SchDot", "--target", "kicad", "--out", "x.kicad_wks", "--dry-run"
    )
    assert code == 3 and err["code"] == "FEN-3004" and err["where"] == "n.SchDot:record[0]"


def test_missing_file_and_usage(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, tmp_path, "nope.SchDot", "--target", "kicad", "--out", "o", "--dry-run")
    assert code == 3 and err["code"] == "FEN-3001"
    write(tmp_path, "t.SchDot", "title_block")
    code, _, _ = run(monkeypatch, tmp_path, "t.SchDot", "--target", "other", "--out", "o", "--dry-run")
    assert code == 2
    code, _, _ = run(monkeypatch, tmp_path, "t.SchDot", "--target", "kicad", "--dry-run")
    assert code == 2


def test_actions_and_evidence() -> None:
    assert ACTIONS == ("build", "import")
    assert IMPORT_EVIDENCE.hypotheses == ("H-A-RD-SHT-SAME", "H-K-WKS-CORNER")


def test_capabilities_keep_one_template_entry(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    assert cli_main.main(["capabilities", "--json", "--no-tools"]) == 0
    entries = [c for c in json.loads(out.getvalue())["result"]["commands"] if c["name"] == "template"]
    assert len(entries) == 1 and entries[0]["mutates"] is True
