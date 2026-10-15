# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native template builds, hierarchy, atomic plans and compatibility guards (c0164)."""

import hashlib
import io
import json
from pathlib import Path
from typing import Any

import pytest
from _altium import SAMPLE

import fenolite.cli.main as cli_main
from fenolite.backends.altium.binary import file_header_stream, storage_stream
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.native_template import TEMPLATE_PATH, TEMPLATE_REFERENCE
from fenolite.backends.altium.read.sch import read_schematic


def run(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(["build", *args, "--json"])
    return code, json.loads(out.getvalue() or err.getvalue())


@pytest.fixture
def native(tmp_path: Path) -> Path:
    path = tmp_path / "sheet.SchDot"
    path.write_bytes(
        write_compound(
            (
                (
                    "FileHeader",
                    file_header_stream(
                        [
                            [
                                ("RECORD", "31"),
                                ("FONTIDCOUNT", "1"),
                                ("FONTNAME1", "Arial"),
                                ("SIZE1", "14"),
                                ("SYSTEMFONT", "1"),
                                ("AREACOLOR", "16777215"),
                                ("SHEETSTYLE", "1"),
                            ],
                            [("RECORD", "4"), ("TEXT", "=Title"), ("FONTID", "1"), ("OWNERPARTID", "-1")],
                        ]
                    ),
                ),
                ("Storage", storage_stream()),
            )
        )
    )
    return path


@pytest.mark.parametrize("sheets", ["flat", "modules"])
def test_build_and_rebuild_native(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, native: Path, sheets: str
) -> None:
    out = tmp_path / "out"
    args = (
        str(SAMPLE),
        "--out",
        str(out),
        "--target",
        "altium",
        "--altium-template",
        str(native),
        "--altium-sheets",
        sheets,
    )
    code, env = run(monkeypatch, *args, "--dry-run")
    assert code == 0, env
    assert not out.exists()
    info = env["result"]["native_template"]
    assert info["sha256"] == hashlib.sha256(native.read_bytes()).hexdigest()
    code, env = run(monkeypatch, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, env
    assert (out / TEMPLATE_PATH).read_bytes() == native.read_bytes()
    assert len(info["pages"]) == (1 if sheets == "flat" else 3)
    for number, page in enumerate(info["pages"], 1):
        doc = read_schematic(Path(page).read_bytes())
        assert doc.sheet is not None and doc.sheet.template_file_name == TEMPLATE_REFERENCE
        assert doc.sheet.props.int("SIZE1") == 14
        assert not [i for i in doc.issues if i.severity == "error"]
        assert len(doc.components()) > 0
        parameters = {
            r.props.text("NAME"): r.props.text("TEXT")
            for r in doc.records
            if r.props is not None and r.props.int("RECORD") == 41 and r.owner is None
        }
        assert parameters["SheetNumber"] == str(number)
        assert parameters["SheetTotal"] == str(len(info["pages"]))
    # The build record must contain the composed bytes, not the pre-template digests.
    code, env = run(monkeypatch, *args, "--dry-run")
    assert code == 0, env


def test_template_is_reviewed_input(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, native: Path) -> None:
    out = tmp_path / "out"
    args = (str(SAMPLE), "--out", str(out), "--target", "altium", "--altium-template", str(native))
    code, env = run(monkeypatch, *args, "--dry-run")
    assert code == 0, env
    native.write_bytes(native.read_bytes() + b"changed")
    code, refused = run(monkeypatch, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 4, refused
    assert not out.exists()


@pytest.mark.parametrize("extra", [("--target", "kicad"), ("--target", "altium", "--altium-format", "ascii")])
def test_incompatible_target(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, native: Path, extra: tuple[str, ...]
) -> None:
    code, _ = run(
        monkeypatch,
        str(SAMPLE),
        "--out",
        str(tmp_path / "out"),
        "--altium-template",
        str(native),
        *extra,
        "--dry-run",
    )
    assert code == 2
    assert not (tmp_path / "out").exists()


def test_conflicts_with_neutral_sheet(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, native: Path) -> None:
    script = tmp_path / "design.py"
    script.write_text(
        'from fenolite.dsl import Design\ndesign = Design("test")\n'
        'design.sheet(drawing_sheet="sheet.kicad_wks")\n'
    )
    code, _ = run(
        monkeypatch,
        str(script),
        "--out",
        str(tmp_path / "out"),
        "--target",
        "altium",
        "--altium-template",
        str(native),
        "--dry-run",
    )
    assert code == 2


def test_missing_template_no_writes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    code, _ = run(
        monkeypatch,
        str(SAMPLE),
        "--out",
        str(tmp_path / "out"),
        "--target",
        "altium",
        "--altium-template",
        str(tmp_path / "missing.SchDot"),
        "--confirm",
    )
    assert code == 3
    assert not (tmp_path / "out").exists()


def test_title_block_on_schematic_only_script(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, native: Path
) -> None:
    script = tmp_path / "design.py"
    script.write_text(SAMPLE.read_text() + '\ndesign.title_block(title="Authored title", revision="B")\n')
    out = tmp_path / "out"
    code, env = run(
        monkeypatch,
        str(script),
        "--out",
        str(out),
        "--target",
        "altium",
        "--altium-template",
        str(native),
        "--confirm",
    )
    assert code == 0, env
    doc = read_schematic((out / "altium_sample.SchDoc").read_bytes())
    params = {
        r.props.text("NAME"): r.props.text("TEXT")
        for r in doc.records
        if r.props is not None and r.props.int("RECORD") == 41 and r.owner is None
    }
    assert params["Title"] == "Authored title"
    assert params["Revision"] == "B"
