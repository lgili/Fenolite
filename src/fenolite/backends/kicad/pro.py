# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad project files (``.kicad_pro``): versions, reading, synthesis and in-place updates.

Facts and Fenolite choices: ``docs/formats/kicad/project.md``. The project file is JSON and stays
outside ``versions.FileKind``. Every key name comes from KiCad-written files (GUI saves and the demo
census), never from a specification, because none is public.
"""

from __future__ import annotations

import dataclasses
import hashlib
import os
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from functools import cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.lowering import (
    FLOOR_KEYS,
    MINIMUM_KEYS,
    NETCLASS_KEYS,
    class_conflicts,
    governing_rule,
    lower_minimums,
    lower_netclass,
    millimetres,
)
from fenolite.backends.kicad.pcb import source_info
from fenolite.backends.kicad.proerrors import ISSUE_CODES, project_issue
from fenolite.backends.kicad.versions import (
    DEFAULT_TARGET,
    TARGET_MAJORS,
    DowngradeRefusedError,
    FileKind,
    FutureFormatError,
    LossyWriteError,
    UnsupportedFormatError,
    VersionStatus,
)
from fenolite.backends.kicad.wks import RESERVED_VARIABLES
from fenolite.core.errors import ConsistencyError, FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.provenance import Provenance
from fenolite.core.units import Nm, parse_length
from fenolite.model.circuit import Net, NetClass
from fenolite.model.design import Design, presentation_issues
from fenolite.model.presentation import TitleBlock

PROJECT_VERSIONS: Mapping[int, tuple[int, int]] = MappingProxyType({9: (3, 4), 10: (3, 5)})
"""The pair (``meta.version``, ``net_settings.meta.version``) Fenolite writes per target."""
PROJECT_READ_MAX = 3
NET_SETTINGS_READ_MAX = 5
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PRO-PATTERNS",))
"""A user's project may use pattern forms the oracle has not run (``H-K-PRO-PATTERNS``)."""
UNSAFE_PATTERN_CHARS: frozenset[str] = frozenset("*?")
"""Characters a classed net name must not hold: they are wildcards in a pattern."""
PATTERNS = "/net_settings/netclass_patterns"
PATTERN_ENTRY_PATHS: frozenset[str] = frozenset(
    {f"{PATTERNS}/*", f"{PATTERNS}/*/netclass", f"{PATTERNS}/*/pattern"}
)
"""The key paths a pattern entry adds; the only paths synthesis may add to the template's."""
DEFAULT_CLASS = "Default"
MINIMUM_POINTER = "/board/design_settings/rules"
"""Where the board-setup minimums live (``project.md``, "Board-setup minimums")."""
REWRITE_HINT = "re-save the project in KiCad 9 or 10, or let Fenolite synthesise a new one"


def read_project_text(text: str, *, file: str = "") -> JsonObject:
    """A project file's JSON with key order and number spellings kept (``_json.loads``)."""
    return _json.loads(text, file=file)


def write_project_text(data: JsonObject) -> str:
    """The project JSON printed with two-space indentation and a final newline (``_json.dumps``)."""
    return _json.dumps(data)


def classify_project(meta_version: int | None, net_settings_version: int | None) -> VersionStatus:
    """``FUTURE`` above ``meta.version`` 3 or ``net_settings.meta.version`` 5, ``SUPPORTED`` otherwise
    (absent versions included: KiCad reads a ``{}`` project)."""
    if (meta_version or 0) > PROJECT_READ_MAX or (net_settings_version or 0) > NET_SETTINGS_READ_MAX:
        return VersionStatus.FUTURE
    return VersionStatus.SUPPORTED


def project_major(meta_version: int | None, net_settings_version: int | None) -> int | None:
    """The target whose pair equals the given pair, or ``None``."""
    for major, pair in PROJECT_VERSIONS.items():
        if pair == (meta_version, net_settings_version):
            return major
    return None


# --- templates ------------------------------------------------------------------------------------


@cache
def _template_text(target: int) -> str:
    name = f"data/project_template_{target}.json"
    return resources.files("fenolite.backends.kicad").joinpath(name).read_text(encoding="utf-8")


def template(target: int) -> JsonObject:
    """A fresh copy of the packaged template of ``target`` (an empty project saved by the KiCad GUI)."""
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    return _json.loads(_template_text(target), file=f"project_template_{target}.json")


def _ten_only() -> frozenset[str]:
    return _json.key_paths(template(10)) - _json.key_paths(template(9))


TEN_ONLY_PATHS: frozenset[str] = _ten_only()
"""Key paths of the 10 template absent from the 9 template (list items written ``*``)."""


# --- small JSON helpers ---------------------------------------------------------------------------


def _object(data: JsonObject, key: str, file: str, where: str) -> JsonObject | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise FormatError(f"{key!r} is not an object", file=file, locator=f"{where}/{key}")
    return cast(JsonObject, value)


def _version(meta: JsonObject | None, file: str, where: str) -> int | None:
    if meta is None or meta.get("version") is None:
        return None
    value = meta["version"]
    if not isinstance(value, JsonNumber) or not re.fullmatch(r"-?\d+", value.text):
        raise FormatError("the version is not an integer", file=file, locator=f"{where}/version")
    return int(value.text)


def _versions(data: JsonObject, file: str = "") -> tuple[int | None, int | None]:
    meta = _object(data, "meta", file, "")
    settings = _object(data, "net_settings", file, "")
    inner = _object(settings, "meta", file, "/net_settings") if settings is not None else None
    return _version(meta, file, "/meta"), _version(inner, file, "/net_settings/meta")


def _nm(value: Any, where: str, issues: list[Issue]) -> Nm | None:
    if not isinstance(value, JsonNumber):
        return None
    try:
        return parse_length(value.text, default_unit="mm")
    except ValueError:
        issues.append(
            project_issue(
                "kicad.project.inexact-value",
                f"{value.text} mm is not a whole number of nanometres; read as unset",
                where=where,
            )
        )
        return None


def _escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


# --- patterns -------------------------------------------------------------------------------------


def _wildcard(pattern: str) -> re.Pattern[str]:
    parts = [".*" if c == "*" else "." if c == "?" else re.escape(c) for c in pattern]
    return re.compile("".join(parts), re.DOTALL)


def pattern_matches(pattern: str, name: str) -> bool:
    """Whether a net-class pattern matches ``name`` as KiCad's manual describes (S-0046): as a whole-name
    wildcard (``*`` any run, ``?`` one character, case-sensitive) or as a regular expression.

    Python's ``re`` stands in for the wxWidgets flavour, and whole-name matching is assumed
    (``INFERRED``, ``H-K-PRO-PATTERNS``); a pattern that does not compile matches as a wildcard only.
    """
    if _wildcard(pattern).fullmatch(name):
        return True
    try:
        compiled = re.compile(pattern)
    except re.error:
        return False
    return compiled.fullmatch(name) is not None


# --- reading --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ProjectClass:
    """A ``net_settings.classes`` entry: its name and the four modelled values in nm."""

    name: str
    clearance: Nm | None = None
    track_width: Nm | None = None
    via_diameter: Nm | None = None
    via_drill: Nm | None = None


@dataclass(frozen=True)
class ProjectInfo:
    """A read project file: its tree, versions, classes, pattern entries, assignments and floors."""

    file: str
    data: JsonObject
    meta_version: int | None
    net_settings_version: int | None
    status: VersionStatus
    major: int | None
    classes: tuple[ProjectClass, ...] = ()
    patterns: tuple[tuple[str, str], ...] = ()
    assignments: tuple[tuple[str, tuple[str, ...]], ...] = ()
    floors: dict[str, Nm] = field(default_factory=lambda: {})
    sha256: str = ""
    priorities: tuple[int, ...] = ()
    """The ``priority`` of each class, in ``classes`` order (absent: the largest value)."""
    drawing_sheet: str | None = None
    """``pcbnew.page_layout_descr_file`` (``None`` when absent or empty; change c0012)."""
    text_variables: tuple[tuple[str, str], ...] = ()
    """``text_variables`` members with a string value, in file order (change c0012)."""


def project_floors(data: JsonObject, *, issues: list[Issue] | None = None) -> dict[str, Nm]:
    """Model field → the nm value of its ``board.design_settings.rules`` minimum, when present."""
    found = issues if issues is not None else []
    rules = _json.get(data, "/board/design_settings/rules")
    if not isinstance(rules, dict):
        return {}
    table = cast(JsonObject, rules)
    floors: dict[str, Nm] = {}
    for model_field, key in FLOOR_KEYS.items():
        value = _nm(table.get(key), f"/board/design_settings/rules/{key}", found)
        if value is not None:
            floors[model_field] = value
    return floors


def project_minimums(data: JsonObject, *, issues: list[Issue] | None = None) -> dict[str, Nm]:
    """Key → the nm value of each ``MINIMUM_KEYS`` member of ``board.design_settings.rules`` that is a
    JSON number; an inexact value reads as absent with ``kicad.project.inexact-value``."""
    found = issues if issues is not None else []
    rules = _json.get(data, MINIMUM_POINTER)
    if not isinstance(rules, dict):
        return {}
    table = cast(JsonObject, rules)
    keys = dict.fromkeys(key for kinds in MINIMUM_KEYS.values() for key in kinds.values())
    minimums: dict[str, Nm] = {}
    for key in keys:
        value = _nm(table.get(key), f"{MINIMUM_POINTER}/{key}", found)
        if value is not None:
            minimums[key] = value
    return minimums


def _source(source: str | os.PathLike[str], file: str) -> tuple[str, str]:
    if isinstance(source, str):
        return source, file
    path = Path(source)
    return path.read_text(encoding="utf-8"), file or os.fspath(path)


def read_project(
    source: str | os.PathLike[str], *, file: str = "", issues: list[Issue] | None = None
) -> ProjectInfo:
    """A project file (a path, or its text) read into a ``ProjectInfo`` (project.md, "Reading")."""
    found = issues if issues is not None else []
    text, file = _source(source, file)
    data = _json.loads(text, file=file)
    meta_version, settings_version = _versions(data, file)
    status = classify_project(meta_version, settings_version)
    if status == VersionStatus.FUTURE:
        found.append(
            Issue(
                "kicad.version.future",
                "warning",
                f"project versions ({meta_version}, {settings_version}) are newer than every supported pair; "
                "the file is read-only for Fenolite",
            )
        )
    settings = _object(data, "net_settings", file, "") or {}
    raw_classes: Any = settings.get("classes")
    raw_classes = [] if raw_classes is None else raw_classes
    if not isinstance(raw_classes, list):
        raise FormatError("'classes' is not a list", file=file, locator="/net_settings/classes")
    classes: list[ProjectClass] = []
    priorities: list[int] = []
    for index, entry in enumerate(cast(list[Any], raw_classes)):
        where = f"/net_settings/classes/{index}"
        if not isinstance(entry, dict):
            raise FormatError("a class is not an object", file=file, locator=where)
        item = cast(JsonObject, entry)
        name = item.get("name")
        if not isinstance(name, str):
            raise FormatError("a class has no string 'name'", file=file, locator=where)
        values = {f: _nm(item.get(k), f"{where}/{k}", found) for f, k in NETCLASS_KEYS.items()}
        classes.append(ProjectClass(name, **values))
        priority = item.get("priority")
        number = priority.text if isinstance(priority, JsonNumber) else ""
        priorities.append(int(number) if re.fullmatch(r"-?\d+", number) else 2**31 - 1)
    patterns: list[tuple[str, str]] = []
    raw_patterns: Any = settings.get("netclass_patterns") or []
    for index, entry in enumerate(cast(list[Any], raw_patterns) if isinstance(raw_patterns, list) else []):
        item = cast(JsonObject, entry) if isinstance(entry, dict) else {}
        cls, pattern = item.get("netclass"), item.get("pattern")
        if isinstance(cls, str) and isinstance(pattern, str):
            patterns.append((pattern, cls))
        else:
            found.append(
                project_issue(
                    "kicad.project.unread-entry",
                    "a pattern entry without a string 'netclass' and 'pattern' is ignored",
                    where=f"{PATTERNS}/{index}",
                )
            )
    assignments: list[tuple[str, tuple[str, ...]]] = []
    raw_assignments = settings.get("netclass_assignments")
    for net, value in cast(JsonObject, raw_assignments).items() if isinstance(raw_assignments, dict) else ():
        if isinstance(value, str):
            assignments.append((net, (value,)))
        elif isinstance(value, list) and all(isinstance(v, str) for v in cast(list[Any], value)):
            assignments.append((net, tuple(cast(list[str], value))))
        else:
            found.append(
                project_issue(
                    "kicad.project.unread-entry",
                    f"the assignment of net {net!r} is neither a class name nor a list of names; ignored",
                    where=f"/net_settings/netclass_assignments/{_escape(net)}",
                )
            )
    drawing_sheet = _json.get(data, PAGE_LAYOUT_POINTER)
    variables: list[tuple[str, str]] = []
    raw_variables = data.get("text_variables")
    for key, value in cast(JsonObject, raw_variables).items() if isinstance(raw_variables, dict) else ():
        if isinstance(value, str):
            variables.append((key, value))
        else:
            found.append(
                project_issue(
                    "kicad.project.unread-variable",
                    f"text variable {key!r} has no string value; ignored",
                    where=f"/text_variables/{_escape(key)}",
                )
            )
    return ProjectInfo(
        file=file,
        data=data,
        meta_version=meta_version,
        net_settings_version=settings_version,
        status=status,
        major=project_major(meta_version, settings_version),
        classes=tuple(classes),
        patterns=tuple(patterns),
        assignments=tuple(assignments),
        floors=project_floors(data, issues=found),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        priorities=tuple(priorities),
        drawing_sheet=drawing_sheet if isinstance(drawing_sheet, str) and drawing_sheet else None,
        text_variables=tuple(variables),
    )


def _class_id(name: str) -> str:
    return derived_id("cls", "kicad", f"netclass:{name}")


def apply_project(design: Design, info: ProjectInfo, *, issues: list[Issue] | None = None) -> Design:
    """``design`` with the project's classes and each net's class (project.md, "Reading")."""
    found = issues if issues is not None else []
    netclasses = tuple(
        NetClass(
            id=_class_id(c.name),
            provenance=Provenance("kicad", info.file, info.sha256, f"/net_settings/classes/{i}", EVIDENCE),
            name=c.name,
            clearance=c.clearance,
            track_width=c.track_width,
            via_diameter=c.via_diameter,
            via_drill=c.via_drill,
        )
        for i, c in enumerate(info.classes)
    )
    rank = {
        c.name: (info.priorities[i] if i < len(info.priorities) else 2**31 - 1, i)
        for i, c in enumerate(info.classes)
    }
    entries: list[tuple[str, str, str | None, str]] = [
        (f"{PATTERNS}/{i}", cls, pattern, "") for i, (pattern, cls) in enumerate(info.patterns)
    ]
    for net, names in info.assignments:
        entries += [(f"/net_settings/netclass_assignments/{_escape(net)}", n, None, net) for n in names]
    usable: list[tuple[str | None, str, str]] = []
    for where, cls, pattern, assigned in entries:
        if cls not in rank:
            found.append(
                project_issue(
                    "kicad.project.unknown-class",
                    f"class {cls!r} is not in 'classes'; the entry is skipped",
                    where=where,
                )
            )
            continue
        usable.append((pattern, assigned, cls))
    nets: list[Net] = []
    for net in design.circuit.nets:
        candidates: list[str] = []
        for pattern, assigned, cls in usable:
            hit = assigned == net.name if pattern is None else pattern_matches(pattern, net.name)
            if hit and cls not in candidates:
                candidates.append(cls)
        chosen = min(candidates, key=lambda c: rank[c]) if candidates else None
        if len(candidates) > 1:
            found.append(
                project_issue(
                    "kicad.project.multiple-classes",
                    f"net {net.name!r} matches the classes {', '.join(candidates)}; "
                    "KiCad aggregates them, the "
                    f"model keeps {chosen!r}, the one of highest priority",
                    where=f"/net/{net.name}",
                )
            )
        nets.append(dataclasses.replace(net, netclass_id=_class_id(chosen) if chosen is not None else None))
    circuit = dataclasses.replace(design.circuit, netclasses=netclasses, nets=tuple(nets))
    return _apply_sheet(dataclasses.replace(design, circuit=circuit), info)


def _apply_sheet(design: Design, info: ProjectInfo) -> Design:
    """The project's drawing sheet into ``Board.sheet.drawing_sheet`` (when the board has a sheet) and
    its text variables into ``Board.title_block.params`` (change c0012)."""
    board = design.board
    if board is None:
        return design
    sheet = board.sheet
    if sheet is not None:
        sheet = dataclasses.replace(sheet, drawing_sheet=info.drawing_sheet)
    block = board.title_block
    params = dict(info.text_variables)
    if block is not None:
        block = dataclasses.replace(block, params=params)
    elif params:
        block = TitleBlock(params=params)
    return dataclasses.replace(design, board=dataclasses.replace(board, sheet=sheet, title_block=block))


# --- writing --------------------------------------------------------------------------------------

PAGE_LAYOUT_POINTER = "/pcbnew/page_layout_descr_file"
"""The project key naming the board's drawing sheet (change c0012); the schematic key is never touched."""
SHEET_KEY_PATHS: frozenset[str] = frozenset({"/text_variables/*"})
"""The only key paths ``apply_sheet_keys`` may add beyond the template's and ``PATTERN_ENTRY_PATHS``."""


def apply_sheet_keys(
    project_text: str,
    design: Design,
    *,
    schematic: bool = False,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> str:
    """``project_text`` with ``pcbnew.page_layout_descr_file`` and ``text_variables`` set from the design's
    ``Board.sheet.drawing_sheet`` and ``Board.title_block.params`` (``kicad-file-backend``, "Projects
    carry the drawing sheet and text variables"). The text comes back unchanged when the design sets
    neither; existing variables are replaced in place, new ones appended sorted by name, none deleted.

    With ``schematic``, which a build passes when it writes a schematic, the drawing sheet is also set as
    ``schematic.page_layout_descr_file``, the key that gives the schematic its frame
    (``H-K-PRO-WKS-SCH``); otherwise that key is not touched."""
    found = issues if issues is not None else []
    board = design.board
    sheet = board.sheet if board is not None else None
    block = board.title_block if board is not None else None
    drawing_sheet = sheet.drawing_sheet if sheet is not None else None
    params = dict(block.params) if block is not None else {}
    if drawing_sheet is None and not params:
        return project_text
    problems = [
        i
        for i in presentation_issues(sheet, block, "board")
        if i.code in ("model.sheet-path", "model.param-name")
    ]
    if problems:
        raise ConsistencyError("; ".join(f"{i.code}: {i.message}" for i in problems))
    errors: list[Issue] = []
    kept: dict[str, str] = {}
    for name, value in params.items():
        if name in RESERVED_VARIABLES:
            where = f"/text_variables/{_escape(name)}"
            if allow_lossy:
                message = f"text variable {name!r} is reserved by KiCad; left out"
                found.append(project_issue("kicad.project.dropped-variable", message, where=where))
            else:
                message = f"text variable {name!r} is a reserved KiCad variable"
                errors.append(project_issue("kicad.project.reserved-variable", message, where=where))
            continue
        kept[name] = value
    if errors:
        raise LossyWriteError(errors, droppable=True)
    data = read_project_text(project_text)
    if drawing_sheet is not None:
        pcbnew = data.setdefault("pcbnew", {})
        if not isinstance(pcbnew, dict):
            raise FormatError("'pcbnew' is not an object", locator="/pcbnew")
        cast(JsonObject, pcbnew)["page_layout_descr_file"] = drawing_sheet
        if schematic:
            eeschema = data.setdefault("schematic", {})
            if not isinstance(eeschema, dict):
                raise FormatError("'schematic' is not an object", locator="/schematic")
            cast(JsonObject, eeschema)["page_layout_descr_file"] = drawing_sheet
    if kept:
        variables = data.setdefault("text_variables", {})
        if not isinstance(variables, dict):
            raise FormatError("'text_variables' is not an object", locator="/text_variables")
        table = cast(JsonObject, variables)
        for name in [n for n in kept if n in table]:
            table[name] = kept[name]
        for name in sorted(n for n in kept if n not in table):
            table[name] = kept[name]
    return write_project_text(data)


def _classes(data: JsonObject) -> list[Any]:
    settings = data.setdefault("net_settings", {})
    return cast(list[Any], cast(JsonObject, settings).setdefault("classes", []))


def _model_classes(design: Design) -> dict[str, NetClass]:
    return {c.id: c for c in design.circuit.netclasses}


def _net_class_names(design: Design) -> dict[str, str]:
    """Net name → class name (``Default`` for a net without a class); unknown ids raise."""
    classes = _model_classes(design)
    out: dict[str, str] = {}
    for net in design.circuit.nets:
        if net.netclass_id is None:
            out[net.name] = DEFAULT_CLASS
            continue
        cls = classes.get(net.netclass_id)
        if cls is None:
            raise ConsistencyError(
                f"model.unknown-netclass: net {net.name!r} names class id {net.netclass_id!r}, "
                "which the circuit "
                "does not hold; run Design.validate() first"
            )
        out[net.name] = cls.name
    return out


def _exact_entries(design: Design, *, allow_lossy: bool, issues: list[Issue]) -> list[JsonObject]:
    """One exact-name pattern entry per classed net, sorted by net name, after the check of Decision 8."""
    names = _net_class_names(design)
    errors: list[Issue] = []
    entries: list[JsonObject] = []
    for net in sorted(n for n, c in names.items() if c != DEFAULT_CLASS):
        cls = names[net]
        unsafe = sorted(UNSAFE_PATTERN_CHARS & set(net))
        others = sorted(o for o, c in names.items() if o != net and c != cls and pattern_matches(net, o))
        if unsafe or others:
            reason = (
                f"holds the wildcard character(s) {' '.join(unsafe)}"
                if unsafe
                else f"would also match {', '.join(repr(o) for o in others)} of another class"
            )
            errors.append(
                project_issue(
                    "kicad.project.pattern-unsafe",
                    f"net {net!r} of class {cls!r}: its exact-name pattern {reason}",
                    where=f"/net/{net}",
                    hint="rename the net, or re-run with --allow-lossy to leave it in the Default class",
                )
            )
            continue
        entries.append({"netclass": cls, "pattern": net})
    if errors and not allow_lossy:
        raise LossyWriteError(errors, droppable=True)
    for error in errors:
        issues.append(
            project_issue(
                "kicad.project.dropped-pattern",
                f"{error.message}; written without a pattern, so it falls back to Default",
                where=error.where,
            )
        )
    return entries


def _rules_object(data: JsonObject) -> JsonObject:
    """``board.design_settings.rules``, with missing objects appended to their parents."""
    node = data
    pointer = ""
    for part in MINIMUM_POINTER.split("/")[1:]:
        pointer += "/" + part
        child = node.setdefault(part, {})
        if not isinstance(child, dict):
            raise FormatError(f"{pointer} is not an object; the board-setup minimums cannot be written",
                              locator=pointer)  # fmt: skip
        node = cast(JsonObject, child)
    return node


def _write_minimums(
    data: JsonObject, design: Design, *, target: int, update: bool, issues: list[Issue]
) -> None:
    """Decision 5 of c0026: the minimums that ``lower_minimums`` derives from the board-wide rules."""
    current = {**project_minimums(template(target)), **project_minimums(data)}
    minimums = lower_minimums(design.rules, target=target, current=current, issues=issues)
    if not minimums:
        return
    rules = _rules_object(data)
    for kind, key in MINIMUM_KEYS[target].items():
        if key not in minimums:
            continue
        value = minimums[key]
        present, old = key in rules, rules.get(key)
        if isinstance(old, JsonNumber) and _same_nm(old, millimetres(value)):
            continue
        rules[key] = millimetres(value)
        if update:
            rule = governing_rule(design.rules, kind)
            before = _text(old) if present else "absent"
            issues.append(
                project_issue(
                    "kicad.project.minimum-replaced",
                    f"{key}: {before} → {millimetres(value).text} mm, from the board-wide rule "
                    f"{rule.name if rule is not None else '?'!r}",
                    where=f"{MINIMUM_POINTER}/{key}",
                )
            )


def _text(value: Any) -> str:
    return value.text if isinstance(value, JsonNumber) else repr(value)


def _class_clearances(classes: Sequence[Any]) -> dict[str, Nm]:
    out: dict[str, Nm] = {}
    for entry in classes:
        item = cast(JsonObject, entry) if isinstance(entry, dict) else {}
        name, value = item.get("name"), item.get("clearance")
        if isinstance(name, str) and isinstance(value, JsonNumber):
            try:
                out[name] = parse_length(value.text, default_unit="mm")
            except ValueError:
                continue
    return out


def _check_classes(data: JsonObject, design: Design, *, target: int, issues: list[Issue]) -> None:
    class_conflicts(
        design.rules,
        target=target,
        clearances=_class_clearances(_classes(data)),
        model_names={c.name for c in design.circuit.netclasses},
        issues=issues,
    )


def synthesize_project(
    design: Design,
    *,
    target: int = DEFAULT_TARGET,
    board_name: str,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
) -> str:
    """A complete project file for ``design`` from the packaged template of ``target`` (project.md)."""
    found = issues if issues is not None else []
    data = template(target)
    cast(JsonObject, data.setdefault("meta", {}))["filename"] = f"{board_name}.kicad_pro"
    _write_minimums(data, design, target=target, update=False, issues=found)
    classes = _classes(data)
    base = cast(JsonObject, classes[0])
    floors = project_floors(data, issues=found)
    model = sorted(design.circuit.netclasses, key=lambda c: c.name)
    written: list[JsonObject] = []
    for cls in model:
        entry = lower_netclass(cls, base=base, floors=floors, issues=found)
        if cls.name == DEFAULT_CLASS:
            classes[0] = entry
        else:
            written.append(entry)
    classes[1:] = written
    _check_classes(data, design, target=target, issues=found)
    settings = cast(JsonObject, data["net_settings"])
    settings["netclass_patterns"] = _exact_entries(design, allow_lossy=allow_lossy, issues=found)
    return _json.dumps(data)


def _remove(data: JsonObject, path: str) -> None:
    """Remove every key at ``path`` (list items written ``*``)."""
    parts = path.split("/")[1:]

    def walk(node: Any, rest: list[str]) -> None:
        if not rest:
            return
        head, tail = rest[0], rest[1:]
        if head == "*":
            for item in cast(list[Any], node) if isinstance(node, list) else []:
                walk(item, tail)
        elif isinstance(node, dict):
            obj = cast(JsonObject, node)
            if not tail:
                obj.pop(head.replace("~1", "/").replace("~0", "~"), None)
            else:
                walk(obj.get(head), tail)

    walk(data, parts)


def _gate_nine(data: JsonObject, design: Design, pair: tuple[int | None, int | None], *, allow_lossy: bool,
               issues: list[Issue]) -> None:  # fmt: skip
    """Decision 10: 10.0-only keys and the pair (3, 5) in a project written for target 9."""
    paths = sorted(_json.key_paths(data) & TEN_ONLY_PATHS)
    top = [p for p in paths if not any(p != q and p.startswith(q + "/") for q in paths)]
    too_new = [*top, *(["/net_settings/meta/version"] if pair == PROJECT_VERSIONS[10] else [])]
    if not too_new:
        return
    info = source_info(design)
    if info is not None and info.major == 10:
        raise DowngradeRefusedError(FileKind.BOARD, 10, 9)
    errors = [
        project_issue(
            "kicad.project.too-new-key",
            f"{path} is written only by KiCad 10.0; the target is KiCad 9.0",
            where=path,
        )
        for path in too_new
    ]
    if not allow_lossy:
        raise LossyWriteError(errors, droppable=True)
    for path in top:
        _remove(data, path)
    settings = data.get("net_settings")
    if isinstance(settings, dict):
        meta = cast(JsonObject, settings).get("meta")
        if isinstance(meta, dict):
            cast(JsonObject, meta)["version"] = JsonNumber(str(PROJECT_VERSIONS[9][1]))
    issues += [
        project_issue("kicad.project.dropped-too-new", f"{e.message}; removed", where=e.where) for e in errors
    ]


def update_project(
    existing_text: str,
    design: Design,
    *,
    target: int = DEFAULT_TARGET,
    allow_lossy: bool = False,
    issues: list[Issue] | None = None,
    renamed_nets: Collection[str] = (),
) -> str:
    """``existing_text`` with only its managed keys changed (project.md, "Updates").

    ``renamed_nets`` are the old names of the nets that the design renamed (``moved_net()``): the
    exact-name pattern of such a net is Fenolite's own entry for a net that now has another name, so it is
    left out instead of being kept as a user's pattern."""
    if target not in TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {TARGET_MAJORS}")
    found = issues if issues is not None else []
    data = _json.loads(existing_text)
    pair = _versions(data)
    if classify_project(*pair) == VersionStatus.FUTURE:
        raise FutureFormatError(
            f"project versions {pair} are newer than every supported pair", hint=REWRITE_HINT
        )
    if pair not in PROJECT_VERSIONS.values():
        raise UnsupportedFormatError(
            f"project versions {pair} are not a pair Fenolite edits "
            f"({', '.join(map(str, PROJECT_VERSIONS.values()))})",
            hint=REWRITE_HINT,
        )
    if target == 9:
        _gate_nine(data, design, pair, allow_lossy=allow_lossy, issues=found)
    _write_minimums(data, design, target=target, update=True, issues=found)
    classes = _classes(data)
    by_name = {cast(JsonObject, c).get("name"): i for i, c in enumerate(classes) if isinstance(c, dict)}
    default_index = by_name.get(DEFAULT_CLASS, 0)
    base = cast(JsonObject, classes[default_index]) if classes else {}
    floors = project_floors(data, issues=found)
    appended: list[JsonObject] = []
    for cls in sorted(design.circuit.netclasses, key=lambda c: c.name):
        index = by_name.get(cls.name)
        if index is None:
            appended.append(lower_netclass(cls, base=base, floors=floors, issues=found))
            continue
        entry = cast(JsonObject, classes[index])
        lowered = lower_netclass(cls, base=entry, floors=floors, issues=found)
        for key in NETCLASS_KEYS.values():
            old, new = entry.get(key), lowered.get(key)
            same = isinstance(old, JsonNumber) and isinstance(new, JsonNumber) and _same_nm(old, new)
            if not same:
                entry[key] = new
    classes.extend(appended)
    _check_classes(data, design, target=target, issues=found)
    settings = cast(JsonObject, data["net_settings"])
    names = _net_class_names(design)
    existing = settings.get("netclass_patterns")
    kept: list[Any] = []
    for entry in cast(list[Any], existing) if isinstance(existing, list) else []:
        pattern = cast(JsonObject, entry).get("pattern") if isinstance(entry, dict) else None
        exact = isinstance(pattern, str) and not (UNSAFE_PATTERN_CHARS & set(pattern))
        if exact and (pattern in names or pattern in renamed_nets):
            continue
        kept.append(entry)
    _conflicts(kept, settings.get("netclass_assignments"), names, found)
    settings["netclass_patterns"] = [*_exact_entries(design, allow_lossy=allow_lossy, issues=found), *kept]
    return _json.dumps(data)


def _same_nm(a: JsonNumber, b: JsonNumber) -> bool:
    try:
        return parse_length(a.text, default_unit="mm") == parse_length(b.text, default_unit="mm")
    except ValueError:
        return False


def _conflicts(kept: Sequence[Any], assignments: Any, names: Mapping[str, str], issues: list[Issue]) -> None:
    """``kicad.project.pattern-conflict`` for each kept entry that gives a model net another class."""
    entries: list[tuple[str, str, str]] = []
    for i, entry in enumerate(kept):
        item = cast(JsonObject, entry) if isinstance(entry, dict) else {}
        pattern, cls = item.get("pattern"), item.get("netclass")
        if isinstance(pattern, str) and isinstance(cls, str):
            entries.append((pattern, cls, f"{PATTERNS}/{i}"))
    for net, value in cast(JsonObject, assignments).items() if isinstance(assignments, dict) else ():
        for cls in (
            [value] if isinstance(value, str) else cast(list[Any], value) if isinstance(value, list) else []
        ):
            if isinstance(cls, str):
                entries.append((re.escape(net), cls, f"/net_settings/netclass_assignments/{_escape(net)}"))
    for net, model_class in names.items():
        for pattern, cls, where in entries:
            if cls != model_class and pattern_matches(pattern, net):
                issues.append(
                    project_issue(
                        "kicad.project.pattern-conflict",
                        f"net {net!r} is in {model_class} in the model, "
                        f"but the kept entry {pattern!r} also gives it "
                        f"{cls}; KiCad gives a net every matching class",
                        where=where,
                    )
                )


__all__ = [
    "DEFAULT_CLASS",
    "EVIDENCE",
    "ISSUE_CODES",
    "MINIMUM_POINTER",
    "NET_SETTINGS_READ_MAX",
    "PAGE_LAYOUT_POINTER",
    "PATTERN_ENTRY_PATHS",
    "PROJECT_READ_MAX",
    "PROJECT_VERSIONS",
    "SHEET_KEY_PATHS",
    "TEN_ONLY_PATHS",
    "UNSAFE_PATTERN_CHARS",
    "ProjectClass",
    "ProjectInfo",
    "apply_project",
    "apply_sheet_keys",
    "classify_project",
    "pattern_matches",
    "project_floors",
    "project_minimums",
    "project_major",
    "read_project",
    "read_project_text",
    "synthesize_project",
    "template",
    "update_project",
    "write_project_text",
]
