# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The direction from KiCad to KiCad, for a target major not older than the source's (capability
design-conversion, "KiCad to KiCad direction" and "KiCad downgrade refused"; change c0159).

The board read from the source keeps its opaque content and is written with ``write_board`` for the target
(``write_triad``, with the source's project file updated by ``pro.update_project``); the rules file is the
source's, read and written again for the target with ``dru.write_rules``, which keeps its order and names.
The schematic files are copied byte for byte when the source's major equals the target, and are reported
as not converted otherwise (a schematic re-target is change c0162's). A target older than the source's
major raises ``DowngradeRefusedError`` (``FEN-7002``) until a direction for it is registered. Changes c0161
and c0162 extend this module.
"""

from __future__ import annotations

import dataclasses

from fenolite.backends.kicad import dru
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import TARGET_MAJORS, DowngradeRefusedError, FileKind
from fenolite.convert.direction import Direction, Options, Written
from fenolite.convert.report import ConversionReport, census
from fenolite.convert.sources import KICAD, SourceProject
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CONV-RETARGET", "H-K-PCB-WRITE"))
"""The board writer's re-target: a KiCad 9 project converted to 10 loads in 10.0.6 and gives the DRC of the
source in 9.0.9 (``H-K-CONV-RETARGET``, confirmed on 2026-10-09)."""
PROFILE = "kicad-to-kicad"
SCHEMATIC = "schematic"
SCHEMATIC_SUFFIX = ".kicad_sch"
WRITER_KINDS: tuple[str, ...] = (SCHEMATIC,)
"""The kinds this direction's writer names besides the census: the schematic files it does not convert."""


def _text(data: bytes) -> str:
    return data.decode("utf-8")


def write(source: SourceProject, options: Options) -> Written:
    """The KiCad project of a KiCad source for ``options.kicad_version``, with its report."""
    target = options.kicad_version
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    if source.major is not None and target < source.major:
        raise DowngradeRefusedError(FileKind.BOARD, source.major, target)
    name = options.name or source.name
    design = source.design
    project_name = f"{source.name}.kicad_pro"
    rules_name = f"{source.name}.kicad_dru"
    existing = _text(source.files[project_name].read_bytes()) if project_name in source.files else None
    issues: list[Issue] = []
    # the rules of the source were read from its rules file: that file is written again below, so the
    # triad lowers no rule of its own (``lowering.lower_rules`` refuses a set read from a file)
    texts = write_triad(
        dataclasses.replace(design, rules=None),
        name=name,
        target=target,
        existing_project=existing,
        issues=issues,
    )
    if rules_name in source.files:
        path = source.files[rules_name]
        ruleset = dru.read_rules(_text(path.read_bytes()), file=path.name)
        texts[f"{name}.kicad_dru"] = dru.write_rules(ruleset, target=target, issues=issues)
    files: dict[str, bytes] = {key: text.encode("utf-8") for key, text in texts.items()}
    sheets = sorted(key for key in source.files if key.endswith(SCHEMATIC_SUFFIX))
    lost: dict[str, dict[str, tuple[str, ...]]] = {}
    if sheets and source.major == target:
        for key in sheets:
            written = f"{name}{SCHEMATIC_SUFFIX}" if key == f"{source.name}{SCHEMATIC_SUFFIX}" else key
            files[written] = source.files[key].read_bytes()
    elif sheets:
        reason = (
            f"a schematic of KiCad {source.major} is not re-targeted to KiCad {target}: the board and its "
            "project files are converted alone"
        )
        lost[SCHEMATIC] = {reason: tuple(sheets)}
    counts = census(design)
    if sheets:
        counts[SCHEMATIC] = len(sheets)
    report = ConversionReport.of(source=counts, lost=lost)
    return Written(dict(sorted(files.items())), report, design, f"{name}.kicad_pcb", tuple(i for i in issues))


DIRECTION = Direction(
    source=KICAD,
    target=KICAD,
    write=write,
    evidence=EVIDENCE,
    experimental=False,
    profile=PROFILE,
    targets=TARGET_MAJORS,
    kinds=WRITER_KINDS,
)

__all__ = ["DIRECTION", "EVIDENCE", "PROFILE", "WRITER_KINDS", "write"]
