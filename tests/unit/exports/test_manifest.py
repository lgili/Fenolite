# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The artefact manifest (capability manufacturing-exports, "Artefact manifest" and "Manifest merging";
changes c0024 and c0065)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import _schema
import pytest

import fenolite
from fenolite.core.errors import FormatError
from fenolite.exports import DOCUMENTS_EVIDENCE, EVIDENCE
from fenolite.exports.manifest import (
    DESIGN_KINDS,
    FILE_NAME,
    SCHEMA,
    STATES,
    ArtifactEntry,
    BoardRef,
    ToolRef,
    build,
    content_sha256,
    design_kind,
    dumps,
    entry,
    file_entry,
    load,
    merge,
    to_data,
)
from fenolite.exports.plan import DOCUMENT_KINDS, FAB_KINDS, Artifact

V01 = Path(__file__).resolve().parents[2] / "data" / "exports" / "manifest_v01.json"

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


def test_entries_carry_a_state() -> None:
    manifest = _manifest()
    entries = manifest["artifacts"]
    assert isinstance(entries, list) and len(entries) == 3
    for item in entries:
        assert item["state"] == "generated" and item["stale"] is False and item["held"] == ""
        assert item["from"] == {"board": "a" * 64} and item["tool"] == "kicad-cli 10.0.6"
        assert "from_" not in item
    states = manifest["states"]
    assert isinstance(states, dict)
    assert states == {**dict.fromkeys(STATES, 0), "generated": 3} and set(states) == set(STATES)
    assert manifest["check"] is None
    assert manifest["project"] == {"board": manifest["board"], "schematic": None}


def test_schema_names_the_states() -> None:
    schema = _schema.load("fenolite.artifacts.v0.json")
    entry = schema["$defs"]["ArtifactEntry"]
    assert entry["properties"]["state"] == {"enum": list(STATES)}
    assert "from" in entry["properties"] and "from_" not in entry["properties"]
    added = {"state", "stale", "from", "tool", "held"}
    assert added <= set(entry["properties"]) and not added & set(entry["required"])
    assert not {"project", "check", "states"} & set(schema["required"])
    manifest = _manifest()
    manifest["artifacts"][0]["state"] = "verified"  # type: ignore[index]
    assert _schema.validate(manifest, schema)


def test_manifest_of_v01_is_still_read() -> None:
    text = V01.read_text(encoding="utf-8")
    assert _schema.validate(json.loads(text), _schema.load("fenolite.artifacts.v0.json")) == []
    assert "state" not in text and "from" not in text
    manifest = load(text)
    assert [e.path for e in manifest.artifacts] == [
        "drill/board-PTH.drl", "gerbers/board-F_Cu.gbr", "pos/board-pos.csv",
    ]  # fmt: skip
    for item in manifest.artifacts:
        assert (item.state, item.stale, item.from_, item.tool, item.held) == (
            "generated",
            False,
            {},
            None,
            "",
        )
    assert manifest.project is None and manifest.check is None and manifest.states["generated"] == 3
    assert manifest.board.format_version == 20260206 and manifest.tool == ToolRef("kicad-cli", "10.0.6")


def test_a_written_manifest_reads_back() -> None:
    text = dumps(_manifest())
    again = load(text)
    assert dumps(to_data(again)) == text
    assert again.artifacts[1].layer == "F.Cu" and again.artifacts[1].from_ == {"board": "a" * 64}


@pytest.mark.parametrize(
    ("text", "locator"),
    [
        ("{", ""),
        ("[]", "/"),
        ('{"schema": "fenolite.artifacts.v1", "artifacts": []}', "/schema"),
        ('{"schema": "fenolite.artifacts.v0"}', "/artifacts"),
    ],
)
def test_load_refuses_what_is_not_a_manifest(text: str, locator: str) -> None:
    with pytest.raises(FormatError) as caught:
        load(text)
    assert caught.value.locator == locator and caught.value.file == FILE_NAME


@pytest.mark.parametrize(
    ("key", "value", "locator"),
    [
        ("state", "verified", "/artifacts/0/state"),
        ("sha256", "abc", "/artifacts/0/sha256"),
        ("path", "../board.kicad_pcb", "/artifacts/0/path"),
        ("path", "/tmp/board.gbr", "/artifacts/0/path"),
        ("from", {"board": "xyz"}, "/artifacts/0/from/board"),
        ("stale", "no", "/artifacts/0/stale"),
        ("bytes", -1, "/artifacts/0/bytes"),
    ],
)
def test_load_refuses_a_bad_entry(key: str, value: object, locator: str) -> None:
    manifest = _manifest()
    manifest["artifacts"][0][key] = value  # type: ignore[index]
    with pytest.raises(FormatError) as caught:
        load(json.dumps(manifest))
    assert caught.value.locator == locator


def test_design_kinds() -> None:
    names = ("b.kicad_pcb", "s/x.kicad_sch", "b.kicad_pro", "b.kicad_dru")
    assert [design_kind(name) for name in names] == ["kicad_pcb", "kicad_sch", "kicad_pro", "kicad_dru"]
    assert design_kind("lib/Mini.pretty/R.kicad_mod") == "kicad_mod"
    assert design_kind("lib/Mini.kicad_sym") == "kicad_sym" and design_kind("a4.kicad_wks") == "kicad_wks"
    assert design_kind("fp-lib-table") == design_kind("sub/sym-lib-table") == "lib-table"
    assert design_kind("lib/Mini.pretty/r.step") == "file"
    # a file below the project's 3dmodels/ folder is a vendored 3D model, whatever its suffix (c0116)
    assert design_kind("3dmodels/Fenolite.3dshapes/Box_2x1.step") == "3d-model"
    assert design_kind("3dmodels\\L.3dshapes\\a.wrl") == "3d-model"
    assert design_kind("3dmodels") == "file" and design_kind("fab/3dmodels/a.step") == "file"
    assert "3d-model" in DESIGN_KINDS and not set(DOCUMENT_KINDS) & DESIGN_KINDS


def _entry(path: str, data: bytes, board: str) -> ArtifactEntry:
    return file_entry(path, "gerbers", data, from_={"board": board}, tool="kicad-cli 10.0.6")


def test_merge_replaces_by_path_and_keeps_the_rest() -> None:
    old = BoardRef("board.kicad_pcb", "a" * 64, 20260206)
    new = BoardRef("board.kicad_pcb", "b" * 64, 20260206)
    tool = ToolRef("kicad-cli", "10.0.6")
    entries = [_entry("g/b.gbr", b"1", old.sha256), _entry("g/a.gbr", b"2", old.sha256)]
    first = merge(None, entries, board=old, tool=tool, timestamp=WHEN)
    assert [e.path for e in first.artifacts] == ["g/a.gbr", "g/b.gbr"]
    kept = dataclasses.replace(first.artifacts[0], state="checked", held="x")
    first = dataclasses.replace(first, artifacts=[kept, first.artifacts[1]])
    later = datetime(2026, 2, 3, tzinfo=UTC)
    entries = [_entry("g/b.gbr", b"3", new.sha256), _entry("d/c.drl", b"4", new.sha256)]
    second = merge(first, entries, board=new, tool=ToolRef("fenolite", "9.9"), timestamp=later)
    assert [e.path for e in second.artifacts] == ["d/c.drl", "g/a.gbr", "g/b.gbr"]
    assert second.artifacts[1] is kept  # not written by the second run: unchanged, its state included
    assert second.artifacts[2].from_ == {"board": "b" * 64} and second.artifacts[2].state == "generated"
    assert second.board == new and second.tool.name == "fenolite" and second.check is None
    assert second.generated == later.isoformat()
    assert second.states == {**dict.fromkeys(STATES, 0), "generated": 2, "checked": 1}
    assert _schema.validate(to_data(second), _schema.load("fenolite.artifacts.v0.json")) == []


# --- document kinds (c0116)


def test_pdf_date_does_not_change_the_content_hash() -> None:
    one = b"%PDF-1.5\n<<\n/CreationDate (D:20261005135825)\n/Title (b-F_Cu.pdf)\n>>\n%%EOF\n"
    two = one.replace(b"D:20261005135825", b"D:2026:10:05:21:44:59")
    assert one != two
    for kind in ("pdf", "sch-pdf"):
        assert content_sha256(one, kind) == content_sha256(two, kind)
        assert content_sha256(one, kind) != hashlib.sha256(one).hexdigest()
    # a kind whose runs share nothing has no prefix: its content hash is the hash of its bytes
    for kind in ("step", "odb", "ipc2581"):
        assert content_sha256(one, kind) != content_sha256(two, kind)
        assert content_sha256(one, kind) == hashlib.sha256(one).hexdigest()
    other_title = one.replace(b"b-F_Cu.pdf", b"b-B_Cu.pdf")
    assert content_sha256(one, "pdf") != content_sha256(other_title, "pdf")


def test_entry_level_follows_the_kind() -> None:
    assert DOCUMENTS_EVIDENCE.hypotheses == (
        "H-K-EXPORT-DOCS",
        "H-K-EXPORT-DOCS-REPEAT",
        "H-K-EXPORT-MODELS",
        "H-K-EXPORT-SHEETS",
    )
    for kind in DOCUMENT_KINDS:
        assert (
            entry(Artifact(f"x/{kind}", kind, None, b"x", False)).evidence == DOCUMENTS_EVIDENCE.level.value
        )
    for kind in FAB_KINDS:
        assert entry(Artifact(f"x/{kind}", kind, None, b"x", False)).evidence == EVIDENCE.level.value
    assert entry(Artifact("x/s", "step", None, b"x", False), evidence="UNVERIFIED").evidence == "UNVERIFIED"
