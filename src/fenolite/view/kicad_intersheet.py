# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ephemeral, source-bound project/instance reference text (c0348).

The raw bytes scene API uses None for an explicit standalone/no-project view, whose native default is
reference display disabled. Path-aware callers must resolve known projects and must not turn a failed
owner/instance lookup into that standalone default. Discovery is limited to explicit project paths or
adjacent project files; it never walks ancestors or scans the disk.
"""

from __future__ import annotations

import hashlib
import json
import posixpath
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import cast

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.schlayout import natural_key
from fenolite.core.errors import FormatError
from fenolite.model.schematic import SchematicSheet


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _pairs(values: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for name, value in values:
        if name in result:
            raise ValueError("duplicate project JSON key")
        result[name] = value
    return result


@dataclass(frozen=True, slots=True)
class Settings:
    enabled: bool = False
    own_page: bool = False
    short: bool = False
    prefix: str = ""
    suffix: str = ""


@dataclass(frozen=True, slots=True)
class Context:
    file: str
    instance: tuple[str, ...]
    page: str
    settings: Settings
    membership: tuple[tuple[str, tuple[str, ...]], ...]
    source_sha256: str
    fingerprint: str

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def reference(self, label: str) -> str:
        if not self.enabled:
            return ""
        members = dict(self.membership)
        if label not in members:
            raise FormatError("global label missing from its project context", file=self.file, locator=label)
        pages = [p for p in members[label] if self.settings.own_page or p != self.page]
        ordered = sorted(pages, key=natural_key)  # Stable numeric ties preserve measured hierarchy order.
        text = (
            f"{ordered[0]}..{ordered[-1]}" if self.settings.short and len(ordered) > 2 else ",".join(ordered)
        )
        return self.settings.prefix + text + self.settings.suffix


def _settings(data: bytes, file: str) -> Settings:
    try:
        root = json.loads(data, object_pairs_hook=_pairs)
        drawing = root.get("schematic", {}).get("drawing", {})
        if not isinstance(drawing, dict):
            raise ValueError("schematic.drawing is an object")
        drawing = cast(dict[str, object], drawing)
        values: dict[str, bool] = {}
        for name in ("show", "own_page", "short"):
            value = drawing.get(f"intersheets_ref_{name}", False)
            if not isinstance(value, bool):
                raise ValueError(f"intersheets_ref_{name} is a JSON boolean")
            values[name] = value
        affixes: dict[str, str] = {}
        for name in ("prefix", "suffix"):
            value = drawing.get(f"intersheets_ref_{name}", "")
            if not isinstance(value, str):
                raise ValueError(f"intersheets_ref_{name} is text")
            if values["show"] and ("${" in value or "$(" in value):
                raise ValueError("reference affix text-variable expansion is not represented")
            affixes[name] = value
        return Settings(
            values["show"], values["own_page"], values["short"], affixes["prefix"], affixes["suffix"]
        )
    except (ValueError, AttributeError, TypeError) as error:
        raise FormatError(str(error), file=file, locator="schematic.drawing") from error


class Project:
    """One explicit project's checked tree; no persistent/canonical model field."""

    def __init__(self, project: Path, data: bytes, *, dependencies: set[Path] | None = None) -> None:
        self.dependencies = dependencies
        self.project = project.resolve()
        self.root = self.project.parent
        self.settings = _settings(data, self.project.name)
        self._data: dict[str, bytes] = {self.project.name: data}
        self._sheets: dict[str, SchematicSheet] = {}
        self._specs: list[tuple[str, tuple[str, ...], str]] = []
        self._loaded = False
        self._membership: tuple[tuple[str, tuple[str, ...]], ...] = ()
        if self.settings.enabled:
            self._load()

    def _relative(self, file: str | Path) -> str:
        value = str(file).replace("\\", "/")
        given = Path(value)
        if not given.is_absolute():
            if PurePosixPath(value).is_absolute() or (len(value) > 1 and value[1] == ":"):
                raise FormatError("a sheet path must remain within its project", file=self.project.name)
            given = self.root / value
        target = given.resolve()
        if not target.is_relative_to(self.root) or target.suffix.lower() != ".kicad_sch":
            raise FormatError("a sheet path leaves its project", file=self.project.name)
        return target.relative_to(self.root).as_posix()

    def _read(self, file: str) -> SchematicSheet:
        if file not in self._sheets:
            if self.dependencies is not None:
                self.dependencies.add(self.root / file)
            try:
                data = (self.root / file).read_bytes()
                result = sch.read_schematic(data.decode("utf-8"), file=file)
            except (OSError, UnicodeError) as error:
                raise FormatError("required project sheet is missing or unreadable", file=file) from error
            self._data[file] = data
            self._sheets[file] = result
        return self._sheets[file]

    @property
    def fingerprint(self) -> str:
        parts = [(name, _sha(data)) for name, data in sorted(self._data.items())]
        return _sha(json.dumps(parts, separators=(",", ":")).encode())

    @property
    def input_paths(self) -> tuple[Path, ...]:
        return tuple(self.root / name for name in sorted(self._data))

    def _load(self) -> None:
        if self._loaded:
            return
        root_file = self._relative(self.project.with_suffix(".kicad_sch"))
        root = self._read(root_file)
        pages = [item.page for item in root.pages if item.path == "/"]
        if self.settings.enabled and (len(pages) != 1 or not pages[0]):
            raise FormatError("the project root requires one explicit page", file=root_file, locator="page")
        root_page = pages[0] if pages else ""
        used_pages: set[str] = set()
        members: dict[str, list[str]] = {}

        def walk(file: str, logical: tuple[str, ...], native: str, page: str, trail: tuple[str, ...]) -> None:
            if file in trail:
                raise FormatError("cycle in project sheet hierarchy", file=file)
            sheet = self._read(file)
            if self.settings.enabled:
                if not page or not page.isprintable() or "${" in page:
                    raise FormatError("missing or unsupported sheet page", file=file, locator="page")
                if page in used_pages:
                    raise FormatError(
                        "duplicate sheet page has differing native9/native10 meanings",
                        file=file,
                        locator="page",
                    )
                used_pages.add(page)
            self._specs.append((file, logical, page))
            for label in sheet.labels:
                if label.kind != "global":
                    continue
                if self.settings.enabled and (
                    not label.name or not label.name.isprintable() or "${" in label.name or "$(" in label.name
                ):
                    raise FormatError(
                        "global-label text-variable expansion is not represented",
                        file=file,
                        locator=label.name,
                    )
                listed = members.setdefault(label.name, [])
                if page not in listed:
                    listed.append(page)
            names: set[str] = set()
            for child in sheet.sheets:
                if self.settings.enabled and (not child.name or child.name in names):
                    raise FormatError("ambiguous logical sheet instance name", file=file, locator=child.name)
                names.add(child.name)
                relative = self._relative(
                    posixpath.join(posixpath.dirname(file), child.file.replace("\\", "/"))
                )
                uses = [use for use in child.uses if use.project == self.project.stem and use.path == native]
                if self.settings.enabled and (len(uses) != 1 or not uses[0].page):
                    raise FormatError(
                        "missing or ambiguous native sheet instance page", file=file, locator=child.name
                    )
                uuid = child.native_ids.get("kicad", "")
                if self.settings.enabled and not uuid:
                    raise FormatError("missing native sheet instance identity", file=file, locator=child.name)
                walk(
                    relative,
                    (*logical, child.name),
                    native + "/" + uuid,
                    uses[0].page if uses else "",
                    (*trail, file),
                )

        walk(root_file, (), "/" + root.native_ids.get("kicad", ""), root_page, ())
        self._membership = tuple((name, tuple(pages)) for name, pages in sorted(members.items()))
        self._loaded = True

    def owns(self, file: Path) -> bool:
        relative = self._relative(file)
        self._load()  # Off-project discovery still proves ownership rather than assuming a stem match.
        return relative in self._sheets

    def for_file(self, file: str | Path) -> tuple[Context, ...]:
        relative = self._relative(file)
        if not self.settings.enabled:
            try:
                data = (self.root / relative).read_bytes()
            except OSError as error:
                raise FormatError("required scene file is unreadable", file=relative) from error
            self._data[relative] = data
            return (Context(relative, (), "", self.settings, (), _sha(data), self.fingerprint),)
        found: list[Context] = []
        for current, logical, page in self._specs:
            if current == relative:
                key = json.dumps((self.fingerprint, logical, page), separators=(",", ":")).encode()
                found.append(
                    Context(
                        relative,
                        logical,
                        page,
                        self.settings,
                        self._membership,
                        _sha(self._data[relative]),
                        _sha(key),
                    )
                )
        if not found:
            raise FormatError("scene file has no owning project instance", file=relative, locator="instance")
        return tuple(found)

    def select(self, file: str | Path, *, instance: tuple[str, ...] | None = None) -> Context:
        matches = self.for_file(file)
        if instance is not None:
            matches = tuple(value for value in matches if value.instance == instance or not value.enabled)
        if len(matches) != 1:
            raise FormatError("select one explicit sheet instance", file=str(file), locator="instance")
        return matches[0]

    @property
    def contexts(self) -> tuple[Context, ...]:
        self._load()
        return tuple(
            value for file in dict.fromkeys(item[0] for item in self._specs) for value in self.for_file(file)
        )


def resolve_project(path: Path, *, dependencies: set[Path] | None = None) -> Project:
    if dependencies is not None:
        dependencies.add(path.resolve())
    try:
        data = path.read_bytes()
    except OSError as error:
        raise FormatError("required owning project is missing or unreadable", file=path.name) from error
    return Project(path, data, dependencies=dependencies)


def contexts_for_path(
    path: Path, *, project: Path | None = None, dependencies: set[Path] | None = None
) -> tuple[Context | None, ...]:
    """Explicit project or adjacent owners only; no owner failure becomes a standalone fallback."""
    if project is not None:
        return resolve_project(project, dependencies=dependencies).for_file(path)
    candidates = sorted(
        candidate
        for candidate in path.parent.iterdir()
        if candidate.suffix.lower() == ".kicad_pro" and not candidate.is_dir()
    )
    if not candidates:
        return (None,)
    owners = [
        bound
        for candidate in candidates
        if (bound := resolve_project(candidate, dependencies=dependencies)).owns(path)
    ]
    if len(owners) != 1:
        raise FormatError(
            "missing or ambiguous owning project; select an explicit project", file=path.name, locator="owner"
        )
    return cast(tuple[Context | None, ...], owners[0].for_file(path))
