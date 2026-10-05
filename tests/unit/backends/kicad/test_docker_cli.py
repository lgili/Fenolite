# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Docker runner command and missing-image errors through a fake docker executable."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from _resources import posix_tools

from fenolite.backends.kicad.cli import DockerCli, cli_for, find_kicad_cli
from fenolite.cli._kicadtool import preflight
from fenolite.cli.errors import CliError

pytestmark = posix_tools  # the fake tool of this file is a shell script

FIXTURES = Path(__file__).resolve().parents[3] / "data" / "kicad" / "fill"
IMAGE = "kicad/kicad:10.0.6@sha256:" + "a" * 64


def _docker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, fail: bool = False) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "docker"
    source = f"""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
pathlib.Path({str(tmp_path / "calls.json")!r}).write_text(json.dumps(args))
if {fail!r}:
    print('No such image', file=sys.stderr)
    sys.exit(125)
if args[-1] == 'version':
    print('10.0.6')
else:
    board = pathlib.Path(args[args.index('-v') + 1].split(':/w')[0]) / args[-1]
    board.write_text(pathlib.Path({str(FIXTURES / "triad_t9_refilled.kicad_pcb")!r}).read_text())
    pathlib.Path('drc.json').write_text('{{}}')
"""
    script.write_text(source, encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("PATH", str(bin_dir) + os.pathsep + os.environ.get("PATH", ""))
    return script


def test_fake_docker_mounts_copy_and_returns_saved_board(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _docker(tmp_path, monkeypatch)
    marker = find_kicad_cli("docker:" + IMAGE)
    assert marker is not None
    cli = cli_for(marker)
    assert isinstance(cli, DockerCli) and cli.version() == "10.0.6"
    board = FIXTURES / "triad_t9.kicad_pcb"
    before = board.read_bytes()
    result = cli.refill(board)
    assert result.board == (FIXTURES / "triad_t9_refilled.kicad_pcb").read_bytes()
    assert board.read_bytes() == before
    args = json.loads((tmp_path / "calls.json").read_text())
    assert args[:6] == ["run", "--rm", "--pull", "never", "--platform", "linux/amd64"]
    assert (
        args[-2:]
        == [
            "triad_t9.kicad_pcb",
        ]
        or args[-1] == "triad_t9.kicad_pcb"
    )


def test_missing_image_gets_pull_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _docker(tmp_path, monkeypatch, fail=True)
    with pytest.raises(CliError) as exc:
        preflight("docker:" + IMAGE, 2, FIXTURES / "triad_t9.kicad_pcb")
    assert exc.value.info().code == "FEN-6001" and "docker pull" in exc.value.info().hint


def test_doctor_candidates_exclude_container(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.kicad.cli import kicad_cli_candidates

    monkeypatch.setenv("FENOLITE_KICAD_CLI", "docker:" + IMAGE)
    assert all(not str(candidate.path).startswith("docker:") for candidate in kicad_cli_candidates())
