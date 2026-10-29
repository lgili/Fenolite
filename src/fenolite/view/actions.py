# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The writing actions a page served with ``--allow-actions`` may plan (capability board-viewer, "Allowed
actions"; change c0271).

The server never takes words from the page. An action is a name of :data:`ACTIONS`, a document id of the tree
and typed options; :func:`plan` checks each option against its type (booleans, lengths with a unit, angles,
references of the board's parts, the index of a DRC finding of the session, a reason of one line, an output
path under the project root) and fills the action's fixed template, giving the words of the command without
its run flags (``--dry-run``, ``--confirm --plan``), which the server adds. ``--no-backup``, ``--kicad-cli``,
``--out`` of the board and every global flag are never set. Only KiCad boards are written: an Altium document
shows every action as unavailable. Standard library only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, cast

from fenolite.view.project import Document, ProjectTree
from fenolite.view.runs import KICAD_BOARD, KICAD_PROJECT, is_altium, under_root

ACTION_HEADER = "X-Fenolite-Action"
"""The header every action request carries."""
TOKEN_HEADER = "X-Fenolite-Token"
"""The header that carries the session token, which ``GET /actions`` gives only to a guarded request."""
ACTION_BYTES = 16 * 1024
LENGTH = re.compile(r"^-?\d{1,6}(\.\d{1,6})?(mm|mil|um)$")
ANGLE = re.compile(r"^-?\d{1,4}(\.\d{1,6})?$")
REF = re.compile(r"^[A-Za-z0-9_.+#\-/\[\]]{1,64}$")
ROLE_NAME = re.compile(r"^[^\s,=:\\]{1,128}$")
"""A net or group name the Confirm roles action passes on: no space, comma, ``=``, ``:`` or backslash."""
NO_ROLES = "the board has no role data in this session: run roles first"
REASON_CHARS = 300
ALTIUM = "Altium documents are not written from the viewer"
NOT_A_BOARD = "the actions write a KiCad board: open the board of the project"
EXPORT_KINDS = ("gerbers", "drill", "pos", "pdf")
SIDES = ("top", "bottom")

Json = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Option:
    """One typed option of an action: its kind and default (``None``: the command's own)."""

    kind: str
    default: Any = None
    required: bool = False
    choices: tuple[str, ...] = ()
    label: str = ""


@dataclass(frozen=True, slots=True)
class Action:
    """One action: its command, its title for the page and its options."""

    command: str
    title: str
    options: Mapping[str, Option] = field(default_factory=lambda: cast("Mapping[str, Option]", {}))
    note: str = ""


ACTIONS: Mapping[str, Action] = {
    "fill": Action("fill", "Fill zones", note="kicad-cli 10 refills every zone on a copy"),
    "tidy": Action(
        "tidy",
        "Tidy copper",
        {
            "prune": Option("boolean", False, label="remove dangling tracks and vias"),
            "straighten": Option("boolean", False, label="straighten runs"),
            "chamfer": Option("boolean", False, label="chamfer right angles"),
            "zones": Option("boolean", False, label="also cut zone corners (with chamfer)"),
            "gate_drc": Option("boolean", True, label="keep only edits KiCad's DRC accepts"),
        },
    ),
    "silk": Action(
        "silk",
        "Silkscreen",
        {
            "designators": Option("boolean", False, label="place the designators"),
            "keep": Option("boolean", False, label="move only designators that meet an obstacle"),
            "clip": Option("boolean", False, label="cut silkscreen at mask openings"),
        },
    ),
    "testpoints": Action(
        "testpoints",
        "Place test points",
        {
            "side": Option("choice", None, choices=("top", "bottom", "both"), label="probe side"),
            "grid": Option("length", None, label="grid of probe sites"),
            "size": Option("length", None, label="probe pad diameter"),
        },
    ),
    "waive": Action(
        "check",
        "Waive a DRC finding",
        {
            "finding": Option("finding", required=True, label="the DRC finding"),
            "reason": Option("reason", required=True, label="why it is accepted"),
        },
        note="stored as a KiCad DRC exclusion in the project file",
    ),
    "move": Action(
        "place",
        "Move or rotate a part",
        {
            "ref": Option("ref", required=True, label="part"),
            "x": Option("length", required=True, label="X from the outline's left"),
            "y": Option("length", required=True, label="Y from the outline's top"),
            "rot": Option("angle", None, label="rotation, degrees (kept when empty)"),
            "side": Option("choice", None, choices=SIDES, label="side"),
        },
    ),
    "shift": Action(
        "place",
        "Move parts with their copper",
        {
            "refs": Option("refs", required=True, label="parts"),
            "dx": Option("length", required=True, label="shift X"),
            "dy": Option("length", required=True, label="shift Y"),
        },
    ),
    "turn": Action(
        "place",
        "Turn parts with their copper",
        {
            "refs": Option("refs", required=True, label="parts"),
            "about_x": Option("length", required=True, label="centre X"),
            "about_y": Option("length", required=True, label="centre Y"),
            "angle": Option("angle", required=True, label="angle, degrees"),
        },
    ),
    "roles": Action(
        "roles",
        "Confirm roles",
        {
            "nets": Option("nets", label="inferred roles to confirm (nets)"),
            "groups": Option("groups", label="inferred groups to confirm"),
        },
        note="stored in the role document of the board; a script's declared roles stay the script's",
    ),
    "export": Action(
        "export",
        "Export fabrication files",
        {
            "kinds": Option("kinds", ["gerbers", "drill"], choices=EXPORT_KINDS, label="files"),
            "out": Option("folder", "fab", label="folder under the project"),
        },
    ),
    "bom": Action(
        "bom",
        "Bill of materials",
        {
            "out": Option("csv", "fab/bom.csv", label="CSV file under the project"),
            "source": Option("choice", None, choices=("kicad", "model"), label="parts from"),
        },
    ),
}
"""The actions of the page; ``waive`` is ``check --exclude``, ``roles`` (change c0273) is ``roles --accept``
and ``--accept-group`` on the board."""


@dataclass(frozen=True, slots=True)
class ActionRequest:
    """A validated action: its name, its document, its command and its words without the run flags (the
    positional path last, after ``--``)."""

    action: str
    doc: str
    command: str
    words: tuple[str, ...]
    target: Path


@dataclass(frozen=True, slots=True)
class ActionRefused:
    """Why an action request was refused (answered 400)."""

    reason: str


@dataclass(frozen=True, slots=True)
class Context:
    """What the server knows of the document: its board's part references, its session's check findings (as
    the page lists them, ``check_overlay`` order) and the nets and groups its role data shows as inferred
    (change c0273; ``None`` without role data)."""

    refs: frozenset[str] = frozenset()
    findings: tuple[Json, ...] = ()
    roles: frozenset[str] | None = None
    groups: frozenset[str] | None = None


def availability(tree: ProjectTree, doc: Document | None) -> str | None:
    """Why the actions are unavailable for ``doc``, or ``None`` when it is a KiCad board of the tree."""
    if doc is None or doc.file is None:
        return NOT_A_BOARD
    if is_altium(tree, doc.file):
        return ALTIUM
    if doc.kind != "pcb" or doc.file.suffix.lower() != KICAD_BOARD or under_root(tree, doc) is None:
        return NOT_A_BOARD
    return None


def target(tree: ProjectTree, doc: Document) -> Path:
    """The file an action names: the KiCad project file when there is one, else the board."""
    if tree.project_file and tree.project_file.lower().endswith(KICAD_PROJECT):
        project = tree.root / tree.project_file
        if project.is_file():
            return project
    assert doc.file is not None
    return doc.file


def offered(tree: ProjectTree, doc: Document | None) -> dict[str, Json]:
    """The actions and their options for the page's forms (``GET /actions``)."""
    why = availability(tree, doc)
    out: dict[str, Json] = {}
    for name, action in ACTIONS.items():
        options = {
            key: {
                "type": o.kind,
                "default": o.default,
                "required": o.required,
                "choices": list(o.choices),
                "label": o.label,
            }  # fmt: skip
            for key, o in action.options.items()
        }
        row: Json = {
            "title": action.title,
            "command": action.command,
            "options": options,
            "available": why is None,
        }
        if action.note:
            row["note"] = action.note
        if why is not None:
            row["why"] = why
        out[name] = row
    return out


def confined(root: Path, value: Any, name: str, *, suffix: str = "") -> str | ActionRefused:
    """``value`` as a relative output path under ``root`` (symlinks resolved), or why not."""
    if not isinstance(value, str) or not 0 < len(value) <= 200:
        return ActionRefused(f"{name}: a relative path of 1 to 200 characters")
    if any(c in value for c in "\\:\0") or value.startswith(("-", "/", "~")) or not value.isprintable():
        return ActionRefused(f"{name}: {value!r} is not a relative path under the project")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part == ".." for part in path.parts):
        return ActionRefused(f"{name}: {value!r} leaves the project folder")
    if suffix and path.suffix.lower() != suffix:
        return ActionRefused(f"{name}: a file name ending in {suffix}")
    try:
        (root / path).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return ActionRefused(f"{name}: {value!r} resolves outside the project folder")
    return path.as_posix()


def _typed(key: str, option: Option, value: Any, context: Context, root: Path) -> Any:  # noqa: C901, PLR0911 - one table
    """The checked value of one option, or an :class:`ActionRefused`."""
    kind = option.kind
    if kind == "boolean":
        return value if isinstance(value, bool) else ActionRefused(f"{key}: true or false")
    if kind == "length":
        ok = isinstance(value, str) and LENGTH.fullmatch(value)
        return value if ok else ActionRefused(f"{key}: a length with its unit, as 1.5mm, 20mil or 300um")
    if kind == "angle":
        ok = isinstance(value, str | int) and not isinstance(value, bool) and ANGLE.fullmatch(str(value))
        return str(value) if ok else ActionRefused(f"{key}: an angle in degrees, as 90 or -45.5")
    if kind == "choice":
        return (
            value if value in option.choices else ActionRefused(f"{key}: one of {', '.join(option.choices)}")
        )
    if kind == "ref":
        if not isinstance(value, str) or not REF.fullmatch(value) or value not in context.refs:
            return ActionRefused(f"{key}: {value!r} is not a part of this board")
        return value
    if kind == "refs":
        if not isinstance(value, list) or not value or len(cast("list[Any]", value)) > 500:
            return ActionRefused(f"{key}: a list of part references")
        refs = [_typed(key, Option("ref"), item, context, root) for item in cast("list[Any]", value)]
        bad = next((r for r in refs if isinstance(r, ActionRefused)), None)
        return bad or ",".join(dict.fromkeys(cast("list[str]", refs)))
    if kind == "kinds":
        if not isinstance(value, list) or not value:
            return ActionRefused(f"{key}: a non-empty list of {', '.join(option.choices)}")
        items = cast("list[Any]", value)
        if any(item not in option.choices for item in items):
            return ActionRefused(f"{key}: each one of {', '.join(option.choices)}")
        return [k for k in option.choices if k in items]
    if kind == "folder":
        return confined(root, value, key)
    if kind == "csv":
        return confined(root, value, key, suffix=".csv")
    if kind == "reason":
        if (
            not isinstance(value, str)
            or not value.strip()
            or len(value) > REASON_CHARS
            or not value.isprintable()
        ):
            return ActionRefused(f"{key}: one line of 1 to {REASON_CHARS} printable characters")
        return value.strip()
    if kind == "finding":
        return _finding(key, value, context)
    if kind in ("nets", "groups"):
        return _role_names(key, value, context.roles if kind == "nets" else context.groups)
    raise AssertionError(kind)


def _role_names(key: str, value: Any, known: frozenset[str] | None) -> str | ActionRefused:
    """``value`` as the comma-joined names of inferred roles or groups of the session's role data."""
    if known is None:
        return ActionRefused(NO_ROLES)
    if not isinstance(value, list) or len(cast("list[Any]", value)) > 500:
        return ActionRefused(f"{key}: a list of names")
    names: list[str] = []
    for item in cast("list[Any]", value):
        if not isinstance(item, str) or not ROLE_NAME.fullmatch(item) or item not in known:
            return ActionRefused(f"{key}: {item!r} is not an inferred {key[:-1]} of this board's roles")
        names.append(item)
    return ",".join(dict.fromkeys(names))


def _finding(key: str, value: Any, context: Context) -> str | ActionRefused:
    """``CODE:ITEM_A[:ITEM_B]`` of the session's DRC finding at index ``value``."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < len(context.findings):
        return ActionRefused(f"{key}: the index of a finding of this document's last check")
    found = context.findings[value]
    code = str(found.get("code") or "")
    if found.get("stage") != "drc.kicad" or not code.startswith("kicad.drc."):
        return ActionRefused(f"{key}: only a finding of KiCad's DRC (drc.kicad) can be waived")
    items = [part.strip() for part in str(found.get("where") or "").split(", ") if part.strip()]
    if not 1 <= len(items) <= 2 or any(":" in item or not item.isprintable() for item in items):
        return ActionRefused(f"{key}: this finding does not name one or two items that KiCad can exclude")
    return ":".join((code, *items))


def plan(body: Any, tree: ProjectTree, context: Context = Context()) -> ActionRequest | ActionRefused:  # noqa: B008, C901, PLR0911, PLR0912 - one table
    """The action ``body`` asks for, as a fixed template filled with checked options, or why it is refused."""
    if not isinstance(body, dict):
        return ActionRefused("an action request is a JSON object")
    data = cast("Json", body)
    unknown = sorted(set(data) - {"action", "doc", "options"})
    if unknown:
        return ActionRefused(f"an action request takes no {unknown[0]!r}")
    name = data.get("action")
    action = ACTIONS.get(name) if isinstance(name, str) else None
    if action is None or not isinstance(name, str):
        return ActionRefused(f"{name!r} is not an action of the page (actions: {', '.join(ACTIONS)})")
    doc = tree.document(data["doc"]) if isinstance(data.get("doc"), str) else None
    if doc is None or doc.id != data.get("doc"):
        return ActionRefused("doc: a document id of the project")
    why = availability(tree, doc)
    if why is not None:
        return ActionRefused(why)
    raw = data.get("options", {})
    if not isinstance(raw, dict):
        return ActionRefused("options: a JSON object")
    given = cast("Json", raw)
    for key in given:
        if key == "no_backup":
            return ActionRefused("--no-backup is never set from the page: every write keeps a backup")
        if key not in action.options:
            return ActionRefused(f"{name} takes no option {key!r}")
    values: Json = {}
    for key, option in action.options.items():
        if key not in given or given[key] is None:
            if option.required:
                return ActionRefused(f"{name} needs {key} ({option.label})")
            if option.default is None:
                continue
            value: Any = option.default
        else:
            value = given[key]
        checked = _typed(key, option, value, context, tree.root)
        if isinstance(checked, ActionRefused):
            return checked
        values[key] = checked
    flags = _flags(name, values)
    if isinstance(flags, ActionRefused):
        return flags
    path = doc.file if name == "roles" and doc.file is not None else target(tree, doc)
    rel = path.resolve().relative_to(tree.root.resolve()).as_posix()
    return ActionRequest(name, doc.id, action.command, (action.command, *flags, "--", rel), path)


def _flags(name: str, v: Json) -> list[str] | ActionRefused:  # noqa: PLR0911 - one template per action
    """The options of the template of action ``name`` for the checked values ``v``."""
    if name == "fill":
        return []
    if name == "tidy":
        if not (v["prune"] or v["straighten"] or v["chamfer"]):
            return ActionRefused("tidy: choose prune, straighten or chamfer")
        if v["zones"] and not v["chamfer"]:
            return ActionRefused("tidy: zones goes with chamfer")
        on = [f"--{k}" for k in ("prune", "straighten", "chamfer", "zones") if v[k]]
        return [*on, *(["--gate=drc"] if v["gate_drc"] else [])]
    if name == "silk":
        if not (v["designators"] or v["clip"]):
            return ActionRefused("silk: choose designators or clip")
        if v["keep"] and not v["designators"]:
            return ActionRefused("silk: keep goes with designators")
        return [f"--{k}" for k in ("designators", "keep", "clip") if v[k]]
    if name == "testpoints":
        for key in ("grid", "size"):
            if key in v and str(v[key]).startswith("-"):
                return ActionRefused(f"testpoints: {key} is a length above 0")
        return ["--place", *(f"--{k}={v[k]}" for k in ("side", "grid", "size") if k in v)]
    if name == "waive":
        return [f"--exclude={v['finding']}", f"--reason={v['reason']}"]
    if name == "move":
        if "side" in v and "rot" not in v:
            return ActionRefused("move: a side goes with a rotation")
        spec = ",".join([f"{v['ref']}={v['x']}", v["y"], *(v[k] for k in ("rot", "side") if k in v)])
        return [f"--move={spec}"]
    if name == "shift":
        return [f"--shift={v['refs']}", f"--by={v['dx']},{v['dy']}"]
    if name == "turn":
        return [f"--turn={v['refs']}", f"--about={v['about_x']},{v['about_y']}", f"--angle={v['angle']}"]
    if name == "roles":
        if not v.get("nets") and not v.get("groups"):
            return ActionRefused("roles: choose the nets or groups to confirm")
        return [*([f"--accept={v['nets']}"] if v.get("nets") else []),
                *([f"--accept-group={v['groups']}"] if v.get("groups") else [])]  # fmt: skip
    if name == "export":
        return [f"--out={v['out']}", *(f"--{kind}" for kind in v["kinds"])]
    if name == "bom":
        return [f"--out={v['out']}", *([f"--source={v['source']}"] if "source" in v else [])]
    raise AssertionError(name)


def undo_words(receipt: Path, root: Path) -> tuple[str, ...]:
    """The words of ``restore`` on a receipt file the server wrote, in the project folder."""
    return ("restore", f"--in={root}", "--", str(receipt))


def with_flags(words: tuple[str, ...], *flags: str) -> list[str]:
    """``words`` with run flags inserted before the ``--`` that precedes the positional path."""
    at = words.index("--") if "--" in words else len(words)
    return [*words[:at], *flags, *words[at:]]


__all__ = [
    "ACTIONS",
    "ACTION_BYTES",
    "ACTION_HEADER",
    "ALTIUM",
    "TOKEN_HEADER",
    "Action",
    "ActionRefused",
    "ActionRequest",
    "Context",
    "availability",
    "confined",
    "offered",
    "plan",
    "target",
    "undo_words",
    "with_flags",
]
