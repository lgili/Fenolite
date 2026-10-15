# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The directions to KiCad: from KiCad (capability design-conversion, "KiCad to KiCad direction", "KiCad
downgrade direction" and "KiCad downgrade report"; changes c0159 and c0162) and from Altium ("Altium to
KiCad direction", change c0161, ``write_altium`` below).

The board read from the source keeps its opaque content and is written with ``write_board`` for the target
(``write_triad``, with the source's project file updated by ``pro.update_project``); the rules file is the
source's, read and written again for the target with ``dru.write_rules``, which keeps its order and names.
The schematic files are copied byte for byte when the source's major equals the target, and are reported
as not converted for a newer target.

A target older than the source's major is a downgrade (change c0162): every file is written with
``downgrade=True``, so the capability resolver (``backends/kicad/resolver.py``) decides each construct of
the newer major, and its edits become one report row per resolver id (kind ``downgrade:<id>``). The
schematic sheets are re-targeted (``sch.retarget_schematic``), the footprint and symbol libraries of the
project's own tables are written for the target (``mod.write_footprint``, ``sym.retarget_symbol_library``),
and the library tables and drawing sheets, whose formats both majors read, are copied. The writers run
with ``allow_lossy``: the consent to a ``design`` loss is ``convert_project``'s, by the report.
"""

from __future__ import annotations

import dataclasses
from collections import defaultdict
from pathlib import Path, PurePosixPath

from fenolite.backends.kicad import dru, resolver, sch, sym
from fenolite.backends.kicad.dru import DROPPED_CODE as RULE_DROPPED
from fenolite.backends.kicad.lowering import lower_rules
from fenolite.backends.kicad.mod import read_footprint, write_footprint
from fenolite.backends.kicad.triad import write_triad
from fenolite.backends.kicad.versions import TARGET_MAJORS
from fenolite.convert import from_altium, kicad_project
from fenolite.convert.direction import Direction, Options, TargetLimitError, Written
from fenolite.convert.report import DOWNGRADE_KINDS, DOWNGRADE_PREFIX, ConversionReport, census
from fenolite.convert.sources import ALTIUM, KICAD, SourceProject
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.design import Design
from fenolite.model.rules import Rule

EVIDENCE = Evidence(Level.KICAD_VERIFIED, hypotheses=("H-K-CONV-RETARGET", "H-K-PCB-WRITE"))
"""The board writer's re-target: a KiCad 9 project converted to 10 loads in 10.0.6 and gives the DRC of the
source in 9.0.9 (``H-K-CONV-RETARGET``, confirmed on 2026-10-09)."""
DOWNGRADE_EVIDENCE = resolver.EVIDENCE
"""A downgrade: the evidence of the resolver's table (``H-K-DOWN-ROWS``, ``H-K-DOWN-DEMOS``)."""
PROFILE = "kicad-to-kicad"
DOWNGRADE_PROFILE = "kicad-downgrade"
SCHEMATIC = "schematic"
SCHEMATIC_SUFFIX = ".kicad_sch"
FOOTPRINT_SUFFIX = ".kicad_mod"
SYMBOL_SUFFIX = ".kicad_sym"
LIBRARY_FOLDER = ".pretty"
WRITER_KINDS: tuple[str, ...] = (SCHEMATIC, *(row.name for row in DOWNGRADE_KINDS))
"""The kinds this direction's writer names besides the census: the schematic files, and one kind per row
of the downgrade resolver."""
REASONS: dict[resolver.Action, str] = {
    "rewrite": "written in the form of the target",
    "same": "dropped: the target behaves the same without it",
    "presentation": "dropped: a drawing, a text or metadata of the target differs",
    "design": "dropped: what is made or checked differs",
}


def _text(data: bytes) -> str:
    return data.decode("utf-8")


def _renamed(key: str, source: SourceProject, name: str) -> str:
    """The written name of the project file ``key``: the files of the source's stem take ``name``."""
    path = PurePosixPath(key)
    if len(path.parts) == 1 and path.stem == source.name:
        return f"{name}{path.suffix}"
    return key


def write(source: SourceProject, options: Options) -> Written:
    """The KiCad project of a KiCad source for ``options.kicad_version``, with its report."""
    target = options.kicad_version
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    if source.major is not None and target < source.major:
        return _downgrade(source, options)
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


def _downgrade(source: SourceProject, options: Options) -> Written:
    """The project of a source of a newer major written for ``options.kicad_version`` (change c0162)."""
    target = options.kicad_version
    name = options.name or source.name
    design = source.design
    project_name = f"{source.name}.kicad_pro"
    rules_name = f"{source.name}.kicad_dru"
    existing = _text(source.files[project_name].read_bytes()) if project_name in source.files else None
    issues: list[Issue] = []
    edits: list[resolver.Edit] = []
    found: list[resolver.Edit] = []
    texts = write_triad(
        dataclasses.replace(design, rules=None),
        name=name,
        target=target,
        existing_project=existing,
        allow_lossy=True,
        issues=issues,
        downgrade=True,
        edits=found,
    )
    for edit in found:
        suffix = ".kicad_pro" if edit.row.startswith(resolver.PROJECT_PREFIX) else ".kicad_pcb"
        edits.append(dataclasses.replace(edit, file=f"{name}{suffix}"))
    if rules_name in source.files:
        path = source.files[rules_name]
        ruleset = dru.read_rules(_text(path.read_bytes()), file=path.name)
        found = []
        texts[f"{name}.kicad_dru"] = dru.write_rules(
            ruleset, target=target, allow_lossy=True, issues=issues, downgrade=True, edits=found
        )
        edits += [dataclasses.replace(edit, file=f"{name}.kicad_dru") for edit in found]
    files: dict[str, bytes] = {key: text.encode("utf-8") for key, text in texts.items()}
    written_triad = set(files)
    sheets = 0
    for key, path in sorted(source.files.items()):
        out = _renamed(key, source, name)
        if out in written_triad or key in (project_name, rules_name, f"{source.name}.kicad_pcb"):
            continue
        if key.endswith(SCHEMATIC_SUFFIX):
            sheet = sch.read_schematic(path, file=key)
            found = []
            text = sch.retarget_schematic(
                sheet, target=target, downgrade=True, allow_lossy=True, issues=issues, edits=found
            )
            files[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in found]
            sheets += 1
        elif key.endswith(SYMBOL_SUFFIX) and path.is_file():
            found = []
            text = sym.retarget_symbol_library(
                _text(path.read_bytes()), target=target, downgrade=True, allow_lossy=True, file=key,
                issues=issues, edits=found,
            )  # fmt: skip
            files[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in found]
        elif key.endswith(LIBRARY_FOLDER) and path.is_dir():
            files.update(_footprints(key, path, target, issues, edits))
        elif path.is_file():
            files[out] = path.read_bytes()
    counts = census(design)
    if sheets:
        counts[SCHEMATIC] = sheets
    changed: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    lost: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for edit in edits:
        into = changed if edit.action in resolver.CHANGED else lost
        into[DOWNGRADE_PREFIX + edit.row][REASONS[edit.action]].append(f"{edit.file}:{edit.where}")
    report = ConversionReport.of(
        source=counts,
        changed={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in changed.items()},
        lost={kind: {r: tuple(ids) for r, ids in reasons.items()} for kind, reasons in lost.items()},
    )
    return Written(
        dict(sorted(files.items())),
        report,
        design,
        f"{name}.kicad_pcb",
        tuple(issues),
        schematic=f"{name}{SCHEMATIC_SUFFIX}" if f"{name}{SCHEMATIC_SUFFIX}" in files else None,
        profile=DOWNGRADE_PROFILE,
        evidence=DOWNGRADE_EVIDENCE,
    )


def _footprints(
    key: str, folder: Path, target: int, issues: list[Issue], edits: list[resolver.Edit]
) -> dict[str, bytes]:
    """The footprints of the library folder ``key``, each written for ``target``; any other file of the
    folder copied."""
    found: dict[str, bytes] = {}
    for path in sorted(folder.iterdir()):
        out = f"{key}/{path.name}"
        if path.suffix == FOOTPRINT_SUFFIX and path.is_file():
            defn = read_footprint(path, library=folder.stem)
            mine: list[resolver.Edit] = []
            text = write_footprint(
                defn, target=target, allow_lossy=True, issues=issues, downgrade=True, edits=mine
            )
            found[out] = text.encode("utf-8")
            edits += [dataclasses.replace(edit, file=out) for edit in mine]
        elif path.is_file():
            found[out] = path.read_bytes()
    return found


# --- Altium to KiCad (change c0161) -------------------------------------------------------------------

ALTIUM_EVIDENCE = Evidence(
    Level.INFERRED,
    hypotheses=("H-K-CONV-A2K-LOAD", "H-K-CONV-A2K-IMPORT", "H-K-CONV-A2K-SCH", "H-K-PCB-WRITE"),
)
"""The direction from Altium: the read keeps its labels (``INFERRED``); the written boards are checked by
the three oracles of ``tests/kicad/convert/`` (``docs/evidence/conversion.md``)."""
ALTIUM_PROFILE = "altium-to-kicad"
ALTIUM_KINDS: tuple[str, ...] = (SCHEMATIC,)
REASON_RULE_TARGET = "a rule the target's rules file cannot hold"
REASON_RULE_OPT = "the preferred value of the rule is not written: the rules file takes none for its kind"


def _merge(into: dict[str, dict[str, list[str]]], items: dict[str, dict[str, tuple[str, ...]]]) -> None:
    for kind, reasons in items.items():
        for reason, ids in reasons.items():
            into.setdefault(kind, {}).setdefault(reason, []).extend(ids)


def _writable_rules(
    design: Design, target: int
) -> tuple[Design, dict[str, tuple[str, ...]], dict[str, tuple[str, ...]]]:
    """``design`` without the rules that the rules file of ``target`` cannot hold, each lowered alone
    (``lowering.lower_rules``); the ids of those left out per reason, and of those written without their
    preferred value (``opt``), which the rules file refused."""
    rules = design.rules
    if rules is None or not rules.rules:
        return design, {}, {}
    kept: list[Rule] = []
    refused: dict[str, list[str]] = {}
    changed: dict[str, list[str]] = {}
    for rule in rules.rules:
        try:
            try:
                lower_rules(dataclasses.replace(rules, rules=(rule,)), target=target, allow_lossy=True)
            except (FenoliteError, ValueError):
                if rule.opt is None:
                    raise
                plain = dataclasses.replace(rule, opt=None)
                lower_rules(dataclasses.replace(rules, rules=(plain,)), target=target, allow_lossy=True)
                rule = plain
                changed.setdefault(REASON_RULE_OPT, []).append(rule.id)
        except (FenoliteError, ValueError) as error:
            first = getattr(error, "issues", ())
            detail = first[0].message if first else str(error)
            detail = detail.split(": ", 1)[1] if detail.startswith("rule '") and ": " in detail else detail
            refused.setdefault(f"{REASON_RULE_TARGET}: {detail}", []).append(rule.id)
            continue
        kept.append(rule)
    made = dataclasses.replace(design, rules=dataclasses.replace(rules, rules=tuple(kept)))
    return made, {r: tuple(ids) for r, ids in refused.items()}, {r: tuple(ids) for r, ids in changed.items()}


def write_altium(source: SourceProject, options: Options) -> Written:
    """The KiCad project of an Altium source for ``options.kicad_version``, with its report: the board
    lowered by ``from_altium.lower_board``, the footprint library derived from its instances, the generated
    schematic with generic symbols, and the project and rules files of ``write_triad``."""
    target = options.kicad_version
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    name = options.name or source.name
    design = source.design
    try:
        lowered = from_altium.lower_board(design, project=name, target=target)
    except ValueError as error:
        raise TargetLimitError(f"{source.path.name} cannot be written as a KiCad board: {error}") from None
    changed: dict[str, dict[str, list[str]]] = {}
    lost: dict[str, dict[str, list[str]]] = {}
    _merge(changed, lowered.items(lowered.changed))
    _merge(lost, lowered.items(lowered.lost))
    issues: list[Issue] = []
    written = lowered.design
    library = kicad_project.derived_library(written, name)
    if library.edited:
        _merge(changed, {"footprint": {kicad_project.REASON_EDITED: library.edited}})
    files: dict[str, bytes] = {}
    library_texts, refused = kicad_project.library_files(library, name, target=target, issues=issues)
    files.update(library_texts)
    for footprint_name, message in refused.items():
        ids = tuple(
            fp.id
            for fp in (written.board.footprints if written.board else ())
            if fp.lib_ref == f"{name}:{footprint_name}"
        )
        _merge(lost, {"footprint-graphic": {f"the library footprint is not written: {message}": ids}})
    counts = census(design)
    if design.circuit.components:
        counts[SCHEMATIC] = 1
        generated = kicad_project.schematic(written, name, target=target)
        issues += [found for found in generated.issues if found.severity != "error"]
        if generated.files:
            files.update(generated.files)
            written = generated.design
            _merge(changed, {SCHEMATIC: {kicad_project.REASON_SCHEMATIC: (design.header.id,)}})
        else:
            _merge(lost, {SCHEMATIC: {kicad_project.REASON_SCHEMATIC_REFUSED: (design.header.id,)}})
    written, refused_rules, plain_rules = _writable_rules(written, target)
    _merge(lost, {"rule": refused_rules})
    _merge(changed, {"rule": plain_rules})
    texts = write_triad(
        written,
        name=name,
        target=target,
        schematic=bool(design.circuit.components),
        allow_lossy=True,
        issues=issues,
    )
    files.update({key: text.encode("utf-8") for key, text in texts.items()})
    rules = {rule.name: rule.id for rule in (design.rules.rules if design.rules is not None else ())}
    dropped = tuple(rules.get(found.where, found.where) for found in issues if found.code == RULE_DROPPED)
    if dropped:
        _merge(lost, {"rule": {REASON_RULE_TARGET: dropped}})
    report = ConversionReport.of(
        source=counts,
        changed={k: {r: tuple(v) for r, v in rs.items()} for k, rs in changed.items()},
        lost={k: {r: tuple(v) for r, v in rs.items()} for k, rs in lost.items()},
    )
    return Written(
        dict(sorted(files.items())),
        report,
        written,
        f"{name}.kicad_pcb",
        tuple(issues),
        profile=ALTIUM_PROFILE,
    )


ALTIUM_DIRECTION = Direction(
    source=ALTIUM,
    target=KICAD,
    write=write_altium,
    evidence=ALTIUM_EVIDENCE,
    experimental=True,
    profile=ALTIUM_PROFILE,
    targets=TARGET_MAJORS,
    kinds=ALTIUM_KINDS,
)

DIRECTION = Direction(
    source=KICAD,
    target=KICAD,
    write=write,
    evidence=EVIDENCE,
    experimental=False,
    profile=PROFILE,
    targets=TARGET_MAJORS,
    kinds=WRITER_KINDS,
    downgrade=True,
)

__all__ = [
    "ALTIUM_DIRECTION",
    "ALTIUM_EVIDENCE",
    "ALTIUM_PROFILE",
    "DIRECTION",
    "DOWNGRADE_PROFILE",
    "EVIDENCE",
    "PROFILE",
    "WRITER_KINDS",
    "write",
    "write_altium",
]
