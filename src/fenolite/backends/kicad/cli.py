# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The package ``kicad-cli`` runner: KiCad's command-line tool as an oracle, always on copies.

``kicad-cli`` writes files next to the board it opens (S-0020), so every run copies its inputs to a
fresh temporary folder, runs there with an isolated environment and returns the files the run
created or changed. The caller's files are only ever read. Commands: S-0022 (10.0), S-0037 (9.0).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal, cast

from fenolite.backends.base import DrcReport
from fenolite.core.errors import FenoliteError

MACOS_KICAD_CLI = Path("/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli")
CONFIG_DIR = "config"
DRC_REPORT = "drc.json"
RENDER_DIR = "render"
_VERSION = re.compile(r"(\d+)\.(\d+)")
DOCKER_PREFIX = "docker:"


def find_kicad_cli(explicit: str | os.PathLike[str] | None = None) -> Path | None:
    """The ``kicad-cli`` to use: ``explicit``, else ``FENOLITE_KICAD_CLI``, else ``PATH``, else the
    macOS application bundle. An explicit path or override naming a missing file gives ``None``."""
    if explicit is not None:
        if os.fspath(explicit).startswith(DOCKER_PREFIX) and os.fspath(explicit)[len(DOCKER_PREFIX) :]:
            return Path(os.fspath(explicit))
        path = Path(os.fspath(explicit))
        return path if path.is_file() else None
    override = os.environ.get("FENOLITE_KICAD_CLI")
    if override:
        if override.startswith(DOCKER_PREFIX) and override[len(DOCKER_PREFIX) :]:
            return Path(override)
        return Path(override) if Path(override).is_file() else None
    found = shutil.which("kicad-cli")
    if found:
        return Path(found)
    return MACOS_KICAD_CLI if MACOS_KICAD_CLI.is_file() else None


CandidateSource = Literal["explicit", "env", "path", "macos-app"]


@dataclass(frozen=True, slots=True)
class CliCandidate:
    """An existing ``kicad-cli`` file and where it was found."""

    path: Path
    source: CandidateSource


def kicad_cli_candidates(explicit: Sequence[str | os.PathLike[str]] = ()) -> tuple[CliCandidate, ...]:
    """Every existing ``kicad-cli``: each ``explicit`` path, ``FENOLITE_KICAD_CLI``, ``kicad-cli`` in each
    ``PATH`` entry, then the macOS bundle; deduplicated by resolved path, keeping the first source."""
    found: list[tuple[Path, CandidateSource]] = [(Path(os.fspath(p)), "explicit") for p in explicit]
    override = os.environ.get("FENOLITE_KICAD_CLI")
    if override:
        found.append((Path(override), "env"))
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry:
            found.append((Path(entry) / "kicad-cli", "path"))
    found.append((MACOS_KICAD_CLI, "macos-app"))
    seen: set[Path] = set()
    candidates: list[CliCandidate] = []
    for path, source in found:
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        candidates.append(CliCandidate(path, source))
    return tuple(candidates)


@dataclass(frozen=True)
class CliRun:
    """One ``kicad-cli`` run: its outcome, output streams and the files it created or changed."""

    outcome: Literal["exit", "timeout"]
    returncode: int | None
    stdout: str
    stderr: str
    outputs: Mapping[str, bytes]

    @property
    def ok(self) -> bool:
        return self.outcome == "exit" and self.returncode == 0


@dataclass(frozen=True)
class RefillRun:
    """A zone-refill run and the board KiCad saved, if it saved one."""

    run: CliRun
    board: bytes | None


class KicadCliError(FenoliteError):
    """A ``kicad-cli`` helper failed (non-zero exit or timeout); ``run`` holds what happened."""

    def __init__(self, message: str, run: CliRun) -> None:
        self.run = run
        super().__init__(message)


class KicadCliVersionError(KicadCliError):
    """The command needs another ``kicad-cli`` major (for example ``pcb upgrade``, 10.0 only)."""

    cli_code = "FEN-6002"

    def __init__(self, message: str, run: CliRun, hint: str = "") -> None:
        super().__init__(message, run)
        self.hint = hint


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _files(root: Path) -> dict[str, Path]:
    """Every regular file under ``root``, keyed by POSIX path relative to it, the config folder excluded."""
    found: dict[str, Path] = {}
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if rel.parts[0] == CONFIG_DIR or not path.is_file():
            continue
        found[rel.as_posix()] = path
    return found


def _relative(name: str) -> PurePosixPath:
    rel = PurePosixPath(name)
    if rel.is_absolute() or not rel.parts or ".." in rel.parts or rel.parts[0] == CONFIG_DIR:
        raise ValueError(f"run file name {name!r} must be a relative path outside {CONFIG_DIR!r}")
    return rel


def _environment(config: Path, extra: Mapping[str, str] | None) -> dict[str, str]:
    environ = {key: value for key, value in os.environ.items() if not key.startswith("KICAD")}
    environ.update({"KICAD_CONFIG_HOME": str(config), "LANG": "C", "LC_ALL": "C"})
    environ.update(extra or {})
    return environ


def _decode(data: bytes | str | None) -> str:
    if data is None:
        return ""
    return data if isinstance(data, str) else data.decode("utf-8", "replace")


class KicadCli:
    """A ``kicad-cli`` binary, run as a subprocess on temporary copies (``timeout`` in seconds)."""

    def __init__(self, path: Path, *, timeout: float = 120) -> None:
        self.path = Path(path)
        self.timeout = timeout
        self._version: str | None = None

    def version(self) -> str:
        """The first line that ``kicad-cli version`` prints, for example ``10.0.6``."""
        if self._version is None:
            run = self.run(["version"], files={})
            lines = run.stdout.strip().splitlines()
            if not run.ok or not lines:
                raise KicadCliError(f"kicad-cli version failed: {run.stderr.strip()}", run)
            self._version = lines[0].strip()
        return self._version

    def major(self) -> int:
        match = _VERSION.search(self.version())
        if match is None:
            raise ValueError(f"cannot read a version from {self.version()!r}")
        return int(match.group(1))

    def run(
        self,
        args: Sequence[str],
        *,
        files: Mapping[str, Path],
        env: Mapping[str, str] | None = None,
        folders: Sequence[str] = (),
    ) -> CliRun:
        """Copy ``files`` (relative name → file or folder) to a fresh folder, create the empty ``folders``
        there, and run."""
        tmp = Path(tempfile.mkdtemp(prefix="fenolite-kicad-"))
        try:
            config = tmp / CONFIG_DIR
            config.mkdir()
            for name, source in files.items():
                target = tmp / _relative(name)
                target.parent.mkdir(parents=True, exist_ok=True)
                if Path(source).is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copyfile(source, target)
            for name in folders:
                (tmp / _relative(name)).mkdir(parents=True, exist_ok=True)
            before = {rel: _sha256(path) for rel, path in _files(tmp).items()}
            command = self._command(args, tmp)
            try:
                proc = subprocess.run(
                    command,
                    cwd=tmp,
                    env=_environment(config, env),
                    capture_output=True,
                    timeout=self.timeout,
                    check=False,
                )
                outcome: Literal["exit", "timeout"] = "exit"
                returncode: int | None = proc.returncode
                stdout, stderr = _decode(proc.stdout), _decode(proc.stderr)
            except subprocess.TimeoutExpired as exc:
                outcome, returncode = "timeout", None
                stdout, stderr = _decode(exc.stdout), _decode(exc.stderr)
            outputs = {
                rel: path.read_bytes()
                for rel, path in _files(tmp).items()
                if rel not in before or _sha256(path) != before[rel]
            }
            return CliRun(outcome, returncode, _sanitise(stdout, tmp), _sanitise(stderr, tmp), outputs)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def _command(self, args: Sequence[str], tmp: Path) -> list[str]:
        return [str(self.path), *map(str, args)]

    def _checked(self, args: Sequence[str], files: Mapping[str, Path], what: str) -> CliRun:
        run = self.run(args, files=files)
        if run.outcome == "timeout":
            raise KicadCliError(f"kicad-cli {what} timed out after {self.timeout} s", run)
        if run.returncode != 0:
            detail = (run.stderr or run.stdout).strip()
            raise KicadCliError(f"kicad-cli {what} exited {run.returncode}: {detail}", run)
        return run

    def load_board_svg(self, board: Path, *, files: Mapping[str, Path] | None = None) -> CliRun:
        """The board load check: ``pcb export svg -l Edge.Cuts --mode-single`` exits 0 and writes the SVG.

        ``files`` are copied next to the board (a project file, ``fp-lib-table``, library folders).
        """
        name = Path(board).name
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", name]
        run = self._checked(args, _with(board, files), "pcb export svg")
        if "out.svg" not in run.outputs:
            raise KicadCliError("kicad-cli pcb export svg wrote no SVG", run)
        return run

    def export_pos_csv(self, board: Path, *, files: Mapping[str, Path] | None = None) -> str:
        """``pcb export pos --format csv --side both --units mm`` (the default unit is inches)."""
        name = Path(board).name
        args = ["pcb", "export", "pos", "--format", "csv", "--side", "both", "--units", "mm"]
        run = self._checked([*args, "-o", "pos.csv", name], _with(board, files), "pcb export pos")
        return _output(run, "pos.csv", "pcb export pos")

    def export_ipcd356(self, board: Path, *, files: Mapping[str, Path] | None = None) -> str:
        """``pcb export ipcd356``: the IPC-D-356 netlist text."""
        name = Path(board).name
        run = self._checked(
            ["pcb", "export", "ipcd356", "-o", "board.d356", name], _with(board, files), "pcb export ipcd356"
        )
        return _output(run, "board.d356", "pcb export ipcd356")

    def export(
        self, args: Sequence[str], board: Path, *, files: Mapping[str, Path] | None = None, out: str
    ) -> CliRun:
        """An export command (``args`` without the board) on a copy of ``board``, with the folder ``out``
        created in the run folder first; the caller reads ``returncode`` and the files under ``out``."""
        return self.run([*args, Path(board).name], files=_with(board, files), folders=(out,))

    def render(
        self,
        board: Path,
        *,
        side: Literal["top", "bottom"],
        width: int,
        height: int,
        files: Mapping[str, Path] | None = None,
    ) -> CliRun:
        """``pcb render --side <side>``: the PNG is ``render/<side>.png`` among the outputs. The image is at
        most ``width`` by ``height`` (``docs/formats/kicad/cli.md``)."""
        args = ["pcb", "render", "--side", side, "--width", str(width), "--height", str(height)]
        return self.export([*args, "-o", f"{RENDER_DIR}/{side}.png"], board, files=files, out=RENDER_DIR)

    def _require_ten(self, what: str) -> None:
        if self.major() < 10:
            run = CliRun("exit", None, "", "", {})
            raise KicadCliVersionError(
                f"{what} needs kicad-cli 10.0 or newer; running {self.version()}",
                run,
                hint="run the 10.0 image, for example the kicad-10 job's container",
            )

    def upgrade_board(self, board: Path, *, files: Mapping[str, Path] | None = None) -> bytes:
        """``pcb upgrade --force`` (10.0 only): the board re-saved in the running version's format."""
        self._require_ten("pcb upgrade")
        name = Path(board).name
        run = self._checked(["pcb", "upgrade", "--force", name], _with(board, files), "pcb upgrade")
        return run.outputs.get(name, Path(board).read_bytes())

    def drc(
        self,
        board: Path,
        *,
        files: Mapping[str, Path] | None = None,
        env: Mapping[str, str] | None = None,
    ) -> DrcRun:
        """``pcb drc --format json --severity-all``: the run and its report (``None`` when none was written).

        The exit code is only a load signal; ``--exit-code-violations`` is never passed, and every
        verdict is read from the report. ``env`` is passed unchanged to ``run``, which applies its entries
        after its own ``KICAD_CONFIG_HOME``: the way a probe names a configuration folder or a library
        variable.
        """
        from fenolite.backends.kicad.drc import read_drc_report

        name = Path(board).name
        args = ["pcb", "drc", "--format", "json", "--severity-all", "-o", DRC_REPORT, name]
        run = self.run(args, files=_with(board, files), env=env)
        data = run.outputs.get(DRC_REPORT)
        report = None if data is None else read_drc_report(data.decode("utf-8"), file=DRC_REPORT)
        return DrcRun(run, report)

    def refill(self, board: Path, *, files: Mapping[str, Path] | None = None) -> RefillRun:
        """Refill zones on a copy with KiCad 10 and return the saved board bytes."""
        self._require_ten("pcb drc --refill-zones")
        name = Path(board).name
        args = [
            "pcb",
            "drc",
            "--format",
            "json",
            "--severity-all",
            "--refill-zones",
            "--save-board",
            "-o",
            DRC_REPORT,
            name,
        ]
        run = self.run(args, files=_with(board, files))
        return RefillRun(run, run.outputs.get(name))

    def export_stats(self, board: Path, *, files: Mapping[str, Path] | None = None) -> dict[str, object]:
        """``pcb export stats --format json`` (10.0 only): the board statistics report."""
        self._require_ten("pcb export stats")
        name = Path(board).name
        run = self._checked(
            ["pcb", "export", "stats", "--format", "json", "-o", "stats.json", name],
            _with(board, files),
            "pcb export stats",
        )
        data: object = json.loads(_output(run, "stats.json", "pcb export stats"))
        if not isinstance(data, dict):
            raise KicadCliError("kicad-cli pcb export stats wrote no JSON object", run)
        return cast(dict[str, object], data)


class DockerCli(KicadCli):
    """The same copy runner with ``kicad-cli`` invoked through a pinned Docker image."""

    def __init__(self, image: str, *, timeout: float = 120) -> None:
        self.image = image
        super().__init__(Path(DOCKER_PREFIX + image), timeout=timeout)

    def _command(self, args: Sequence[str], tmp: Path) -> list[str]:
        return [
            "docker",
            "run",
            "--rm",
            "--pull",
            "never",
            "--platform",
            "linux/amd64",
            "-v",
            f"{tmp}:/w",
            "-w",
            "/w",
            "-e",
            "KICAD_CONFIG_HOME=/w/config",
            "-e",
            "LANG=C",
            "-e",
            "LC_ALL=C",
            self.image,
            "kicad-cli",
            *map(str, args),
        ]


def cli_for(path: Path, *, timeout: float = 120) -> KicadCli:
    """Build the package runner for a binary path or ``docker:<image>`` marker."""
    name = os.fspath(path)
    if name.startswith(DOCKER_PREFIX):
        return DockerCli(name[len(DOCKER_PREFIX) :], timeout=timeout)
    return KicadCli(path, timeout=timeout)


@dataclass(frozen=True)
class DrcRun:
    """A ``pcb drc`` run and the report it wrote, or ``None`` when it wrote none."""

    run: CliRun
    report: DrcReport | None


def _with(board: Path, files: Mapping[str, Path] | None) -> dict[str, Path]:
    """The board under its own name, and the extra files next to it."""
    found = {Path(board).name: Path(board)}
    for name, source in (files or {}).items():
        found[name] = Path(source)
    return found


def _output(run: CliRun, name: str, what: str) -> str:
    if name not in run.outputs:
        raise KicadCliError(f"kicad-cli {what} wrote no {name}", run)
    return run.outputs[name].decode("utf-8", "replace")


def _sanitise(text: str, tmp: Path) -> str:
    for spelling in sorted({os.path.realpath(tmp), str(tmp)}, key=len, reverse=True):
        text = text.replace(spelling, "<tmp>")
    home = str(Path.home())
    if home and home != "/":
        text = text.replace(home, "~")
    return text


__all__ = [
    "DRC_REPORT",
    "DOCKER_PREFIX",
    "MACOS_KICAD_CLI",
    "RENDER_DIR",
    "CandidateSource",
    "CliCandidate",
    "CliRun",
    "DrcRun",
    "DockerCli",
    "KicadCli",
    "KicadCliError",
    "KicadCliVersionError",
    "RefillRun",
    "cli_for",
    "find_kicad_cli",
    "kicad_cli_candidates",
]
