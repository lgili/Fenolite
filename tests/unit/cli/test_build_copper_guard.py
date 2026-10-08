# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The copper guard of ``fenolite build`` (capability design-dsl, "Copper guard before writing"; change
c0029). Hermetic: the guard reads the planned bytes back and runs no tool."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from _coppercheck import bridge_pads, renet_bench

import fenolite.cli.main as cli_main
from fenolite.backends.kicad.triad import write_triad
from fenolite.cli.cmd_build import COPPER_CHECK_MODES, WARN_NOTE, copper_guard

ROOT = Path(__file__).resolve().parents[3]
BLINK_DIR = ROOT / "examples" / "blink_2layer"
OPAQUE = '(rule "text_gap"\n  (condition "A.Type == \'Text\'")\n  (constraint clearance (min 0.5mm)))\n'


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("a subprocess was started")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


# --- the guard on triad texts ---------------------------------------------------------------------


def triad(name: str = "padded", target: int = 10) -> dict[str, bytes]:
    """The triad of a re-net bench: a ``GND`` via that touches a ``VIN`` track."""
    texts = write_triad(renet_bench(name, target).design, name="bench", target=target)
    return {rel: text.encode("utf-8") for rel, text in texts.items()}


def test_modes() -> None:
    assert COPPER_CHECK_MODES == ("refuse", "warn")
    with pytest.raises(ValueError, match="off"):
        copper_guard(triad(), name="bench", mode="off", target=10)


@pytest.mark.parametrize("target", [9, 10])
def test_guard_refuses_a_via_touching_a_track(target: int) -> None:
    issues, result = copper_guard(triad(target=target), name="bench", mode="refuse", target=target)
    (short,) = [i for i in issues if i.code == "copper.short"]
    assert short.severity == "error" and "GND" in short.message and "VIN" in short.message
    assert not short.message.endswith(WARN_NOTE)
    assert result["mode"] == "refuse" and result["ran"] is True
    assert (result["shorts"], result["clearance"]) == (1, 0)
    assert result["rules"] == {"min_clearance": 0, "opaque_clearance_rules": 0, "unread": []}
    assert result["evidence"]["level"] == "INFERRED"  # type: ignore[index]
    assert "H-K-COPPER-SHAPES" in result["evidence"]["hypotheses"]  # type: ignore[index]
    assert "H-K-PCB-READ" in result["evidence"]["hypotheses"]  # type: ignore[index]


def test_guard_in_warn_mode() -> None:
    issues, result = copper_guard(triad(), name="bench", mode="warn", target=10)
    (short,) = [i for i in issues if i.code == "copper.short"]
    assert short.severity == "warning" and short.message.endswith(WARN_NOTE)
    assert not [i for i in issues if i.severity == "error"]
    assert result["mode"] == "warn" and result["shorts"] == 1


def test_guard_judges_the_bytes_it_is_given() -> None:
    files = triad("tied")
    assert copper_guard(files, name="bench", mode="refuse", target=10)[1]["shorts"] == 1
    assert copper_guard({}, name="bench", mode="refuse", target=10) == ((), {"mode": "refuse", "ran": False})
    board_only = {"bench.kicad_pcb": files["bench.kicad_pcb"]}
    issues, result = copper_guard(board_only, name="bench", mode="refuse", target=10)
    assert result["shorts"] == 1 and result["rules"]["min_clearance"] is None  # type: ignore[index]
    assert result["evidence"]["level"] == "UNVERIFIED"  # type: ignore[index]  (no project file was read)


def test_guard_reports_incomplete_rules() -> None:
    files = triad()
    files["bench.kicad_dru"] = files["bench.kicad_dru"] + OPAQUE.encode("utf-8")
    issues, result = copper_guard(files, name="bench", mode="refuse", target=10)
    (incomplete,) = [i for i in issues if i.code == "copper.rules-incomplete"]
    assert incomplete.severity == "warning" and incomplete.message.startswith("1 clearance rule(s)")
    assert result["rules"]["opaque_clearance_rules"] == 1  # type: ignore[index]
    assert result["evidence"]["level"] == "UNVERIFIED"  # type: ignore[index]
    files["bench.kicad_pro"] = b"{"
    issues, result = copper_guard(files, name="bench", mode="refuse", target=10)
    assert result["rules"]["unread"] == ["bench.kicad_pro"]  # type: ignore[index]
    assert sum(1 for i in issues if i.code == "copper.rules-incomplete") == 2


# --- the command ----------------------------------------------------------------------------------


class Blink:
    """A copy of the blink example and its libraries; ``build`` runs ``fenolite build`` into ``out``."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int = 10) -> None:
        self.monkeypatch = monkeypatch
        self.target = target
        root = tmp_path / "repo"
        shutil.copytree(BLINK_DIR, root / "examples" / "blink_2layer")
        shutil.copytree(ROOT / "tests" / "data" / "libs", root / "tests" / "data" / "libs")
        self.script = root / "examples" / "blink_2layer" / "design.py"
        self.out = tmp_path / "B"

    def build(self, *flags: str) -> tuple[int, dict[str, object], dict[str, object]]:
        out, err = io.StringIO(), io.StringIO()
        self.monkeypatch.setattr("sys.stdout", out)
        self.monkeypatch.setattr("sys.stderr", err)
        args = ["--kicad-version", str(self.target), "build", str(self.script), "--out", str(self.out)]
        code = cli_main.main([*args, *flags, "--json"])
        return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}")

    @property
    def board(self) -> Path:
        return self.out / "blink.kicad_pcb"

    def files(self) -> dict[str, bytes]:
        return {
            path.relative_to(self.out).as_posix(): path.read_bytes()
            for path in sorted(self.out.rglob("*"))
            if path.is_file()
        }

    def bridge(self) -> None:
        """A segment on the net of ``R1`` pad 2 laid across ``R1`` pad 1, added to the built board."""
        text = self.board.read_text(encoding="utf-8")
        self.board.write_text(bridge_pads(text, "R1", "2", "1"), encoding="utf-8")


def copper_issues(env: dict[str, object]) -> list[dict[str, str]]:
    return [i for i in env["issues"] if i["code"].startswith("copper.")]  # type: ignore[union-attr,index]


def test_blink_passes_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blink = Blink(tmp_path, monkeypatch)
    code, env, _ = blink.build("--confirm")
    assert code == 0, env["issues"]
    check = env["result"]["copper_check"]  # type: ignore[index]
    assert check["mode"] == "refuse" and check["ran"] is True
    assert (check["shorts"], check["clearance"]) == (0, 0)
    assert check["rules"]["unread"] == [] and check["evidence"]["level"] == "INFERRED"
    assert not [i for i in copper_issues(env) if i["severity"] in ("error", "warning")]
    assert blink.board.is_file()


@pytest.mark.parametrize("target", [9, 10])
def test_blink_dry_run_runs_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: int) -> None:
    blink = Blink(tmp_path, monkeypatch, target)
    code, env, _ = blink.build("--dry-run")
    assert code == 0 and env["result"]["copper_check"]["ran"] is True  # type: ignore[index]
    assert not blink.out.exists()


def test_bridge_refused_before_writing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Short refused before writing"."""
    blink = Blink(tmp_path, monkeypatch)
    assert blink.build("--confirm")[0] == 0
    blink.bridge()
    before = blink.files()
    code, env, err = blink.build("--confirm")
    assert code == 5 and err["code"] == "FEN-5001"
    (short,) = [i for i in copper_issues(env) if i["code"] == "copper.short"]
    assert short["severity"] == "error" and "R1-1" in short["where"]
    assert blink.files() == before
    assert env["result"]["files"] == [] and env["result"]["copper_check"]["shorts"] == 1  # type: ignore[index]
    code, env, _ = blink.build("--dry-run")
    assert code == 5 and env["result"]["files"] == []  # type: ignore[index]
    assert blink.files() == before


def test_warn_mode_writes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Warn mode writes"."""
    blink = Blink(tmp_path, monkeypatch)
    assert blink.build("--confirm")[0] == 0
    blink.bridge()
    code, env, _ = blink.build("--copper-check", "warn", "--confirm")
    assert code == 0, env["issues"]
    (short,) = [i for i in copper_issues(env) if i["code"] == "copper.short"]
    assert short["severity"] == "warning" and short["message"].endswith("(copper guard in warn mode)")
    check = env["result"]["copper_check"]  # type: ignore[index]
    assert check["mode"] == "warn" and check["shorts"] == 1
    assert env["result"]["files"] and "segment" in blink.board.read_text(encoding="utf-8")  # type: ignore[index]


def test_unknown_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blink = Blink(tmp_path, monkeypatch)
    code, _, err = blink.build("--copper-check", "off", "--dry-run")
    assert code == 2 and err["code"] == "FEN-2001"
    assert not blink.out.exists()


def test_the_altium_target_has_its_own_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Change c0088: ``--copper-check`` is no usage error with the Altium target any more; the guard of
    that branch judges the PCB document (``test_build_altium_guard.py``)."""
    blink = Blink(tmp_path, monkeypatch)
    code, env, _ = blink.build("--target", "altium", "--copper-check", "warn", "--dry-run")
    assert code == 0 and env["result"]["copper_check"]["mode"] == "warn"  # type: ignore[index]
    code, env, _ = blink.build("--target", "altium", "--dry-run")
    check = env["result"]["copper_check"]  # type: ignore[index]
    assert code == 0 and (check["mode"], check["ran"], check["shorts"]) == ("refuse", True, 0)


def test_refused_build_does_not_run_the_guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    blink = Blink(tmp_path, monkeypatch)
    text = blink.script.read_text(encoding="utf-8")
    assert "connect(led_a, r1[2], d1[2])" in text
    blink.script.write_text(
        text.replace("connect(led_a, r1[2], d1[2])", "connect(led_a, r1[7], d1[2])"), "utf-8"
    )
    code, env, _ = blink.build("--dry-run")
    assert code == 5 and "build.unknown-pin" in [i["code"] for i in env["issues"]]  # type: ignore[union-attr,index]
    assert env["result"]["copper_check"] == {"mode": "refuse", "ran": False}  # type: ignore[index]
    assert copper_issues(env) == []
