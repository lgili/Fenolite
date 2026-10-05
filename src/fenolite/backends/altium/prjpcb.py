# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The minimal PCB project file (capability altium-schematic-writer, "Project file").

Facts: ``docs/formats/altium/project.md``. The file lists the schematic beside it, by its bare file name,
then the module sheets of a hierarchical project (change c0037), then the PCB document (change c0035,
``H-A-PCB-PRJ``), the libraries the build writes (change c0034, ``H-A-SCHLIB-PRJ``) and the harness
definition files (change c0037, ``H-A-SCH-HIER-PRJ``); Altium takes defaults for every other key
(``H-A-PRJ-OPEN``). The schematic documents come first and together: with this minimal file Altium
Designer took only the first module sheet into the hierarchy when the PCB document and the libraries
stood between the top sheet and the module sheets (``H-A-SCH-HIER-ORDER``).

Change c0048 adds the class generation options ("Class generation" of the fact page): three keys in the
section of every schematic document of a project with module sheets or a PCB document, so that Altium
derives a component class per sheet and no room, and the section ``[PrjClassGen]`` for a design with a net
class, so that
Altium takes the net classes from the directives of the schematic (``H-A-ECO-PRJ-KEYS``, ``H-A-ECO-ROOMS``).
"""

# evidence: see project

from __future__ import annotations

from collections.abc import Sequence

from fenolite.backends.altium.ascii import LINE_END, text_problem
from fenolite.backends.altium.cfb import name_key

VERSION = "1.0"
SHEET_CLASS_KEYS: tuple[tuple[str, str], ...] = (
    ("ClassGenCCAutoEnabled", "1"),
    ("ClassGenCCAutoRoomEnabled", "0"),
    ("ClassGenNCAutoScope", "None"),
)
"""The class options of one schematic document of a project with module sheets or a PCB document (change
c0048): a component class for the sheet, no room, no net class of the sheet's nets."""
CLASS_SECTION = "PrjClassGen"
CLASS_GENERATION: tuple[tuple[str, str], ...] = (
    ("CompClassManualEnabled", "0"),
    ("CompClassManualRoomEnabled", "0"),
    ("NetClassAutoBusEnabled", "1"),
    ("NetClassAutoCompEnabled", "0"),
    ("NetClassAutoNamedHarnessEnabled", "0"),
    ("NetClassManualEnabled", "1"),
    ("NetClassSeparateForBusSections", "0"),
)
"""The keys of ``[PrjClassGen]`` with the values of the public saved projects (change c0048):
``NetClassManualEnabled=1`` is the option "Generate Net Classes" for user-defined classes."""


def _file_name(name: str, what: str) -> str:
    problem = text_problem(name)
    if problem is not None or "/" in name or "\\" in name:
        raise ValueError(f"the {what} file name {name!r} cannot be written: {problem or 'a path'}")
    return name


def write_prjpcb(
    *,
    schematic: str,
    pcb: str | None = None,
    libraries: Sequence[str] = (),
    sheets: Sequence[str] = (),
    harnesses: Sequence[str] = (),
    net_classes: bool = False,
) -> bytes:
    """``[Design]``, ``Version=1.0``, an empty line, ``[Document1]`` and ``DocumentPath=<schematic>``; then,
    each after an empty line as ``[Document<i>]`` and ``DocumentPath=<file>``, numbered from 2: each module
    sheet of ``sheets`` in the order given (change c0037), the PCB document ``pcb`` (change c0035), each
    library (``.SchLib`` and ``.PcbLib`` alike) in the MS-CFB order of the names, and each harness
    definition file of ``harnesses`` in the MS-CFB order of the names. Every schematic document so precedes
    every other document, the top sheet first (``H-A-SCH-HIER-ORDER``); without module sheets the bytes
    are those of changes c0032 to c0035. Each line ends with CR LF, in 7-bit ASCII without a byte-order
    mark. No key names the top sheet or the net scope (``H-A-SCH-HIER-PRJ``, ``H-A-SCH-HIER-COMPILE``).

    Change c0048: with ``sheets`` not empty or with a PCB document, the section of every schematic
    document, the single or top sheet and each module sheet, holds the three lines of ``SHEET_CLASS_KEYS``
    after ``DocumentPath``; with ``net_classes`` true the file ends with an empty line, ``[PrjClassGen]``
    and the seven lines of ``CLASS_GENERATION``. Without module sheets, PCB document and net class the
    bytes do not change."""
    with_keys = bool(sheets) or pcb is not None
    sheet_keys = [f"{key}={value}" for key, value in SHEET_CLASS_KEYS] if with_keys else []
    lines = [
        "[Design]",
        f"Version={VERSION}",
        "",
        "[Document1]",
        f"DocumentPath={_file_name(schematic, 'schematic')}",
        *sheet_keys,
    ]
    schematics = [_file_name(sheet, "sheet") for sheet in sheets]
    documents = [_file_name(pcb, "PCB document")] if pcb is not None else []
    documents += [_file_name(library, "library") for library in sorted(libraries, key=name_key)]
    documents += [_file_name(harness, "harness") for harness in sorted(harnesses, key=name_key)]
    for index, document in enumerate([*schematics, *documents], start=2):
        lines += ["", f"[Document{index}]", f"DocumentPath={document}"]
        if index - 2 < len(schematics):
            lines += sheet_keys
    if net_classes:
        lines += ["", f"[{CLASS_SECTION}]", *(f"{key}={value}" for key, value in CLASS_GENERATION)]
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


__all__ = ["CLASS_GENERATION", "CLASS_SECTION", "SHEET_CLASS_KEYS", "VERSION", "write_prjpcb"]
