# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pinned KiCad 10 image and the local binary produce the same lifted board."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from _resources import kicad_cli

from fenolite.backends.kicad.cli import DockerCli, KicadCli
from fenolite.backends.kicad.fill import fill_board

IMAGE = "kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec"
BOARD = Path(__file__).resolve().parents[2] / "data" / "kicad" / "fill" / "triad_t9.kicad_pcb"


@pytest.mark.needs_kicad
@pytest.mark.kicad_min_major(10)
def test_container_matches_local() -> None:
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    image = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    if image.returncode:
        pytest.skip("pinned KiCad 10 image is not local")
    path = kicad_cli()
    assert path is not None
    original = BOARD.read_text(encoding="utf-8")
    local = KicadCli(Path(path), timeout=300).refill(BOARD)
    container = DockerCli(IMAGE, timeout=300).refill(BOARD)
    assert local.board is not None and container.board is not None
    local_fill = fill_board(original, local.board.decode("utf-8"))
    container_fill = fill_board(original, container.board.decode("utf-8"))
    assert local_fill.text == container_fill.text


def test_container_writes_the_callers_run_folder() -> None:
    """c0156: whoever runs Fenolite (root included), the pinned image writes the run folder of mode 0700
    and the report is read, with no "Permission denied" from ``kicad-cli``. Needs Docker and the image,
    not a local ``kicad-cli``."""
    if shutil.which("docker") is None:
        pytest.skip("Docker is unavailable")
    image = subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, check=False)
    if image.returncode:
        pytest.skip("pinned KiCad 10 image is not local")
    board = Path(__file__).resolve().parents[2] / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
    run = DockerCli(IMAGE, timeout=300).drc(board)
    assert run.run.returncode == 0, run.run.stderr
    assert "Permission denied" not in run.run.stderr
    assert run.report is not None
