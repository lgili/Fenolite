# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite export --readback`` on the running ``kicad-cli`` (change c0203; capability
manufacturing-exports, "Fabrication read-back"), on the authored bench of ``tests/_readbackbench.py``."""

from __future__ import annotations

import dataclasses
import io
import json
import sys
from pathlib import Path
from typing import Any

import pytest
from _probes import major, runner

from fenolite.backends.kicad.pcb import write_board
from fenolite.cli import cmd_export
from fenolite.cli import main as cli_main
from fenolite.exports.plan import Artifact

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from _readbackbench import bench  # noqa: E402

pytestmark = pytest.mark.needs_kicad


def export(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, *args: str) -> tuple[int, dict[str, Any]]:
    board = tmp_path / "rb.kicad_pcb"
    board.write_text(write_board(bench(), target=major()).text, encoding="utf-8", newline="\n")
    monkeypatch.chdir(tmp_path)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", io.StringIO())
    cli = str(runner().path)
    code = cli_main.main(["export", board.name, "-o", "out", "--kicad-cli", cli, *args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def test_the_files_read_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Outline, holes, slots, positions and copper layers of the bench all match."""
    code, env = export(monkeypatch, tmp_path, "--gerbers", "--drill", "--pos", "--readback", "--confirm")
    assert code == 0, env
    assert not [i for i in env["issues"] if i["code"].startswith("export.readback")]
    assert (tmp_path / "out" / "drill" / "rb-NPTH.drl").is_file()


def test_a_missing_slot(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A missing slot": the slot dropped from the drill file read back stops every write."""

    def drop_slot(artifacts: list[Artifact]) -> list[Artifact]:
        out: list[Artifact] = []
        for artifact in artifacts:
            if artifact.path.endswith("NPTH.drl"):
                lines = [line for line in artifact.data.decode().splitlines(True) if "G85" not in line]
                artifact = dataclasses.replace(artifact, data="".join(lines).encode())
            out.append(artifact)
        return out

    monkeypatch.setattr(cmd_export, "READBACK_FILTER", drop_slot)
    code, env = export(monkeypatch, tmp_path, "--gerbers", "--drill", "--readback", "--confirm")
    assert code == 5
    found = [i for i in env["issues"] if i["code"].startswith("export.readback")]
    assert [(i["code"], i["where"]) for i in found] == [("export.readback-drill", "H1")]
    assert "slot" in found[0]["message"] and not (tmp_path / "out").exists()
