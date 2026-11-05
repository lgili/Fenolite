# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``import --to python`` of an Altium source exposes the conversion's report (capability board-to-code,
"Import exposes the conversion report"; change c0429): the same rows as ``convert``, every lost, changed
and kept row with its ``convert.*`` issue, and the same refusal without ``--allow-lossy``.

The source is the authored c0423 document (``tests/_altium_models.py``), whose ``UNKNOWN`` body is a
``body`` loss; the refusal adds an authored ``refuse`` loss to the Altium direction's report."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import _altium_models as am
import pytest
from _importcode import STAMP
from _result_contract import result_problems

import fenolite.convert as convert_module
from fenolite.api import run
from fenolite.convert.direction import Options, Written
from fenolite.convert.report import ConversionReport, merge
from fenolite.convert.sources import SourceProject

LEDGER = ("convert.lossy", "convert.changed", "convert.kept")


def _kinds(issues: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {code: [i["where"] for i in issues if i["code"] == code] for code in LEDGER}


def _rows(report: dict[str, Any]) -> dict[str, list[str]]:
    rows = report["rows"]
    return {
        "convert.lossy": [r["kind"] for r in rows if r["lost"]],
        "convert.changed": [r["kind"] for r in rows if r["changed"]],
        "convert.kept": [r["kind"] for r in rows if r.get("kept", 0)],
    }


def test_import_report_equals_convert_report(tmp_path: Path) -> None:
    """Scenario "Same rows as convert": with ``--allow-lossy`` the import's ``result.report`` is the
    conversion's, and both replies give one issue per lost, changed and kept row."""
    source = am.write_folder(tmp_path, unknown=True)
    converted = run("convert", source.name, "--to", "kicad", "--out", "conv", "--allow-lossy", "--dry-run",
                    cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert converted.exit_code == 0, converted.error
    imported = run("import", source.name, "--to", "python", "--out", "out", "--allow-lossy", "--dry-run",
                   cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert imported.exit_code == 0, imported.error
    assert converted.envelope is not None and imported.envelope is not None
    report = imported.envelope["result"]["report"]
    assert report == converted.envelope["result"]["report"]
    assert report["lossy"] and "body" in _rows(report)["convert.lossy"]
    assert _kinds(imported.envelope["issues"]) == _rows(report)
    assert _kinds(converted.envelope["issues"]) == _rows(report)
    assert not result_problems("import", imported.envelope["result"])
    assert not result_problems("convert", converted.envelope["result"])


def test_a_kicad_import_has_no_report(tmp_path: Path) -> None:
    """Negative case: a KiCad source is not converted, so ``result.report`` is null."""
    from _importcode import copy_project

    project = copy_project(tmp_path)
    reply = run("import", str(project), "--to", "python", "--out", "out",
                "--dry-run", "--no-verify", cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert reply.exit_code == 0, reply.error
    assert reply.envelope is not None and reply.envelope["result"]["report"] is None


def test_import_refuses_as_convert_does(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``--allow-lossy`` an import whose conversion loses a ``refuse`` kind exits 7 with the
    ``FEN-7001`` and the ``convert.lossy`` issues of ``convert``."""
    key = ("altium", "kicad")
    direction = convert_module.DIRECTIONS[key]
    extra = ConversionReport.of(source={"pad": 1}, lost={"pad": {"authored loss": ["pad/1"]}})

    def write(read: SourceProject, options: Options) -> Written:
        written = direction.write(read, options)
        return dataclasses.replace(written, report=merge(written.report, extra))

    monkeypatch.setitem(convert_module.DIRECTIONS, key, dataclasses.replace(direction, write=write))
    source = am.write_folder(tmp_path)
    converted = run("convert", source.name, "--to", "kicad", "--out", "conv", "--dry-run",
                    cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    imported = run("import", source.name, "--to", "python", "--out", "out", "--dry-run",
                   cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert converted.exit_code == imported.exit_code == 7
    assert converted.error is not None and imported.error is not None
    assert converted.error["code"] == imported.error["code"] == "FEN-7001"
    assert converted.envelope is not None and imported.envelope is not None
    assert converted.envelope["issues"] == imported.envelope["issues"]
    assert [i["where"] for i in imported.envelope["issues"] if i["code"] == "convert.lossy"] == ["pad"]


def test_kept_rules_agree_in_both_replies(tmp_path: Path) -> None:
    """Change c0424's ``kept`` outcome: the authored project with one rule record of each kind keeps rules
    for an Altium write; convert and import give the same ``rule`` row and one ``convert.kept`` for it."""
    from _altium_rules_doc import ONE_OF_EACH
    from _altium_rules_doc import project as rules_project

    source = rules_project(tmp_path / "src", ONE_OF_EACH)
    converted = run("convert", str(source), "--to", "kicad", "--out", "conv", "--allow-lossy", "--dry-run",
                    cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    imported = run("import", str(source), "--to", "python", "--out", "out", "--allow-lossy", "--dry-run",
                   cwd=tmp_path, timestamp=STAMP)  # fmt: skip
    assert converted.exit_code == 0, converted.error
    assert imported.exit_code == 0, imported.error
    assert converted.envelope is not None and imported.envelope is not None
    report = imported.envelope["result"]["report"]
    assert report == converted.envelope["result"]["report"]
    assert "rule" in _rows(report)["convert.kept"]
    assert _kinds(imported.envelope["issues"]) == _kinds(converted.envelope["issues"]) == _rows(report)
    assert not result_problems("import", imported.envelope["result"])
    assert not result_problems("convert", converted.envelope["result"])
