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


def _docker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, fail: bool = False, security: str = "name=seccomp"
) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = bin_dir / "docker"
    source = f"""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
if args[:1] == ['info']:
    print(json.dumps([{security!r}]))
    sys.exit(0)
pathlib.Path({str(tmp_path / "calls.json")!r}).write_text(json.dumps(args))
pathlib.Path({str(tmp_path / "env.json")!r}).write_text(json.dumps(dict(os.environ)))
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


def test_docker_client_keeps_the_callers_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """c0153: the container has its own temporary folder, so the ``docker`` client keeps the caller's
    ``XDG_RUNTIME_DIR`` (a rootless daemon's socket) and the command passes no state variable."""
    _docker(tmp_path, monkeypatch)
    monkeypatch.setenv("XDG_RUNTIME_DIR", "/run/user/1000")
    monkeypatch.setenv("TMPDIR", "/shared")
    assert DockerCli(IMAGE).version() == "10.0.6"
    env = json.loads((tmp_path / "env.json").read_text())
    assert env["XDG_RUNTIME_DIR"] == "/run/user/1000" and env["TMPDIR"] == "/shared"
    args = json.loads((tmp_path / "calls.json").read_text())
    passed = [args[i + 1] for i, arg in enumerate(args) if arg == "-e"]
    assert passed == ["HOME=/w/.fenolite-state/home", "KICAD_CONFIG_HOME=/w/config", "LANG=C", "LC_ALL=C"]


def _user_of(args: list[str]) -> str | None:
    return args[args.index("--user") + 1] if "--user" in args else None


def test_container_runs_as_the_owner_of_the_run_folder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """c0156: the run folder is mode 0700 and owned by this process's user, so the container runs as
    that user (``--user uid:gid`` under a daemon run by root), with ``HOME`` in the run's state folder."""
    _docker(tmp_path, monkeypatch)
    cli = DockerCli(IMAGE)
    assert cli.version() == "10.0.6"
    args = json.loads((tmp_path / "calls.json").read_text())
    assert _user_of(args) == f"{os.getuid()}:{os.getgid()}"
    assert args.index("--user") < args.index(IMAGE)
    assert "HOME=/w/.fenolite-state/home" in args


def test_rootless_daemon_runs_the_container_as_its_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """c0156: under a rootless daemon the container's root is this process's user (S-0727)."""
    _docker(tmp_path, monkeypatch, security="name=rootless")
    assert DockerCli(IMAGE).version() == "10.0.6"
    assert _user_of(json.loads((tmp_path / "calls.json").read_text())) == "0:0"


def test_command_line_makes_the_home_folder(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The command line alone, without docker: the user is given, the home folder exists in the run
    folder before the container starts, and the image and its arguments end the line."""
    import fenolite.backends.kicad.cli as cli_module

    monkeypatch.setattr(cli_module, "docker_rootless", lambda timeout=30: False)
    cli = DockerCli(IMAGE)
    command = cli._command(["version"], tmp_path)  # pyright: ignore[reportPrivateUsage]
    assert command[:2] == ["docker", "run"]
    assert command[command.index("--user") + 1] == f"{os.getuid()}:{os.getgid()}"
    assert command[command.index(IMAGE) :] == [IMAGE, "kicad-cli", "version"]
    assert (tmp_path / ".fenolite-state" / "home").is_dir()


def test_docker_user_by_daemon_and_host(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.kicad.cli import docker_user

    monkeypatch.setattr(os, "getuid", lambda: 1234, raising=False)
    monkeypatch.setattr(os, "getgid", lambda: 5678, raising=False)
    assert docker_user(False) == "1234:5678"
    assert docker_user(True) == "0:0"
    monkeypatch.delattr(os, "getuid")
    assert docker_user(False) is None


def test_docker_rootless_without_a_client(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.kicad.cli import docker_rootless

    monkeypatch.setenv("PATH", "")
    assert docker_rootless() is False


def test_missing_image_gets_pull_hint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _docker(tmp_path, monkeypatch, fail=True)
    with pytest.raises(CliError) as exc:
        preflight("docker:" + IMAGE, 2, FIXTURES / "triad_t9.kicad_pcb")
    assert exc.value.info().code == "FEN-6001" and "docker pull" in exc.value.info().hint


def test_doctor_candidates_exclude_container(monkeypatch: pytest.MonkeyPatch) -> None:
    from fenolite.backends.kicad.cli import kicad_cli_candidates

    monkeypatch.setenv("FENOLITE_KICAD_CLI", "docker:" + IMAGE)
    assert all(not str(candidate.path).startswith("docker:") for candidate in kicad_cli_candidates())
