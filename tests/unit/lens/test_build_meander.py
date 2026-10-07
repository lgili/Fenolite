# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Meanders in a build (capability design-dsl, "Meanders in a build"; change c0106). Hermetic: the build
runs no tool."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import _meanderdesign as md
import pytest

from fenolite.backends.kicad import lengths
from fenolite.backends.kicad.copper import copper_uuid
from fenolite.backends.kicad.pcb import read_board
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]


def totals(design: Design, major: int) -> dict[str, int]:
    return {name: length.total for name, length in lengths.length_facts(design, major=major).nets.items()}


@pytest.mark.parametrize("target", [9, 10])
def test_pair_matched_in_a_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, target: int) -> None:
    md.isolate(monkeypatch, tmp_path)
    script = md.pair_script(tmp_path)
    code, env, err = md.build(monkeypatch, script, tmp_path / "dry", target, "--dry-run")
    assert code == 0, (env.get("issues"), err)
    assert env["result"]["copper"]["meanders"] == 1
    assert not (tmp_path / "dry").exists()
    assert not [i for i in env["issues"] if i["code"].startswith("kicad.meander.")]
    out = tmp_path / "B"
    code, env, err = md.build(monkeypatch, script, out, target, "--confirm")
    assert code == 0, (env.get("issues"), err)
    assert env["result"]["copper"]["meanders"] == 1
    board = read_board((out / "pair.kicad_pcb").read_text(encoding="utf-8"))
    found = totals(board, target)
    assert found["USB_P"] == 25_200_000
    assert abs(found["USB_N"] - found["USB_P"]) <= 10
    assert board.board is not None
    natives = {t.native_ids["kicad"] for t in board.board.tracks}
    assert copper_uuid("n_tune", "m[0]") in natives and copper_uuid("usb_n", "seg[1]") not in natives
    assert {"H-K-NETLEN-MEANDER"} <= set(env["evidence"]["hypotheses"])


def test_without_meanders_the_reply_holds_no_count(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    md.isolate(monkeypatch, tmp_path)
    script = md.pair_script(tmp_path, meander=False)
    out = tmp_path / "B"
    code, env, err = md.build(monkeypatch, script, out, 10, "--confirm")
    assert code == 0, (env.get("issues"), err)
    assert "meanders" not in env["result"]["copper"]
    found = totals(read_board((out / "pair.kicad_pcb").read_text(encoding="utf-8")), 10)
    assert (found["USB_N"], found["USB_P"]) == (24_000_000, 25_200_000)


def test_no_room_stops_the_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    md.isolate(monkeypatch, tmp_path)
    script = md.pair_script(tmp_path, amplitude="0.1")
    out = tmp_path / "B"
    code, env, _ = md.build(monkeypatch, script, out, 10, "--confirm")
    assert code == 5
    refused = [i for i in env["issues"] if i["code"] == "kicad.meander.no-room"]
    assert len(refused) == 1 and "n_tune" in refused[0]["message"] and refused[0]["severity"] == "error"
    assert not out.exists()


def test_rebuild_writes_the_same_bytes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    md.isolate(monkeypatch, tmp_path)
    script = md.pair_script(tmp_path)
    out = tmp_path / "B"
    code, _, err = md.build(monkeypatch, script, out, 10, "--confirm")
    assert code == 0, err
    first = md.files(out)
    code, env, err = md.build(monkeypatch, script, out, 10, "--confirm")
    assert code == 0, (env.get("issues"), err)
    assert md.files(out) == first
    assert "kicad.copper.stale" not in [i["code"] for i in env["issues"]]
    assert env["result"]["copper"]["meanders"] == 1
    # seed and timestamp change no file either
    code, _, err = md.build(
        monkeypatch, script, out, 10, "--confirm", "--seed", "7", "--timestamp", "2020-01-01T00:00:00Z"
    )
    assert code == 0, err
    assert md.files(out) == first


def test_dropping_the_meander_restores_the_segment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    md.isolate(monkeypatch, tmp_path)
    out = tmp_path / "B"
    code, _, err = md.build(monkeypatch, md.pair_script(tmp_path), out, 10, "--confirm")
    assert code == 0, err
    code, env, err = md.build(monkeypatch, md.pair_script(tmp_path, meander=False), out, 10, "--confirm")
    assert code == 0, (env.get("issues"), err)
    board = read_board((out / "pair.kicad_pcb").read_text(encoding="utf-8"))
    assert board.board is not None
    natives = {t.native_ids["kicad"] for t in board.board.tracks}
    assert copper_uuid("usb_n", "seg[1]") in natives and copper_uuid("n_tune", "m[0]") not in natives
    assert totals(board, 10)["USB_N"] == 24_000_000


def test_hash_seed_changes_no_file(tmp_path: Path) -> None:
    script = md.pair_script(tmp_path)
    digests = set()
    for seed in ("0", "99"):
        out = tmp_path / f"B{seed}"
        env = {
            **os.environ,
            "PYTHONHASHSEED": seed,
            "KICAD_CONFIG_HOME": str(tmp_path / "kicad-config"),
        }
        done = subprocess.run(
            [sys.executable, "-m", "fenolite", "build", str(script), "--out", str(out), "--confirm",
             "--json"],
            capture_output=True, text=True, env=env, check=False, cwd=ROOT,
        )  # fmt: skip
        assert done.returncode == 0, done.stdout[-600:] + done.stderr[-600:]
        digests.add(
            tuple(sorted((name, data) for name, data in md.files(out).items() if ".fenolite" not in name))
        )
    assert len(digests) == 1
