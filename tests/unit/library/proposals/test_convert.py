# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Proposals generate deterministic unverified records, bodies and native definitions (c0265)."""

from dataclasses import replace
from pathlib import Path

from fenolite.catalog.records import PinsRecord, ProposalOrigin, parse_record
from fenolite.core.coords import Size
from fenolite.library.proposals import parse_proposal
from fenolite.library.proposals.convert import GenerationRefused, convert
from fenolite.library.proposals.schema import Proposal, proposal_text

DATA = Path(__file__).resolve().parents[3] / "data/proposals"


def example(name="exb6202.proposal.toml"):
    return parse_proposal((DATA / name).read_text(), file=name)


def test_device_folder_and_same_bytes():
    pdf = (DATA / "exb6202.pdf").read_bytes()
    first = convert([example()], pdf, date="2026-11-01", licence="CC0-1.0")
    assert first.files == convert([example()], pdf, date="2026-11-01", licence="CC0-1.0").files
    assert set(first.files) == {
        "device.toml",
        "pins.toml",
        "package.toml",
        "EXB6202.kicad_sym",
        "EXB6202.kicad_mod",
        "EXB6202.step",
        "proposal.toml",
    }
    assert first.footprint.bodies
    assert not [f for f in first.issues if f.severity == "error"]
    for name in ("device.toml", "pins.toml", "package.toml"):
        record = parse_record(first.files[name].decode())
        assert record.header.evidence == "UNVERIFIED" and record.header.licence == "CC0-1.0"
        assert isinstance(record.header.origin, ProposalOrigin)
        assert record.header.origin.datasheet_sha256 == example().data["datasheet"]["sha256"]
        assert record.header.origin.proposer[0].name == "First reader"


def test_dense_grid_pair_and_alternates_stay_in_proposal():
    pair = [example(f"grid-{i}.proposal.toml") for i in (1, 2)]
    result = convert(pair, (DATA / "exb6202.pdf").read_bytes())
    assert len(result.footprint.pads) == 8 and "B2" not in {p.number for p in result.footprint.pads}
    assert "proposal-2.toml" in result.files
    proposal = example()
    proposal.data["pin"][0]["alternates"] = [{"name": "MUX", "type": "output"}]
    proposal = parse_proposal(proposal_text(Proposal(proposal.data, {}, {})))
    result = convert([proposal], (DATA / "exb6202.pdf").read_bytes())
    assert all(not pin.alternates for pin in result.symbol.pins)
    assert b"MUX" in result.files["proposal.toml"] and b"MUX" not in result.files["pins.toml"]


def test_generator_or_rules_reject_inconsistent_span():
    proposal = example()
    proposal.data["package"]["span"] = "3.1mm"
    proposal = parse_proposal(proposal_text(Proposal(proposal.data, {}, {})))
    try:
        result = convert([proposal], (DATA / "exb6202.pdf").read_bytes())
        findings = result.issues
    except GenerationRefused as error:
        findings = error.issues
    assert any(f.severity == "error" and ("span" in f.message or "span" in f.where) for f in findings)


def test_conversion_calls_no_network_or_subprocess(monkeypatch):
    def refused(*args, **kwargs):
        raise AssertionError("extraction belongs outside Fenolite")

    monkeypatch.setattr("subprocess.run", refused)
    monkeypatch.setattr("subprocess.Popen", refused)
    monkeypatch.setattr("socket.socket", refused)
    assert convert([example()], (DATA / "exb6202.pdf").read_bytes()).files


def test_center_depopulation_keeps_printed_row_labels():
    pair = [example(f"grid-{i}.proposal.toml") for i in (1, 2)]
    for proposal in pair:
        proposal.data["package"].update(row_labels=["A", "C", "E"], depopulated={"center": "1x1"})
        for pin in proposal.data["pin"]:
            pin["number"] = {"A": "A", "B": "C", "C": "E"}[pin["number"][0]] + pin["number"][1:]
    pair = [parse_proposal(proposal_text(Proposal(p.data, {}, {}))) for p in pair]
    result = convert(pair, (DATA / "exb6202.pdf").read_bytes())
    assert {p.number for p in result.footprint.pads} == {f"{r}{c}" for r in "ACE" for c in (1, 2, 3)} - {"C2"}
    assert not [f for f in result.issues if f.severity == "error"]


def test_pin_groups_are_preserved_and_checked():
    proposal = example()
    proposal.data["pin"][0].update(group="ground", type="output")
    proposal = parse_proposal(proposal_text(Proposal(proposal.data, {}, {})))
    result = convert([proposal], (DATA / "exb6202.pdf").read_bytes())
    pins = next(r for r in result.records if isinstance(r, PinsRecord))
    assert pins.pins[0].group == "ground"
    assert "library.pin-group-type" in {f.code for f in result.issues}


def test_manufacturer_land_detects_generator_drift(monkeypatch):
    from fenolite.library.proposals import convert as pipeline

    original = pipeline.generate

    def drift(package):
        generated = original(package)
        footprint = generated.footprint
        assert footprint is not None
        pads = (
            replace(
                footprint.pads[0], size=Size(footprint.pads[0].size.w + 100_000, footprint.pads[0].size.h)
            ),
            *footprint.pads[1:],
        )
        return replace(generated, footprint=replace(footprint, pads=pads))

    monkeypatch.setattr(pipeline, "generate", drift)
    result = convert([example()], (DATA / "exb6202.pdf").read_bytes())
    assert "library.land-mismatch" in {f.code for f in result.issues if f.severity == "error"}
