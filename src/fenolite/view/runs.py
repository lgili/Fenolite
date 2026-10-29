# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the viewer's live server may run when the page asks (capability board-viewer, "Allowed run
commands"; change c0245).

The page sends a command name, a document id of the tree and typed options, never a command line or a path.
``request`` turns that body into a :class:`RunRequest` (the command, the file of the document and the JSON
arguments of the command's tool) or a :class:`RunRefused` with the reason. Only the read-only commands of
:data:`ALLOWED` run, only on files of the tree under its root, and only with the options of their row, each
checked by type and against the command's own choices, which ``cmd_view`` passes in as :class:`Choices`
(they live in ``cli`` and ``checks``, which ``view`` does not import). The runner itself is injected
(:class:`Runner`): ``cli/_viewrun.py`` builds the words from the command's parser and runs them in a child
process. Standard library only.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, cast

from fenolite.view.project import Document, ProjectTree

ALLOWED = ("check", "analyze", "ready", "equivalent")
"""The commands a page may run: each is read-only."""
RUN_HEADER = "X-Fenolite-Run"
"""The header every run request carries (see ``server``: the guard)."""
RUN_BYTES = 16 * 1024
"""The largest body of a run request."""
ALTIUM_SUFFIXES = (".prjpcb", ".pcbdoc", ".schdoc")
KICAD_BOARD = ".kicad_pcb"
KICAD_PROJECT = ".kicad_pro"
NEVER = frozenset({"exclude", "reason", "kicad_cli", "requirements", "timeout", "out", "path", "a"})
"""Options a page never sets: writes (``check --exclude``), files and external tools, and the targets the
server derives from the document id."""

Json = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Choices:
    """The choices of the allowed commands' options, passed in by ``cmd_view``."""

    stages: tuple[str, ...] = ()
    """``check --stages`` for KiCad and Fenolite input (``checks.STAGE_ORDER``)."""
    default_stages: tuple[str, ...] = ()
    document_stages: tuple[str, ...] = ()
    """``check --stages`` for Altium input (``checks.documents.ALL_DOCUMENT_STAGES``)."""
    kinds: tuple[str, ...] = ()
    """``analyze --kinds`` (``KINDS`` and ``OPT_IN_KINDS`` of ``cmd_analyze``)."""
    default_kinds: tuple[str, ...] = ()
    levels: tuple[int, ...] = ()
    """``equivalent --level``."""
    frames: tuple[str, ...] = ()
    """``equivalent --frame``."""


@dataclass(frozen=True, slots=True)
class RunRequest:
    """A validated run: the command, the document id and file, and the JSON arguments of its tool (the
    property names of ``fenolite.mcp.tools``; the target is a path relative to the tree's root)."""

    command: str
    doc: str
    path: Path
    arguments: Json = field(default_factory=lambda: cast("Json", {}))


@dataclass(frozen=True, slots=True)
class RunRefused:
    """Why a run request was refused (answered 400)."""

    reason: str


class Handle(Protocol):
    """A started job: ``cancel`` stops it, ``wait`` blocks until it ends and gives its outcome."""

    def cancel(self) -> None: ...

    def wait(self) -> Outcome: ...


@dataclass(frozen=True, slots=True)
class Outcome:
    """How a job ended: ``state`` (``done``, ``failed``, ``cancelled`` or ``timeout``), the exit code, and
    the envelope (exit 0 or 5) or the error object."""

    state: str
    exit: int | None = None
    envelope: Json | None = None
    error: Json | None = None


ProgressSink = Callable[[Json], None]


class Runner(Protocol):
    """What runs the jobs of the page (``cli/_viewrun.py``; tests pass a fake)."""

    def start(self, request: RunRequest, on_progress: ProgressSink) -> Handle: ...


def _list(value: Any, name: str, allowed: tuple[str, ...]) -> list[str] | RunRefused:
    if not isinstance(value, list) or not value:
        return RunRefused(f"{name}: a non-empty list of names")
    items = cast("list[Any]", value)
    out: list[str] = []
    for item in items:
        if not isinstance(item, str) or item not in allowed:
            return RunRefused(f"{name}: {item!r} is not one of {', '.join(allowed)}")
        if item not in out:
            out.append(item)
    return out


def under_root(tree: ProjectTree, doc: Document) -> Path | None:
    """The file of ``doc`` when it is present and lies under the tree's root (symlinks resolved)."""
    if doc.file is None or not doc.present:
        return None
    try:
        resolved = doc.file.resolve()
        resolved.relative_to(tree.root.resolve())
    except (OSError, ValueError):
        return None
    return doc.file


def _relative(tree: ProjectTree, path: Path) -> str:
    return path.resolve().relative_to(tree.root.resolve()).as_posix()


def _project(tree: ProjectTree) -> Path | None:
    if not tree.project_file:
        return None
    path = tree.root / tree.project_file
    try:
        path.resolve().relative_to(tree.root.resolve())
    except (OSError, ValueError):
        return None
    return path if path.is_file() else None


def is_altium(tree: ProjectTree, path: Path) -> bool:
    return tree.source == "altium" or path.suffix.lower() in ALTIUM_SUFFIXES


def _document(tree: ProjectTree, value: Any, name: str = "doc") -> tuple[Document, Path] | RunRefused:
    if not isinstance(value, str) or not value:
        return RunRefused(f"{name}: a document id of the project")
    doc = next((d for d in tree.documents if d.id == value), None)
    if doc is None:
        return RunRefused(f"{name}: the project holds no document {value!r}")
    path = under_root(tree, doc)
    if path is None:
        return RunRefused(f"{name}: {doc.name} is not present in the project folder")
    if not doc.viewable and doc.kind != "project":
        return RunRefused(f"{name}: {doc.name} ({doc.kind}) is not a document that can be checked")
    return doc, path


def request(body: Any, tree: ProjectTree, choices: Choices = Choices()) -> RunRequest | RunRefused:  # noqa: B008, C901, PLR0911, PLR0912 - one table
    """The run that ``body`` asks for (module docstring), or why it is refused."""
    if not isinstance(body, dict):
        return RunRefused("a run request is a JSON object")
    data = cast("Json", body)
    unknown = sorted(set(data) - {"command", "doc", "options"})
    if unknown:
        return RunRefused(f"a run request takes no {unknown[0]!r}")
    command = data.get("command")
    if command not in ALLOWED:
        return RunRefused(f"{command!r} is not a command the page may run (allowed: {', '.join(ALLOWED)})")
    found = _document(tree, data.get("doc"))
    if isinstance(found, RunRefused):
        return found
    doc, path = found
    raw_options = data.get("options", {})
    if not isinstance(raw_options, dict):
        return RunRefused("options: a JSON object")
    options = cast("Json", raw_options)
    allowed_keys = {"check": {"stages"}, "analyze": {"kinds"}, "ready": {"no_kicad"}}.get(
        str(command), {"b", "level", "frame"}
    )
    for key in options:
        if key in NEVER or key not in allowed_keys:
            return RunRefused(f"{command} from the page takes no option {key!r}")
    arguments: Json = {}
    if command == "check":
        target = _project(tree) or path
        stages = choices.document_stages if is_altium(tree, target) else choices.stages
        arguments["path"] = _relative(tree, target)
        if "stages" in options:
            names = _list(options["stages"], "stages", stages)
            if isinstance(names, RunRefused):
                return names
            arguments["stages"] = ",".join(names)
        return RunRequest("check", doc.id, target, arguments)
    if command == "analyze":
        if doc.kind != "pcb":
            return RunRefused(f"analyze reads a board, and {doc.name} is a {doc.kind}")
        arguments["path"] = _relative(tree, path)
        if "kinds" in options:
            names = _list(options["kinds"], "kinds", choices.kinds)
            if isinstance(names, RunRefused):
                return names
            arguments["kinds"] = ",".join(names)
        return RunRequest("analyze", doc.id, path, arguments)
    if command == "ready":
        project = _project(tree)
        target = project if project is not None and project.suffix.lower() == KICAD_PROJECT else path
        if target.suffix.lower() not in (KICAD_PROJECT, KICAD_BOARD):
            return RunRefused("ready reads a KiCad project or board")
        arguments["path"] = _relative(tree, target)
        if "no_kicad" in options:
            if not isinstance(options["no_kicad"], bool):
                return RunRefused("no_kicad: true or false")
            arguments["no_kicad"] = options["no_kicad"]
        return RunRequest("ready", doc.id, target, arguments)
    arguments["a"] = _relative(tree, path)
    if "b" not in options:
        return RunRefused("equivalent needs b: the id of the document to compare with")
    other = _document(tree, options["b"], "b")
    if isinstance(other, RunRefused):
        return other
    if other[0].id == doc.id:
        return RunRefused("b: compare with another document")
    arguments["b"] = _relative(tree, other[1])
    if "level" in options:
        level = options["level"]
        if isinstance(level, bool) or not isinstance(level, int) or level not in choices.levels:
            return RunRefused(f"level: one of {', '.join(map(str, choices.levels))}")
        arguments["level"] = level
    if "frame" in options:
        if options["frame"] not in choices.frames:
            return RunRefused(f"frame: one of {', '.join(choices.frames)}")
        arguments["frame"] = options["frame"]
    return RunRequest("equivalent", doc.id, path, arguments)


def offered(choices: Choices) -> dict[str, Json]:
    """The commands and options the page may offer (``GET /runs``)."""
    return {
        "check": {
            "options": {
                "stages": {
                    "type": "names",
                    "choices": list(choices.stages),
                    "default": list(choices.default_stages),
                    "altium": list(choices.document_stages),
                }
            }
        },
        "analyze": {
            "options": {
                "kinds": {
                    "type": "names",
                    "choices": list(choices.kinds),
                    "default": list(choices.default_kinds),
                }
            }
        },
        "ready": {"options": {"no_kicad": {"type": "boolean", "default": False}}},
        "equivalent": {
            "options": {
                "b": {"type": "document"},
                "level": {"type": "integer", "choices": list(choices.levels)},
                "frame": {"type": "choice", "choices": list(choices.frames)},
            }
        },
    }


def describe(mapping: Mapping[str, int]) -> dict[str, int]:
    """The counts of runs by final state, without the empty ones (``result.serve.runs``)."""
    return {state: n for state, n in sorted(mapping.items()) if n}


__all__ = [
    "ALLOWED",
    "RUN_BYTES",
    "RUN_HEADER",
    "Choices",
    "Handle",
    "Outcome",
    "Runner",
    "RunRefused",
    "RunRequest",
    "describe",
    "is_altium",
    "offered",
    "request",
    "under_root",
]
