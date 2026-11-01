# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Human review binds the PDF, all citations, doubts and generated content (c0265)."""

from pathlib import Path

from fenolite.catalog.records import DeviceRecord, parse_record
from fenolite.library.proposals import parse_proposal, proposal_outputs_current, review_gate
from fenolite.library.proposals.convert import convert

DATA = Path(__file__).resolve().parents[3] / "data/proposals"


def folder(tmp_path, change=None):
    proposal = parse_proposal((DATA / "exb6202.proposal.toml").read_text())
    if change:
        change(proposal.data)
    from fenolite.library.proposals.schema import Proposal, proposal_text

    proposal = parse_proposal(proposal_text(Proposal(proposal.data, {}, {})))
    generated = convert([proposal], (DATA / "exb6202.pdf").read_bytes())
    for name, data in generated.files.items():
        (tmp_path / name).write_bytes(data)
    return tmp_path


def test_exact_datasheet_and_current_content_required(tmp_path):
    path = folder(tmp_path)
    assert review_gate(path, DATA / "exb6202.pdf") == []
    assert "proposal.review-datasheet" in {i.code for i in review_gate(path, None)}
    other = tmp_path / "other.pdf"
    other.write_bytes(b"%PDF-authored different")
    assert "proposal.review-datasheet" in {i.code for i in review_gate(path, other)}
    (path / "EXB6202.kicad_mod").write_text("changed")
    assert "proposal.review-unchecked" in {i.code for i in review_gate(path, DATA / "exb6202.pdf")}


def test_open_doubt_and_missing_citation_block_review(tmp_path):
    path = folder(
        tmp_path,
        lambda r: (
            r.update(doubt=[{"field": "package.lead.length", "reason": "unreadable"}]),
            r["pin"][0].pop("cite"),
        ),
    )
    assert {i.code for i in review_gate(path, DATA / "exb6202.pdf")} >= {
        "proposal.review-doubt",
        "proposal.review-uncited",
    }


def test_output_verifier_needs_no_pdf_and_hashes_exact_bytes(tmp_path):
    path = folder(tmp_path)
    record = parse_record((path / "device.toml").read_text())
    assert isinstance(record, DeviceRecord)
    assert proposal_outputs_current(record, path)
    (path / "proposal.toml").write_text((path / "proposal.toml").read_text() + "\n# authored edit\n")
    assert not proposal_outputs_current(record, path)
