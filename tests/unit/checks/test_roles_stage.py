# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stage ``roles.rules`` (change c0222; capability verification-loop, "Roles stage" and "Roles judge
injected into the stage")."""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest
from fakes import FakeRolesJudge, FakeValidator, validation

from fenolite.backends.base import ProjectSet
from fenolite.checks import STAGE_ORDER, run_checks
from fenolite.checks.documents import DOCUMENT_STAGES
from fenolite.checks.roles import DOCUMENT_SUFFIX, has_roles
from fenolite.checks.stages import DEFAULT_STAGES, ORACLE_STAGES
from fenolite.model.design import Design
from fenolite.model.rules import NetRole, RoleSet

ROOT = Path(__file__).resolve().parents[3]
TWO_LAYER = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
sys.path.insert(0, str(ROOT / "tests" / "unit" / "cli"))
sys.path.insert(0, str(ROOT / "tests" / "unit" / "roles"))
from _checkcli import hide_kicad, run  # noqa: E402
from _roleboards import build  # noqa: E402

from fenolite.roles.store import SUFFIX  # noqa: E402


def test_the_stage_stands_after_placement_rules() -> None:
    assert STAGE_ORDER.index("placement.rules") + 1 == STAGE_ORDER.index("roles.rules")
    assert STAGE_ORDER.index("roles.rules") + 1 == STAGE_ORDER.index("zone.fill")
    assert DOCUMENT_STAGES.index("placement.rules") + 1 == DOCUMENT_STAGES.index("roles.rules")
    assert DOCUMENT_STAGES.index("roles.rules") + 1 == DOCUMENT_STAGES.index("parity")
    assert "roles.rules" in DEFAULT_STAGES and "roles.rules" not in ORACLE_STAGES
    assert DOCUMENT_SUFFIX == SUFFIX


def _model_with_a_role() -> Design:
    model = Design.new("roles", seed=1)
    assert model.rules is not None
    rules = dataclasses.replace(model.rules, roles=RoleSet(nets=(NetRole("SW", "switch_node", "confirmed"),)))
    return dataclasses.replace(model, rules=rules)


def _project(tmp_path: Path) -> ProjectSet:
    board = tmp_path / "board.kicad_pcb"
    board.write_text("", encoding="utf-8")
    return ProjectSet(tmp_path, "board.kicad_pcb", {"board.kicad_pcb": board})


def test_fake(tmp_path: Path) -> None:
    """A fake judge on a board with a stored role: the stage runs it; without a judge it is skipped."""
    model = _model_with_a_role()
    judge = FakeRolesJudge()
    common = {"project": _project(tmp_path), "stages": ("roles.rules",), "model": model, "built": True,
              "validator": FakeValidator(validation(model)), "oracle": None}  # fmt: skip
    report = run_checks(**common, roles_judge=judge)  # type: ignore[arg-type]
    (stage,) = report.stages
    assert (stage.name, stage.status) == ("roles.rules", "ok")
    assert [found.code for found in stage.issues] == ["roles.loop-area"]
    assert stage.evidence.hypotheses == ("H-FAKE-ROLES",) and stage.summary == {"measures": 1}
    assert len(judge.calls) == 1 and judge.calls[0][1] is model
    (stage,) = run_checks(**common).stages  # type: ignore[arg-type]
    assert (stage.status, stage.reason) == ("skipped", "not-judged")


def test_no_roles_is_skipped(tmp_path: Path) -> None:
    project = _project(tmp_path)
    plain = Design.new("plain", seed=1)
    assert not has_roles(plain, project) and not has_roles(None, project)
    judge = FakeRolesJudge()
    validator = FakeValidator(validation(plain))
    report = run_checks(
        project=project, stages=("roles.rules",), model=None, built=False, validator=validator, oracle=None,
        roles_judge=judge,
    )  # fmt: skip
    (stage,) = report.stages
    assert (stage.status, stage.reason) == ("skipped", "no-roles") and judge.calls == []
    (tmp_path / f"board{DOCUMENT_SUFFIX}").write_text("{}", encoding="utf-8")
    assert has_roles(None, project)


def test_a_board_without_roles_is_unchanged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "check", str(TWO_LAYER), "--stages", "roles.rules")
    assert code == 0, error
    (stage,) = env["result"]["stages"]
    assert (stage["name"], stage["status"], stage["reason"]) == ("roles.rules", "skipped", "no-roles")


def test_confirmed_roles_are_judged(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    built = build("buck_shunt", "bad", tmp_path / "bad")
    code, _, error, _ = run(monkeypatch, tmp_path, "roles", str(built.out), "--accept-all", "--confirm")
    assert code == 0, error
    stages = "model.validate,copper.clearance,placement.rules,roles.rules"
    code, env, error, _ = run(monkeypatch, tmp_path, "check", str(built.out), "--stages", stages)
    names = [stage["name"] for stage in env["result"]["stages"]]
    assert names.index("placement.rules") + 1 == names.index("roles.rules")
    outer = [i for i in env["issues"] if i["code"] == "roles.kelvin-outer"]
    assert [i["severity"] for i in outer] == ["error"]
    assert code == 5
    roles = next(stage for stage in env["result"]["stages"] if stage["name"] == "roles.rules")
    assert roles["status"] == "errors" and roles["evidence"]["level"] == "INFERRED"
    assert "H-G-ROLE-LOOP-RATIO" in roles["evidence"]["hypotheses"]


def test_an_unreadable_document(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = tmp_path / "board.kicad_pcb"
    board.write_bytes(TWO_LAYER.read_bytes())
    board.with_name(f"board{DOCUMENT_SUFFIX}").write_text("{not json", encoding="utf-8")
    code, env, _, _ = run(monkeypatch, tmp_path, "check", str(board), "--stages", "roles.rules")
    assert code == 5
    assert [i["code"] for i in env["issues"]] == ["check.roles-unreadable"]
