# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The level RT-A3 and its stage ``roundtrip.rta3`` (capability altium-verification, "Round-trip level
RT-A3"; change c0090): a document is read, its model is written as new documents, and those are read
again. The documents are Fenolite's own samples; the corpus is measured by
``tests/corpus/test_altium_rta3.py``."""

from __future__ import annotations

import ast
import hashlib
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest

import fenolite.backends.altium.import_evidence as import_evidence
import fenolite.backends.altium.pcbdoc as pcbdoc
import fenolite.backends.altium.rta3 as rta3_module
import fenolite.cli.main as cli_main
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.roundtrip import EVIDENCE_RT_A3, RECORD_PREFIX, RT_A2_SCOPE, RT_A3_SCOPE
from fenolite.backends.base import Change, ModelRoundTrip, ModelWriter
from fenolite.checks.documents import ALL_DOCUMENT_STAGES, DOCUMENT_STAGES, OPT_IN_DOCUMENT_STAGES
from fenolite.checks.rta3 import MAX_ISSUES, compare, rta3_stage
from fenolite.core.evidence import Evidence, Level

ROOT = Path(__file__).resolve().parents[3]
SAMPLES = ROOT / "tests" / "data" / "altium"
ROUTED = SAMPLES / "routed"
BOARD6 = SAMPLES / "board6"


def _snapshot(folder: Path) -> dict[str, str]:
    return {
        path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(folder.rglob("*"))
        if path.is_file()
    }


def _check(monkeypatch: pytest.MonkeyPatch, *args: str) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", *args, "--json"])
    return code, json.loads(out.getvalue())


def test_scope_and_evidence() -> None:
    """The scope of RT-A3 is the written scope of the writers. The constant carries the level of its row,
    ``CORPUS-VERIFIED`` since change c0127 (the eight public PCB documents are equal); combined with the
    import's evidence a verdict stays ``INFERRED``, which the tests below assert on a trip and a stage."""
    assert RT_A3_SCOPE is RT_A2_SCOPE is AltiumBackend().written_scope()
    assert EVIDENCE_RT_A3 == Evidence(Level.CORPUS_VERIFIED, hypotheses=("H-A-VER-RTA3",))
    assert Evidence.combine(EVIDENCE_RT_A3, import_evidence.EVIDENCE).level is Level.INFERRED
    assert AltiumBackend().stage_evidence()["roundtrip.rta3"] is EVIDENCE_RT_A3
    assert isinstance(AltiumBackend(), ModelWriter)
    assert OPT_IN_DOCUMENT_STAGES == ("roundtrip.rta3",) and "roundtrip.rta3" not in DOCUMENT_STAGES
    assert ALL_DOCUMENT_STAGES == (*DOCUMENT_STAGES, "roundtrip.rta3")


@pytest.mark.parametrize("sample", ["blink", "routed", "board6"])
def test_own_documents_hold_rta3(sample: str) -> None:
    """Every PCB document that Fenolite committed holds RT-A3. Since change c0126 the lines and arcs of the
    footprints are model items that the rewrite writes: 27 under ``footprint-graphic`` and no
    ``record:footprint-graphics`` (edited by c0126: it asserted that key was above 0)."""
    (document,) = sorted((SAMPLES / sample).glob("*.PcbDoc"))
    trip = AltiumBackend().model_roundtrip(document, compare=compare)
    assert trip.judged and trip.equal and trip.differences == ()
    assert trip.written["footprint"] >= 3 and trip.written["pad"] >= 3
    assert RECORD_PREFIX + "footprint-graphics" not in trip.unwritten
    assert trip.written["footprint-graphic"] == 27 and "footprint-graphic" not in trip.unwritten
    assert f"{document.stem}.PcbDoc" in trip.files
    assert trip.evidence.level is Level.INFERRED and "H-A-VER-RTA3" in trip.evidence.hypotheses


def test_project_holds_rta3() -> None:
    """A project is read with its schematic, written, and read again as a project: the circuit comes back
    from the generated schematic, and the board from the PCB document."""
    trip = AltiumBackend().model_roundtrip(ROUTED / "routed.PrjPcb", compare=compare)
    assert trip.judged and trip.equal, trip.differences[:3]
    assert {"routed.PcbDoc", "routed.PrjPcb", "routed.SchDoc"} <= set(trip.files)
    assert (trip.written["track"], trip.written["via"], trip.written["zone"]) == (5, 3, 2)


def test_stage_on_an_own_sample(monkeypatch: pytest.MonkeyPatch) -> None:
    """The stage is opt-in, reports the unwritten kinds once, and writes nothing under the input folder.
    Edited by change c0126: the two texts and five of the six graphics of ``board6`` on Mechanical 13 are
    written now; one graphic, on the keep-out layer, is still counted (it asserted text 2 and graphic 6)."""
    before = _snapshot(BOARD6)
    code, env = _check(monkeypatch, str(BOARD6), "--stages", "roundtrip.rta3")
    assert code == 0 and _snapshot(BOARD6) == before
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"]) == ("roundtrip.rta3", "ok")
    summary = stage["summary"]
    assert (summary["level"], summary["holds"], summary["differences"]) == ("RT-A3", True, 0)
    assert summary["presentation"] == "regenerated"
    assert "text" not in summary["unwritten"] and summary["unwritten"]["graphic"] == 1
    assert summary["written"]["via"] == 3 and "board6.PcbDoc" in summary["files"]
    assert stage["evidence"]["level"] == "INFERRED" and "H-A-VER-RTA3" in stage["evidence"]["hypotheses"]
    found = [i for i in env["issues"] if i["code"].startswith("check.rta3")]
    assert [(i["code"], i["severity"]) for i in found] == [("check.rta3-unwritten", "info")]
    assert "text " not in found[0]["message"] and "graphic 1" in found[0]["message"]
    # without --stages the stage does not run
    code, env = _check(monkeypatch, str(BOARD6))
    assert code == 0 and "roundtrip.rta3" not in {stage["name"] for stage in env["result"]["stages"]}


def test_a_writer_defect_is_caught(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A writer defect is caught": with a writer that drops the last via, the level does not hold
    and a difference names a via."""
    real = pcbdoc.via_records

    def dropping(vias: Any, copper: Any, **options: Any) -> list[bytes]:
        return real(vias, copper, **options)[:-1]

    monkeypatch.setattr(pcbdoc, "via_records", dropping)
    trip = AltiumBackend().model_roundtrip(ROUTED / "routed.PcbDoc", compare=compare)
    assert trip.judged and not trip.equal
    assert [change.path.split("/")[1] for change in trip.differences] == ["via"]
    assert trip.differences[0].change == "removed"
    code, env = _check(monkeypatch, str(ROUTED / "routed.PcbDoc"), "--stages", "roundtrip.rta3")
    failed = [i for i in env["issues"] if i["code"] == "check.rta3-failed"]
    assert code == 5 and [(i["severity"], i["where"]) for i in failed] == [("error", "/via/0")]
    (stage,) = env["result"]["stages"]
    assert stage["status"] == "errors" and stage["summary"]["holds"] is False
    assert stage["evidence"]["level"] == "UNVERIFIED"


def test_stage_of_a_verdict() -> None:
    """The stage of a verdict: an unjudged trip is skipped with ``no-document``; the unwritten counts
    never change the verdict; at most ``MAX_ISSUES`` differences are issues."""
    assert rta3_stage(ModelRoundTrip(False, False, reason="no-document")).reason == "no-document"
    clean = rta3_stage(ModelRoundTrip(True, True, unwritten={"body": 3, "record:polygons": 1}))
    assert clean.status == "ok" and clean.summary["holds"] is True
    assert [(i.code, i.severity) for i in clean.issues] == [("check.rta3-unwritten", "info")]
    assert "body 3, record:polygons 1" in clean.issues[0].message
    many = tuple(Change(f"/track/{n}", "removed", "{}", "") for n in range(MAX_ISSUES + 5))
    failed = rta3_stage(ModelRoundTrip(True, False, many))
    assert failed.status == "errors" and failed.summary["differences"] == MAX_ISSUES + 5
    assert len(failed.issues) == MAX_ISSUES and failed.evidence.level is Level.UNVERIFIED


def test_rta3_module_touches_no_file() -> None:
    """``backends.altium.rta3`` judges a trip from its parts: it imports no path, process or temporary-file
    module and calls no ``open``; the backend's ``model_roundtrip`` reads and writes."""
    tree = ast.parse(Path(rta3_module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
        elif isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else getattr(node.func, "attr", "")
            assert name not in {"open", "read_bytes", "write_bytes", "write_text", "exec", "eval"}, name
    assert not imported & {"pathlib", "os", "subprocess", "io", "tempfile", "shutil"}
    assert {name for name in imported if name.startswith("fenolite.")} == {
        "fenolite.backends.altium.import_evidence",
        "fenolite.backends.altium.lower",
        "fenolite.backends.altium.roundtrip",
        "fenolite.backends.base",
        "fenolite.core.evidence",
        "fenolite.model.design",
    }
