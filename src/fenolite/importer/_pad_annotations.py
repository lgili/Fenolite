# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact native pad annotations across the importer's local transform (c0355)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import TypeAlias

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse
from fenolite.core.errors import FormatError

_ANNOTATIONS = frozenset({"pinfunction", "pintype"})
_REMOVED = _ANNOTATIONS | {"net"}
_Identity: TypeAlias = tuple[tuple[str, str], ...]
_Key: TypeAlias = tuple[tuple[str, ...], tuple[_Identity, ...]]


def _error(message: str) -> FormatError:
    return FormatError(message, locator="/kicad_pcb/footprint/pad-annotations")


def _identity(pad: Node) -> _Identity:
    leading = pad.children[:3]
    if len(leading) != 3 or not all(isinstance(c, Atom) for c in leading):
        raise _error("physical pad identity needs number, kind and shape")
    ids = tuple(c for c in pad.nodes() if c.name in {"uuid", "tstamp"})
    return tuple((c.kind.value, c.value) for c in leading if isinstance(c, Atom)) + tuple(
        (c.name, dumps(c, style="compact")) for c in ids
    )


def _key(footprint: Node) -> _Key:
    refs: list[str] = []
    for child in footprint.nodes():
        atoms = child.atoms()
        if child.name == "property" and len(atoms) >= 2 and atoms[0].value == "Reference":
            refs.append(atoms[1].value)
        elif child.name == "fp_text" and len(atoms) >= 2 and atoms[0].value == "reference":
            refs.append(atoms[1].value)
    return tuple(refs), tuple(_identity(p) for p in footprint.nodes("pad"))


def _has_annotations(footprint: Node) -> bool:
    return any(c.name in _ANNOTATIONS for pad in footprint.nodes("pad") for c in pad.nodes())


def _restore(original: Node, local: Node) -> Node:
    """Preserve annotation positions through the known order-preserving local pad transform."""
    incoming = iter(local.children)
    children: list[Node | Atom] = []
    for source in original.children:
        if isinstance(source, Node) and source.name in _REMOVED:
            if source.name in _ANNOTATIONS:
                children.append(source)
            continue
        value = next(incoming, None)
        if (
            value is None
            or (isinstance(source, Node) and (not isinstance(value, Node) or source.name != value.name))
            or (isinstance(source, Atom) and value != source)
        ):
            raise _error("physical pad child order changed during local transformation")
        children.append(value)
    if next(incoming, None) is not None:
        raise _error("physical pad gained children during local transformation")
    return local.with_children(children)


def annotation_restorer(text: str) -> Callable[[Node], Node]:
    """Prepare import-only physical definitions; generic library extraction remains circuit-free."""
    footprints = parse(text).nodes("footprint")
    if not any(_has_annotations(fp) for fp in footprints):
        return lambda node: node
    originals: dict[_Key, list[Node]] = defaultdict(list)
    for footprint in footprints:
        for pad in footprint.nodes("pad"):
            for name in _ANNOTATIONS:
                found = pad.nodes(name)
                if len(found) > 1 or any(
                    len(c.children) != 1
                    or not isinstance(c.children[0], Atom)
                    or c.children[0].kind != AtomKind.STRING
                    for c in found
                ):
                    raise _error(f"{name} needs exactly one string and at most one child per pad")
        originals[_key(footprint)].append(footprint)

    def restore(local: Node) -> Node:
        candidates = originals.get(_key(local), [])
        if not candidates:
            raise _error("physical pad identity/cardinality/order changed during local transformation")
        if not any(_has_annotations(fp) for fp in candidates):
            return local  # Complete original candidate set proves exact absence, including shared refs.
        if len(candidates) != 1:
            raise _error("annotated physical footprint identity is ambiguous")
        original = candidates[0]  # Uniqueness is checked; no reference/number fallback.
        sources = iter(original.nodes("pad"))
        return local.with_children(
            [
                _restore(next(sources), c) if isinstance(c, Node) and c.name == "pad" else c
                for c in local.children
            ]
        )

    return restore
