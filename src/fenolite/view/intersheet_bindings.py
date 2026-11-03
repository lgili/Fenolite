# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Path/instance bindings for viewer callers; ephemeral and never serialized into the design."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from pathlib import Path
from urllib.parse import quote

from fenolite.core.errors import FormatError
from fenolite.view.kicad_intersheet import Context, contexts_for_path
from fenolite.view.project import Document, ProjectTree


def instance_suffix(instance: tuple[str, ...]) -> str:
    return ":instance:" + quote(json.dumps(instance, separators=(",", ":")), safe="")


class Bindings:
    """Resolve fresh project bytes per read and retain exact dependencies even after failed reads."""

    def __init__(self, tree: ProjectTree) -> None:
        self.project = (
            tree.root / tree.project_file if tree.project_file.lower().endswith(".kicad_pro") else None
        )
        self.dependencies: set[Path] = set()
        self.instances: dict[str, tuple[str, ...]] = {}
        self.discovery: set[Path] = set()
        documents: list[Document] = []
        for doc in tree.documents:
            if doc.file is None or doc.file.suffix.lower() != ".kicad_sch" or not doc.present:
                documents.append(doc)
                continue
            try:
                contexts = self._contexts(doc.file)
            except FormatError:
                # Keep invalid/unowned files listed; selection/export must resolve and refuse them.
                documents.append(doc)
                continue
            active = [context for context in contexts if context is not None and context.enabled]
            if not active:
                documents.append(doc)
                continue
            for context in active:
                identity = doc.id + instance_suffix(context.instance)
                self.instances[identity] = context.instance
                documents.append(dataclasses.replace(doc, id=identity))
        self.tree = dataclasses.replace(tree, documents=tuple(documents))

    def _contexts(self, path: Path) -> tuple[Context | None, ...]:
        self.dependencies.add(path.resolve())
        if self.project is None:
            self.discovery.add(path.parent.resolve())
        return contexts_for_path(path, project=self.project, dependencies=self.dependencies)

    def context(self, path: Path, doc: Document | None = None) -> Context | None:
        if path.suffix.lower() != ".kicad_sch":
            return None
        values = self._contexts(path)
        instance = self.instances.get(doc.id) if doc is not None else None
        if instance is not None:
            values = tuple(
                value
                for value in values
                if value is not None and (not value.enabled or value.instance == instance)
            )
        if len(values) != 1:
            raise FormatError(
                "select one explicit sheet instance document id", file=path.name, locator="instance"
            )
        return values[0]

    def dependency_key(self, _doc: Document) -> str:
        """No parser in the watcher: watch bytes, missing inputs and adjacent project inventory."""
        rows: list[tuple[str, str | None]] = []
        for path in sorted(self.dependencies):
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                digest = None
            rows.append((str(path), digest))
        for folder in sorted(self.discovery):
            try:
                names = sorted(
                    path.name
                    for path in folder.iterdir()
                    if path.suffix.lower() == ".kicad_pro" and not path.is_dir()
                )
            except OSError:
                names = []
            rows.append((str(folder), json.dumps(names)))
        return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
