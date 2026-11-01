# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""c0266 library device-kind audit scenarios, on original illustrative Fenolite data."""

from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.catalog.records import DeviceRecord, Review, parse_record, record_digest, record_text
from fenolite.core.errors import FormatError
from fenolite.library.audit import audit
from fenolite.library.device_items import _proposal_issues

DEVICE = "devices/cc0/Demo/EXB"


def test_device_items_read(demo: Path) -> None:
    report = audit(demo)
    assert not report.issues, [(i.code, i.message) for i in report.issues]
    assert {f.kind for f in report.items} >= {"device", "symbol", "footprint"}


@pytest.mark.parametrize("field,value", [("id", "Other:Mismatch"), ("licence", "MIT")])
def test_device_record_identity_matches_item(demo: Path, field: str, value: str) -> None:
    path = demo / DEVICE / "EXB.toml"
    old = 'id = "Demo:EXB"' if field == "id" else 'licence = "CC0-1.0"'
    path.write_text(path.read_text().replace(old, f'{field} = "{value}"'))
    assert "library.provenance-invalid" in {i.code for i in audit(demo).issues}


def test_reserved_namespace(demo: Path) -> None:
    path = demo / DEVICE / "EXB.toml"
    path.write_text(path.read_text().replace('id = "Demo:EXB"', 'id = "Fenolite:X"'))
    assert any(i.code == "library.provenance-invalid" and "Fenolite" in i.message for i in audit(demo).issues)


def test_unregistered_source_is_bad_input(demo: Path) -> None:
    path = demo / DEVICE / "EXB.toml"
    path.write_text(path.read_text().replace("D-0001", "D-0099"))
    with pytest.raises(FormatError, match="Demo:EXB.*D-0099") as caught:
        audit(demo)
    assert caught.value.file.endswith("EXB.toml")
    from fenolite.api import run

    reply = run("library", "audit", str(demo), cwd=demo)
    assert reply.exit_code == 3 and reply.error is not None and reply.error["code"] == "FEN-3004"
    assert "D-0099" in reply.error["message"]


def test_local_import_never_ships(demo: Path) -> None:
    path = demo / DEVICE / "EXB.toml"
    path.write_text(path.read_text().replace('licence = "CC0-1.0"', 'licence = "see source terms"'))
    assert "library.not-shippable" in {i.code for i in audit(demo).issues}


def test_version_step_missing(demo: Path, tmp_path: Path) -> None:
    base = tmp_path / "base"
    shutil.copytree(demo, base)
    path = demo / DEVICE / "EXB.toml"
    path.write_text(path.read_text().replace("Two-pin regulator stand-in", "Changed regulator stand-in"))
    assert any(
        i.code == "library.version-rule" and "Demo:EXB" in i.message
        for i in audit(demo, base=str(base)).issues
    )


def test_device_dependency_matches_definition(demo: Path) -> None:
    path = demo / DEVICE / "item.json"
    data = json.loads(path.read_text())
    data["depends"] = []
    path.write_text(json.dumps(data))
    assert any(i.code == "library.provenance-invalid" and "depends" in i.message for i in audit(demo).issues)


def test_proposal_review_and_current_outputs_both_required(tmp_path: Path) -> None:
    """Real c0265 seals survive review metadata, but changed proposal/native/model bytes refuse shipping."""
    from fenolite.library.proposals import parse_proposal
    from fenolite.library.proposals.convert import convert

    data = Path(__file__).resolve().parents[3] / "tests/data/proposals"
    proposal = parse_proposal((data / "exb6202.proposal.toml").read_text())
    made = convert([proposal], (data / "exb6202.pdf").read_bytes(), licence="CC0-1.0")
    for name, payload in made.files.items():
        (tmp_path / name).write_bytes(payload)
    path = tmp_path / "device.toml"
    record = parse_record(path.read_text())
    assert isinstance(record, DeviceRecord)
    assert _proposal_issues(record, tmp_path)
    review = Review("Human Reviewer", "2026-11-01", record.header.version, record_digest(record), "INFERRED")
    record = replace(record, header=replace(record.header, reviewed_by=(review,)))
    path.write_text(record_text(record))
    assert not _proposal_issues(record, tmp_path)
    native = next(tmp_path.glob("*.kicad_mod"))
    before = native.read_bytes()
    native.write_bytes(before + b"\n")
    assert _proposal_issues(record, tmp_path)
    native.write_bytes(before)
    copied = tmp_path / "proposal.toml"
    copied.write_text(copied.read_text() + "\n# after review\n")
    assert _proposal_issues(record, tmp_path)
    changed = replace(record, header=replace(record.header, summary="changed after review"))
    assert _proposal_issues(changed, tmp_path)
