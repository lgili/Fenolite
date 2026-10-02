# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The minimal PCB project file (capability altium-schematic-writer, "Project file").

Facts: ``docs/formats/altium/project.md``. The file lists one document, the schematic beside it, by its
bare file name; Altium takes defaults for every other key (``H-A-PRJ-OPEN``).
"""

from __future__ import annotations

from fenolite.backends.altium.ascii import LINE_END, text_problem

VERSION = "1.0"


def write_prjpcb(*, schematic: str) -> bytes:
    """``[Design]``, ``Version=1.0``, an empty line, ``[Document1]`` and ``DocumentPath=<schematic>``,
    each line ending with CR LF, in 7-bit ASCII without a byte-order mark."""
    problem = text_problem(schematic)
    if problem is not None or "/" in schematic or "\\" in schematic:
        raise ValueError(f"the schematic file name {schematic!r} cannot be written: {problem or 'a path'}")
    lines = ("[Design]", f"Version={VERSION}", "", "[Document1]", f"DocumentPath={schematic}")
    return b"".join(line.encode("ascii") + LINE_END for line in lines)


__all__ = ["VERSION", "write_prjpcb"]
