# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``--progress`` writes progress records on stderr (capability cli-contract, "Progress on stderr" and
"Typed errors on stderr"; change c0120). Hermetic."""

from __future__ import annotations

import io
import json
import tempfile
from pathlib import Path
from typing import Any

import pytest
from _checkcli import hide_kicad, without_elapsed
from _fakecli import fake_kicad_cli
from _projects import authored_project

import fenolite.cli.main as cli_main
from fenolite.cli import progress as progress_records
from fenolite.cli.progress import StderrProgress
from fenolite.core.progress import NULL_PROGRESS, Progress

MonkeyPatch = pytest.MonkeyPatch
KEYS = {"command", "event", "step", "index", "total", "detail", "elapsed_ms"}


def run(monkeypatch: MonkeyPatch, cwd: Path, *args: str) -> tuple[int, str, list[str]]:
    """``(exit code, stdout, the lines of stderr)``."""
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(list(args))
    return code, out.getvalue(), err.getvalue().splitlines()


def records(lines: list[str]) -> list[dict[str, Any]]:
    found = []
    for line in lines:
        data = json.loads(line)
        assert list(data) == ["progress"] and set(data["progress"]) == KEYS, line
        assert data["progress"]["event"] in progress_records.EVENTS
        found.append(data["progress"])
    return found


def test_protocol_and_null_reporter() -> None:
    reporter: Progress = NULL_PROGRESS
    assert reporter.step("a", index=1, total=2) is None and reporter.done("a", detail="x") is None
    assert (
        isinstance(StderrProgress("json", io.StringIO(), "x"), object) and progress_records.INTERVAL == 10.0
    )


def test_silent_by_default(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Silent by default"."""
    code, out, err = run(monkeypatch, tmp_path, "_echo", "--steps", "3", "--json")
    assert code == 0 and err == [] and json.loads(out)["ok"] is True


def test_units_in_order(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, out, err = run(monkeypatch, tmp_path, "_echo", "--steps", "2", "--progress", "--json")
    found = records(err)
    assert code == 0 and [(r["event"], r["step"]) for r in found] == [
        ("step", "step-1"), ("done", "step-1"), ("step", "step-2"), ("done", "step-2"),
    ]  # fmt: skip
    assert (found[0]["index"], found[0]["total"]) == (1, 2) and found[1]["index"] is None
    assert all(r["command"] == "_echo" and isinstance(r["elapsed_ms"], int) for r in found)
    _, plain, _ = run(monkeypatch, tmp_path, "_echo", "--steps", "2", "--json")
    assert without_elapsed(out) == without_elapsed(plain), "stdout is the same with and without the flag"


def test_long_step_stays_alive(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A long step stays alive": the interval is 0.1 s, the step takes 1.0 s (a loaded
    runner, the macOS job of CI run 37850716795, wrote two records in a step of 0.5 s)."""
    monkeypatch.setattr(progress_records, "INTERVAL", 0.1)
    args = ("_echo", "--steps", "1", "--sleep", "1.0", "--progress", "--json")
    code, _, err = run(monkeypatch, tmp_path, *args)
    events = [r["event"] for r in records(err)]
    assert code == 0 and events[0] == "step" and events[-1] == "done"
    assert events[1:-1].count("alive") >= 3 and set(events[1:-1]) == {"alive"}
    assert all(r["step"] == "step-1" for r in records(err))


def test_error_is_the_last_line(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "The error is the last line under progress"."""
    code, out, err = run(monkeypatch, tmp_path, "_echo", "--steps", "3", "--raise", "--progress", "--json")
    assert code == 1 and len(records(err[:-1])) == 6
    assert json.loads(err[-1])["code"] == "FEN-1001" and json.loads(out)["ok"] is False


def test_text_mode_lines(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, _, err = run(monkeypatch, tmp_path, "_echo", "--steps", "1", "--raise", "--progress", "--text")
    assert code == 1 and len(err) == 3
    assert all(line.startswith("progress: _echo: ") for line in err[:-1])
    assert "step step-1 [1/1]" in err[0] and err[-1].startswith("error FEN-1001: ")


def test_heartbeat_stops_before_the_envelope() -> None:
    stream = io.StringIO()
    reporter = StderrProgress("json", stream, "x", interval=0.02)
    reporter.start()
    reporter.step("a")
    import time

    time.sleep(0.1)
    reporter.close()
    size = len(stream.getvalue())
    time.sleep(0.1)
    reporter.done("a")
    assert len(stream.getvalue()) == size and '"alive"' in stream.getvalue()
    reporter.close()


def test_capabilities_list_the_flag(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    code, out, _ = run(monkeypatch, tmp_path, "capabilities", "--no-tools", "--json")
    result = json.loads(out)["result"]
    assert code == 0 and "--progress" in result["global_flags"] and "--json" in result["global_flags"]
    assert result["mutation_flags"] == ["--dry-run", "--confirm", "--plan"]
    assert set(result["global_flags"]) | set(result["mutation_flags"]) >= {
        "--dry-run", "--confirm", "--plan", "--json", "--text", "--fields", "--limit", "--cursor", "--format",
        "--progress", "--seed", "--timestamp", "--no-backup",
    }  # fmt: skip


def test_units_of_a_check(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Units of a check"."""
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10)
    args = ("check", str(root), "--stages", "model.validate,roundtrip", "--json")
    code, out, err = run(monkeypatch, tmp_path, *args, "--progress")
    found = records(err)
    assert code == 0, out
    assert [(r["event"], r["step"]) for r in found] == [
        ("step", "model.validate"), ("done", "model.validate"), ("step", "roundtrip"), ("done", "roundtrip"),
    ]  # fmt: skip
    assert (found[2]["index"], found[2]["total"]) == (2, 2) and found[1]["detail"] == "ok"
    code, plain, silent = run(monkeypatch, tmp_path, *args)
    assert code == 0 and silent == [] and without_elapsed(out) == without_elapsed(plain)


def test_records_hold_no_path_of_the_machine(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Records hold no path of the machine": one unit per kind of ``export``."""
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10)
    fake = fake_kicad_cli(tmp_path / "bin")
    work = tmp_path / "work"
    work.mkdir()
    args = ("export", str(root), "--out", "fab", "--all", "--dry-run", "--progress", "--json")
    code, out, err = run(monkeypatch, work, *args, "--kicad-cli", str(fake))
    found = records(err)
    kinds = json.loads(out)["result"]["kinds"]
    assert code == 0 and kinds == ["gerbers", "drill", "pos", "ipcd356"]
    assert [r["step"] for r in found if r["event"] == "step"] == kinds
    assert [r["step"] for r in found if r["event"] == "done"] == kinds
    for needle in (str(tmp_path), str(Path.home()), tempfile.gettempdir(), "fenolite-kicad-"):
        assert all(needle not in line for line in err), needle


def test_units_of_render_and_fill(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    hide_kicad(monkeypatch, tmp_path)
    root = authored_project(tmp_path, major=10)
    fake = fake_kicad_cli(tmp_path / "bin")
    work = tmp_path / "work"
    work.mkdir()
    args = ("render", str(root), "--out", "views", "--svg", "--dry-run", "--progress", "--json")
    code, out, err = run(monkeypatch, work, *args, "--kicad-cli", str(fake))
    views = [view["path"] for view in json.loads(out)["result"]["views"]]
    steps = [r for r in records(err) if r["event"] == "step"]
    assert code == 0 and views and len(steps) == len(views)
    assert len([r for r in records(err) if r["event"] == "done"]) == len(views)
