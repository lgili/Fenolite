# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Proposals use the CLI plan protocol and share the human review gate (c0265)."""

import hashlib
import shutil
from pathlib import Path

from _checkcli import run

from fenolite.library.proposals import parse_proposal
from fenolite.library.proposals.schema import Proposal, proposal_text

DATA = Path(__file__).resolve().parents[3] / "tests/data/proposals"
STAMP = ("--timestamp", "2026-11-01T00:00:00Z")


def args():
    return (
        "library",
        "propose",
        "--datasheet",
        str(DATA / "exb6202.pdf"),
        "--proposal",
        str(DATA / "exb6202.proposal.toml"),
        "--out",
        "devices/proposed",
        *STAMP,
    )


def test_skeleton_read_only_and_invalid_pdf(monkeypatch, tmp_path):
    code, reply, _, _ = run(
        monkeypatch, tmp_path, "library", "propose", "--datasheet", str(DATA / "exb6202.pdf")
    )
    assert code == 0 and reply["result"]["guide"] == "datasheets" and "plan" not in reply["result"]
    assert hashlib.sha256((DATA / "exb6202.pdf").read_bytes()).hexdigest() in reply["result"]["skeleton"]
    (tmp_path / "bad.pdf").write_bytes(b"not a PDF")
    assert run(monkeypatch, tmp_path, "library", "propose", "--datasheet", "bad.pdf")[0] == 3


def test_plan_confirm_result_and_checked_records(monkeypatch, tmp_path):
    code, reply, error, _ = run(monkeypatch, tmp_path, *args(), "--dry-run")
    assert code == 0, (reply, error)
    result = reply["result"]
    assert set(result) >= {
        "device",
        "folder",
        "datasheet",
        "proposals",
        "package",
        "doubts",
        "uncited",
        "plan",
    }
    assert result["schema"] == "fenolite.library-propose.v0" and len(result["plan"]) == 7
    assert not (tmp_path / "devices").exists()
    code, written, error, _ = run(monkeypatch, tmp_path, *args(), "--confirm", "--plan", result["plan_id"])
    assert code == 0, (written, error)
    assert len(written["receipt"]["written"]) == 7
    code, checked, error, _ = run(monkeypatch, tmp_path, "library", "check", "devices/proposed/EXB6202")
    assert code == 0, (checked, error)
    assert len(checked["result"]["items"]) == 3
    assert all(i["evidence"] == "UNVERIFIED" for i in checked["result"]["items"])


def test_proposal_and_pdf_edits_invalidate_staged_plan(monkeypatch, tmp_path):
    pdf = tmp_path / "sheet.pdf"
    shutil.copy(DATA / "exb6202.pdf", pdf)
    command = (
        "library",
        "propose",
        "--datasheet",
        "sheet.pdf",
        "--proposal",
        str(DATA / "exb6202.proposal.toml"),
        "--out",
        "devices",
        *STAMP,
    )
    code, reply, _, _ = run(monkeypatch, tmp_path, *command, "--dry-run")
    assert code == 0
    pdf.write_bytes(pdf.read_bytes() + b"changed")
    assert run(monkeypatch, tmp_path, *command, "--confirm", "--plan", reply["result"]["plan_id"])[0] == 4
    assert not (tmp_path / "devices").exists()


def test_dense_second_proposal_is_required_and_disagreements_plan_nothing(monkeypatch, tmp_path):
    command = ("library", "propose", "--datasheet", str(DATA / "exb6202.pdf"), "--out", "devices", *STAMP)
    code, reply, _, _ = run(
        monkeypatch, tmp_path, *command, "--proposal", str(DATA / "grid-1.proposal.toml"), "--dry-run"
    )
    assert code == 5 and "proposal.second-required" in {f["code"] for f in reply["issues"]}
    assert "plan" not in reply["result"]
    assert (
        run(
            monkeypatch,
            tmp_path,
            *command,
            "--proposal",
            str(DATA / "grid-1.proposal.toml"),
            "--proposal",
            str(DATA / "grid-2.proposal.toml"),
            "--dry-run",
        )[0]
        == 0
    )


def test_review_gate_and_reviewed_or_edited_reproposal_refused(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, *args(), "--confirm")[0] == 0
    target = "devices/proposed/EXB6202/device.toml"
    code, checked, _, _ = run(monkeypatch, tmp_path, "library", "check", target)
    assert code == 0
    sha = checked["result"]["items"][0]["sheet"]["sha256"]
    review = (
        "library",
        "review",
        target,
        "--accept",
        "--reviewer",
        "human-reviewer",
        "--sheet",
        sha,
        *STAMP,
        "--confirm",
    )
    code, reply, _, _ = run(monkeypatch, tmp_path, *review)
    assert code == 5 and "proposal.review-datasheet" in {f["code"] for f in reply["issues"]}
    code, reply, error, _ = run(monkeypatch, tmp_path, *review, "--datasheet", str(DATA / "exb6202.pdf"))
    assert code == 0, (reply, error)
    for _ in range(2):
        assert run(monkeypatch, tmp_path, "library", "check", target)[0] == 0
    assert run(monkeypatch, tmp_path, *args(), "--confirm")[0] == 7
    copied = tmp_path / "devices/proposed/EXB6202/proposal.toml"
    copied.write_text(copied.read_text() + "\n# authored annotation after review\n")
    code, changed, _, _ = run(monkeypatch, tmp_path, "library", "check", target)
    assert code == 5
    assert changed["result"]["items"][0]["review"]["state"] == "stale"


def test_target_escape_and_unknown_flags_are_refused(monkeypatch, tmp_path):
    command = list(args())
    command[command.index("devices/proposed")] = "../outside"
    assert run(monkeypatch, tmp_path, *command, "--dry-run")[0] == 2
    assert run(monkeypatch, tmp_path, "library", "check", str(DATA), "--proposal", "unused")[0] == 2
    assert run(monkeypatch, tmp_path, *args(), "--item", "irrelevant", "--dry-run")[0] == 2


def test_corrected_draft_replaces_only_unedited_files(monkeypatch, tmp_path):
    assert run(monkeypatch, tmp_path, *args(), "--confirm")[0] == 0
    source = parse_proposal((DATA / "exb6202.proposal.toml").read_text())
    source.data["pin"][0]["name"] = "CORRECTED"
    replacement = tmp_path / "corrected.toml"
    replacement.write_text(proposal_text(Proposal(source.data, {}, {})))
    command = list(args())
    command[command.index(str(DATA / "exb6202.proposal.toml"))] = str(replacement)
    code, reply, error, _ = run(monkeypatch, tmp_path, *command, "--confirm")
    assert code == 0, (reply, error)
    native = tmp_path / "devices/proposed/EXB6202/EXB6202.kicad_sym"
    assert "CORRECTED" in native.read_text()
    native.write_text(native.read_text() + "\n; authored manual edit\n")
    assert run(monkeypatch, tmp_path, *command, "--confirm", "--allow-lossy")[0] == 7


def test_open_doubt_blocks_human_acceptance(monkeypatch, tmp_path):
    source = parse_proposal((DATA / "exb6202.proposal.toml").read_text())
    source.data["doubt"] = [{"field": "package.lead.length", "reason": "unreadable"}]
    proposal = tmp_path / "doubt.toml"
    proposal.write_text(proposal_text(Proposal(source.data, {}, {})))
    command = list(args())
    command[command.index(str(DATA / "exb6202.proposal.toml"))] = str(proposal)
    assert run(monkeypatch, tmp_path, *command, "--confirm")[0] == 0
    target = "devices/proposed/EXB6202/device.toml"
    code, checked, _, _ = run(monkeypatch, tmp_path, "library", "check", target)
    assert code == 0
    code, reply, error, _ = run(
        monkeypatch,
        tmp_path,
        "library",
        "review",
        target,
        "--accept",
        "--reviewer",
        "human-reviewer",
        "--sheet",
        checked["result"]["items"][0]["sheet"]["sha256"],
        "--datasheet",
        str(DATA / "exb6202.pdf"),
        "--confirm",
        *STAMP,
    )
    assert code == 5, (reply, error)
    assert "proposal.review-doubt" in {i["code"] for i in reply["issues"]}
    assert 'evidence = "UNVERIFIED"' in (tmp_path / target).read_text()
