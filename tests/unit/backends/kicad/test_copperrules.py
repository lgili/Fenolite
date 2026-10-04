# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design rules of a KiCad project for the copper check (capability kicad-file-backend, "Design rules
for the copper check"; capability backend-protocol, "Design rules source"; change c0029)."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from _netclass_bench import HV_NETS, bench_design

from fenolite.backends.base import DesignRules, DesignRulesSource, ProjectSet
from fenolite.backends.kicad import dru, lowering, pro
from fenolite.backends.kicad.backend import KicadBackend
from fenolite.backends.kicad.copperrules import (
    design_rules_from_texts,
    opaque_clearance_rules,
    project_major,
)
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.triad import write_triad
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design

OPAQUE_RULES = """(version 1)
(rule "text_gap"
  (condition "A.Type == 'Text'")
  (constraint clearance (min 0.5mm)))
(rule "text_width"
  (condition "A.Type == 'Text'")
  (constraint track_width (min 0.2mm)))
"""
LIFTED_RULES = """(version 1)
(rule "hv"
  (condition "A.NetClass == 'HV'")
  (constraint clearance (min 1mm)))
"""


def triad(target: int = 10) -> dict[str, str]:
    return write_triad(bench_design(target=target), name="bench", target=target)


def board(files: dict[str, str]) -> Design:
    return read_board(files["bench.kicad_pcb"], file="bench.kicad_pcb")


def project_set(tmp_path: Path, files: dict[str, str]) -> ProjectSet:
    for name, text in files.items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    return ProjectSet(
        root=tmp_path,
        board="bench.kicad_pcb",
        files={name: tmp_path / name for name in files},
        has_project="bench.kicad_pro" in files,
        has_rules="bench.kicad_dru" in files,
    )


def test_bench_applied() -> None:
    files = triad()
    design = board(files)
    assert design.circuit.netclasses == () and design.rules is None  # a board file holds neither
    found = design_rules_from_texts(
        design, project_text=files["bench.kicad_pro"], rules_text=files["bench.kicad_dru"], file_stem="bench"
    )
    classes = {c.name: c for c in found.design.circuit.netclasses}
    assert sorted(classes) == ["Default", "HV"]
    nets = {net.name: net for net in found.design.circuit.nets}
    assert {nets[name].netclass_id for name in HV_NETS} == {classes["HV"].id}
    assert nets["GND"].netclass_id is None
    info = pro.read_project(files["bench.kicad_pro"])
    assert found.min_clearance == info.floors.get("clearance")
    assert found.design.rules is not None and [r.kind for r in found.design.rules.rules] == ["clearance"]
    assert found.opaque_clearance_rules == 0 and found.unread == ()
    assert found.evidence == Evidence.combine(pro.EVIDENCE, dru.EVIDENCE)
    assert found.design.board == design.board


def test_opaque_clearance_rule_counted() -> None:
    design = board(triad())
    issues: list[Issue] = []
    found = design_rules_from_texts(design, project_text=None, rules_text=OPAQUE_RULES, issues=issues)
    assert found.opaque_clearance_rules == 1
    assert found.design.rules is not None and found.design.rules.rules == ()
    assert [(i.code, i.severity) for i in issues] == [("rules.kept-opaque", "info")] * 2
    assert found.evidence == Evidence.combine(dru.EVIDENCE)
    assert opaque_clearance_rules(LIFTED_RULES) == 0


def test_rule_with_a_comment_inside_is_opaque() -> None:
    text = LIFTED_RULES.replace('(condition "A.NetClass', '# why\n  (condition "A.NetClass')
    assert opaque_clearance_rules(text) == 1


def test_lifted_rule_reaches_the_design() -> None:
    found = design_rules_from_texts(board(triad()), project_text=None, rules_text=LIFTED_RULES)
    assert found.design.rules is not None
    (rule,) = found.design.rules.rules
    assert (rule.kind, rule.min, rule.name) == ("clearance", 1_000_000, "hv")
    assert found.min_clearance is None and found.design.circuit.netclasses == ()


def test_no_project_files() -> None:
    design = board(triad())
    found = design_rules_from_texts(design, project_text=None, rules_text=None)
    assert found.design is design and found.min_clearance is None and found.unread == ()
    assert found.evidence.level is Level.UNVERIFIED and found.opaque_clearance_rules == 0


def test_measured_tables_applied(monkeypatch: pytest.MonkeyPatch) -> None:
    design = board(triad())
    assert design_rules_from_texts(design, project_text=None, rules_text=None).rules_over_classes is True
    assert design_rules_from_texts(design, project_text=None, rules_text=None).floor_over_rules is False
    monkeypatch.setattr(lowering, "RULES_OVER_CLASSES", frozenset({10}))
    monkeypatch.setattr(lowering, "FLOOR_OVER_RULES", {"min_clearance": frozenset({9})})
    nine = design_rules_from_texts(design, project_text=None, rules_text=None, major=9)
    ten = design_rules_from_texts(design, project_text=None, rules_text=None, major=10)
    assert (nine.rules_over_classes, nine.floor_over_rules) == (False, True)
    assert (ten.rules_over_classes, ten.floor_over_rules) == (True, False)


def test_unread_texts_keep_the_design() -> None:
    files = triad()
    design = board(files)
    found = design_rules_from_texts(design, project_text="{", rules_text="(rule x)", file_stem="bench")
    assert [name for name, _ in found.unread] == ["bench.kicad_dru", "bench.kicad_pro"]
    assert all(message for _, message in found.unread)
    assert found.design is design and found.evidence == Evidence()
    half = design_rules_from_texts(design, project_text="{", rules_text=files["bench.kicad_dru"])
    assert [name for name, _ in half.unread] == [".kicad_pro"] and half.evidence == Evidence.combine(
        dru.EVIDENCE
    )
    assert half.design.circuit.netclasses == design.circuit.netclasses


def test_project_major() -> None:
    assert project_major(None) == 10 and project_major("{") == 10 and project_major("{}") == 10
    assert project_major(triad(9)["bench.kicad_pro"]) == 9
    assert project_major(triad(10)["bench.kicad_pro"]) == 10


# --- the backend as a rules source ----------------------------------------------------------------


def test_backend_reads_the_copy_set(tmp_path: Path) -> None:
    files = triad()
    project = project_set(tmp_path, files)
    design = board(files)
    issues: list[Issue] = []
    found = KicadBackend().design_rules(design, project, issues=issues)
    assert isinstance(found, DesignRules)
    assert found == design_rules_from_texts(
        design, project_text=files["bench.kicad_pro"], rules_text=files["bench.kicad_dru"], file_stem="bench"
    )
    assert {c.name for c in found.design.circuit.netclasses} == {"Default", "HV"}


def test_backend_without_side_files(tmp_path: Path) -> None:
    files = {"bench.kicad_pcb": triad()["bench.kicad_pcb"]}
    design = board(files)
    found = KicadBackend().design_rules(design, project_set(tmp_path, files))
    assert found.design is design and found.unread == () and found.evidence == Evidence()


def test_unread_file_reported_not_raised(tmp_path: Path) -> None:
    files = {**triad(), "bench.kicad_pro": "{"}
    design = board(files)
    found = KicadBackend().design_rules(design, project_set(tmp_path, files))
    ((name, message),) = found.unread
    assert name == "bench.kicad_pro" and message
    assert found.design.circuit.netclasses == design.circuit.netclasses
    assert found.design.rules is not None and len(found.design.rules.rules) == 1


def test_undecodable_file_reported_not_raised(tmp_path: Path) -> None:
    files = triad()
    project = project_set(tmp_path, files)
    (tmp_path / "bench.kicad_dru").write_bytes(b"\xff\xfe(version 1)")
    found = KicadBackend().design_rules(board(files), project)
    assert [name for name, _ in found.unread] == ["bench.kicad_dru"]
    assert {c.name for c in found.design.circuit.netclasses} == {"Default", "HV"}


def test_backend_takes_the_major_of_the_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(lowering, "RULES_OVER_CLASSES", frozenset({10}))
    nine, ten = triad(9), triad(10)
    (tmp_path / "nine").mkdir()
    (tmp_path / "ten").mkdir()
    backend = KicadBackend()
    assert backend.design_rules(board(nine), project_set(tmp_path / "nine", nine)).rules_over_classes is False
    assert backend.design_rules(board(ten), project_set(tmp_path / "ten", ten)).rules_over_classes is True


def test_backend_reads_no_other_file(tmp_path: Path) -> None:
    files = {**triad(), "other.kicad_pro": "{", "other.kicad_dru": "nonsense"}
    found = KicadBackend().design_rules(board(files), project_set(tmp_path, files))
    assert found.unread == ()


def test_rules_source_protocol() -> None:
    backend = KicadBackend()
    assert isinstance(backend, DesignRulesSource)
    assert "design_rules" not in backend.capabilities().operations
    assert dataclasses.is_dataclass(DesignRules)
