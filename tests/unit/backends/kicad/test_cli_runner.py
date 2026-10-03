# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The package kicad-cli runner against a fake ``kicad-cli`` (capability kicad-oracle, change c0009)."""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

import pytest

from fenolite.backends.kicad.cli import (
    DRC_REPORT,
    KicadCli,
    KicadCliError,
    KicadCliVersionError,
    find_kicad_cli,
)

FAKE = """import json, os, sys, time
args = sys.argv[1:]
log = os.environ.get("FAKE_LOG")
if log:
    with open(log, "a") as fh:
        fh.write(json.dumps(args) + "\\n")
mode = os.environ.get("FAKE_MODE", "")
if args[:1] == ["version"]:
    print(os.environ.get("FAKE_VERSION", "10.0.6"))
    sys.exit(0)
if mode == "env":
    print(json.dumps({"cwd": os.getcwd(), "env": dict(os.environ)}))
elif mode == "write":
    board = args[-1]
    open(board.rsplit(".", 1)[0] + ".kicad_prl", "w").write("{}")
    open("out.svg", "w").write("<svg/>")
elif mode == "inplace":
    board = args[-1]
    data = open(board).read()
    open(board, "w").write(data + "(rewritten)")
elif mode == "sleep":
    open(os.environ["FAKE_RECORD"], "w").write(os.getcwd())
    time.sleep(30)
elif mode == "paths":
    print(os.path.abspath(args[-1]))
    print(os.path.expanduser("~"))
elif mode == "fail":
    print("bad board", file=sys.stderr)
    sys.exit(3)
elif mode == "drc":
    out = args[args.index("-o") + 1]
    report = {"source": args[-1], "date": "d", "kicad_version": "10.0.6", "coordinate_units": "mm",
              "violations": [{"type": "clearance", "description": "c", "severity": "error",
                              "items": [{"uuid": "u", "description": "t", "pos": {"x": 1.5, "y": 2}}]}],
              "unconnected_items": [], "schematic_parity": []}
    open(out, "w").write(json.dumps(report))
    print(json.dumps({"env": dict(os.environ)}))
elif mode == "nodrc":
    sys.exit(3)
elif mode == "list":
    print(json.dumps(sorted(os.listdir("."))))
    open("out.svg", "w").write("<svg/>")
elif mode == "stats":
    open(args[args.index("-o") + 1], "w").write(json.dumps({"components": {"total": {"total": 3}}}))
"""


@pytest.fixture
def fake(tmp_path: Path) -> Path:
    return write_fake(tmp_path / "bin", FAKE)


def write_fake(folder: Path, program: str) -> Path:
    """An executable ``kicad-cli`` that runs ``program`` with this interpreter (paths may hold spaces)."""
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "fake.py").write_text(program)
    script = folder / "kicad-cli"
    script.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{folder / "fake.py"}" "$@"\n')
    script.chmod(0o755)
    return script


@pytest.fixture
def board(tmp_path: Path) -> Path:
    folder = tmp_path / "src"
    folder.mkdir()
    path = folder / "b.kicad_pcb"
    path.write_text('(kicad_pcb (version 20241229) (generator "t"))\n')
    return path


def _digests(folder: Path) -> dict[str, str]:
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir())}


def test_env_isolated(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LANG", "de_DE.UTF-8")
    monkeypatch.setenv("KICAD10_FOOTPRINT_DIR", "/x")
    monkeypatch.setenv("FAKE_MODE", "env")
    run = KicadCli(fake).run(["pcb", "x", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    assert run.ok
    record = json.loads(run.stdout)
    env = record["env"]
    assert env["LANG"] == "C" and env["LC_ALL"] == "C"
    assert env["KICAD_CONFIG_HOME"] == "<tmp>/config"
    assert "KICAD10_FOOTPRINT_DIR" not in env
    assert record["cwd"] == "<tmp>"


def test_env_entries_are_added(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "env")
    run = KicadCli(fake).run(["x"], files={}, env={"KICAD10_SYMBOL_DIR": "/probe"})
    assert json.loads(run.stdout)["env"]["KICAD10_SYMBOL_DIR"] == "/probe"


def test_source_folder_unchanged(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "write")
    before = _digests(board.parent)
    run = KicadCli(fake).run(["pcb", "x", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    assert _digests(board.parent) == before
    assert set(run.outputs) == {"b.kicad_prl", "out.svg"}
    assert run.outputs["out.svg"] == b"<svg/>"


def test_input_changed_in_place(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "inplace")
    original = board.read_bytes()
    run = KicadCli(fake).run(["pcb", "upgrade", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    assert run.outputs["b.kicad_pcb"] == original + b"(rewritten)"
    assert board.read_bytes() == original


def test_folder_copied(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "env")
    lib = tmp_path / "Lib.pretty"
    lib.mkdir()
    (lib / "A.kicad_mod").write_text("(footprint A)")
    run = KicadCli(fake).run(["x"], files={"Lib.pretty": lib})
    assert run.ok and run.outputs == {}


def test_timeout(fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.kicad import cli as module

    made: list[str] = []
    real_mkdtemp = module.tempfile.mkdtemp

    def mkdtemp(*args: Any, **kwargs: Any) -> str:
        made.append(real_mkdtemp(*args, **kwargs))
        return made[-1]

    monkeypatch.setattr(module.tempfile, "mkdtemp", mkdtemp)
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_RECORD", str(tmp_path / "cwd.txt"))
    run = KicadCli(fake, timeout=1).run(["pcb", "x", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    assert run.outcome == "timeout" and run.returncode is None
    assert len(made) == 1 and not Path(made[0]).exists()


def test_sanitised_output(fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "paths")
    run = KicadCli(fake).run(["pcb", "x", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    lines = run.stdout.splitlines()
    assert lines[0] == "<tmp>/b.kicad_pcb"
    assert lines[1] == "~"
    assert str(Path.home()) not in run.stdout and str(tmp_path) not in run.stdout


def test_bad_names_refused(fake: Path, board: Path) -> None:
    for name in ("/abs.kicad_pcb", "../up.kicad_pcb", "config/x"):
        with pytest.raises(ValueError, match="relative path"):
            KicadCli(fake).run(["x"], files={name: board})


def test_version_and_major(fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_VERSION", "9.0.9")
    cli = KicadCli(fake)
    assert cli.version() == "9.0.9" and cli.major() == 9


def test_upgrade_refused_on_kicad_9(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_VERSION", "9.0.9")
    monkeypatch.setenv("FAKE_LOG", str(log))
    with pytest.raises(KicadCliVersionError) as info:
        KicadCli(fake).upgrade_board(board)
    assert info.value.cli_code == "FEN-6002"
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert all(call[:2] != ["pcb", "upgrade"] for call in calls)


def test_upgrade_returns_the_changed_copy(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "inplace")
    assert KicadCli(fake).upgrade_board(board).endswith(b"(rewritten)")


def test_helpers_raise_on_failure(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "fail")
    cli = KicadCli(fake)
    with pytest.raises(KicadCliError, match="exited 3") as info:
        cli.export_pos_csv(board)
    assert info.value.run.returncode == 3 and "bad board" in info.value.run.stderr
    with pytest.raises(KicadCliError):
        cli.export_ipcd356(board)
    with pytest.raises(KicadCliError):
        cli.load_board_svg(board)


def test_helper_requires_its_output(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "")
    with pytest.raises(KicadCliError, match="wrote no"):
        KicadCli(fake).export_ipcd356(board)


def test_find_explicit_and_override(fake: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    assert find_kicad_cli(fake) == fake
    assert find_kicad_cli(tmp_path / "missing") is None
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(fake))
    assert find_kicad_cli() == fake


def test_missing_override(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(tmp_path / "does-not-exist"))
    assert find_kicad_cli() is None


def test_path_then_bundle(fake: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from fenolite.backends.kicad import cli as module

    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setenv("PATH", str(fake.parent) + os.pathsep + os.environ.get("PATH", ""))
    assert find_kicad_cli() == fake
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    monkeypatch.setattr(module, "MACOS_KICAD_CLI", fake)
    assert find_kicad_cli() == fake
    monkeypatch.setattr(module, "MACOS_KICAD_CLI", tmp_path / "none")
    assert find_kicad_cli() is None


def test_unchanged_resave_returns_the_copy(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A re-save that writes the same bytes leaves no output; the helper returns the copy's bytes."""
    monkeypatch.setenv("FAKE_MODE", "")
    assert KicadCli(fake).upgrade_board(board) == board.read_bytes()


def test_drc_report_is_the_verdict(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_MODE", "drc")
    monkeypatch.setenv("FAKE_LOG", str(log))
    run = KicadCli(fake).drc(board)
    assert run.run.ok and run.report is not None
    (call,) = [json.loads(line) for line in log.read_text().splitlines()]
    assert call == ["pcb", "drc", "--format", "json", "--severity-all", "-o", DRC_REPORT, "b.kicad_pcb"]
    assert "--exit-code-violations" not in call
    (violation,) = run.report.of_type("clearance")
    assert violation.items[0].position.x == 1_500_000


def test_drc_without_report(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "nodrc")
    run = KicadCli(fake).drc(board)
    assert run.report is None and run.run.returncode == 3


def test_extra_files_next_to_the_board(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_MODE", "list")
    pro, table = tmp_path / "x.kicad_pro", tmp_path / "fp-lib-table"
    pro.write_text("{}")
    table.write_text("(fp_lib_table (version 7))")
    lib = tmp_path / "Lib.pretty"
    lib.mkdir()
    (lib / "A.kicad_mod").write_text("(footprint A)")

    def snapshot() -> dict[str, str]:
        return {
            str(f): hashlib.sha256(f.read_bytes()).hexdigest()
            for f in sorted(tmp_path.rglob("*"))
            if f.is_file()
        }

    before = snapshot()
    files = {"board.kicad_pro": pro, "fp-lib-table": table, "Lib.pretty": lib}
    run = KicadCli(fake).load_board_svg(board, files=files)
    listing = json.loads(run.stdout.splitlines()[0])
    assert {"b.kicad_pcb", "board.kicad_pro", "fp-lib-table", "Lib.pretty"} <= set(listing)
    assert snapshot() == before


def test_helpers_take_extra_files(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_MODE", "inplace")
    pro = tmp_path / "x.kicad_pro"
    pro.write_text("{}")
    assert KicadCli(fake).upgrade_board(board, files={"b.kicad_pro": pro}).endswith(b"(rewritten)")


def test_export_stats(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "stats")
    assert KicadCli(fake).export_stats(board) == {"components": {"total": {"total": 3}}}


def test_export_stats_needs_kicad_10(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_VERSION", "9.0.9")
    monkeypatch.setenv("FAKE_MODE", "stats")
    with pytest.raises(KicadCliVersionError) as info:
        KicadCli(fake).export_stats(board)
    assert info.value.cli_code == "FEN-6002"


def test_drc_env_entries(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``KicadCli.drc(env=…)`` reaches ``kicad-cli`` after the runner's own entries (c0021)."""
    monkeypatch.setenv("FAKE_MODE", "drc")
    monkeypatch.setenv("KICAD10_FOOTPRINT_DIR", "/from-the-caller")
    plain = KicadCli(fake).drc(board)
    seen = json.loads(plain.run.stdout)["env"]
    assert seen["KICAD_CONFIG_HOME"] == "<tmp>/config" and "KICAD10_FOOTPRINT_DIR" not in seen
    entries = {"KICAD_CONFIG_HOME": "/probe/config", "FENOLITE_PROBE_LIBS": "/probe/libs"}
    probed = KicadCli(fake).drc(board, env=entries)
    seen = json.loads(probed.run.stdout)["env"]
    assert seen["KICAD_CONFIG_HOME"] == "/probe/config" and seen["FENOLITE_PROBE_LIBS"] == "/probe/libs"
    assert "KICAD10_FOOTPRINT_DIR" not in seen and seen["LANG"] == "C"
    assert probed.report is not None and len(probed.report.violations) == 1
