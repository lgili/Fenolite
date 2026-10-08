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


# --- absolute paths of the machine (change c0139) ------------------------------------------------------

DRIVE = "D:\\work\\project\\flat.PcbDoc"
"""An invented path of the shape a saved document holds: another drive, no home folder."""


def _pcb_document(filename: str) -> bytes:
    """A PCB document written by Fenolite whose board record names ``filename``."""
    from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
    from fenolite.core.coords import Point

    outline = (Point(0, 0), Point(20_000_000, 0), Point(20_000_000, 10_000_000), Point(0, 10_000_000))
    return write_pcbdoc(PcbDocSpec(outline=outline), filename=filename)


def _kinds(files: dict[str, bytes]) -> list[tuple[str, str]]:
    return [(found.kind, found.text) for found in privacy_scan(files)]


def test_a_path_on_another_drive_in_a_saved_document_is_listed() -> None:
    """The board record of a document that a tool saved holds the file's full name: a path that is under
    no home folder is listed too, in the bytes of the document."""
    clean = _pcb_document("flat.PcbDoc")
    saved = _pcb_document(DRIVE)
    assert DRIVE.encode("cp1252") in saved and privacy_scan({"results/flat/flat.PcbDoc": clean}) == ()
    found = privacy_scan({"results/flat/flat.PcbDoc": saved})
    assert [(f.kind, f.text) for f in found] == [("absolute-path", DRIVE)]
    assert saved[found[0].offset :].startswith(DRIVE.encode("cp1252"))


def test_every_shape_of_absolute_path_is_listed() -> None:
    unc = "\\\\fileserver\\share\\kit\\flat.SchDoc"
    cases = {
        "drive": (f"|FILENAME={DRIVE}|".encode("cp1252"), DRIVE),
        "drive, forward slashes": (b'href="file:///E:/kit/results/drc.html"', "E:/kit/results/drc.html"),
        "drive, escaped in JSON": (b'{"file": "D:\\\\work\\\\kit\\\\a.txt"}', "D:\\\\work\\\\kit\\\\a.txt"),
        "drive, accented in the code page": (
            "|PATH=F:\\Projeto Tensão\\placa.PcbDoc|".encode("cp1252"),
            None,
        ),
        "share": (f"saved to {unc}\n".encode(), unc),
        "posix": (b"written to /srv/builds/kit/results/flat.PcbDoc\n", "/srv/builds/kit/results/flat.PcbDoc"),
        "posix, mounted volume": (b"FILE=/Volumes/data/kit/x.SchDoc|", "/Volumes/data/kit/x.SchDoc"),
    }
    for name, (data, text) in cases.items():
        found = _kinds({"results/x": data})
        assert len(found) == 1 and found[0][0] == "absolute-path", (name, found)
        if text is not None:
            assert found[0][1] == text, name
    accented = _kinds({"results/x": cases["drive, accented in the code page"][0]})
    assert accented[0][1] == "F:\\Projeto Tensão\\placa.PcbDoc"


def test_absolute_paths_in_wide_text_at_any_alignment() -> None:
    """Altium keeps some strings in UTF-16: the scan reads them at an even and at an odd byte offset."""
    wide = DRIVE.encode("utf-16-le")
    for lead in (b"", b"\x07", b"\x07\x08\x09"):
        found = privacy_scan({"results/x.bin": lead + wide + b"\x00\x00"})
        assert [(f.kind, f.text, f.offset) for f in found] == [("absolute-path", DRIVE, len(lead))], lead


def test_a_home_folder_is_reported_once_and_as_a_home_folder() -> None:
    home = f"C:\\{USERS}\\jdoe\\Documents\\kit\\flat.PcbDoc"
    assert _kinds({"results/x": home.encode()}) == [("home-folder", f"C:\\{USERS}\\jdoe")]
    both = f"{home}|{DRIVE}".encode()
    assert [kind for kind, _ in _kinds({"results/x": both})] == ["home-folder", "absolute-path"]


def test_what_is_part_of_the_format_is_not_a_path() -> None:
    """Relative paths, stream names, web addresses, dates, fractions, markup and a bare drive letter are
    not reported, and neither is anything in the documents that Fenolite writes."""
    quiet = [
        b"DocumentPath=..\\..\\flat\\flat.SchDoc\r\n",
        b"Project Outputs\\routed.GTL\n",
        b"Board6/Data\x00Components6/Header\x00",
        b"see https://www.example.org/docs/kit/steps.html and http://example.org/a/b",
        b"saved 10/7/2026 at 1/2 scale, 3 mm/s, and/or later",
        b"<html><body><td>x</td><br/></body></html>",
        b"RATIO=4:3|TIME=12:30:05|SCOPE=A:B|DRIVE=C:|",
        b"C:\\ ",
        "|NAME=Tensão 5 V|TEXT=N/A|".encode("cp1252"),
    ]
    for data in quiet:
        assert privacy_scan({"results/x": data}) == (), data


def test_the_kit_s_own_documents_hold_no_path(built_kit: Path) -> None:
    files = {
        path.relative_to(built_kit).as_posix(): path.read_bytes()
        for path in sorted(built_kit.rglob("*"))
        if path.is_file()
    }
    assert len(files) > 30 and privacy_scan(files) == ()


def test_verify_carries_the_path_of_a_saved_document(kit: Path) -> None:
    simulate(kit, replace={"flat/flat.PcbDoc": _pcb_document(DRIVE)})
    verdict = verify_results(kit, judge=quick)
    assert [(f.file, f.kind, f.text) for f in verdict.privacy] == [
        ("results/flat/flat.PcbDoc", "absolute-path", DRIVE)
    ]


# --- the kit's own project file, saved again by the tool (change c0139) ----------------------------------

RESAVED = "[Design]\r\nVersion=1.0\r\nHierarchyMode=0\r\nOutputPath=Project Outputs for flat\r\n\r\n"
"""The start of a project file as a tool might write it again: more keys than Fenolite writes. The keys
here are written for this test."""


def _resaved_project(kit: Path, sample: str = "flat", *, drop: str = "", add: str = "") -> bytes:
    """The sample's project file written again with other bytes: a byte-order mark, the same documents,
    more keys; ``drop`` leaves one document out and ``add`` lists one more."""
    from fenolite.backends.altium.read.project import read_project

    path = kit / sample / f"{sample}.PrjPcb"
    documents = [d.path for d in read_project(path.read_bytes(), file=path.name).documents]
    documents = [name for name in documents if name != drop] + ([add] if add else [])
    text = RESAVED + "".join(
        f"[Document{n}]\r\nDocumentPath={name}\r\nAnnotationEnabled=1\r\nDoLibraryUpdate=1\r\n\r\n"
        for n, name in enumerate(documents, 1)
    )
    return b"\xef\xbb\xbf" + (text + "[Configuration1]\r\nName=Default\r\n").encode("cp1252")


def test_a_project_file_saved_again_with_its_documents_is_accepted(kit: Path) -> None:
    """Altium writes a sample's own project file again when the project is saved: a project file that
    still lists exactly the sample's documents does not fail the sample's steps, and the verdict says
    which file was saved again."""
    simulate(kit)
    data = _resaved_project(kit)
    (kit / "flat" / "flat.PrjPcb").write_bytes(data)
    (kit / "flat" / "flat.PrjPcbStructure").write_bytes(b"written by the tool\n")
    verdict = verify_results(kit, judge=simulated_judge)
    assert verdict.kit_problems == () and verdict.resaved == ("flat/flat.PrjPcb",)
    assert set(_outcomes(verdict).values()) == {"pass"} and verdict.passed
    assert sum(1 for step in verdict.steps if step.sample == "flat") == 10


def test_a_project_file_changed_in_another_way_still_fails(kit: Path) -> None:
    simulate(kit)
    own = (kit / "flat" / "flat.PrjPcb").read_bytes()
    cases = {
        "a document left out": _resaved_project(kit, drop="flat.PcbDoc"),
        "a document more": _resaved_project(kit, add="other.SchDoc"),
        "a document outside the folder": _resaved_project(
            kit, drop="flat.SchDoc", add="..\\tree\\tree.SchDoc"
        ),
        "a document on a drive": _resaved_project(kit, drop="flat.SchDoc", add="D:\\work\\flat.SchDoc"),
        "no project file": b"not a project file\r\n",
        "empty": b"",
    }
    for name, data in cases.items():
        (kit / "flat" / "flat.PrjPcb").write_bytes(data)
        verdict = verify_results(kit, judge=quick)
        assert verdict.kit_problems == ("flat/flat.PrjPcb differs from its digest in kit.json",), name
        assert verdict.resaved == () and len(verdict.failed) == 10, name
    (kit / "flat" / "flat.PrjPcb").unlink()
    assert verify_results(kit, judge=quick).kit_problems == ("flat/flat.PrjPcb is missing",)
    (kit / "flat" / "flat.PrjPcb").write_bytes(own)
    assert verify_results(kit, judge=quick).kit_problems == ()


def test_only_a_project_file_may_differ(kit: Path) -> None:
    """Any other file of the kit that differs fails the manifest check, as before."""
    simulate(kit)
    for name in ("flat/flat.SchDoc", "flat/flat.SchLib", "flat/flat.OutJob", "kit_script.pas", "STEPS.md"):
        target = kit / name
        kept = target.read_bytes()
        target.write_bytes(_resaved_project(kit))
        verdict = verify_results(kit, judge=quick)
        assert (
            verdict.kit_problems == (f"{name} differs from its digest in kit.json",) and not verdict.resaved
        )
        target.write_bytes(kept)


def test_the_documents_of_every_sample_project_are_its_files(built_kit: Path) -> None:
    """What the manifest check takes for a sample's documents is what its project file lists."""
    from fenolite.backends.altium.read.project import read_project
    from fenolite.verify.kit.manifest import load_kit

    kit = load_kit(built_kit)
    for sample in kit.samples:
        path = built_kit / sample / f"{sample}.PrjPcb"
        listed = [d.path for d in read_project(path.read_bytes(), file=path.name).documents]
        assert results.project_documents(path.read_bytes()) == listed
        assert sorted(listed) == sorted(results.sample_documents(kit, f"{sample}/{sample}.PrjPcb")), sample
    assert results.project_documents(b"\xff\xfe not a project") is None
    marked = b"\xef\xbb\xbf[Design]\r\n[Document1]\r\nDocumentPath=a.SchDoc\r\n[Other]\r\nDocumentPath=b\r\n"
    assert results.project_documents(marked) == ["a.SchDoc"]
    assert results.project_documents(b"[Document1]\r\nDocumentPath=a.SchDoc\r\n") is None


# --- a result file of another document kind (change c0139) -----------------------------------------------


def test_a_result_file_of_another_document_kind_is_named(kit: Path) -> None:
    """A schematic saved where the step wants the PCB document fails with what the file is and what the
    step wants, not with a read error."""
    simulate(
        kit,
        replace={
            "board6/board6.PcbDoc": (kit / "board6" / "board6.SchDoc").read_bytes(),
            "libs/libs.SchLib": (kit / "libs" / "libs.PcbLib").read_bytes(),
            "flat/flat.SchDoc": (kit / "flat" / "flat.PrjPcb").read_bytes(),
            "flat/flat.PrjPcb": (kit / "flat" / "flat.SchLib").read_bytes(),
        },
    )
    failed = {step.id: step.reasons for step in verify_results(kit, judge=simulated_judge).failed}
    assert sorted(failed) == ["K1.1", "K1.3", "K1.5", "K5.1"]
    assert failed["K5.1"][0] == (
        "resave: the file is a schematic document, and the step wants a PCB document: "
        "save board6.PcbDoc of the sample, not another document of its project"
    )
    assert "is a PCB library, and the step wants a schematic library" in failed["K1.3"][0]
    assert "is a project file, and the step wants a schematic document" in failed["K1.1"][0]
    assert "is a schematic library, and the step wants a project file" in failed["K1.5"][0]
    assert not any("cannot read" in text for reasons in failed.values() for text in reasons)
    assert all(len(reasons) == 1 for reasons in failed.values())


def test_document_kinds(built_kit: Path) -> None:
    from fenolite.cli._kit import document_kind

    kinds = {
        "flat/flat.SchDoc": "a schematic document",
        "flat/ascii/flat.SchDoc": "a schematic document",
        "flat/flat.PcbDoc": "a PCB document",
        "flat/flat.SchLib": "a schematic library",
        "flat/flat.PcbLib": "a PCB library",
        "flat/flat.PrjPcb": "a project file",
        "tree/tree_io.leds.SchDoc": "a schematic document",
        "board6/board6.PcbDoc": "a PCB document",
        "templates/iso5457_generic.SchDot": "a schematic document",
        "STEPS.md": None,
        "flat/flat.OutJob": None,
    }
    for name, kind in kinds.items():
        assert document_kind((built_kit / name).read_bytes()) == kind, name
    assert document_kind(b"") is None and document_kind(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1garbage") is None


def test_a_document_saved_under_the_name_of_another_kind_is_named(kit: Path) -> None:
    """The schematic of ``board6`` saved as ``board6.SchDoc`` where step K5.1 wants ``board6.PcbDoc``: the
    step is not passed over as not done, it fails and names the file it found. A file that another step
    asks for is not taken for such a file."""
    simulate(kit, skip=("K5.1", "K1.2"))
    stray = kit / "results" / "board6" / "board6.SchDoc"
    stray.write_bytes((kit / "board6" / "board6.SchDoc").read_bytes())
    (kit / "results" / "board6" / "__Previews").mkdir()
    verdict = verify_results(kit, judge=quick)
    outcomes = _outcomes(verdict)
    assert outcomes["K5.1"] == "fail" and outcomes["K1.2"] == "skipped"
    reasons = {step.id: step.reasons for step in verdict.steps}
    assert reasons["K5.1"] == (
        "results/board6/board6.PcbDoc does not exist, and the folder holds board6.SchDoc, which no step "
        "asks for: the step wants board6.PcbDoc, not another document of the project",
    )
    assert reasons["K1.2"] == ("results/flat/flat.PcbDoc does not exist",)
    stray.unlink()
    assert _outcomes(verify_results(kit, judge=quick))["K5.1"] == "skipped"
