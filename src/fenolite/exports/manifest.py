# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite-artifacts.json``: which file came from which board, by which tool, with its hashes and its
state (capability manufacturing-exports, "Artefact manifest", "Artefact states" and "Manifest merging";
schema ``schemas/fenolite.artifacts.v0.json``; user guide ``docs/exports.md``).

One format serves two writers. A producing command (``export``, ``render``, ``bom``, ``pnp``) merges its
files into the manifest of its output folder, each ``generated``. ``fenolite manifest`` writes the project
manifest: the design files and the artefacts of the folders it is given, with the states that
``fenolite.exports.states`` assigns from a check.

KiCad stamps the creation date into Gerber and drill files, so two exports of one board are not
byte-equal. ``content_sha256`` is the hash of a file without those lines: equal for two exports of an
unchanged board. The files themselves are never edited.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any, Literal, cast, get_args

from fenolite import __version__
from fenolite.core.errors import FormatError
from fenolite.core.evidence import Level
from fenolite.exports import EVIDENCE
from fenolite.exports.plan import VOLATILE_PREFIXES, Artifact

SCHEMA = "fenolite.artifacts.v0"
FILE_NAME = "fenolite-artifacts.json"
_SHA = {"pattern": "^[0-9a-f]{64}$"}
_ADDED: dict[str, Any] = {"optional": True}
"""A field added after v0 was published: a manifest written before it still validates."""

State = Literal["generated", "checked", "roundtrip-ok", "oracle-verified", "native-verified"]
STATES: tuple[State, ...] = get_args(State)
"""The states of an entry, in rising order (``docs/exports.md``, "States")."""

DESIGN_SUFFIXES: Mapping[str, str] = {
    ".kicad_pcb": "kicad_pcb",
    ".kicad_sch": "kicad_sch",
    ".kicad_pro": "kicad_pro",
    ".kicad_dru": "kicad_dru",
    ".kicad_mod": "kicad_mod",
    ".kicad_sym": "kicad_sym",
    ".kicad_wks": "kicad_wks",
}
LIB_TABLES = ("fp-lib-table", "sym-lib-table")
LIB_TABLE_KIND = "lib-table"
OTHER_KIND = "file"
"""The kind of a file of a project that is none of KiCad's design files (a 3D model in a library)."""
DESIGN_KINDS = frozenset({*DESIGN_SUFFIXES.values(), LIB_TABLE_KIND, OTHER_KIND})


@dataclass(frozen=True, slots=True)
class BoardRef:
    """A design file the artefacts were made from: the board, or the root schematic."""

    path: str
    sha256: str = dataclasses.field(metadata=_SHA)
    format_version: int | None


@dataclass(frozen=True, slots=True)
class ToolRef:
    """The tool of the run that wrote the manifest."""

    name: str
    version: str


@dataclass(frozen=True, slots=True)
class ArtifactEntry:
    """One file: its path below the manifest's folder, its kind, the layer of a Gerber, its size, the hash
    of its bytes, the hash without date-bearing lines, the evidence level of the entry, and its state.

    ``held`` says why the entry is not one state higher (``<state>: <what is missing>``), and is ``""``
    when no higher state applies to its kind."""

    path: str
    kind: str
    layer: str | None
    bytes: int = dataclasses.field(metadata={"minimum": 0})
    sha256: str = dataclasses.field(metadata=_SHA)
    content_sha256: str = dataclasses.field(metadata=_SHA)
    evidence: str
    state: State = dataclasses.field(default="generated", metadata=_ADDED)
    stale: bool = dataclasses.field(default=False, metadata=_ADDED)
    from_: dict[str, str] = dataclasses.field(default_factory=lambda: {}, metadata={**_ADDED, "name": "from"})
    tool: str | None = dataclasses.field(default=None, metadata=_ADDED)
    held: str = dataclasses.field(default="", metadata=_ADDED)


@dataclass(frozen=True, slots=True)
class ProjectRef:
    """The board and the root schematic of the project, each ``None`` when the project has none."""

    board: BoardRef | None
    schematic: BoardRef | None


@dataclass(frozen=True, slots=True)
class StageRef:
    """One stage of the check behind the states: its status, evidence level and oracle."""

    name: str
    status: str
    level: str
    oracle: str | None


@dataclass(frozen=True, slots=True)
class CheckRef:
    """The check that gave the states: the stages that ran, and the version of the tool they ran."""

    stages: list[StageRef]
    tool_version: str | None


@dataclass(frozen=True, slots=True)
class Manifest:
    """The artefact manifest of a folder, or of a project (``fenolite manifest``)."""

    schema: str
    fenolite: str
    generated: str
    board: BoardRef
    tool: ToolRef
    artifacts: list[ArtifactEntry]
    project: ProjectRef | None = dataclasses.field(default=None, metadata=_ADDED)
    check: CheckRef | None = dataclasses.field(default=None, metadata=_ADDED)
    states: dict[str, int] = dataclasses.field(default_factory=lambda: {}, metadata=_ADDED)


def content_sha256(data: bytes, kind: str) -> str:
    """The SHA-256 of ``data`` without the lines that carry the creation date for ``kind``."""
    prefixes = VOLATILE_PREFIXES.get(kind, ())
    if not prefixes:
        return hashlib.sha256(data).hexdigest()
    kept = [line for line in data.splitlines(keepends=True) if not line.lstrip(b" \t").startswith(prefixes)]
    return hashlib.sha256(b"".join(kept)).hexdigest()


def design_kind(path: str) -> str:
    """The kind of a design file, from its name: ``kicad_pcb``, ``kicad_sch``, ``kicad_pro``,
    ``kicad_dru``, ``kicad_mod``, ``kicad_sym``, ``kicad_wks``, ``lib-table``, or ``file`` for any other
    file of a project."""
    name = PurePosixPath(path.replace("\\", "/")).name
    if name in LIB_TABLES:
        return LIB_TABLE_KIND
    return DESIGN_SUFFIXES.get(PurePosixPath(name).suffix, OTHER_KIND)


def file_entry(
    path: str,
    kind: str,
    data: bytes,
    *,
    layer: str | None = None,
    evidence: str = Level.UNVERIFIED.value,
    from_: Mapping[str, str] | None = None,
    tool: str | None = None,
) -> ArtifactEntry:
    """The entry of the file ``data`` at ``path``, ``generated``. ``from_`` names the hash of each source
    the file was made from (``board``, ``schematic``); ``tool`` is what wrote it."""
    return ArtifactEntry(
        path=path,
        kind=kind,
        layer=layer,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        content_sha256=content_sha256(data, kind),
        evidence=evidence,
        from_=dict(sorted((from_ or {}).items())),
        tool=tool,
    )


def entry(
    artifact: Artifact,
    *,
    from_: Mapping[str, str] | None = None,
    tool: str | None = None,
    evidence: str | None = None,
) -> ArtifactEntry:
    """The entry of a file that ``kicad-cli`` exported, at the level of ``exports.EVIDENCE`` unless the
    run gives another (an export with a preset)."""
    return file_entry(
        artifact.path,
        artifact.kind,
        artifact.data,
        layer=artifact.layer,
        evidence=EVIDENCE.level.value if evidence is None else evidence,
        from_=from_,
        tool=tool,
    )


def count_states(entries: Iterable[ArtifactEntry]) -> dict[str, int]:
    """The number of entries per state, with every state as a key."""
    counts: dict[str, int] = dict.fromkeys(STATES, 0)
    for item in entries:
        counts[item.state] += 1
    return counts


def to_data(manifest: Manifest) -> dict[str, Any]:
    """The manifest as JSON data: ``from_`` is written as ``from``."""
    data = dataclasses.asdict(manifest)
    for item in data["artifacts"]:
        item["from"] = item.pop("from_")
    return data


def merge(
    existing: Manifest | None,
    entries: Sequence[ArtifactEntry],
    *,
    board: BoardRef,
    tool: ToolRef,
    timestamp: datetime,
) -> Manifest:
    """The manifest of a folder after a command wrote ``entries`` into it: the entries of ``existing``
    with ``entries`` replacing equal paths, sorted by path. The entries that are kept are unchanged;
    ``board``, ``tool`` and the date are those of this run, which checked nothing."""
    by_path = {item.path: item for item in (existing.artifacts if existing is not None else ())}
    by_path.update({item.path: item for item in entries})
    artifacts = [by_path[path] for path in sorted(by_path)]
    return Manifest(
        schema=SCHEMA,
        fenolite=__version__,
        generated=timestamp.isoformat(),
        board=board,
        tool=tool,
        artifacts=artifacts,
        project=ProjectRef(board=board, schematic=None),
        check=None,
        states=count_states(artifacts),
    )


def build(
    *, board: BoardRef, tool_version: str, artifacts: Sequence[Artifact], timestamp: datetime
) -> dict[str, Any]:
    """The manifest of one export as JSON data, its artefacts sorted by path, each ``generated``."""
    tool = ToolRef("kicad-cli", tool_version)
    made = {"board": board.sha256}
    entries = [entry(a, from_=made, tool=f"{tool.name} {tool.version}") for a in artifacts]
    return to_data(merge(None, entries, board=board, tool=tool, timestamp=timestamp))


def dumps(manifest: dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, two-space indent, a final newline."""
    return json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# --- reading --------------------------------------------------------------------------------------


def relative_posix(path: str) -> bool:
    """True for a relative path written with ``/`` that never leaves its folder."""
    parts = PurePosixPath(path).parts
    return (
        bool(parts)
        and not path.startswith("/")
        and ".." not in parts
        and "\\" not in path
        and ":" not in parts[0]
    )


class _Reader:
    """Typed access to the JSON of a manifest; any other shape is a ``FormatError``."""

    def __init__(self, file: str) -> None:
        self.file = file

    def fail(self, message: str, locator: str) -> FormatError:
        return FormatError(message, file=self.file, locator=locator)

    def obj(self, value: object, at: str) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise self.fail("an object is expected", at)
        return cast(dict[str, Any], value)

    def text(self, holder: Mapping[str, Any], key: str, at: str) -> str:
        value = holder.get(key)
        if not isinstance(value, str):
            raise self.fail("a string is expected", f"{at}/{key}")
        return value

    def sha(self, holder: Mapping[str, Any], key: str, at: str) -> str:
        value = self.text(holder, key, at)
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise self.fail("a SHA-256 in lowercase hex is expected", f"{at}/{key}")
        return value

    def optional_text(self, holder: Mapping[str, Any], key: str, at: str) -> str | None:
        return None if holder.get(key) is None else self.text(holder, key, at)

    def ref(self, value: object, at: str) -> BoardRef:
        holder = self.obj(value, at)
        number = holder.get("format_version")
        if number is not None and (not isinstance(number, int) or isinstance(number, bool)):
            raise self.fail("an integer or null is expected", f"{at}/format_version")
        return BoardRef(self.text(holder, "path", at), self.sha(holder, "sha256", at), number)

    def entry(self, value: object, at: str) -> ArtifactEntry:
        holder = self.obj(value, at)
        size = holder.get("bytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise self.fail("a size in bytes is expected", f"{at}/bytes")
        state = holder.get("state", STATES[0])
        if state not in STATES:
            raise self.fail(f"a state of {', '.join(STATES)} is expected", f"{at}/state")
        stale = holder.get("stale", False)
        if not isinstance(stale, bool):
            raise self.fail("true or false is expected", f"{at}/stale")
        made = self.obj(holder.get("from", {}), f"{at}/from")
        path = self.text(holder, "path", at)
        if not relative_posix(path):
            raise self.fail("a relative path with '/' is expected", f"{at}/path")
        return ArtifactEntry(
            path=path,
            kind=self.text(holder, "kind", at),
            layer=self.optional_text(holder, "layer", at),
            bytes=size,
            sha256=self.sha(holder, "sha256", at),
            content_sha256=self.sha(holder, "content_sha256", at),
            evidence=self.text(holder, "evidence", at),
            state=state,
            stale=stale,
            from_={str(k): self.sha(made, str(k), f"{at}/from") for k in sorted(made)},
            tool=self.optional_text(holder, "tool", at),
            held=self.text(holder, "held", at) if "held" in holder else "",
        )

    def check(self, value: object) -> CheckRef | None:
        if value is None:
            return None
        holder = self.obj(value, "/check")
        stages = holder.get("stages")
        if not isinstance(stages, list):
            raise self.fail("a list is expected", "/check/stages")
        found: list[StageRef] = []
        for index, item in enumerate(cast(list[object], stages)):
            at = f"/check/stages/{index}"
            stage = self.obj(item, at)
            found.append(
                StageRef(
                    self.text(stage, "name", at),
                    self.text(stage, "status", at),
                    self.text(stage, "level", at),
                    self.optional_text(stage, "oracle", at),
                )
            )
        return CheckRef(found, self.optional_text(holder, "tool_version", "/check"))

    def manifest(self, text: str) -> Manifest:
        try:
            loaded: object = json.loads(text)
        except ValueError as exc:
            raise self.fail(f"not JSON: {exc}", "") from None
        root = self.obj(loaded, "/")
        if root.get("schema") != SCHEMA:
            raise self.fail(f"the schema is not {SCHEMA}", "/schema")
        items = root.get("artifacts")
        if not isinstance(items, list):
            raise self.fail("a list is expected", "/artifacts")
        entries = [self.entry(item, f"/artifacts/{i}") for i, item in enumerate(cast(list[object], items))]
        tool = self.obj(root.get("tool"), "/tool")
        project = root.get("project")
        refs: ProjectRef | None = None
        if project is not None:
            holder = self.obj(project, "/project")
            board, schematic = holder.get("board"), holder.get("schematic")
            refs = ProjectRef(
                None if board is None else self.ref(board, "/project/board"),
                None if schematic is None else self.ref(schematic, "/project/schematic"),
            )
        return Manifest(
            schema=SCHEMA,
            fenolite=self.text(root, "fenolite", ""),
            generated=self.text(root, "generated", ""),
            board=self.ref(root.get("board"), "/board"),
            tool=ToolRef(self.text(tool, "name", "/tool"), self.text(tool, "version", "/tool")),
            artifacts=sorted(entries, key=lambda item: item.path),
            project=refs,
            check=self.check(root.get("check")),
            states=count_states(entries),
        )


def load(text: str, *, file: str = FILE_NAME) -> Manifest:
    """The manifest in ``text``. An entry written before the states existed is ``generated``, not stale,
    with no source and no tool. A text that is not JSON, that has another schema id or that does not have
    the manifest's shape raises ``FormatError``."""
    return _Reader(file).manifest(text)


__all__ = [
    "DESIGN_KINDS",
    "FILE_NAME",
    "SCHEMA",
    "STATES",
    "ArtifactEntry",
    "BoardRef",
    "CheckRef",
    "Manifest",
    "ProjectRef",
    "StageRef",
    "State",
    "ToolRef",
    "build",
    "content_sha256",
    "count_states",
    "design_kind",
    "dumps",
    "entry",
    "file_entry",
    "load",
    "merge",
    "relative_posix",
    "to_data",
]
