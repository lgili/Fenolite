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
from _resources import posix_tools

from fenolite.backends.kicad.cli import (
    DRC_REPORT,
    ERC_REPORT,
    NETLIST,
    STATE_DIR,
    STATE_VARIABLES,
    KicadCli,
    KicadCliError,
    KicadCliVersionError,
    find_kicad_cli,
    private_state,
)

pytestmark = posix_tools  # the fake tool of this file is a shell script

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
elif mode == "state":
    found = {}
    for name in ("TMPDIR", "TMP", "TEMP", "XDG_RUNTIME_DIR", "XDG_CACHE_HOME", "XDG_STATE_HOME"):
        value = os.environ.get(name, "")
        mode_bits = oct(os.stat(value).st_mode & 0o777) if os.path.isdir(value) else None
        found[name] = [value, mode_bits]
        if mode_bits:
            open(os.path.join(value, "written"), "w").write("x")
    record = os.environ.get("FAKE_RECORD")
    if record:
        open(record, "a").write(os.environ["TMPDIR"] + "\\n")
    print(json.dumps(found))
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
elif mode == "erc":
    sheet = args[-1]
    open(sheet.rsplit(".", 1)[0] + ".kicad_prl", "w").write("{}")
    open(args[args.index("-o") + 1], "w").write(open(os.environ["FAKE_ERC"]).read())
    print(json.dumps({"env": dict(os.environ)}))
elif mode == "noerc":
    print("Failed to load schematic", file=sys.stderr)
    sys.exit(3)
elif mode == "list":
    print(json.dumps(sorted(os.listdir("."))))
    open("out.svg", "w").write("<svg/>")
elif mode == "stats":
    open(args[args.index("-o") + 1], "w").write(json.dumps({"components": {"total": {"total": 3}}}))
elif mode == "netlist":
    sheet = args[-1]
    open(sheet.rsplit(".", 1)[0] + ".kicad_prl", "w").write("{}")
    open(args[args.index("-o") + 1], "w").write(
        '(export (version "E") (components (comp (ref "R1") (value "330") (footprint "L:F"))'
        ' (comp (ref "U1") (value "IC"))))'
    )
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


STATE = {
    "TMPDIR": "tmp",
    "TMP": "tmp",
    "TEMP": "tmp",
    "XDG_RUNTIME_DIR": "runtime",
    "XDG_CACHE_HOME": "cache",
    "XDG_STATE_HOME": "xdg-state",
}


def test_private_state_folders(tmp_path: Path) -> None:
    """c0153: ``private_state`` makes one owner-only folder per kind and names it in its variables."""
    found = private_state(tmp_path / "s")
    assert found == {name: str(tmp_path / "s" / folder) for name, folder in STATE.items()}
    assert dict(STATE_VARIABLES) == STATE
    for value in found.values():
        assert Path(value).is_dir() and Path(value).stat().st_mode & 0o777 == 0o700
    assert private_state(tmp_path / "s") == found  # a second call keeps the folders


def test_env_private_state(fake: Path, board: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """c0153: every run has its own temporary, runtime, cache and state folders inside its run folder,
    whatever the caller's are, and what the tool writes there is not an output."""
    monkeypatch.setenv("FAKE_MODE", "state")
    for name in STATE:
        monkeypatch.setenv(name, "/shared")
    run = KicadCli(fake).run(["sch", "erc", "b.kicad_pcb"], files={"b.kicad_pcb": board})
    assert run.ok
    record = json.loads(run.stdout)
    assert record == {name: [f"<tmp>/{STATE_DIR}/{folder}", "0o700"] for name, folder in STATE.items()}
    assert run.outputs == {}


def test_private_state_per_run_and_removed(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """c0153: eight runs at once get eight temporary folders, and none is left afterwards."""
    from concurrent.futures import ThreadPoolExecutor

    monkeypatch.setenv("FAKE_MODE", "state")
    monkeypatch.setenv("FAKE_RECORD", str(tmp_path / "tmpdirs.txt"))
    cli = KicadCli(fake)
    with ThreadPoolExecutor(max_workers=8) as pool:
        runs = list(pool.map(lambda _: cli.run(["x"], files={"b.kicad_pcb": board}), range(8)))
    assert all(run.ok for run in runs)
    folders = (tmp_path / "tmpdirs.txt").read_text().split()
    assert len(folders) == 8 == len(set(folders))
    assert not any(Path(folder).exists() for folder in folders)


def test_state_entries_can_be_given(fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit ``env`` entry still wins, as it does over ``KICAD_CONFIG_HOME``."""
    monkeypatch.setenv("FAKE_MODE", "env")
    run = KicadCli(fake).run(["x"], files={}, env={"TMPDIR": "/probe"})
    env = json.loads(run.stdout)["env"]
    assert env["TMPDIR"] == "/probe" and env["TMP"] == f"<tmp>/{STATE_DIR}/tmp"


def test_oracle_env_of_the_tests(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """c0153: the environment of the tests that run ``kicad-cli`` themselves keeps their configuration
    folder and adds private state folders beside it."""
    from _kicad import oracle_env

    monkeypatch.setenv("TMPDIR", "/shared")
    env = oracle_env(tmp_path / "config")
    assert env["KICAD_CONFIG_HOME"] == str(tmp_path / "config")
    assert {name: env[name] for name in STATE} == private_state(tmp_path / "kicad-state")


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
    for name in ("/abs.kicad_pcb", "../up.kicad_pcb", "config/x", ".fenolite-state/x"):
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


# -- schematics (change c0060: "Schematic components agree with kicad-cli", "Third-party schematics …")

FLAT = Path(__file__).resolve().parents[3] / "data" / "kicad" / "schematic" / "flat.kicad_sch"


def _folder_state(folder: Path) -> dict[str, str]:
    return {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(folder.iterdir()) if p.is_file()
    }


def test_export_netlist_runs_on_copies(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import _netlist

    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_MODE", "netlist")
    monkeypatch.setenv("FAKE_LOG", str(log))
    before = _folder_state(FLAT.parent)
    run = KicadCli(fake).export_netlist(FLAT)
    assert run.ok and _folder_state(FLAT.parent) == before
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    command = next(c for c in calls if c[:1] == ["sch"])
    assert command[:5] == ["sch", "export", "netlist", "--format", "kicadsexpr"]
    assert command[-1] == "flat.kicad_sch" and command[command.index("-o") + 1] == NETLIST
    found = _netlist.components(run.outputs[NETLIST].decode("utf-8"))
    assert found == {("R1", "330", "L:F"), ("U1", "IC", "")}


def test_export_netlist_does_not_raise_for_a_failed_load(fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "fail")
    run = KicadCli(fake).export_netlist(FLAT)
    assert not run.ok and run.returncode == 3 and NETLIST not in run.outputs


def test_upgrade_schematic(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_MODE", "inplace")
    monkeypatch.setenv("FAKE_LOG", str(log))
    before = _folder_state(FLAT.parent)
    assert KicadCli(fake).upgrade_schematic(FLAT).endswith(b"(rewritten)")
    assert _folder_state(FLAT.parent) == before
    calls = [json.loads(line) for line in log.read_text().splitlines()]
    assert ["sch", "upgrade", "--force", "flat.kicad_sch"] in calls


def test_upgrade_schematic_refused_on_kicad_9(fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_VERSION", "9.0.9")
    with pytest.raises(KicadCliVersionError):
        KicadCli(fake).upgrade_schematic(FLAT)


def test_netlist_helper_refuses_other_roots() -> None:
    import _netlist

    with pytest.raises(ValueError, match="kicad_sch"):
        _netlist.components("(kicad_sch (version 1))")
    assert _netlist.components('(export (version "E"))') == set()


def test_export_bom_arguments(tmp_path: Path) -> None:
    """``sch export bom`` with the fields as their own labels, nothing grouped (capability kicad-oracle,
    "BOM export through the package runner"; change c0064)."""
    from _fakecli import calls, fake_kicad_cli

    from fenolite.backends.kicad.cli import BOM

    fake = fake_kicad_cli(tmp_path / "bin", bom='"Reference","Value","Bin"\n')
    before = _folder_state(FLAT.parent)
    run = KicadCli(fake).export_bom(FLAT, fields=("Reference", "Value", "Bin"))
    assert run.ok and run.outputs[BOM] == b'"Reference","Value","Bin"\n'
    assert _folder_state(FLAT.parent) == before
    args = next(c["args"] for c in calls(fake) if c["args"][:3] == ["sch", "export", "bom"])
    assert args[args.index("--fields") + 1] == "Reference,Value,Bin"
    assert args[args.index("--labels") + 1] == "Reference,Value,Bin"
    assert args[args.index("--ref-range-delimiter") + 1] == ""
    assert args[args.index("-o") + 1] == BOM and args[-1] == "flat.kicad_sch"
    for option in (
        "--group-by",
        "--preset",
        "--format-preset",
        "--exclude-dnp",
        "--include-excluded-from-bom",
    ):
        assert option not in args


def test_export_bom_does_not_raise_for_a_failed_load(tmp_path: Path) -> None:
    from _fakecli import fake_kicad_cli

    from fenolite.backends.kicad.cli import BOM

    run = KicadCli(fake_kicad_cli(tmp_path / "bin")).export_bom(FLAT, fields=("Reference",))
    assert not run.ok and run.returncode == 3 and BOM not in run.outputs


# -- ERC and the parity flag (capability kicad-oracle, "ERC runs through the package runner"; c0062)

ERC_TEN = Path(__file__).resolve().parents[4] / "tests" / "data" / "kicad" / "erc" / "report_10.json"


def test_erc_arguments_and_report(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_MODE", "erc")
    monkeypatch.setenv("FAKE_LOG", str(log))
    monkeypatch.setenv("FAKE_ERC", str(ERC_TEN))
    before = _folder_state(FLAT.parent)
    run = KicadCli(fake).erc(FLAT)
    assert _folder_state(FLAT.parent) == before
    command = next(c for c in map(json.loads, log.read_text().splitlines()) if c[:1] == ["sch"])
    assert command == ["sch", "erc", "--format", "json", "--severity-all", "-o", ERC_REPORT, "flat.kicad_sch"]
    assert "--exit-code-violations" not in command
    assert run.run.ok and run.report is not None
    assert run.report.violations[0].type == "pin_not_connected"
    assert run.report.violations[0].items[0].position.x == 139_700_000
    assert sorted(run.run.outputs) == [ERC_REPORT, "flat.kicad_prl"]


def test_erc_without_report(fake: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "noerc")
    run = KicadCli(fake).erc(FLAT)
    assert run.report is None and run.run.returncode == 3
    assert "Failed to load schematic" in run.run.stderr


def test_erc_timeout_is_an_outcome(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "sleep")
    monkeypatch.setenv("FAKE_RECORD", str(tmp_path / "cwd.txt"))
    run = KicadCli(fake, timeout=0.5).erc(FLAT)
    assert run.report is None and run.run.outcome == "timeout" and run.run.returncode is None


def test_erc_env_and_extra_files(fake: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_MODE", "erc")
    monkeypatch.setenv("FAKE_ERC", str(ERC_TEN))
    table = tmp_path / "sym-lib-table"
    table.write_text("(sym_lib_table (version 7))", encoding="utf-8")
    run = KicadCli(fake).erc(FLAT, files={"sym-lib-table": table}, env={"FENOLITE_PROBE": "x"})
    seen = json.loads(run.run.stdout)["env"]
    assert seen["FENOLITE_PROBE"] == "x" and seen["KICAD_CONFIG_HOME"] == "<tmp>/config"
    monkeypatch.setenv("FAKE_MODE", "list")
    listed = KicadCli(fake).run(["x"], files={"flat.kicad_sch": FLAT, "sym-lib-table": table})
    assert {"flat.kicad_sch", "sym-lib-table"} <= set(json.loads(listed.stdout))


def test_parity_flag_only_when_asked(
    fake: Path, board: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    log = tmp_path / "log.jsonl"
    monkeypatch.setenv("FAKE_MODE", "drc")
    monkeypatch.setenv("FAKE_LOG", str(log))
    KicadCli(fake).drc(board, schematic_parity=True)
    KicadCli(fake).drc(board)
    with_flag, plain = [c for c in map(json.loads, log.read_text().splitlines()) if c[:2] == ["pcb", "drc"]]
    assert with_flag == [
        "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "-o", DRC_REPORT,
        "b.kicad_pcb",
    ]  # fmt: skip
    assert plain == ["pcb", "drc", "--format", "json", "--severity-all", "-o", DRC_REPORT, "b.kicad_pcb"]
