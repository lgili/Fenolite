# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The clearance rules of a KiCad project, applied to a board for the copper check (capability
kicad-file-backend, "Design rules for the copper check"; facts: ``docs/formats/kicad/copper.md``,
``project.md`` and ``rules.md``).

What KiCad enforces between two copper items lives in two files next to the board: the project file holds
the net classes, the class of each net and the board minimum clearance, and the rules file holds the custom
rules. ``design_rules_from_texts`` applies both texts to a board design with the project reader and the
rules reader, and adds the two switches that say how KiCad combines a custom rule with the classes and with
the minimum, from the tables that the minimums oracle measured per major (``lowering``). It reads no file:
``KicadBackend.design_rules`` passes the texts of a copy set, and the build passes the texts it is about to
write.
"""

# evidence: see dru, pro

from __future__ import annotations

import dataclasses

from fenolite.backends.base import DesignRules
from fenolite.backends.kicad import dru, lowering, pro, rulemap, versions
from fenolite.backends.kicad.sexpr import Node
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.units import Nm
from fenolite.model.design import Design

CLEARANCE = "clearance"
MINIMUM_KEY = "min_clearance"


def _is_clearance(node: Node) -> bool:
    """Whether a rule list holds a ``(constraint clearance …)``."""
    for child in node.nodes():
        if child.name == "constraint":
            atoms = child.atoms()
            if atoms and atoms[0].text == CLEARANCE:
                return True
    return False


def opaque_clearance_rules(rules_text: str, *, file: str = "") -> int:
    """How many rules of a rules file hold a clearance constraint and stay opaque for the model: a rule
    outside the closed grammar, a rule with a comment line inside it, or any rule of a file whose version
    is newer than every supported one."""
    document = dru.parse_rules(rules_text, file=file)
    future = versions.inspect(document.node, file=file).status == versions.VersionStatus.FUTURE
    count = 0
    for item in document.items:
        if not isinstance(item, dru.RuleItem) or not _is_clearance(item.node):
            continue
        if future or item.has_comment or isinstance(rulemap.lift_rule(item.node), str):
            count += 1
    return count


def project_major(project_text: str | None) -> int:
    """The KiCad major of a project file's versions, else the default target (also for a text that does
    not parse)."""
    if project_text is None:
        return versions.DEFAULT_TARGET
    try:
        major = pro.read_project(project_text).major
    except FormatError:
        return versions.DEFAULT_TARGET
    return major if major is not None else versions.DEFAULT_TARGET


def design_rules_from_texts(
    design: Design,
    *,
    project_text: str | None,
    rules_text: str | None,
    major: int = versions.DEFAULT_TARGET,
    file_stem: str = "",
    issues: list[Issue] | None = None,
) -> DesignRules:
    """``design`` with the classes, the class of each net and the rules of the two texts (``None``: the
    file is absent), the board minimum clearance, and the switches of ``major``.

    A text that the reader refuses is named in ``unread`` with the error's message, and the design keeps
    what that file would have given. The readers' warnings and infos are appended to ``issues``.
    """
    found = issues if issues is not None else []
    unread: list[tuple[str, str]] = []
    evidence: list[Evidence] = []
    minimum: Nm | None = None
    opaque = 0
    if project_text is not None:
        name = f"{file_stem}.kicad_pro"
        try:
            read: list[Issue] = []
            info = pro.read_project(project_text, file=name, issues=read)
            applied = pro.apply_project(design, info, issues=read)
        except FormatError as error:
            unread.append((name, error.message))
        else:
            design, minimum = applied, info.floors.get(CLEARANCE)
            found.extend(read)
            evidence.append(pro.EVIDENCE)
    if rules_text is not None:
        name = f"{file_stem}.kicad_dru"
        try:
            read = []
            rules = dru.read_rules(rules_text, file=name, issues=read)
            opaque = opaque_clearance_rules(rules_text, file=name)
        except FormatError as error:
            unread.append((name, error.message))
        else:
            design = dataclasses.replace(design, rules=rules)
            found.extend(read)
            evidence.append(dru.EVIDENCE)
    return DesignRules(
        design=design,
        min_clearance=minimum,
        rules_over_classes=major in lowering.RULES_OVER_CLASSES,
        floor_over_rules=major in lowering.FLOOR_OVER_RULES[MINIMUM_KEY],
        opaque_clearance_rules=opaque,
        unread=tuple(sorted(unread)),
        evidence=Evidence.combine(*evidence) if evidence else Evidence(),
    )


__all__ = ["design_rules_from_texts", "opaque_clearance_rules", "project_major"]
