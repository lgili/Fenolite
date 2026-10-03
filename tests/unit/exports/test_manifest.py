# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The artefact manifest (capability manufacturing-exports, "Artefact manifest"; change c0024)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import _schema

import fenolite
from fenolite.exports import EVIDENCE
from fenolite.exports.manifest import FILE_NAME, SCHEMA, BoardRef, build, content_sha256, dumps
from fenolite.exports.plan import Artifact

WHEN = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
BOARD = BoardRef(path="board.kicad_pcb", sha256="a" * 64, format_version=20260206)
BODY = b"%ADD10C,0.2*%\n"
GERBER_A = (
    b"%TF.CreationDate,2026-10-03T16:30:49+08:00*%\nG04 Created by KiCad (PCBNEW 10.0.6) date 1*\n" + BODY
)
GERBER_B = (
    b"%TF.CreationDate,2027-01-01T00:00:00+00:00*%\nG04 Created by KiCad (PCBNEW 10.0.6) date 2*\n" + BODY
)
ARTIFACTS = (
    Artifact("pos/b-pos.csv", "pos", None, b"Ref\n", True),
    Artifact("gerbers/b-F_Cu.gbr", "gerbers", "F.Cu", GERBER_A, False),
    Artifact("drill/b-PTH.drl", "drill", None, b"M48\n; DRILL file KiCad 10.0.6 date x\nM30\n", False),
)


def _manifest() -> dict[str, object]:
    return build(board=BOARD, tool_version="10.0.6", artifacts=ARTIFACTS, timestamp=WHEN)


def test_manifest_validates_against_its_schema() -> None:
    manifest = _manifest()
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json")) == []
    assert manifest["schema"] == SCHEMA == "fenolite.artifacts.v0"
    assert manifest["fenolite"] == fenolite.__version__
    assert manifest["generated"] == "2026-01-02T03:04:05+00:00"
    assert manifest["tool"] == {"name": "kicad-cli", "version": "10.0.6"}
    assert manifest["board"] == {"path": "board.kicad_pcb", "sha256": "a" * 64, "format_version": 20260206}
    entries = manifest["artifacts"]
    assert isinstance(entries, list)
    assert [e["path"] for e in entries] == ["drill/b-PTH.drl", "gerbers/b-F_Cu.gbr", "pos/b-pos.csv"]
    gerber = entries[1]
    assert gerber["layer"] == "F.Cu" and gerber["kind"] == "gerbers" and gerber["bytes"] == len(GERBER_A)
    assert gerber["sha256"] == hashlib.sha256(GERBER_A).hexdigest()
    assert gerber["evidence"] == EVIDENCE.level.value
    assert entries[2]["layer"] is None
    assert FILE_NAME not in [e["path"] for e in entries]


def test_schema_rejects_a_bad_hash() -> None:
    manifest = _manifest()
    manifest["artifacts"][0]["sha256"] = "xyz"  # type: ignore[index]
    assert _schema.validate(manifest, _schema.load("fenolite.artifacts.v0.json"))


def test_dates_do_not_change_the_content_hash() -> None:
    assert hashlib.sha256(GERBER_A).hexdigest() != hashlib.sha256(GERBER_B).hexdigest()
    assert content_sha256(GERBER_A, "gerbers") == content_sha256(GERBER_B, "gerbers")
    assert content_sha256(GERBER_A, "gerbers") == hashlib.sha256(b"%ADD10C,0.2*%\n").hexdigest()


def test_a_changed_aperture_changes_the_content_hash() -> None:
    changed = GERBER_A.replace(b"%ADD10C,0.2*%", b"%ADD10C,0.3*%")
    assert content_sha256(GERBER_A, "gerbers") != content_sha256(changed, "gerbers")


def test_drill_and_job_file_date_lines() -> None:
    one = b"M48\n; DRILL file {KiCad 9.0.9} date 2026-10-03T08:31:11\n; #@! TF.CreationDate,2026-10-03*\nT1\n"
    two = b"M48\n; DRILL file {KiCad 9.0.9} date 2027-01-01T00:00:00\n; #@! TF.CreationDate,2027-01-01*\nT1\n"
    assert (
        content_sha256(one, "drill")
        == content_sha256(two, "drill")
        == hashlib.sha256(b"M48\nT1\n").hexdigest()
    )
    job_a = b'{\n  "Header": {\n    "CreationDate": "2026-10-03T16:30:49+08:00"\n  }\n}\n'
    job_b = job_a.replace(b"2026", b"2027")
    assert content_sha256(job_a, "gerbers") == content_sha256(job_b, "gerbers")


def test_repeatable_kinds_and_binary_data_hash_every_byte() -> None:
    data = bytes(range(256)) + b"\n%TF.CreationDate,x\n"
    assert content_sha256(data, "pos") == hashlib.sha256(data).hexdigest()
    assert content_sha256(data, "unknown-kind") == hashlib.sha256(data).hexdigest()


def test_crlf_line_ends_are_kept() -> None:
    crlf = b"%TF.CreationDate,a*%\r\nX1Y1D02*\r\n"
    assert content_sha256(crlf, "gerbers") == hashlib.sha256(b"X1Y1D02*\r\n").hexdigest()


def test_reproducible_with_a_timestamp() -> None:
    text = dumps(_manifest())
    assert text == dumps(_manifest()) and text.endswith("}\n") and not text.endswith("\n\n")
    assert json.loads(text) == _manifest()
    assert list(json.loads(text)) == sorted(json.loads(text))
    assert str(Path.home()) not in text and "/tmp" not in text and "\\" not in text
