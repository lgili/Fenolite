# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Hash-bound owner/instance discovery for the drawn corpus (c0276 task 7.4)."""

from __future__ import annotations

import hashlib
import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

from fenolite.backends.kicad.sexpr import Node, parse_bytes


@dataclass(frozen=True)
class SheetInput:
    id: str
    path: str
    sha256: str
    data: bytes | None


@dataclass(frozen=True)
class Instance:
    sheet: SheetInput
    path: str
    parent: str


@dataclass(frozen=True)
class Owner:
    root: SheetInput
    registered: bool
    instances: tuple[Instance, ...]
    errors: tuple[str, ...]

    def data(self, target: str) -> dict[str, object]:
        def digest(text: str) -> str:
            return hashlib.sha256(text.encode("utf-8")).hexdigest()

        return {
            "owner_id": self.root.id,
            "owner_sha256": self.root.sha256,
            "native_export_root_id": self.root.id,
            "scope": "registered-project" if self.registered else "standalone-unowned",
            "target_instances": sum(i.sheet.id == target for i in self.instances),
            "errors": list(self.errors),
            "instances": [
                {
                    "input_id": i.sheet.id,
                    "input_sha256": i.sheet.sha256,
                    "instance_path_sha256": digest(i.path),
                    "parent_instance_path_sha256": digest(i.parent) if i.parent else None,
                }
                for i in self.instances
            ],
        }


def _first(node: Node | None) -> str:
    return node.atoms()[0].value if node is not None and node.atoms() else ""


class Contexts:
    """Discover ownership only; the normal reader's format and semantic guards still run in measure.

    The existing S-expression parser reads only UUID/Sheetfile edges, including edges into unsupported
    sheets. It never grants format support or decodes symbol definitions. Every supplied byte hash is
    verified before the first parser call; all root contexts are retained rather than chosen by name.
    """

    def __init__(self, sheets: tuple[SheetInput, ...], roots: tuple[str, ...]):
        self.by_id = {s.id: s for s in sheets}
        self.by_path = {s.path: s for s in sheets}
        if len(self.by_id) != len(sheets) or len(self.by_path) != len(sheets):
            raise ValueError("duplicate-context-input")
        for sheet in sheets:
            if sheet.data is not None and hashlib.sha256(sheet.data).hexdigest() != sheet.sha256:
                raise ValueError("context-sha256")
            path = PurePosixPath(sheet.path)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("context-path")
        self.nodes: dict[str, Node | None] = {}
        self.owners = tuple(self._walk(self.by_id[root], True) for root in sorted(set(roots)))

    def _node(self, sheet: SheetInput) -> Node | None:
        if sheet.id not in self.nodes:
            try:
                node = parse_bytes(sheet.data, file=sheet.id) if sheet.data is not None else None
                self.nodes[sheet.id] = node if node is not None and node.name == "kicad_sch" else None
            except ValueError:
                self.nodes[sheet.id] = None
        return self.nodes[sheet.id]

    def _walk(self, root: SheetInput, registered: bool) -> Owner:
        found: list[Instance] = []
        errors: list[str] = []
        root_node = self._node(root)
        uuid = _first(root_node.find("uuid")) if root_node is not None else ""

        def walk(sheet: SheetInput, at: str, parent: str, trail: tuple[str, ...]) -> None:
            found.append(Instance(sheet, at, parent))
            node = self._node(sheet)
            if node is None:
                errors.append("context-missing-input" if sheet.data is None else "context-unreadable")
                return
            if not at or at.endswith("/"):
                errors.append("context-missing-uuid")
            for ref in node.nodes("sheet"):
                names = [
                    p.atoms()[1].value
                    for p in ref.nodes("property")
                    if len(p.atoms()) >= 2 and p.atoms()[0].value == "Sheetfile"
                ]
                if len(names) != 1 or not names[0]:
                    errors.append("context-sheet-file")
                    continue
                path = posixpath.normpath(
                    posixpath.join(posixpath.dirname(sheet.path), names[0].replace("\\", "/"))
                )
                child = self.by_path.get(path)
                if child is None:
                    errors.append("context-undeclared-input")
                    continue
                if PurePosixPath(root.path).parent not in PurePosixPath(path).parents:
                    errors.append("context-outside-project")
                    continue
                if child.id in trail:
                    errors.append("context-sheet-cycle")
                    continue
                walk(child, f"{at}/{_first(ref.find('uuid'))}", at, (*trail, child.id))

        walk(root, f"/{uuid}", "", (root.id,))
        return Owner(root, registered, tuple(found), tuple(sorted(set(errors))))

    def for_row(self, ident: str) -> tuple[Owner, ...]:
        owners = [owner for owner in self.owners if any(i.sheet.id == ident for i in owner.instances)]
        # An unreadable root cannot establish that another file in its project is unowned.
        target = PurePosixPath(self.by_id[ident].path)
        for owner in self.owners:
            if (
                owner not in owners
                and owner.errors
                and PurePosixPath(owner.root.path).parent in target.parents
            ):
                owners.append(owner)
        return tuple(owners) if owners else (self._walk(self.by_id[ident], False),)


def authored(name: str, major: int):
    """Existing CC0 port/repeated fixtures as an owner's complete source graph, without CAD on disk."""
    import _drawn

    output = _drawn.build(name, major)
    root_file = _drawn.root_name(output)
    files = {file: data for file, data in output.files.items() if file.endswith(".kicad_sch")}
    inputs = tuple(
        SheetInput(file, f"authored/{file}", hashlib.sha256(data).hexdigest(), data)
        for file, data in files.items()
    )
    index = Contexts(inputs, (root_file,))
    child = next(sheet for sheet in inputs if sheet.id != root_file)
    (owner,) = index.for_row(child.id)
    return output, files, child, owner
