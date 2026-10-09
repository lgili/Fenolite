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


# --- waivers in the guard (capability design-dsl, "Waivers in the copper guard"; change c0114) -----


def test_waiver_lets_a_short_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "A waived short builds": an authored footprint whose two pads overlap, on two nets and
    without a net-tie group. The waiver names the pads as the refused build prints them: on a base where
    an authored footprint has no ``Reference`` on the board (before change c0077) that is its footprint id
    and the pad number, afterwards ``KS1-1`` and ``KS1-2``."""
    from _routed import Routed
    from _waivercases import KELVIN, plant

    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, KELVIN)
    code, env, _ = routed.build("--dry-run")
    (short,) = [i for i in copper_issues(env) if i["code"] == "copper.short"]
    assert code == 5 and short["severity"] == "error" and env["result"]["files"] == []
    first, second = short["where"].split(", ")
    assert first.endswith("-1") and second.endswith("-2")
    plant(routed, f'design.waive("copper.short", "{first}", "{second}", reason="Kelvin pad")\n')
    name = f"copper.short:{first},{second}"
    code, env, err = routed.build("--confirm")
    assert code == 0, (env.get("issues"), err)
    (short,) = [i for i in copper_issues(env) if i["code"] == "copper.short"]
    assert short["severity"] == "info" and short["message"].endswith(f"(waived by {name}: Kelvin pad)")
    check = env["result"]["copper_check"]
    assert check["waivers"] == {"matched": {name: 1}, "unmatched": []} and check["shorts"] == 1
    assert env["result"]["files"] and routed.board.is_file()
    assert name in (routed.out / ".fenolite" / "findings.json").read_text(encoding="utf-8")


def test_waiver_unmatched_is_listed_in_the_build(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Unmatched waiver listed in the build": the guard names it and emits no
    ``check.waiver-unmatched``; ``fenolite check`` reports stale waivers."""
    from _routed import Routed
    from _waivercases import KELVIN_APART, WAIVER, WAIVER_NAME, plant

    routed = Routed(tmp_path, monkeypatch, confirm=False)
    plant(routed, KELVIN_APART, WAIVER)
    code, env, err = routed.build("--dry-run")
    assert code == 0, err
    assert env["result"]["copper_check"]["waivers"] == {"matched": {}, "unmatched": [WAIVER_NAME]}
    assert not [i for i in env["issues"] if i["code"] == "check.waiver-unmatched"]


def test_waiver_is_applied_before_the_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A waived finding is ``info`` in ``refuse`` and in ``warn`` mode: it gains no warn note, while the
    findings that no waiver names become warnings with it."""
    from _routed import Routed
    from _waivercases import PITCH, tight

    routed = Routed(tmp_path, monkeypatch, confirm=False)
    tight(routed, PITCH)
    code, env, _ = routed.build("--dry-run")
    assert code == 5
    severities = {i["where"]: i["severity"] for i in copper_issues(env) if i["code"] == "copper.clearance"}
    assert severities.pop("U1-10, U1-9") == "info" and set(severities.values()) == {"error"}
    code, env, err = routed.build("--copper-check", "warn", "--dry-run")
    assert code == 0, err
    found = {i["where"]: i for i in copper_issues(env) if i["code"] == "copper.clearance"}
    waived = found.pop("U1-10, U1-9")
    assert waived["severity"] == "info" and WARN_NOTE not in waived["message"]
    assert len(found) == 3 and all(i["message"].endswith(WARN_NOTE) for i in found.values())


def test_waiver_guard_on_a_triad() -> None:
    """The guard function itself: a waiver that names the two items of the bench's short."""
    from fenolite.model.findings import Waiver

    files = triad()
    issues, _ = copper_guard(files, name="bench", mode="refuse", target=10)
    (short,) = [i for i in issues if i.code == "copper.short"]
    items = tuple(short.where.split(", "))
    waiver = Waiver("bench", "copper.short", items, "re-net bench")
    issues, check = copper_guard(files, name="bench", mode="refuse", target=10, waivers=(waiver,))
    (short,) = [i for i in issues if i.code == "copper.short"]
    assert short.severity == "info" and short.message.endswith("(waived by bench: re-net bench)")
    assert check["waivers"] == {"matched": {"bench": 1}, "unmatched": []}
