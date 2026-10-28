# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.run`` gives every command's envelope as the command line prints it, and keeps the mutation
protocol (capability python-api, "In-process command runner" and "Mutation protocol in process"; change
c0206). A new ``cmd_*.py`` is picked up automatically, as in ``test_cli_consistency.py``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest
from _cliexamples import PLANS_NOTHING, folder_snapshot, prepare_example
from _fakecli import EXAMPLE_NETLIST, fake_kicad_cli

from fenolite.api import Reply, run
from fenolite.cli.api import discover
from fenolite.cli.main import main

COMMANDS = discover()
NAMES = sorted(COMMANDS)
SOURCE_WRITERS = frozenset({"sync"})
"""As in ``test_cli_consistency.py``: ``sync`` writes beside its input, in the package folder."""
MUTATING = sorted(n for n, c in COMMANDS.items() if c.mutates and n not in SOURCE_WRITERS | PLANS_NOTHING)
CapSys = pytest.CaptureFixture[str]
SEED = 7
TIMESTAMP = "2026-10-28T12:00:00+00:00"
"""Both runs of a comparison pass these, as the contract asks for byte-identical outputs: the command line
as flags, ``run`` as its keywords."""


@pytest.fixture(autouse=True)
def example_tools(
    request: pytest.FixtureRequest, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A command whose examples need ``kicad-cli`` runs them against the fake, as the CLI suite does."""
    callspec = getattr(request.node, "callspec", None)
    name = callspec.params.get("name") if callspec is not None else None
    if name in COMMANDS and "kicad-cli" in COMMANDS[name].example_tools:
        script = fake_kicad_cli(tmp_path_factory.mktemp("fake-kicad"), netlist=EXAMPLE_NETLIST)
        monkeypatch.setenv("FENOLITE_KICAD_CLI", str(script))


CACHE_COUNTS = {"view": "cache"}
"""Result keys that count what an earlier run left on disk: the first run of ``view`` fills its scene cache
(``--cache user``), so the second one hits it."""


def _masked(envelope: Any, name: str) -> Any:
    """The envelope without ``elapsed_ms`` and without the command's cache counts (``CACHE_COUNTS``)."""
    if envelope is None:
        return None
    masked = {key: value for key, value in envelope.items() if key != "elapsed_ms"}
    if name in CACHE_COUNTS:
        masked["result"] = {k: v for k, v in masked["result"].items() if k != CACHE_COUNTS[name]}
    return masked


def _cli(capsys: CapSys, argv: list[str]) -> tuple[int, Any, Any]:
    code = main([*argv, "--json"])
    captured = capsys.readouterr()
    return (
        code,
        json.loads(captured.out) if captured.out else None,
        json.loads(captured.err) if captured.err else None,
    )


def _folders(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """The command's working folder, with its example files, and an empty folder the process stands in."""
    work, elsewhere = tmp_path / "work", tmp_path / "elsewhere"
    work.mkdir()
    elsewhere.mkdir()
    prepare_example(name, work)
    monkeypatch.chdir(elsewhere)
    return work, elsewhere


def _quiet_run(
    capsys: CapSys, name: str, *args: str, cwd: Path, seed: int | None = None, timestamp: str | None = None
) -> Reply:
    """``run``, checking that it printed nothing and left the process's working folder where it was."""
    before = os.getcwd()
    reply = run(name, *args, cwd=cwd, seed=seed, timestamp=timestamp)
    captured = capsys.readouterr()
    assert (captured.out, captured.err) == ("", ""), f"{name} printed in process"
    assert os.getcwd() == before
    return reply


@pytest.mark.parametrize("name", NAMES)
def test_run_matches_the_cli(
    name: str, capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Same envelope as the command line": every command's examples, ``elapsed_ms`` masked."""
    work, _ = _folders(tmp_path, name, monkeypatch)
    args = list(COMMANDS[name].example_args)
    monkeypatch.chdir(work)
    code, envelope, error = _cli(capsys, [name, "--seed", str(SEED), "--timestamp", TIMESTAMP, *args])
    monkeypatch.chdir(tmp_path / "elsewhere")
    reply = _quiet_run(capsys, name, *args, cwd=work, seed=SEED, timestamp=TIMESTAMP)
    assert reply.exit_code == code == 0, reply.error
    assert _masked(reply.envelope, name) == _masked(envelope, name)
    assert reply.error == error is None


@pytest.mark.parametrize("name", MUTATING)
def test_run_keeps_the_mutation_protocol(
    name: str, capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Plan, review, write": without ``--confirm`` nothing is written; ``--confirm --plan ID``
    writes the reviewed plan into ``cwd`` and nowhere else."""
    work, elsewhere = _folders(tmp_path, name, monkeypatch)
    args = list(COMMANDS[name].mutation_example_args or ())
    before = folder_snapshot(work)

    asked = _quiet_run(capsys, name, *args, cwd=work, seed=SEED, timestamp=TIMESTAMP)
    assert asked.exit_code == 4 and asked.error is not None and asked.error["code"] == "FEN-4001"
    assert asked.result["plan"] and folder_snapshot(work) == before

    planned = _quiet_run(capsys, name, *args, "--dry-run", cwd=work, seed=SEED, timestamp=TIMESTAMP)
    assert planned.ok and folder_snapshot(work) == before
    plan_id = planned.result["plan_id"]
    assert plan_id == asked.result["plan_id"]

    written = _quiet_run(
        capsys, name, *args, "--confirm", "--plan", plan_id, cwd=work, seed=SEED, timestamp=TIMESTAMP
    )
    assert written.ok, written.error
    assert written.envelope is not None
    receipt = written.envelope["receipt"]
    assert receipt["plan"] == plan_id
    assert [w["path"] for w in receipt["written"]] == [row["path"] for row in planned.result["plan"]]
    after = folder_snapshot(work)
    # a receipt names its paths as the command spelled them (with \\ on Windows); the snapshot uses /
    assert all(after[w["path"].replace("\\", "/")] == w["sha256"] for w in receipt["written"])
    assert folder_snapshot(elsewhere) == {}


def test_plan_made_in_process_is_written_by_the_cli(
    capsys: CapSys, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Plan, review, write": a plan id of ``run`` names the same staged plan for ``fenolite``."""
    work, _ = _folders(tmp_path, "_echo", monkeypatch)
    planned = _quiet_run(capsys, "_echo", "--write", "echo.txt", "--dry-run", cwd=work)
    monkeypatch.chdir(work)
    code, envelope, _ = _cli(
        capsys, ["_echo", "--write", "echo.txt", "--confirm", "--plan", planned.result["plan_id"]]
    )
    assert code == 0 and envelope["receipt"]["plan"] == planned.result["plan_id"]
    assert (work / "echo.txt").read_text(encoding="utf-8") == "echo\n"
