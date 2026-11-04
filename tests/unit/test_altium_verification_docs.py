# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pages of the Altium verification (capability altium-verification, "Altium verification is
documented", scenario "Pages name the levels and the codes"; change c0044)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from fenolite.backends.altium.backend import READ_KINDS
from fenolite.checks.codes import ISSUE_CODES
from fenolite.checks.documents import DOCUMENT_STAGES

ROOT = Path(__file__).resolve().parents[2]
LEVELS = ("RT-A0", "RT-A1", "RT-A2")
CODES = (
    "check.document-missing",
    "check.rta0-failed",
    "check.rta1-failed",
    "check.rta1-normalised",
    "check.rta2-failed",
    "check.roundtrip-unjudged",
)
SKIPS = ("native-input", "no-schematic", "single-source", "not-judged", "read-refused", "cache-unreadable")


def _page(name: str) -> str:
    return (ROOT / "docs" / name).read_text(encoding="utf-8")


def _drawn_proof_path() -> Path:
    changes = ROOT / "openspec/changes"
    candidates = [
        changes / "c0276-drawn-schematic",
        *sorted((changes / "archive").glob("*-c0276-drawn-schematic")),
    ]
    found = [path for path in candidates if path.is_dir()]
    assert len(found) == 1, "expected exactly one c0276 change directory"
    return found[0] / "native-visual-proof.json"


def _drawn_visual_proof() -> dict:
    return json.loads(_drawn_proof_path().read_text(encoding="utf-8"))


def _section(text: str, heading: str) -> str:
    start = text.index(f"\n{heading}\n")
    level = heading.split(" ")[0]
    found = re.search(rf"\n{level} ", text[start + 1 :])
    return text[start : start + 1 + found.start()] if found else text[start:]


def test_levels_are_named_in_the_three_pages() -> None:
    for name in ("altium.md", "roadmap.md", "cli-contract.md", "evidence/altium-roundtrip.md"):
        text = _page(name)
        for level in LEVELS:
            assert level in text, (name, level)


def test_contract_names_the_stages_the_codes_and_the_skip_reasons() -> None:
    contract = _page("cli-contract.md")
    section = _section(contract, "### check on Altium input")
    for stage in DOCUMENT_STAGES:
        assert f"`{stage}`" in section, stage
    for reason in SKIPS:
        assert f"`{reason}`" in section, reason
    for key in (
        "backend",
        "project",
        "board",
        "built",
        "files",
        "documents",
        "skipped",
        "compared",
        "unwritten",
    ):
        assert f"`{key}`" in section, key
    for code in CODES:
        assert code in ISSUE_CODES and f"`{code}`" in contract, code
    assert re.search(r"(?m)^## diff$", contract)
    diff = _section(contract, "## diff")
    for view in ("--view model", "--view tree", "--view records"):
        assert view in diff, view
    inspect = _section(contract, "## inspect")
    for kind in READ_KINDS:
        assert f"`{kind}`" in inspect, kind
    assert "`opaque_count`" in inspect and "`result.streams`" in inspect


def test_altium_page_has_the_round_trips_section() -> None:
    section = _section(_page("altium.md"), "## Round trips")
    for word in (
        "not-a-container",
        "too-large",
        "writer-refused",
        "native-input",
        "fenolite check",
        "fenolite inspect",
    ):
        assert word in section, word
    assert "--view records" in section and "model-predates-board" in section and "Written scope" in section
    assert "do not take Altium files yet" not in _page("altium.md")


def test_roadmap_says_what_this_change_adds_to_diff() -> None:
    roadmap = _page("roadmap.md")
    assert "Done as c0044" in roadmap and "--view records" in roadmap and "c0066" in roadmap


def _part_s() -> str:
    return _section(_page("evidence/altium-pcb.md"), "## Part S: slots and cut-outs")


def test_part_s_names_the_eight_cases_with_their_expected_outcomes() -> None:
    """Requirement "Kit cases for slots and cut-outs" (change c0168): cases S1 to S8, each with an expected
    outcome, the kit's files and the hypothesis it settles."""
    part = _part_s()
    for case in range(1, 9):
        found = re.search(rf"\*\*S{case}\*\*(.+?)(?=\n\d+\. \*\*S|\n\nSend)", part, re.S)
        assert found is not None, case
        assert "Expected" in found.group(1), case
    for name in ("regions/", "clearance/", "gate-off/", "SHA256SUMS", "H-A-SLOT-KIT", "CUTOUT_REGIONS"):
        assert name in part, name


def _part_s_reports() -> str:
    reports = _section(_page("evidence/altium-pcb.md"), "## Reports")
    return "\n".join(
        block for block in reports.split("\n### ") if block.split("\n", 1)[0].rstrip().endswith("Part S")
    )


def test_part_s_gate_follows_the_report() -> None:
    """Scenario "Gate follows the report": ``pcbdoc.CUTOUT_REGIONS`` is true only when a report of Part S
    records S3, S4 and S5 as passed."""
    from fenolite.backends.altium.pcbdoc import CUTOUT_REGIONS

    if not CUTOUT_REGIONS:
        return
    reports = _part_s_reports()
    for case in ("S3", "S4", "S5"):
        assert re.search(rf"\|\s*{case}\s*\|[^\n]*\|\s*as expected\s*\|", reports), case


def _part_f() -> str:
    return _section(_page("evidence/altium-draftsman.md"), "## Part F: Draftsman documents")


def test_part_f_f0_names_the_fourteen_steps_with_their_expected_outcomes() -> None:
    """Requirement "Kit cases for Draftsman documents" (change c0172, task 1.3): round F0 names the
    observation files F0.1 to F0.14 in order, each with an expected outcome, the kit's files, the hypotheses
    it settles and the path scan that comes before any file is read."""
    part = _part_f()
    start = part.index("### Round F0")
    end = part.find("\n### ", start + 1)
    f0 = part[start : end if end > 0 else len(part)]
    found = [int(n) for n in re.findall(r"\*\*F0\.(\d+)\*\*", f0)]
    assert found == list(range(1, 15))
    for step in range(1, 15):
        body = re.search(rf"\*\*F0\.{step}\*\*(.+?)(?=\n\d+\. \*\*F0|\n\nSend)", f0, re.S)
        assert body is not None and "Expected" in body.group(1), step
    for name in (
        "session-6/F0-draftsman",
        "blink_routed/",
        "README.md",
        "SHA256SUMS",
        "H-A-DWF-CONTAINER",
        "H-A-DWF-FIELD",
        "fenolite kit verify",
        "Altium Designer 24.5.2.23",
    ):
        assert name in f0 or name in part, name


def test_part_f_reports_hold_no_altium_verified_row_without_a_report() -> None:
    """No ``H-A-DWF-*`` row and no row of ``draftsman.md`` is ``ALTIUM-VERIFIED`` while Part F has no
    recorded report."""
    reports = _section(_page("evidence/altium-draftsman.md"), "## Reports")
    if "No report of Part F has been received" not in reports:
        return
    facts = _page("formats/altium/draftsman.md")
    assert "ALTIUM-VERIFIED" not in facts
    register = _page("hypotheses.md")
    rows = [line for line in register.splitlines() if line.startswith("| H-A-DWF-")]
    assert rows and not [line for line in rows if "| ALTIUM-VERIFIED" in line]


def test_part_f_fp_and_acceptance_cases_are_ready_and_gate_is_closed() -> None:
    from fenolite.backends.altium import draftsman

    part = _part_f()
    assert [int(n) for n in re.findall(r"\*\*FP(\d)\*\*", part)] == list(range(1, 6))
    assert [int(n) for n in re.findall(r"\*\*F(\d)\*\*", part)] == list(range(1, 9))
    assert "status.json" in part and "unjudged" in part and "SHA256SUMS" in part
    assert "FENOLITE_ALTIUM_F8" in part and "kit privacy scan" in part
    reports = _section(_page("evidence/altium-draftsman.md"), "## Reports")
    if draftsman.NATIVE_WRITE:
        for case in ("FP1", "FP2", "FP3", "FP4"):
            assert re.search(rf"\|\s*{case}\s*\|[^\n]*\|\s*as expected\s*\|", reports), case


def _part_q() -> str:
    return _section(_page("evidence/altium-pcb.md"), "## Part Q: panels and the Embedded Board Array")


def test_part_q_names_the_twelve_cases_with_their_expected_outcomes() -> None:
    """Requirement "Kit cases for panels" (change c0173): cases Q1 to Q12, each with an expected outcome,
    the kit's files, the hypotheses they settle and the gate."""
    part = _part_q()
    for case in range(1, 13):
        found = re.search(rf"\*\*Q{case}\*\*(.+?)(?=\n\d+\. \*\*Q|\n\nSend)", part, re.S)
        assert found is not None, case
        assert "Expected" in found.group(1), case
    for name in (
        "board/", "written/", "flat/", "expected.md", "SHA256SUMS", "session-6/Q-panels",
        "H-A-PANEL-RECORD", "H-A-PANEL-LAYERKIND", "H-A-PANEL-KIT", "EMBEDDED_ARRAYS",
    ):  # fmt: skip
        assert name in part, name


def _part_q_reports() -> str:
    reports = _section(_page("evidence/altium-pcb.md"), "## Reports")
    return "\n".join(
        block for block in reports.split("\n### ") if block.split("\n", 1)[0].rstrip().endswith("Part Q")
    )


def test_part_q_gate_follows_the_report() -> None:
    """Scenario "Gate follows the report": ``pcbdoc.EMBEDDED_ARRAYS`` is true only when a report of Part Q
    records Q7, Q8 and Q9 as passed."""
    from fenolite.backends.altium.pcbdoc import EMBEDDED_ARRAYS

    if not EMBEDDED_ARRAYS:
        return
    reports = _part_q_reports()
    for case in ("Q7", "Q8", "Q9"):
        assert re.search(rf"\|\s*{case}\s*\|[^\n]*\|\s*as expected\s*\|", reports), case


def _part_j() -> str:
    return _section(_page("evidence/altium-edit.md"), "## Part J: edit sessions")


def test_part_j_names_the_cases_with_their_expected_outcomes() -> None:
    """Requirement "Kit cases for edit sessions" (change c0241, task 1.1): cases J1 to J33 in order, each
    with an expected outcome, the kit's files, the folder, and every hypothesis of the edit session and of
    the integrity rules named by at least one case."""
    part = _part_j()
    assert [int(n) for n in re.findall(r"^\d+\. \*\*J(\d+)\*\*", part, re.M)] == list(range(1, 34))
    for case in range(1, 34):
        found = re.search(rf"\*\*J{case}\*\*(.+?)(?=\n\d+\. \*\*J|\n\nSend)", part, re.S)
        assert found is not None, case
        assert "Expected" in found.group(1), case
    for name in (
        "board/", "written/", "faults/", "expected.md", "README.md", "PART-J.md", "SHA256SUMS",
        "session-7/J-edit", "fenolite kit verify", "test_part_j.py",
    ):  # fmt: skip
        assert name in part, name
    register = _page("hypotheses.md")
    rows = re.findall(r"^\| (H-A-(?:EDIT|INTEG)-[A-Z]+) \|", register, re.M)
    assert len(rows) == 21
    for row in rows:
        assert f"`{row}`" in part, row
        line = next(line for line in register.splitlines() if line.startswith(f"| {row} |"))
        assert "| INFERRED |" in line and "kit request (maintainer): Part J, case" in line, row


def test_part_j_reports_hold_no_altium_verified_row_without_a_report() -> None:
    """No ``H-A-EDIT-*`` or ``H-A-INTEG-*`` row is ``ALTIUM-VERIFIED`` while Part J has no recorded report."""
    reports = _section(_page("evidence/altium-edit.md"), "## Reports")
    if "No report of Part J has been received" not in reports:
        return
    rows = [
        line
        for line in _page("hypotheses.md").splitlines()
        if line.startswith(("| H-A-EDIT-", "| H-A-INTEG-"))
    ]
    assert rows and not [line for line in rows if "| ALTIUM-VERIFIED" in line]


def test_drawn_report_acceptance_preserves_historical_failures_and_kit_scope() -> None:
    section = _section(
        _page("evidence/altium-schematic.md"), "## Drawn-sheet kit request (c0276, 2026-11-01)"
    )
    for words in (
        "H-A-DRAWN-WRITE",
        "INFERRED",
        "pending",
        "Altium is unavailable",
        "--altium-format binary",
        "--altium-format ascii",
        ".fenolite/circuit.json",
        "repeated instances",
        "new copy",
    ):
        assert words in section
    row = next(line for line in _page("hypotheses.md").splitlines() if line.startswith("| H-A-DRAWN-WRITE |"))
    assert "INFERRED" in row and "formal-kit drawn step/source binding" in row
    assert "Altium24.5.2.23" in row and "altium-drawn-native.md" in row
    proof = _drawn_visual_proof()
    approval = proof["maintainer_report_approval"]
    assert approval["status"] == "APPROVED"
    assert approval["answer"] == "Aprovo o relatório com essas limitações"
    assert len(approval["reviewed_report_sha256"]) == 64
    assert len(proof["captures"]) == 14
    assert all(capture["operator_inspected"] for capture in proof["captures"])
    assert proof["all_fourteen_native_sources_unchanged"]
    assert len(proof["limitations"]) == 5
    assert approval["writer_experimental"] and approval["CI_pending"]
    assert not proof["hypothesis_level_changed"]
    assert not proof["writer_graduation_claimed"] and not proof["current_CI_pass_claimed"]
    observed = json.loads(_page("evidence/altium-drawn-native.json"))
    assert not observed["full_gate_passed"] and not observed["evidence_promoted"]
    assert len(observed["original_cases"]) == 6
    assert all(case["connectivity_equal"] for case in observed["original_cases"])
    assert any(case["compiler_messages"].get("[Error]", 0) for case in observed["original_cases"])
    assert observed["native_saved_copies"]["complete_projects_reopened"] == 10
    assert observed["native_negative_control"]["correctly_refused"]


def test_clean_drawn_native_control_is_scoped_and_preserves_its_negative() -> None:
    observed = json.loads(_page("evidence/altium-clean-drawn-native.json"))
    assert "schema" not in observed  # internal evidence, not a new public persisted format
    assert observed["native_version"] == "24.5.2.23"
    assert observed["writer_source_commit"] == "da89051f6bd7cfe81cae5fd3daedaa3e8d565629"
    assert (
        observed["task_6_3_passed"] and not observed["full_gate_passed"] and not observed["evidence_promoted"]
    )
    assert observed["original_6_2_findings_preserved"]
    assert observed["intentional_unused_pins"] == [["U1", "11"], ["U1", "12"]]
    cases = {case["case"]: case for case in observed["cases"]}
    assert len(cases) == 4
    assert cases["unmarked-ascii"]["compiler_messages"] == {"[Error]": 2, "[Warning]": 2}
    negative = cases["marked-broken-ascii"]
    assert not negative["connectivity_equal"] and negative["native_groups"] == 40
    assert len(negative["name_differences"]) == 4 and negative["compiler_messages"] == {"[Error]": 14}
    positives = [cases[name] for name in ("marked-binary", "marked-ascii")]
    assert len(observed["saved_reopened_cases"]) == 2
    for case in positives + observed["saved_reopened_cases"]:
        assert case["connectivity_equal"] and case["native_groups"] == 36
        assert not case["name_differences"] and not case["blocking_messages"]
        assert case["compiler_messages"] == {"[Info]": 1}
    assert all(
        case["all_pins"] == case["all_native_pins"] == 40
        for case in observed["cases"] + observed["saved_reopened_cases"]
    )
    assert observed["original_mac_and_windows_files_unchanged"] == 60
    assert len(observed["saved_documents"]) == len(observed["marker_comparisons"]) == 4
    for case in observed["marker_comparisons"]:
        assert case["positions_and_flags_exact"] and case["before"] == case["after"]
        assert len(case["before"]) == (2 if case["file"] == "drawn_bus.SchDoc" else 0)
    assert all(
        case["all_native_name_partitions_equal"] and case["groups"] == 36
        for case in observed["all_native_names_before_marking_and_after_save"].values()
    )
    assert "24.5.2.23" in _page("evidence/altium-drawn-native.md")


@pytest.mark.parametrize("archived", [False, True])
def test_drawn_proof_reader_active_or_archived_with_cp1252_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, archived: bool
) -> None:
    original = _drawn_proof_path().read_bytes()
    source_root = ROOT
    changes = tmp_path / "openspec/changes"
    folder = changes / ("archive/2026-11-03-c0276-drawn-schematic" if archived else "c0276-drawn-schematic")
    folder.mkdir(parents=True)
    copied = folder / "native-visual-proof.json"
    copied.write_bytes(original)
    control = tmp_path / "locale-control.txt"
    control.write_bytes("Aprovação “íntegra”".encode())
    original_open = Path.open

    def cp1252_open(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "cp1252"
        return original_open(path, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", cp1252_open)
    with pytest.raises(UnicodeDecodeError):
        control.read_text()
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    monkeypatch.setitem(
        globals(), "_page", lambda name: (source_root / "docs" / name).read_text(encoding="utf-8")
    )
    assert _drawn_visual_proof() == json.loads(original.decode("utf-8"))
    assert copied.read_bytes() == original
    test_drawn_report_acceptance_preserves_historical_failures_and_kit_scope()


@pytest.mark.parametrize("layout", ["missing", "file", "active-and-archive", "two-archives"])
def test_drawn_proof_reader_refuses_missing_or_ambiguous_directories(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, layout: str
) -> None:
    original = _drawn_proof_path().read_bytes()
    changes = tmp_path / "openspec/changes"
    active = changes / "c0276-drawn-schematic"
    archives = [
        changes / "archive/2026-11-03-c0276-drawn-schematic",
        changes / "archive/2026-11-04-c0276-drawn-schematic",
    ]
    if layout == "file":
        changes.mkdir(parents=True)
        active.write_bytes(b"not a directory")
    folders = (
        [active, archives[0]]
        if layout == "active-and-archive"
        else archives
        if layout == "two-archives"
        else []
    )
    for folder in folders:
        folder.mkdir(parents=True)
        (folder / "native-visual-proof.json").write_bytes(original)
    monkeypatch.setitem(globals(), "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="exactly one c0276 change directory"):
        _drawn_visual_proof()
