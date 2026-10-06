# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad's own import of an Altium PCB document, as a second reading of the file (capability
design-equivalence, "Board import runner" and "Importer exclusion list per version").

``kicad-cli pcb import --format altium`` (10.0 only, ``H-K-00``; S-0022, S-0166) converts a copy of the
document in the runner's temporary folder, and the converted board is read with this backend's board
reader. The differences that the converter itself introduces are data: ``data/altium_import_exclusions.toml``
holds them per ``kicad-cli`` version line, each measured by running the tool
(``docs/evidence/equivalence-triangle.md``). This module reads no other backend and compares nothing.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import cast

from fenolite.backends.base import ReadResult
from fenolite.backends.kicad import pcb
from fenolite.backends.kicad.cli import IMPORTED_BOARD, ImportRun, KicadCli, KicadCliError
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence

EXCLUSIONS_FILE = "altium_import_exclusions.toml"
PROFILE = "kicad-import"
"""The name of the profiles of the data file, one per ``kicad-cli`` version line."""
ORACLE = "kicad-cli"
IMPORT_EVIDENCE = Evidence(pcb.EVIDENCE.level, ORACLE, ("H-K-00", *pcb.EVIDENCE.hypotheses))
"""A board that ``kicad-cli`` converted, read by the board reader: the reader's level, with the tool named."""
_SEVERITIES = ("warning", "error")
_LINE = re.compile(r"(?:^|: )(Warning|Error): (.+)$")
"""A warning or error line of the tool's output, after its time stamp."""


@dataclass(frozen=True)
class ImportedDesign:
    """The converted board as a read result, the converter's warnings and errors as ``<severity>: <text>``
    (those of its report, then those it prints only), and the tool version."""

    read: ReadResult
    messages: tuple[str, ...]
    tool_version: str


def _report_messages(report: Mapping[str, object] | None) -> list[str]:
    found: list[str] = []
    for severity in reversed(_SEVERITIES):
        listed = (report or {}).get(severity + "s")
        for entry in cast(list[object], listed) if isinstance(listed, list) else ():
            text = cast(Mapping[str, object], entry).get("message") if isinstance(entry, dict) else entry
            if isinstance(text, str) and text.strip():
                found.append(f"{severity}: {text.strip()}")
    return found


def messages(run: ImportRun) -> tuple[str, ...]:
    """The warnings and errors of an import run: those of the JSON report, then the ``Warning:`` and
    ``Error:`` lines of its output, which KiCad prints without listing them in the report. The runner has
    already replaced its temporary folder by ``<tmp>``."""
    found = _report_messages(run.report)
    for line in (run.run.stdout + "\n" + run.run.stderr).splitlines():
        match = _LINE.search(line.strip())
        if match is not None:
            found.append(f"{match.group(1).lower()}: {match.group(2).strip()}")
    return tuple(found)


def import_design(cli: KicadCli, source: Path) -> ImportedDesign:
    """Convert ``source`` with ``cli`` and read the result. ``KicadCliVersionError`` below 10.0;
    ``KicadCliError`` when the tool writes no board; a reader error when the board cannot be read."""
    run = cli.import_board(source)
    if run.board is None:
        if run.run.outcome == "timeout":
            what = f"timed out after {cli.timeout} s"
        else:
            detail = (run.run.stderr or run.run.stdout).strip().splitlines()
            what = f"wrote no board (exit {run.run.returncode})" + (f": {detail[-1]}" if detail else "")
        raise KicadCliError(f"kicad-cli pcb import {what}", run.run)
    found: list[Issue] = []
    design = pcb.read_board(run.board.decode("utf-8", "replace"), file=IMPORTED_BOARD, issues=found)
    read = ReadResult(design, tuple(found), IMPORT_EVIDENCE)
    return ImportedDesign(read, messages(run), cli.version())


def exclusions_text() -> str:
    """The text of the exclusion profiles of KiCad's importer (``data/altium_import_exclusions.toml``)."""
    data = resources.files("fenolite.backends.kicad").joinpath("data", EXCLUSIONS_FILE)
    return data.read_text(encoding="utf-8")


__all__ = [
    "EXCLUSIONS_FILE",
    "IMPORT_EVIDENCE",
    "ORACLE",
    "PROFILE",
    "ImportedDesign",
    "exclusions_text",
    "import_design",
    "messages",
]
