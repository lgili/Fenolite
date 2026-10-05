# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pad zone connections in a build and across rebuilds (capabilities design-dsl, "Pad zone connections in
a build", and layout-lens, "Pad zone connections across rebuilds"; change c0068).

The build scenarios call ``build_design``; the rebuild scenarios build a pour variant of the blink into
``tmp_path`` with ``fenolite build``, edit the board as KiCad would (by token edit), and build again
in-process."""

from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from _buildhelp import POUR, build, pour_variant

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.pcb import read_board
from fenolite.backends.kicad.zones import PAD_ZONE_ISSUE_CODES
from fenolite.dsl import pad_zones
from fenolite.model.board import FootprintInstance
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
LIBS = ROOT / "tests" / "data" / "libs"
BOARD = "blink.kicad_pcb"
SOLID = 'd1.zone_connection(1, "solid")\n'
LOCKED = 'd1.zone_connection(1, "solid", locked=True)\n'
PLACE = 'd1.place(mm(38), mm(20), side="bottom")'


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def footprint(design: Design, ref: str) -> FootprintInstance:
    assert design.board is not None
    target = design.by_ref[ref].id
    return next(fp for fp in design.board.footprints if fp.component_id == target)


def connections(design: Design, ref: str) -> dict[str, str | None]:
    return {pad.number: pad.zone_connection for pad in footprint(design, ref).pads}


def pad_codes(issues: Any) -> list[str]:
    return [i["code"] if isinstance(i, dict) else i.code for i in issues if _code(i).startswith("kicad.pad.")]


def _code(issue: Any) -> str:
    return issue["code"] if isinstance(issue, dict) else issue.code


# --- a build without an existing board -------------------------------------------------------------


def variant(*requests: tuple[Any, ...], **kwargs: Any):  # type: ignore[no-untyped-def]
    design = pour_variant()
    for args in requests:
        design.parts["D1"].zone_connection(*args, **kwargs)
    return design


@pytest.mark.parametrize("target", [9, 10])
def test_solid_exposed_pad(target: int) -> None:
    """Scenario "Solid exposed pad"."""
    design = variant((1, "solid"))
    output = build(design, target, pad_zones=pad_zones(design))
    assert output.files and pad_codes(output.issues) == []
    text = output.files[BOARD].decode("utf-8")
    assert connections(read_board(text), "D1") == {"1": "solid", "2": None}
    assert text.count("(zone_connect 2)") == 1 and text.count("(zone_connect") == 1
    assert output.summary["preserved"]["pad_zones"] == {"kept": [], "forced": []}  # type: ignore[index]


def test_unknown_pad_stops_the_build() -> None:
    design = variant((7, "solid"))
    output = build(design, 10, pad_zones=pad_zones(design))
    assert output.files == {}
    (error,) = [i for i in output.issues if i.code.startswith("kicad.pad.")]
    assert (error.code, error.severity) == ("kicad.pad.zone-unknown-pad", "error")
    assert "D1" in error.message and "'7'" in error.message


def test_without_requests_the_build_is_unchanged() -> None:
    plain = build(pour_variant(), 10)
    assert build(pour_variant(), 10, pad_zones={}).files == plain.files
    assert "(zone_connect" not in plain.files[BOARD].decode("utf-8")
    design = variant((1, "solid"))
    requested = build(design, 10, pad_zones=pad_zones(design))
    different = {name for name in plain.files if plain.files[name] != requested.files[name]}
    assert BOARD in different and all(n == BOARD or n.startswith(".fenolite/") for n in different)


def test_requests_pass_the_closed_tables() -> None:
    """The codes are ``kicad.*`` codes: the build adds none of its own for a request."""
    design = variant((1, "solid"), (2, "none"))
    output = build(design, 10, pad_zones=pad_zones(design))
    assert connections(read_board(output.files[BOARD].decode("utf-8")), "D1") == {"1": "solid", "2": "none"}
    assert all(code.startswith("kicad.pad.zone-") for code in PAD_ZONE_ISSUE_CODES)


# --- through the command, with rebuilds ---------------------------------------------------------------


class Project:
    """A blink copy with its libraries and the pour line plus ``append`` added to its script."""

    def __init__(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int = 10, *, append: str = ""
    ):
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / "repo"
        shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
        shutil.copytree(LIBS, root / "tests" / "data" / "libs")
        self.script = root / "examples" / "blink_2layer" / "design.py"
        self.add(POUR + append)
        self.out = tmp_path / "B"

    def add(self, text: str) -> None:
        with self.script.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(text)

    def edit_script(self, old: str, new: str) -> None:
        text = self.script.read_text(encoding="utf-8")
        assert old in text, old
        self.script.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def build(self, *flags: str) -> tuple[int, dict[str, Any]]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue() or err.getvalue() or "{}")

    def confirm(self) -> dict[str, Any]:
        code, env = self.build("--confirm")
        assert code == 0, env
        return env

    @property
    def board(self) -> Path:
        return self.out / BOARD

    def edit_board(self, old: str, new: str) -> None:
        text = self.board.read_text(encoding="utf-8")
        assert text.count(old) == 1, (old, text.count(old))
        self.board.write_text(text.replace(old, new), encoding="utf-8", newline="\n")

    def text(self) -> str:
        return self.board.read_text(encoding="utf-8")

    def files(self) -> dict[str, str]:
        return {
            p.relative_to(self.out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(self.out.rglob("*"))
            if p.is_file() and p.suffix != ".bak"
        }


def edited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, request_line: str = SOLID) -> Project:
    """A confirmed target-10 build with the request, whose pad 1 of ``D1`` then gets ``(zone_connect 1)``
    by token edit, as a pad edited in KiCad."""
    project = Project(tmp_path, monkeypatch, append=request_line)
    project.confirm()
    project.edit_board("(zone_connect 2)", "(zone_connect 1)")
    return project


def test_command_dry_run_plans_the_pad(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch, append=SOLID)
    code, env = project.build("--dry-run")
    assert code == 0 and not project.out.exists()
    assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}
    assert pad_codes(env["issues"]) == []


def test_command_unknown_pad_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Unknown pad stops the build"."""
    project = Project(tmp_path, monkeypatch, append='d1.zone_connection(7, "solid")\n')
    code, env = project.build("--confirm")
    assert code == 5
    (error,) = [i for i in env["issues"] if i["code"] == "kicad.pad.zone-unknown-pad"]
    assert "D1" in error["message"] and "7" in error["message"]
    assert not project.board.exists()


def test_a_pad_edited_in_kicad_wins_over_an_unlocked_request(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = edited(tmp_path, monkeypatch)
    env = project.confirm()
    assert project.text().count("(zone_connect 1)") == 1 and "(zone_connect 2)" not in project.text()
    (info,) = [i for i in env["issues"] if i["code"].startswith("kicad.pad.")]
    assert (info["code"], info["severity"]) == ("kicad.pad.zone-overridden", "info")
    assert all(word in info["message"] for word in ("D1", "pad 1", "solid", "thermal"))
    assert "--discard-layout" in info["hint"]
    assert env["result"]["preserved"]["pad_zones"] == {"kept": ["D1:1"], "forced": []}
    assert "D1" in env["result"]["preserved"]["kept"]


def test_a_locked_request_wins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = edited(tmp_path, monkeypatch)
    project.edit_script(SOLID, LOCKED)
    env = project.confirm()
    assert project.text().count("(zone_connect 2)") == 1 and "(zone_connect 1)" not in project.text()
    (warning,) = [i for i in env["issues"] if i["code"].startswith("kicad.pad.")]
    assert (warning["code"], warning["severity"]) == ("kicad.pad.zone-forced", "warning")
    assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": ["D1:1"]}
    # the next build finds the pad as the request wants it and reports nothing
    again = project.confirm()
    assert pad_codes(again["issues"]) == []
    assert again["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}


def test_a_request_added_after_the_first_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = Project(tmp_path, monkeypatch)
    project.confirm()
    assert "(zone_connect" not in project.text()
    project.add(SOLID)
    env = project.confirm()
    assert "D1" in env["result"]["preserved"]["kept"]
    assert project.text().count("(zone_connect 2)") == 1
    assert connections(read_board(project.board), "D1") == {"1": "solid", "2": None}
    assert pad_codes(env["issues"]) == []
    assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}


def test_rebuilds_of_an_unedited_board_are_quiet_and_stable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = Project(tmp_path, monkeypatch, 9, append=SOLID)
    project.confirm()
    first = project.files()
    for _ in range(2):
        env = project.confirm()
        assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}
        assert pad_codes(env["issues"]) == []
        assert project.files() == first


def test_a_replaced_footprint_takes_the_request(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = edited(tmp_path, monkeypatch)
    project.edit_script(PLACE, 'd1.place(mm(40), mm(20), side="bottom", locked=True)')
    env = project.confirm()
    codes = [i["code"] for i in env["issues"]]
    assert "layout.place-forced" in codes and pad_codes(env["issues"]) == []
    assert "D1" in env["result"]["preserved"]["replaced"]
    assert project.text().count("(zone_connect 2)") == 1 and "(zone_connect 1)" not in project.text()
    assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}


def test_a_pad_that_no_request_names_stays_as_edited(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = edited(tmp_path, monkeypatch)
    project.edit_script(SOLID, 'd1.zone_connection(2, "none")\n')
    env = project.confirm()
    assert connections(read_board(project.board), "D1") == {"1": "thermal", "2": "none"}
    assert pad_codes(env["issues"]) == []


def test_discard_layout_takes_the_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project = edited(tmp_path, monkeypatch)
    code, env = project.build("--confirm", "--discard-layout")
    assert code == 0
    assert connections(read_board(project.board), "D1") == {"1": "solid", "2": None}
    assert env["result"]["preserved"]["pad_zones"] == {"kept": [], "forced": []}


# --- reproducibility ---------------------------------------------------------------------------------


def _subprocess_build(script: Path, out: Path, target: int, seed: int, tmp: Path) -> None:
    env = {**os.environ, "PYTHONHASHSEED": str(seed), "KICAD_CONFIG_HOME": str(tmp / "kc")}
    flags = ["--seed", str(seed), "--timestamp", f"2026-0{seed}-01T00:00:00Z", "--kicad-version", str(target)]
    args = [sys.executable, "-m", "fenolite", "build", str(script), "--out", str(out), "--confirm", "--json"]
    subprocess.run([*args, *flags], check=True, capture_output=True, env=env)


@pytest.mark.parametrize("target", [9, 10])
def test_reproducible_builds_with_requests(
    target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Builds with requests are reproducible"."""
    project = Project(
        tmp_path, monkeypatch, target, append=SOLID + 'r1.zone_connection(2, "none", locked=True)\n'
    )
    snapshots = []
    for seed in (1, 2):
        out = tmp_path / f"o{seed}"
        _subprocess_build(project.script, out, target, seed, tmp_path)
        project.out = out
        snapshots.append(project.files())
        assert project.text().count("(zone_connect") == 2
    assert snapshots[0] and snapshots[0] == snapshots[1]
