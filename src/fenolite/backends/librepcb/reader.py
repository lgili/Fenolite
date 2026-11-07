# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library layout and element reader; published facts and limits in formats/librepcb/library.md."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fenolite.backends.librepcb.sexpr import MAX_BYTES, Invalid, Node, parse
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-LIBREPCB-SEED",))
"""The documented, authored-test subset; external compatibility is unverified."""

UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
FORMAT_VERSIONS = frozenset({"0.1"})
ELEMENTS = {
    "sym": ("symbol", "symbol.lp"),
    "pkg": ("package", "package.lp"),
    "cmp": ("component", "component.lp"),
    "dev": ("device", "device.lp"),
}
CC0_SHA256 = "0dd25be0803b1e2764b0323560013cdd5ad9ca92ba4780bd7db0cbe6ce821dd8"


@dataclass(frozen=True, slots=True)
class Element:
    kind: str
    uuid: str
    name: str
    node: Node
    file: Path


@dataclass(frozen=True, slots=True)
class Skipped:
    uuid: str
    reason: str


@dataclass(frozen=True, slots=True)
class Library:
    elements: tuple[Element, ...]
    skipped: tuple[Skipped, ...] = ()

    def of_kind(self, kind: str) -> tuple[Element, ...]:
        return tuple(e for e in self.elements if e.kind == kind)


def _text(path: Path, root: Path) -> str:
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise Invalid("element path escapes the library or is a symlink")
    if path.stat().st_size > MAX_BYTES:
        raise Invalid("element exceeds byte limit")
    return path.read_text(encoding="utf-8")


def default_name(node: Node) -> str:
    """Read only the unlocalized name; reject ambiguous/malformed alternatives."""
    default: str | None = None
    locales: set[str] = set()
    for name in node.children("name"):
        locale = name.child("locale")
        if locale is None:
            if len(name.values) != 1 or len(name.atoms) != 1:
                raise Invalid("name: expected one default atom")
            if default is not None:
                raise Invalid("duplicate default name")
            default = name.atoms[0]
        else:
            if (
                len(name.values) != 2
                or len(name.atoms) != 1
                or len(locale.values) != 1
                or len(locale.atoms) != 1
                or not locale.atoms[0]
            ):
                raise Invalid("malformed localized name")
            if locale.atoms[0] in locales:
                raise Invalid("duplicate name locale")
            locales.add(locale.atoms[0])
    return default or ""


def read_library(root: Path) -> Library:
    """Read four element kinds only. Unsupported or malformed elements become explicit skips."""
    root_version = _text(root / ".librepcb-lib", root).strip()
    if root_version not in FORMAT_VERSIONS:
        raise Invalid(f"unsupported library format {root_version!r}")
    elements: list[Element] = []
    skipped: list[Skipped] = []
    for folder, (kind, filename) in ELEMENTS.items():
        for path in sorted((root / folder).glob(f"*/{filename}")):
            element_id = path.parent.name
            try:
                if not UUID.fullmatch(element_id):
                    raise Invalid("element directory is not a UUID")
                version = _text(path.parent / f".librepcb-{folder}", root).strip()
                if version not in FORMAT_VERSIONS:
                    raise Invalid(f"unsupported element format {version!r}")
                node = parse(_text(path, root))
                if node.head != f"librepcb_{kind}" or node.atoms != (element_id,):
                    raise Invalid("root type/UUID does not match element directory")
                name = default_name(node)
                if not name:
                    raise Invalid("element has no default name")
                elements.append(Element(kind, element_id, name, node, path))
            except (Invalid, OSError, UnicodeError) as exc:
                skipped.append(Skipped(element_id, str(exc)))
    return Library(tuple(elements), tuple(skipped))
