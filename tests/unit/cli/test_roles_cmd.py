# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite roles`` (change c0222; capability cli-contract, "Roles command" and "Roles measuring options";
capability net-roles, "Roles show and confirm", "Role sources", "Role document", "Currents are never
inferred", "Finding severities", "Role measures come from the analyses" and "Role evidence")."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, run
from _projects import tree_snapshot

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "roles"))
from _roleboards import Built, build  # noqa: E402

from fenolite.model.rules import NetRole, RoleSet  # noqa: E402
from fenolite.roles.measure import ANALYSES  # noqa: E402
from fenolite.roles.store import SCHEMA, dumps_document, updated_rules  # noqa: E402

STATES = {"saved_fill", "simulated", "outline", "tracks"}


@pytest.fixture(scope="module")
def boards(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Built]:
    root = tmp_path_factory.mktemp("roles_cmd")
    return {
        name: build(board, variant, root / name)
        for name, (board, variant) in {
            "buck_bad": ("buck_shunt", "bad"),
            "buck_good": ("buck_shunt", "good"),
            "bms_good": ("bms", "good"),
        }.items()
    }


def _copy(built: Built, folder: Path, *, model: bool = True) -> Path:
    """A copy of a built variant in ``folder``: the whole project, or the board alone."""
    if model:
        shutil.copytree(built.out, folder)
    else:
        folder.mkdir(parents=True)
        shutil.copyfile(built.board, folder / built.board.name)
    return folder / built.board.name


def _forbid_subprocess(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("fenolite roles runs no tool")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_readonly(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "project")
    before = tree_snapshot(board.parent)
    _forbid_subprocess(monkeypatch)
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent), "--check")
    assert code == 0, error
    assert tree_snapshot(board.parent) == before
    assert env["schema"] == "fenolite.roles.v0" and "plan" not in env["result"]
    assert {"roles", "loops", "kelvins", "gates", "classes", "store", "measures", "summary"} <= set(
        env["result"]
    )


def test_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]) -> None:
    """Each entry of ``result.measures`` names one of the analyses and a copper state."""
    hide_kicad(monkeypatch, tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(boards["buck_bad"].out), "--check")
    assert code == 0, error
    measures = env["result"]["measures"]
    assert measures and all(m["analysis"] in ANALYSES and set(m["copper"]) <= STATES for m in measures)
    assert env["result"]["summary"]["measures"] == len(measures)


def test_write_needs_confirmation(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "project", model=False)
    before = tree_snapshot(board.parent)
    code, _, error, _ = run(monkeypatch, tmp_path, "roles", str(board), "--accept", "GND")
    assert code == 4 and error["code"] == "FEN-4001"
    assert tree_snapshot(board.parent) == before


def test_board_on_another_drive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    """On Windows a board on another drive has no path relative to the working folder: the file to write is
    shown absolute."""
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "project", model=False)

    def no_relative(path: object, start: object = None) -> str:
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    monkeypatch.setattr("fenolite.cli.cmd_roles.os.path.relpath", no_relative)
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board), "--accept", "GND", "--dry-run")
    assert code == 0, error
    target = board.with_name(board.stem + ".roles.json").as_posix()
    assert env["result"]["store"]["file"] == target
    assert [w["path"] for w in env["result"]["plan"]] == [target]


def test_usage_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, _, error, _ = run(
        monkeypatch, tmp_path, "roles", str(boards["buck_bad"].board), "--set", "SW=motor"
    )
    assert code == 2 and error["code"] == "FEN-2001"
    for bad in (
        ("--accept", "NOPE"),
        ("--current", "VOUT=fast"),
        ("--min-confidence", "high"),
        ("--kinds", "x"),
    ):
        code, _, error, _ = run(monkeypatch, tmp_path, "roles", str(boards["buck_bad"].board), *bad)
        assert code == 2 and error["code"] == "FEN-2001", bad


def test_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]) -> None:
    """The measuring options are parsed by ``analyze``'s code, and need ``--check``."""
    hide_kicad(monkeypatch, tmp_path)
    board = str(boards["buck_bad"].board)
    code, _, error, _ = run(monkeypatch, tmp_path, "roles", board, "--check", "--temp-rise", "1.2345")
    assert code == 2 and error["code"] == "FEN-2001"
    _, _, theirs, _ = run(monkeypatch, tmp_path, "analyze", board, "--temp-rise", "1.2345")
    assert error["message"] == theirs["message"] == "--temp-rise: cannot use '1.2345'"
    for option in (
        ("--split",),
        ("--temp-rise", "10"),
        ("--via-plating", "25um"),
        ("--requirements", "r.toml"),
    ):
        code, _, error, _ = run(monkeypatch, tmp_path, "roles", board, *option)
        assert code == 2 and error["code"] == "FEN-2001" and "goes with --check" in error["message"], option


def test_confirm_through_a_plan(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "copy", model=False)
    original = board.read_bytes()
    args = ("roles", str(board), "--accept-all", "--min-confidence", "high")
    code, env, error, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, error
    assert sorted(p.name for p in board.parent.iterdir()) == [board.name]
    (planned,) = env["result"]["plan"]
    assert planned["path"].endswith("buck_shunt_bad.roles.json")
    code, env, error, _ = run(monkeypatch, tmp_path, *args, "--confirm", "--plan", env["result"]["plan_id"])
    assert code == 0, error
    document = board.with_name("buck_shunt_bad.roles.json")
    assert sorted(p.name for p in board.parent.iterdir()) == sorted([board.name, document.name])
    (written,) = env["receipt"]["written"]
    assert written["sha256"] == hashlib.sha256(document.read_bytes()).hexdigest()
    assert json.loads(document.read_text(encoding="utf-8"))["schema"] == SCHEMA
    assert board.read_bytes() == original


def test_confirm_in_a_built_project(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    """A built project keeps its confirmed roles in ``.fenolite/rules.json``; a rejected net is a confirmed
    signal; a stored current is the role's."""
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "project")
    args = ("roles", str(board.parent), "--accept", "GND,GH", "--reject", "ISNS", "--current", "VDRV=0.5")
    code, env, error, _ = run(monkeypatch, tmp_path, *args, "--confirm")
    assert code == 0, error
    assert [w["path"] for w in env["receipt"]["written"]] == ["project/.fenolite/rules.json"]
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent))
    rows = {row["net"]: row for row in env["result"]["roles"]}
    assert (rows["GND"]["kind"], rows["GND"]["source"]) == ("ground", "confirmed")
    assert (rows["ISNS"]["kind"], rows["ISNS"]["source"]) == ("signal", "confirmed")
    assert (rows["VDRV"]["source"], rows["VDRV"]["milliamps"]) == ("confirmed", 500)
    assert (rows["SW"]["source"], rows["SW"]["milliamps"]) == ("declared", 2000)  # the script's
    assert rows["PWM_H"]["source"] == "inferred"
    assert env["result"]["store"] == {
        "file": ".fenolite/rules.json",
        "built": True,
        "read": ".fenolite/rules.json",
    }


def test_a_declaration_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_good"], tmp_path / "project")
    rules = board.parent / ".fenolite" / "rules.json"
    declared = RoleSet(nets=(NetRole("SW", "signal", "declared"),))
    rules.write_bytes(updated_rules(rules.read_text(encoding="utf-8"), declared))
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent))
    assert code == 0, error
    (row,) = [row for row in env["result"]["roles"] if row["net"] == "SW"]
    assert (row["kind"], row["source"]) == ("signal", "declared")
    assert [i["code"] for i in env["issues"]].count("roles.declared-differs") == 1
    code, _, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent), "--accept", "SW", "--dry-run")
    assert code == 2 and "the script declares the role of SW" in error["message"]


def test_roles_beside_a_hand_routed_board(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "copy", model=False)
    original = board.read_bytes()
    document = board.with_name("buck_shunt_bad.roles.json")
    document.write_bytes(dumps_document(RoleSet(nets=(NetRole("SW", "switch_node", "confirmed"),))))
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board))
    assert code == 0, error
    (row,) = [row for row in env["result"]["roles"] if row["net"] == "SW"]
    assert row["source"] == "confirmed" and board.read_bytes() == original
    assert env["result"]["store"]["read"] == document.name
    document.write_text(
        '{"schema": "fenolite.roles.v0", "roles": {"nets": [{"net": "SW"}]}}', encoding="utf-8"
    )
    code, _, error, _ = run(monkeypatch, tmp_path, "roles", str(board))
    assert code == 3 and error["code"] == "FEN-3004"


def test_a_power_net_without_a_current(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    """The good battery board without the currents its script declares and without a requirements file."""
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["bms_good"], tmp_path / "project")
    rules = board.parent / ".fenolite" / "rules.json"
    rules.write_bytes(updated_rules(rules.read_text(encoding="utf-8"), RoleSet()))
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent), "--check")
    assert code == 0, error
    codes = [i["code"] for i in env["issues"]]
    assert "roles.width-current" not in codes
    missing = sorted(i["where"] for i in env["issues"] if i["code"] == "roles.current-missing")
    powered = sorted(
        r["net"] for r in env["result"]["roles"] if r["kind"] in ("power", "switch_node", "ground")
    )
    assert missing == powered and "BAT_P" in missing


def test_unconfirmed_roles_warn_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(boards["buck_bad"].out), "--check")
    assert code == 0, error
    roles = [i for i in env["issues"] if i["code"].startswith("roles.")]
    assert all(i["severity"] in ("warning", "info") for i in roles)
    assert [i["code"] for i in roles].count("roles.unconfirmed") == 1


def test_evidence_of_a_check(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, boards: dict[str, Built]
) -> None:
    hide_kicad(monkeypatch, tmp_path)
    board = _copy(boards["buck_bad"], tmp_path / "project")
    code, env, error, _ = run(monkeypatch, tmp_path, "roles", str(board.parent), "--check")
    assert code == 0, error
    assert env["evidence"]["level"] == "INFERRED"
    assert {"H-G-ROLE-LOOP-RATIO", "H-G-SHAPE-LOOP"} <= set(env["evidence"]["hypotheses"])
    (width,) = [i for i in env["issues"] if i["code"] == "roles.width-current"]
    assert "S-0851" in width["message"]


# ------------------------------------------------------------------------- requirement table (c0253)


def test_requirements_one_table_for_roles_and_circuit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Change c0253, "One table for roles and circuit"."""
    from _contracts import built_sensor, cli

    out = built_sensor(monkeypatch, tmp_path, "bad")
    before = tree_snapshot(out)
    code, env = cli(monkeypatch, "roles", str(out), "--check")
    assert code in (0, 5), env
    rows = env["result"]["requirements"]
    (inductor,) = [r for r in rows if r["id"] == "circuit.rating-current:L1:current"]
    assert (inductor["value"]["source"], inductor["value"]["basis"]) == ("user", "rail 3V3")
    assert inductor["limit"]["source"] == "device"
    assert [r["id"] for r in rows] == sorted(r["id"] for r in rows)
    assert all(r["limit"]["source"] in ("device", "role", "policy", "user") for r in rows)
    assert tree_snapshot(out) == before
    code, env = cli(monkeypatch, "roles", str(out))
    assert "requirements" not in env["result"]


def test_requirements_of_a_board_fenolite_did_not_build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Change c0253, "A board that Fenolite did not build"."""
    from _contracts import ROOT, cli

    board = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    copy = tmp_path / board.name
    shutil.copyfile(board, copy)
    code, env = cli(monkeypatch, "roles", str(copy), "--check")
    assert code == 0, env
    assert all(not r["id"].startswith("circuit.") for r in env["result"]["requirements"])


def test_requirements_a_stated_current_reaches_the_circuit_rows(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Change c0253, "A stated current reaches the circuit rows"."""
    from _contracts import built_sensor, cli, sensor_model

    from fenolite.model import canonical

    out = built_sensor(monkeypatch, tmp_path, "good")
    folder = out.parent
    board = folder / "contract_board" / "board.py"
    board.write_text(
        board.read_text(encoding="utf-8").replace(
            '    b.design.net_role(sw, "switch_node", current=SW_CURRENT)\n', ""
        ),
        encoding="utf-8",
    )
    model, _devices = sensor_model(folder, "bad")
    canonical.dump_dir(model, out / ".fenolite")
    requirements = tmp_path / "requirements.toml"
    requirements.write_text(
        'schema = "fenolite.requirements.v0"\n[[current]]\nselect = { net = "buck1/SW" }\ncurrent = "0.8A"\n'
        'temp_rise = "10K"\nsource = "bench note"\n',
        encoding="utf-8",
    )
    code, env = cli(monkeypatch, "roles", str(out), "--check", "--requirements", str(requirements))
    assert code in (0, 5), env
    (inductor,) = [r for r in env["result"]["requirements"] if r["id"] == "circuit.rating-current:L1:current"]
    assert inductor["value"]["range"]["high"] == {"m": 8, "e": -1}
    assert (inductor["value"]["source"], inductor["value"]["basis"], inductor["status"]) == (
        "user",
        "bench note",
        "pass",
    )
