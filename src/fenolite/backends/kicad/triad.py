# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The coherent set of files for one design: board, project and custom rules, always together.

A board without its project silently loses its net classes and custom rules (``H-K-TOK-RULES-SILENT``),
so Fenolite never hands out one without the others (``docs/formats/kicad/project.md``). No function of
Fenolite reads or writes ``.kicad_prl``.
"""

# evidence: see dru, pcb, pro

from __future__ import annotations

from collections.abc import Collection

from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.kicad.pro import apply_sheet_keys, synthesize_project, update_project
from fenolite.backends.kicad.resolver import Edit
from fenolite.backends.kicad.tuning import apply_profile_keys
from fenolite.backends.kicad.versions import DEFAULT_TARGET
from fenolite.core.errors import Issue
from fenolite.core.ids import derived_id
from fenolite.model.design import Design
from fenolite.model.rules import RuleSet

TRIAD_SUFFIXES = (".kicad_pcb", ".kicad_pro", ".kicad_dru")


def write_triad(
    design: Design,
    *,
    name: str,
    target: int = DEFAULT_TARGET,
    existing_project: str | None = None,
    renamed_nets: Collection[str] = (),
    schematic: bool = False,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
    downgrade: bool = False,
    edits: list[Edit] | None = None,
) -> dict[str, str]:
    """``<name>.kicad_pcb``, ``<name>.kicad_pro`` and ``<name>.kicad_dru`` for ``target``.

    An error of any of the three writers aborts the whole set; warnings and infos of all three are
    appended to ``issues``. Nothing is written to disk. ``schematic`` says that the caller also writes
    the schematic of the project, so the drawing sheet of the design is named for it too.
    """
    found: list[Issue] = []
    board = write_board(design, target=target, allow_lossy=allow_lossy, downgrade=downgrade, edits=edits)
    found += board.issues
    rules = design.rules if design.rules is not None else RuleSet(id=derived_id("rst", "fenolite", "empty"))
    lowered = lower_rules(rules, target=target, allow_lossy=allow_lossy)
    found += lowered.issues
    if existing_project is None:
        project = synthesize_project(
            design, target=target, board_name=name, allow_lossy=allow_lossy, issues=found
        )
    else:
        project = update_project(
            existing_project,
            design,
            target=target,
            allow_lossy=allow_lossy,
            issues=found,
            renamed_nets=renamed_nets,
            downgrade=downgrade,
            edits=edits,
        )
    project = apply_sheet_keys(project, design, schematic=schematic, allow_lossy=allow_lossy, issues=found)
    # the impedance targets as KiCad 10 tuning profiles; a target-9 project is returned unchanged (c0105)
    project = apply_profile_keys(project, design, target=target, issues=found)
    if issues is not None:
        issues.extend(found)
    return {f"{name}.kicad_pcb": board.text, f"{name}.kicad_pro": project, f"{name}.kicad_dru": lowered.text}


__all__ = ["TRIAD_SUFFIXES", "write_triad"]
