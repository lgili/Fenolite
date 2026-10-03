# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library table layouts for the ``pcb-libtable-*`` probes (change c0021 Decision 8; capability
kicad-oracle, "Library table probes").

Every probe writes c0017's altered control, one bottom QFP whose children are not mirrored: when KiCad
finds its library, the report holds exactly one ``lib_footprint_mismatch`` and no
``lib_footprint_issues``. That mismatch is the control that fires only when the library was loaded, so an
empty report is never read as "found". The library is a copy of the CC0 mini library; nothing here is an
official KiCad file. Each run goes through ``KicadCli.drc(board, files=…, env=…)``, except the two layouts
that put the project into a subfolder of the working directory: ``drc`` runs in the board's folder, so they
pass the same arguments to ``KicadCli.run``. Folders that must lie outside the runner's directory (a
library named by a variable, the configuration folder) are temporary folders of the probe, removed
afterwards.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import _bench
from _boards import census
from _triad import library

from fenolite.backends.base import DrcReport
from fenolite.backends.kicad import drc as drcmod
from fenolite.backends.kicad.cli import DRC_REPORT, KicadCli

LAYOUTS = (
    "relpath-project",
    "relpath-nested",
    "relpath-nested-folder",
    "relpath-global",
    "relpath-cwd",
    "relpath-project-folder",
    "nested",
    "fallback",
    "fallback-defined",
    "confighome",
    "confighome-flat",
    "common",
    "common-env",
)
PROBE_VARIABLE = "FENOLITE_PROBE_LIBS"
PROJECT_FOLDER = "proj"
COMMON_FILE = "kicad_common.json"


def probe_id(layout: str) -> str:
    return f"pcb-libtable-{layout}"


def outcome(report: DrcReport | None, *, timed_out: bool = False) -> str:
    """``absent``: no ``lib_footprint_issues`` and exactly one ``lib_footprint_mismatch`` (the library was
    found and compared). ``present``: ``lib_footprint_issues`` and no mismatch (not found). ``different``:
    any other report. ``reject``: no report. ``timeout``: the run timed out."""
    if timed_out:
        return "timeout"
    if report is None:
        return "reject"
    issues = len(report.of_type(drcmod.LIB_FOOTPRINT_ISSUES))
    mismatches = len(report.of_type(drcmod.LIB_FOOTPRINT_MISMATCH))
    if issues == 0 and mismatches == 1:
        return "absent"
    if issues >= 1 and mismatches == 0:
        return "present"
    return "different"


def row(name: str, uri: str, *, major: int, kind: str = "KiCad") -> str:
    """One table row in the syntax of ``major``: quoted atoms from 10.0, bare atoms in 9.0."""
    if major >= 10:
        return f'\t(lib (name "{name}") (type "{kind}") (uri "{uri}") (options "") (descr ""))\n'
    return f'  (lib (name {name})(type {kind})(uri {uri})(options "")(descr ""))\n'


def table(*rows: str, major: int) -> str:
    head = "(fp_lib_table\n\t(version 7)\n" if major >= 10 else "(fp_lib_table\n"
    return head + "".join(rows) + ")\n"


@dataclass
class Layout:
    """The files next to the board (relative name to path) and the explicit environment of one probe.
    With ``folder``, ``files`` are named from the working directory and the board lies in that subfolder."""

    files: dict[str, Path] = field(default_factory=lambda: {})
    env: dict[str, str] = field(default_factory=lambda: {})
    folder: str = ""


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def _common_file(runner: KicadCli, board: Path, files: dict[str, Path], config: Path, libs: Path) -> None:
    """Put ``FENOLITE_PROBE_LIBS`` into ``environment.vars`` of the major's ``kicad_common.json``: into the
    file that a first run of ``kicad-cli`` wrote there, else into a minimal one."""
    major = runner.major()
    runner.drc(board, files=files, env={"KICAD_CONFIG_HOME": str(config)})
    path = config / f"{major}.0" / COMMON_FILE
    written = path.is_file()
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8")) if written else {}
    environment = data.setdefault("environment", {})
    if not isinstance(environment, dict):
        environment = data["environment"] = {}
    variables = environment.get("vars")  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(variables, dict):
        variables = environment["vars"] = {}
    variables[PROBE_VARIABLE] = str(libs)
    _write(path, json.dumps(data, indent=2) + "\n")
    census("libtables", f"common-file-{major}", {"written_by_kicad_cli": written})


def build(layout: str, runner: KicadCli, work: Path) -> tuple[Path, Layout]:
    """The board and the layout of ``layout`` under ``work`` for the running major."""
    major = runner.major()
    project, outside, empty, config = (work / n for n in ("project", "outside", "empty", "config"))
    for folder in (outside, empty, config):
        folder.mkdir(parents=True)
    design = _bench.control(major, _bench.CONTROLS["unmirrored"])
    board, base = _bench.write(design, major, project, table=False)
    lib = library(major)
    found = Layout(dict(base))

    def local_library() -> None:
        shutil.copytree(lib, project / lib.name)
        found.files[lib.name] = project / lib.name

    def project_table(*rows: str) -> None:
        found.files["fp-lib-table"] = _write(project / "fp-lib-table", table(*rows, major=major))

    def outside_library() -> Path:
        shutil.copytree(lib, outside / lib.name)
        return outside

    if layout == "relpath-project":
        local_library()
        project_table(row("Mini", lib.name, major=major))
    elif layout in ("relpath-nested", "relpath-nested-folder", "nested"):
        local_library()
        # relative to the project folder; relative to the nested table's folder; with a variable
        uri = {
            "relpath-nested": lib.name,
            "relpath-nested-folder": f"../{lib.name}",
            "nested": f"${{KIPRJMOD}}/{lib.name}",
        }[layout]
        nested = _write(project / "sub" / "fp-lib-table", table(row("Mini", uri, major=major), major=major))
        found.files["sub/fp-lib-table"] = nested
        project_table(row("Sub", "${KIPRJMOD}/sub/fp-lib-table", major=major, kind="Table"))
    elif layout in ("fallback", "fallback-defined"):
        project_table(row("Mini", f"${{KICAD9_FOOTPRINT_DIR}}/{lib.name}", major=major))
        found.env["KICAD10_FOOTPRINT_DIR"] = str(outside_library())
        if layout == "fallback-defined":
            found.env["KICAD9_FOOTPRINT_DIR"] = str(empty)
    elif layout in ("relpath-cwd", "relpath-project-folder"):
        # the project is a subfolder of the working directory; the library lies in one of the two
        project_table(row("Mini", lib.name, major=major))
        found.files = {f"{PROJECT_FOLDER}/{name}": path for name, path in found.files.items()}
        found.files[f"{PROJECT_FOLDER}/{board.name}"] = board
        found.files[lib.name if layout == "relpath-cwd" else f"{PROJECT_FOLDER}/{lib.name}"] = lib
        found.folder = PROJECT_FOLDER
    elif layout == "relpath-global":
        local_library()  # the library lies in the project folder, not next to the global table
        global_table = table(row("Mini", lib.name, major=major), major=major)
        _write(config / f"{major}.0" / "fp-lib-table", global_table)
        found.env["KICAD_CONFIG_HOME"] = str(config)
    elif layout in ("confighome", "confighome-flat"):
        folder = config / f"{major}.0" if layout == "confighome" else config
        target = outside_library() / lib.name
        _write(folder / "fp-lib-table", table(row("Mini", str(target), major=major), major=major))
        found.env["KICAD_CONFIG_HOME"] = str(config)
    elif layout in ("common", "common-env"):
        project_table(row("Mini", f"${{{PROBE_VARIABLE}}}/{lib.name}", major=major))
        _common_file(runner, board, found.files, config, outside_library())
        found.env["KICAD_CONFIG_HOME"] = str(config)
        if layout == "common-env":
            found.env[PROBE_VARIABLE] = str(empty)
    else:
        raise KeyError(layout)
    return board, found


def run(layout: str, runner: KicadCli) -> str:
    """The outcome of one layout on the running ``kicad-cli``; its temporary folders are removed."""
    work = Path(tempfile.mkdtemp(prefix="fenolite-libtable-"))
    try:
        board, found = build(layout, runner, work)
        if not found.folder:
            result = runner.drc(board, files=found.files, env=found.env)
            return outcome(result.report, timed_out=result.run.outcome == "timeout")
        name = f"{found.folder}/{board.name}"
        args = ["pcb", "drc", "--format", "json", "--severity-all", "-o", DRC_REPORT, name]
        ran = runner.run(args, files=found.files, env=found.env)
        data = ran.outputs.get(DRC_REPORT)
        report = None if data is None else drcmod.read_drc_report(data.decode("utf-8"), file=DRC_REPORT)
        return outcome(report, timed_out=ran.outcome == "timeout")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def observe_common(runner: KicadCli, config: Path, work: Path) -> dict[str, object]:
    """What ``kicad-cli`` writes into the empty configuration folder ``config``: whether the major's
    ``kicad_common.json`` exists and whether its ``environment`` holds ``vars``. Key names only."""
    major = runner.major()
    board, base = _bench.write(_bench.control(major), major, work / "project", table=False)
    runner.drc(board, files=base, env={"KICAD_CONFIG_HOME": str(config)})
    path = config / f"{major}.0" / COMMON_FILE
    seen: dict[str, object] = {"written": path.is_file()}
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        environment = data.get("environment") if isinstance(data, dict) else None
        seen["top_level_keys"] = sorted(data) if isinstance(data, dict) else []
        seen["environment_keys"] = sorted(environment) if isinstance(environment, dict) else []
        seen["environment_has_vars"] = isinstance(environment, dict) and "vars" in environment
    return seen


def probes(runner: Callable[[], KicadCli]) -> dict[str, Callable[[], str]]:
    """``probe id → function`` for the layouts of ``LAYOUTS``; ``runner`` is called when a probe runs."""
    return {probe_id(layout): (lambda layout=layout: run(layout, runner())) for layout in LAYOUTS}


__all__ = [
    "LAYOUTS",
    "PROBE_VARIABLE",
    "Layout",
    "build",
    "observe_common",
    "outcome",
    "probe_id",
    "probes",
    "row",
    "run",
    "table",
]
