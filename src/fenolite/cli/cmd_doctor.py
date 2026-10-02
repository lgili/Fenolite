# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite doctor``: the external tools Fenolite can use, probed (capability cli-contract, "Doctor
command"; ``docs/cli-contract.md``, "doctor").

Each ``kicad-cli`` candidate reports its version and a command matrix read from its help pages
(``helpmatrix``, ``H-K-CLI-HELP``), always through the package runner. ``java -version`` follows JEP 223
(S-0081) and ``docker version`` its documented template (S-0080). A missing or unsupported tool is a
warning: ``doctor`` describes, so it exits 0. ``capabilities`` stays static and hermetic.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import subprocess
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fenolite.backends.kicad import helpmatrix, versions
from fenolite.backends.kicad.cli import KicadCli, KicadCliError, find_kicad_cli, kicad_cli_candidates
from fenolite.cli.api import Command, Context, Result
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence

HELP = "report the external tools Fenolite can use: kicad-cli candidates and their commands, java, docker"
ISSUE_CODES: Mapping[str, Severity] = {
    "doctor.tool-missing": "warning",
    "doctor.tool-unsupported": "warning",
    "doctor.help-unparsed": "warning",
}
TOOL_TIMEOUT = 15
_JAVA_VERSION = re.compile(r'"([^"]+)"')
_LEADING = re.compile(r"(\d+)(?:\.(\d+))?")
_DOCKER_VERSION = re.compile(r"version\s+([^,\s]+)")


def _issue(code: str, message: str, where: str) -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where)


def _register(parser: argparse.ArgumentParser) -> None:
    parser.description = HELP + "; see docs/cli-contract.md, 'doctor'."
    parser.add_argument("--kicad-cli", dest="kicad_cli", action="append", default=[], metavar="PATH",
                        help="a kicad-cli to report (repeatable)")  # fmt: skip
    parser.add_argument("--no-run", action="store_true", help="list the candidates and run no tool")


def java_major(version_line: str) -> int | None:
    """The Java major of a ``java -version`` line (JEP 223, S-0081): ``1.8.0_402`` gives 8, ``17.0.2`` 17."""
    quoted = _JAVA_VERSION.search(version_line)
    match = _LEADING.search(quoted.group(1) if quoted else version_line)
    if match is None:
        return None
    first, second = match.group(1), match.group(2)
    return int(second) if first == "1" and second is not None else int(first)


def _output(args: list[str]) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=TOOL_TIMEOUT, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def java_info(path: Path) -> dict[str, object]:
    """``path``, the first line of ``java -version`` (printed on stderr) and its major."""
    run = _output([str(path), "-version"])
    lines = (run.stderr or run.stdout).strip().splitlines() if run is not None else []
    line = lines[0].strip() if lines else None
    return {"path": str(path), "version": line, "major": java_major(line) if line else None}


def docker_info(path: Path) -> dict[str, object]:
    """``path``, the client version of ``docker --version``, and the daemon version (``None`` when no
    daemon answers, S-0080)."""
    client = _output([str(path), "--version"])
    found = _DOCKER_VERSION.search(client.stdout) if client is not None else None
    server = _output([str(path), "version", "--format", "{{.Server.Version}}"])
    daemon = server.stdout.strip() if server is not None and server.returncode == 0 else ""
    return {"path": str(path), "version": found.group(1) if found else None, "daemon": daemon or None}


def _matrix(rows: Mapping[str, bool] | None) -> dict[str, object] | None:
    if rows is None:
        return None
    keys = [helpmatrix.row_key(e.command, o) for e in helpmatrix.MATRIX for o in ("", *e.options)]
    return {key: rows.get(key, "unknown") for key in keys}


def _probe(path: Path, issues: list[Issue]) -> tuple[dict[str, object], bool]:
    """The fields of one candidate that ran, and whether every page parsed."""
    cli = KicadCli(path)
    try:
        version, major = cli.version(), cli.major()
    except (KicadCliError, ValueError):
        issues.append(_issue("doctor.tool-unsupported", "it did not report a kicad-cli version", str(path)))
        return {"version": None, "major": None, "supported": False, "matrix": None,
                "evidence": _evidence(Evidence())}, False  # fmt: skip
    supported = major in versions.TARGET_MAJORS
    if not supported:
        issues.append(_issue("doctor.tool-unsupported", f"kicad-cli {version} is not supported", str(path)))
    matrix = helpmatrix.command_matrix(cli)
    for page in matrix.unparsed:
        issues.append(_issue("doctor.help-unparsed", f"{page} did not parse", str(path)))
    parsed = not matrix.unparsed
    evidence = _with_oracle(version) if parsed else Evidence()
    fields: dict[str, object] = {
        "version": version,
        "major": major,
        "supported": supported,
        "matrix": _matrix(matrix.rows),
        "evidence": _evidence(evidence),
    }
    return fields, parsed


def _with_oracle(version: str) -> Evidence:
    e = helpmatrix.EVIDENCE
    return Evidence(e.level, f"kicad-cli {version}", e.hypotheses)


def _evidence(evidence: Evidence) -> dict[str, object]:
    return {"level": evidence.level.value, "oracle": evidence.oracle, "hypotheses": list(evidence.hypotheses)}


def _run(args: argparse.Namespace, ctx: Context) -> Result:
    issues: list[Issue] = []
    explicit: list[str] = list(args.kicad_cli)
    for given in explicit:
        if not Path(given).is_file():
            issues.append(_issue("doctor.tool-missing", f"--kicad-cli names a missing file: {given}", given))
    override = os.environ.get("FENOLITE_KICAD_CLI")
    if override and not Path(override).is_file():
        issues.append(_issue("doctor.tool-missing", f"FENOLITE_KICAD_CLI names a missing file: {override}",
                             "FENOLITE_KICAD_CLI"))  # fmt: skip
    chosen = find_kicad_cli(explicit[0] if explicit else None)
    selected = chosen.resolve() if chosen is not None else None
    entries: list[dict[str, Any]] = []
    ran: list[tuple[bool, str, bool]] = []  # (selected, version, every page parsed)
    for candidate in kicad_cli_candidates(explicit):
        entry: dict[str, Any] = {"path": str(candidate.path), "source": candidate.source,
                                 "selected": candidate.path.resolve() == selected}  # fmt: skip
        if args.no_run:
            entry.update(version=None, major=None, supported=None, matrix=None, evidence=None)
        else:
            fields, parsed = _probe(candidate.path, issues)
            entry.update(fields)
            if fields["version"] is not None:
                ran.append((entry["selected"], str(fields["version"]), parsed))
        entries.append(entry)
    if not entries:
        issues.append(_issue("doctor.tool-missing", "no kicad-cli found", "kicad-cli"))
    by_major: dict[str, list[str]] = {}
    for entry in entries:
        if entry["major"] is not None:
            by_major.setdefault(str(entry["major"]), []).append(entry["path"])
    others: dict[str, Any] = {}
    for tool, probe in (("java", java_info), ("docker", docker_info)):
        found = shutil.which(tool)
        if found is None:
            others[tool] = None
            issues.append(_issue("doctor.tool-missing", f"{tool} not found on PATH", tool))
        elif args.no_run:
            others[tool] = {"path": found}
        else:
            others[tool] = probe(Path(found))
    evidence = Evidence()
    if ran and all(parsed for _, _, parsed in ran):
        version = next((v for sel, v, _ in ran if sel), ran[0][1])
        evidence = _with_oracle(version)
    result = {"kicad_cli": entries, "by_major": dict(sorted(by_major.items())), **others}
    return Result(result=result, issues=tuple(issues), evidence=evidence)


COMMAND = Command(
    name="doctor",
    help=HELP,
    mutates=False,
    register=_register,
    run=_run,
    example_args=("--no-run",),
)
