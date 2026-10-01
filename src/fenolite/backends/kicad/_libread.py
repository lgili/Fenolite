# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the footprint and symbol readers share: inputs, version policy, locators, units, slots.

Facts: ``docs/formats/kicad/libraries.md``. Locators are the bare ``kicad-sexpr`` form
(``/footprint/pad[1]``) in both ``FormatError.locator`` and ``Provenance.locator``.
"""

from __future__ import annotations

import hashlib
import os
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.backends.kicad import versions
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse, parse_bytes
from fenolite.backends.kicad.slots import split
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.provenance import Provenance
from fenolite.core.units import parse_angle
from fenolite.model.base import Opaque, Slot

Source = str | os.PathLike[str] | Node
LIB_KEPT_CODE = "kicad.lib.kept-opaque"


class InexactValueError(FormatError):
    """A number that is valid but not a whole number of nanometres (``length``) or µdeg (``angle``)."""

    def __init__(
        self, what: str, message: str, *, file: str = "", locator: str = "", offset: int | None = None
    ) -> None:
        super().__init__(message, file=file, locator=locator, offset=offset)
        self.what = what


@dataclass(frozen=True, slots=True)
class Loaded:
    """A parsed input: the root node, the SHA-256 of what was read, the file label and the path."""

    node: Node
    sha256: str
    file: str
    path: Path | None


def load_source(source: Source, file: str = "") -> Loaded:
    """A path is read as bytes, a ``str`` is file text, a ``Node`` is used as is."""
    if isinstance(source, Node):
        text = dumps(source, style="compact")
        return Loaded(source, hashlib.sha256(text.encode("utf-8")).hexdigest(), file, None)
    if isinstance(source, str):
        return Loaded(
            parse(source, file=file), hashlib.sha256(source.encode("utf-8")).hexdigest(), file, None
        )
    path = Path(os.fspath(source))
    shown = file or os.fspath(path)
    data = path.read_bytes()
    return Loaded(parse_bytes(data, file=shown), hashlib.sha256(data).hexdigest(), shown, path)


def child_locators(parent: str, node: Node) -> list[tuple[str, Node | Atom]]:
    """``(locator, child)`` for every child; atoms get the parent's locator."""
    seen: dict[str, int] = {}
    out: list[tuple[str, Node | Atom]] = []
    for child in node.children:
        if isinstance(child, Node):
            index = seen.get(child.name, 0)
            seen[child.name] = index + 1
            out.append((f"{parent}/{child.name}[{index}]", child))
        else:
            out.append((parent, child))
    return out


def leading_atoms(node: Node) -> list[Atom]:
    """The atoms written before the first list child (positional values)."""
    out: list[Atom] = []
    for child in node.children:
        if isinstance(child, Node):
            break
        out.append(child)
    return out


def _chains(node: Node, chain: tuple[str, ...]) -> Iterator[tuple[tuple[str, ...], Node]]:
    stack = [(chain + (node.name,), node)]
    while stack:
        path, current = stack.pop()
        yield path, current
        stack.extend((path + (c.name,), c) for c in current.nodes())


@dataclass(slots=True)
class Context:
    """One file being read: its identity, its format version and the caller's issue list."""

    loaded: Loaded
    kind: versions.FileKind
    evidence: Evidence
    issues: list[Issue] = field(default_factory=lambda: [])
    version: int = 0
    future: bool = False
    kept_code: str = LIB_KEPT_CODE

    @property
    def file(self) -> str:
        return self.loaded.file

    def check_version(self, root_head: str, expected: versions.FileKind) -> None:
        """The read path of ``kicad-version-gating``: refuse too old, warn on future, info on dev."""
        node = self.loaded.node
        info = versions.inspect(node, file=self.file)
        if info.kind != expected:
            raise FormatError(
                f"expected a {root_head!r} root, found {node.name!r}",
                file=self.file,
                locator=f"/{node.name}",
                offset=node.offset,
            )
        versions.require_readable(info, file=self.file)
        self.issues.extend(versions.version_issues(info))
        self.version = info.version
        self.future = info.status == versions.VersionStatus.FUTURE

    def provenance(self, locator: str) -> Provenance:
        return Provenance("kicad", self.file, self.loaded.sha256, locator, self.evidence)

    def error(self, message: str, locator: str, node: Node | None) -> FormatError:
        return FormatError(
            message, file=self.file, locator=locator, offset=None if node is None else node.offset
        )

    def kept_opaque(self, message: str, locator: str) -> None:
        """An info with this file's kept-opaque code (``kicad.lib.kept-opaque`` or a board's own)."""
        self.issues.append(Issue(self.kept_code, "info", message, where=locator))

    def inexact(self, what: str, message: str, locator: str, node: Node) -> InexactValueError:
        return InexactValueError(what, message, file=self.file, locator=locator, offset=node.offset)

    def nm(self, atom: Atom, locator: str, node: Node) -> int:
        try:
            return atom.to_nm(exact=True)
        except ValueError as exc:
            try:
                atom.to_nm(exact=False)
            except ValueError:
                raise self.error(str(exc), locator, node) from None
            raise self.inexact("length", str(exc), locator, node) from None

    def udeg(self, atom: Atom, locator: str, node: Node) -> int:
        if atom.kind != AtomKind.NUMBER:
            raise self.error(f"{atom.text!r} is not an angle", locator, node)
        try:
            return parse_angle(atom.text, default_unit="deg")
        except ValueError as exc:
            if "not representable" in str(exc):
                raise self.inexact("angle", f"angle {atom.text!r}: {exc}", locator, node) from None
            raise self.error(f"angle {atom.text!r}: {exc}", locator, node) from None

    def point(self, node: Node, locator: str) -> Point:
        """``(head X Y …)`` as a point in nanometres."""
        atoms = node.atoms()
        if len(atoms) < 2:
            raise self.error(f"{node.name!r} needs two coordinates", locator, node)
        return Point(self.nm(atoms[0], locator, node), self.nm(atoms[1], locator, node))

    def min_version(self, child: Node | Atom, chain: tuple[str, ...]) -> str:
        """Minimum version of an opaque child under the head chain ``chain`` (see libraries.md)."""
        if self.future or not isinstance(child, Node):
            return str(self.version)
        if versions.min_version(self.kind, "/".join(chain + (child.name,))) is None:
            return str(self.version)
        best = 0
        for path, node in _chains(child, chain):
            token = "/".join(path)
            found = [versions.min_version(self.kind, token)]
            found += [
                versions.min_version(self.kind, token, value=a.text)
                for a in node.atoms()
                if a.kind == AtomKind.SYMBOL
            ]
            best = max([best, *(v for v in found if v is not None)])
        return str(best)

    def opaque(self, child: Node | Atom, chain: tuple[str, ...]) -> Opaque:
        return Opaque(dumps(child, style="compact"), self.min_version(child, chain))

    def split(
        self, node: Node, fields: dict[str, str], chain: tuple[str, ...], positional: Sequence[str] = ()
    ) -> list[Slot]:
        """``slots.split`` with this file's minimum-version rule for the opaque children."""
        rule: Callable[[Node | Atom], str | None] = lambda child: self.min_version(child, chain)  # noqa: E731
        return list(split(node, fields, positional=positional, min_version=rule))


__all__ = [
    "LIB_KEPT_CODE",
    "Context",
    "InexactValueError",
    "Loaded",
    "Source",
    "child_locators",
    "leading_atoms",
    "load_source",
]
