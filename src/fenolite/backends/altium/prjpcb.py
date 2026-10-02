# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The minimal PCB project file (capability altium-schematic-writer, "Project file").

Facts: ``docs/formats/altium/project.md``. The file lists the schematic beside it, by its bare file name,
then the PCB document (change c0035, ``H-A-PCB-PRJ``) and the libraries the build writes (change c0034,
``H-A-SCHLIB-PRJ``); Altium takes defaults
for every other key (``H-A-PRJ-OPEN``).
"""

from __future__ import annotations

from collections.abc import Sequence

from fenolite.backends.altium.ascii import LINE_END, text_problem
from fenolite.backends.altium.cfb import name_key

VERSION = "1.0"


def _file_name(name: str, what: str) -> str:
    problem = text_problem(name)
    if problem is not None or "/" in name or "\\" in name:
        raise ValueError(f"the {what} file name {name!r} cannot be written: {problem or 'a path'}")
    return name


def write_prjpcb(*, schematic: str, pcb: str | None = None, libraries: Sequence[str] = ()) -> bytes:
    """``[Design]``, ``Version=1.0``, an empty line, ``[Document1]`` and ``DocumentPath=<schematic>``; then,
    with ``pcb`` (change c0035), ``[Document2]`` and ``DocumentPath=<pcb>``; then per library (``.SchLib`` and
    ``.PcbLib`` alike), in the MS-CFB order of the names and numbered from the next free number, an empty
    line, ``[Document<i>]`` and ``DocumentPath=<library>``; each line ends with CR LF, in 7-bit ASCII without
    a byte-order mark."""
    lines = [
        "[Design]",
        f"Version={VERSION}",
        "",
        "[Document1]",
        f"DocumentPath={_file_name(schematic, 'schematic')}",
    ]
    documents = [_file_name(pcb, "PCB document")] if pcb is not None else []
    documents += [_file_name(library, "library") for library in sorted(libraries, key=name_key)]
    for index, document in enumerate(documents, start=2):
        lines += ["", f"[Document{index}]", f"DocumentPath={document}"]
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


__all__ = ["VERSION", "write_prjpcb"]
