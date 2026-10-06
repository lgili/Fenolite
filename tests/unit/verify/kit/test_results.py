# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checking a kit folder after a run (capability altium-verification, "Kit result verification"), on a
simulated run: Fenolite's own writers stand in for the tool, and the form is marked synthetic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from _simulate import DATE, VERSION, poured, rebuilt, simulate, simulated_judge, without_net

from fenolite.cli._kit import (
    KIT_PROFILE,
    copper_problems,
    judge_document,
    parity_problems,
    poured_problems,
    read_document,
)
from fenolite.core.errors import FormatError
from fenolite.model.design import Design
from fenolite.verify.kit import results
from fenolite.verify.kit.manifest import FORM_FILE, blank_form
from fenolite.verify.kit.results import form_problems, privacy_scan, verify_results
from fenolite.verify.kit.steps import STEPS

USERS = "Users"  # the folder name is put together here, so that this file holds no path of a home folder


def quick(check: str, own: Path, saved: Path) -> list[str]:
    """A judge that reads no document, for the tests of the form, the text files and the scan."""
    return []


def _snapshot(folder: Path) -> dict[str, bytes]:
    files = [path for path in sorted(folder.rglob("*")) if path.is_file()]
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in files}


def _outcomes(verdict: results.KitVerdict) -> dict[str, str]:
    return {step.id: step.outcome for step in verdict.steps}


def _form(kit: Path, **changes: object) -> None:
    path = kit / FORM_FILE
    form = json.loads(path.read_text(encoding="utf-8"))
    form.update(changes)
    path.write_text(json.dumps(form), encoding="utf-8", newline="\n")


def test_a_simulated_run_passes(kit: Path) -> None:
    """Scenario "A simulated run passes": every step passes, the verdict is synthetic, nothing is
    written."""
    simulate(kit)
    before = _snapshot(kit)
    verdict = verify_results(kit, judge=simulated_judge)
    assert _snapshot(kit) == before
    assert set(_outcomes(verdict).values()) == {"pass"} and len(verdict.steps) == len(STEPS)
    assert verdict.passed and verdict.synthetic and verdict.altium_version == VERSION and verdict.date == DATE
    assert verdict.kit_problems == () and verdict.form_problems == () and verdict.privacy == ()
    held = [f.path for f in verdict.results]
    assert "results/form.json" in held and "results/flat/flat.PcbDoc" in held
    assert not any(path.endswith("expected.txt") for path in held)


def test_hypotheses_of_a_simulated_run(kit: Path) -> None:
    simulate(kit)
    found = {h.id: h for h in verify_results(kit, judge=simulated_judge).hypotheses}
    assert found["H-A-KIT-RESAVE"].outcome == "pass" and not found["H-A-KIT-RESAVE"].form
    assert found["H-A-WRITE-SCHDOC"].outcome == "pass" and found["H-A-WRITE-SCHDOC"].form
    assert found["H-A-PCBX-STACK"].form and found["H-A-PCBX-STACK"].steps == ("K5.2",)
    # the copper check runs: on the kit's own board for the report step, on the stand-in for the repour
    assert found["H-A-KIT-REPOUR"].outcome == found["H-A-KIT-DRC"].outcome == "pass"
    assert found["H-A-KIT-SCRIPT"].outcome == "skipped"
    assert not any(step.pending for step in verify_results(kit, judge=quick).steps)


def test_the_product_judge_on_fenolite_s_own_board(kit: Path) -> None:
    """Fenolite writes every polygon unpoured, so with the product's judge the repour step fails on a
    stand-in file and every other step passes; the check passes on a board whose zones hold fills."""
    simulate(kit)
    verdict = verify_results(kit, judge=judge_document)
    failed = {step.id: step.reasons for step in verdict.failed}
    assert set(failed) == {"K6.1"} and failed["K6.1"][0] == "poured: 1 of 1 polygon(s) hold no poured copper"
    assert len(failed["K6.1"]) == 2 and failed["K6.1"][1].startswith("copper.clearance: polygon(s) without")
    own = kit / "routed" / "routed.PcbDoc"
    assert copper_problems(own, repoured=False) == []
    assert copper_problems(kit / "flat" / "flat.PcbDoc", repoured=False) == [
        "0 clearance finding(s) between LED_A and VIN, not the one planted"
    ]
    board = read_document(kit / "routed" / "routed.PcbDoc")
    assert isinstance(board, Design)
    assert poured_problems(board) == ["1 of 1 polygon(s) hold no poured copper"]
    assert poured_problems(poured(board)) == []
    flat = read_document(kit / "tree" / "tree.SchDoc")
    assert isinstance(flat, Design) and poured_problems(flat) == ["the saved board holds no polygon"]
    assert all(KIT_PROFILE.values())


def test_a_lost_net_is_caught(kit: Path) -> None:
    """Scenario "A lost net is caught": the step that re-saves the document fails and names the net, and
    its hypotheses fail."""
    lost = rebuilt("flat", without_net("LED_A"))["flat.PcbDoc"]
    simulate(kit, replace={"flat/flat.PcbDoc": lost})
    verdict = verify_results(kit, judge=simulated_judge)
    assert [step.id for step in verdict.failed] == ["K1.2"]
    assert any("LED_A" in reason and "R1-2" in reason for reason in verdict.failed[0].reasons)
    found = {h.id: h.outcome for h in verdict.hypotheses}
    assert found["H-A-KIT-RESAVE"] == found["H-A-WRITE-PCBDOC"] == "fail"
    assert found["H-A-WRITE-SCHLIB"] == "pass" and not verdict.passed


def test_a_file_that_is_no_document_fails_its_step(kit: Path) -> None:
    simulate(kit, replace={"libs/libs.SchLib": b"not a compound file", "flat/flat.PrjPcb": b"[Design]\r\n"})
    failed = {step.id: step.reasons for step in verify_results(kit, judge=simulated_judge).failed}
    assert sorted(failed) == ["K1.3", "K1.5"]
    assert "cannot read" in failed["K1.3"][0] and "the project lists" in failed["K1.5"][0]


def test_a_touched_sample(kit: Path) -> None:
    """Scenario "A touched sample": every step of that sample fails, naming the kit file."""
    simulate(kit)
    target = kit / "routed" / "routed.SchDoc"
    target.write_bytes(target.read_bytes() + b"\x00")
    verdict = verify_results(kit, judge=simulated_judge)
    outcomes = _outcomes(verdict)
    routed = [step.id for step in STEPS if step.sample == "routed"]
    assert routed and all(outcomes[i] == "fail" for i in routed)
    assert all(outcomes[step.id] == "pass" for step in STEPS if step.sample != "routed")
    assert all("routed/routed.SchDoc differs from its manifest" in s.reasons[0] for s in verdict.failed)
    assert verdict.kit_problems == ("routed/routed.SchDoc differs from its digest in kit.json",)
    (kit / "STEPS.md").unlink()
    assert "STEPS.md is missing" in verify_results(kit, judge=quick).kit_problems


def test_typed_values(kit: Path) -> None:
    simulate(kit, skip=("K5.2", "K9.1"))
    form = json.loads((kit / FORM_FILE).read_text(encoding="utf-8"))
    form["values"].update({"K4.3": 2, "K8.2": "flat", "K1.8": 0})
    (kit / FORM_FILE).write_text(json.dumps(form), encoding="utf-8", newline="\n")
    verdict = verify_results(kit, judge=quick)
    outcomes = _outcomes(verdict)
    assert {i: outcomes[i] for i in ("K4.3", "K8.2", "K1.8", "K5.2", "K9.1", "K4.4")} == {
        "K4.3": "fail",
        "K8.2": "fail",
        "K1.8": "fail",
        "K5.2": "skipped",
        "K9.1": "skipped",
        "K4.4": "pass",
    }
    reasons = {step.id: step.reasons[0] for step in verdict.steps if step.reasons}
    assert "expected 1" in reasons["K4.3"] and "not of the type bool" in reasons["K1.8"]
    found = {h.id: h.outcome for h in verdict.hypotheses}
    assert found["H-A-PCBX-STACK"] == "skipped" and found["H-A-KIT-DRC"] == "fail"


def test_the_form_names_the_tool(kit: Path) -> None:
    simulate(kit)
    for changes, text in (
        ({"altium_version": "26.5"}, "altium_version"),
        ({"altium_version": "AD 26"}, "altium_version"),
        ({"os_family": "Amiga"}, "os_family"),
        ({"date": "yesterday"}, "date"),
        ({"schema": "x"}, "schema"),
        ({"note": "x"}, "unknown field"),
        ({"values": {}}, "one field per form step"),
    ):
        simulate(kit)
        _form(kit, **changes)
        verdict = verify_results(kit, judge=quick)
        assert any(text in problem for problem in verdict.form_problems), changes
        assert not verdict.passed
    assert len(form_problems(blank_form(), STEPS)) == 3
    assert form_problems([], STEPS) == ["the form is not a JSON object"]
    (kit / FORM_FILE).write_bytes(b"{")
    assert "not JSON" in verify_results(kit, judge=quick).form_problems[0]


def test_a_form_that_does_not_say_it_is_real_is_synthetic(kit: Path) -> None:
    simulate(kit, synthetic=False)
    assert not verify_results(kit, judge=quick).synthetic
    _form(kit, synthetic="no")
    assert verify_results(kit, judge=quick).synthetic


def test_messages_and_listings(kit: Path) -> None:
    simulate(
        kit,
        replace={
            "flat/messages.txt": b"[Warning] flat.SchDoc Compiler Net has no driving source\r\n[Error] x\r\n",
            "tree/messages.txt": b"\n \n",
            "routed/messages.txt": "\ufeff[Warning] Off grid pin\n".encode("utf-16"),
            "routed/outputs.txt": b"Project Outputs\\routed.GTL\n",
        },
    )
    failed = {step.id: step.reasons[0] for step in verify_results(kit, judge=quick).failed}
    assert sorted(failed) == ["K2.1", "K2.2", "K7.2"]
    assert "1 message(s) of the class Error" in failed["K2.1"] and "empty" in failed["K2.2"]
    assert "hold a folder" in failed["K7.2"]


def test_privacy_scan_lists_home_folders_and_login_names(kit: Path) -> None:
    home = f"C:\\{USERS}\\jdoe\\Documents\\kit"
    unix = f"/{USERS}/jdoe/kit"
    files = {
        "results/a.txt": f"saved in {home}\nAuthor=jdoe\n".encode(),
        "results/b.bin": b"\x00\x01" + unix.encode("utf-16-le") + b"\x00\x00",
        "results/c.txt": b"routed.GTL\n",
    }
    found = privacy_scan(files)
    assert [(f.file, f.kind) for f in found] == [
        ("results/a.txt", "home-folder"),
        ("results/a.txt", "login-name"),
        ("results/b.bin", "home-folder"),
    ]
    assert found[0].text == f"C:\\{USERS}\\jdoe" and found[0].offset == 9
    assert found[1].text == "jdoe" and found[2].text == f"/{USERS}/jdoe" and found[2].offset == 2
    many = {"results/x.txt": "\n".join(f"/home/user{n}" for n in range(60)).encode()}
    assert len(privacy_scan(many)) == results.MAX_PRIVACY_PER_FILE

    simulate(kit, replace={"flat/messages.txt": f"[Info] compiled {home}\\flat.PrjPcb\n".encode()})
    verdict = verify_results(kit, judge=quick)
    assert [(f.file, f.kind, f.text) for f in verdict.privacy] == [
        ("results/flat/messages.txt", "home-folder", f"C:\\{USERS}\\jdoe")
    ]
    assert verdict.passed  # the list is carried; publishing is the user's decision


def test_a_blank_kit_and_a_folder_that_is_no_kit(built_kit: Path, tmp_path: Path) -> None:
    verdict = verify_results(built_kit, judge=judge_document)
    assert set(_outcomes(verdict).values()) == {"skipped"} and not verdict.passed
    assert len(verdict.form_problems) == 3 and verdict.failed == ()
    assert {h.outcome for h in verdict.hypotheses} == {"skipped"}
    with pytest.raises(FormatError, match="not a kit"):
        verify_results(tmp_path, judge=judge_document)


def test_parity_of_a_saved_document_against_the_kit_s_own(kit: Path, tmp_path: Path) -> None:
    """The stage ``parity`` runs on a copy of the sample's project with the saved document in the place of
    the kit's own: equal findings pass, a board of another sample fails, a sample without a board is not
    judged, and nothing of the kit is written."""
    before = _snapshot(kit)
    flat = kit / "flat"
    assert parity_problems(flat / "flat.PcbDoc", flat / "flat.PcbDoc") == []
    assert parity_problems(flat / "flat.SchDoc", flat / "flat.SchDoc") == []
    assert parity_problems(flat / "ascii" / "flat.SchDoc", flat / "ascii" / "flat.SchDoc") == []
    lost = tmp_path / "lost.PcbDoc"
    lost.write_bytes(rebuilt("flat", without_net("LED_A"))["flat.PcbDoc"])
    other = parity_problems(flat / "flat.PcbDoc", lost)
    assert other and all("with the saved document only" in text for text in other), other
    assert any("LED_A" in text for text in other)
    tree = kit / "tree"
    assert parity_problems(tree / "tree.SchDoc", tree / "tree.SchDoc") == []
    assert judge_document("parity", flat / "flat.PcbDoc", flat / "flat.PcbDoc") == []
    assert _snapshot(kit) == before
    assert [s.id for s in STEPS if "parity" in s.checks] == [
        "K1.1",
        "K1.2",
        "K1.6",
        "K3.1",
        "K5.1",
        "K6.1",
        "K9.1",
    ]
