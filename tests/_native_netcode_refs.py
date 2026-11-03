# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative pre-runtime netcode reference control; no Royal transform (c0355)."""

from __future__ import annotations

import re
from collections.abc import Mapping
from fractions import Fraction

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.errors import FormatError


def netcode_reference_facts(
    root: Node,
    companions: Mapping[str, bytes] | None = None,
    *,
    proved_nonreference_occurrences: frozenset[tuple[int, ...]] = frozenset(),
) -> dict:
    """Recognize exact structural net roles; outside affected numbers conservatively refuse.

    Nonreference numeric occurrences need a separate explicit authored/profile proof. This helper
    does not derive exemptions from input names, approximate strings, or model net names.
    """
    if root.name != "kicad_pcb":
        raise ValueError("numeric-net profile requires a board root")
    declared = {}
    names = set()
    reference_paths = set()
    refs = []
    unnumbered_no_net = []

    def code(atom):
        if atom.kind != AtomKind.NUMBER:
            raise ValueError("netcode is not an exact integer")
        value = atom.to_int()
        if value < 0:
            raise ValueError("netcode is not a nonnegative exact integer")
        return value

    for index, child in enumerate(root.children):
        if not isinstance(child, Node) or child.name != "net":
            continue
        atoms = child.atoms()
        if child.nodes() or len(atoms) != 2 or len(child.children) != 2:
            raise ValueError("malformed root net declaration")
        number = code(atoms[0])
        if atoms[1].kind != AtomKind.STRING:
            raise ValueError("net name is not a string")
        name = atoms[1].value
        if number in declared or name in names or (number == 0) != (name == ""):
            raise ValueError("duplicate or conflicting net declaration")
        declared[number] = name
        names.add(name)
        reference_paths.add((index, 0))
    if declared.get(0) != "":
        raise ValueError("explicit NO_NET declaration missing")

    def gather(node, path=(), parent=None, grandparent=None):
        if isinstance(node, Atom):
            return
        role = (
            parent == "kicad_pcb" and grandparent is None and node.name in {"segment", "arc", "via", "zone"}
        ) or (parent == "footprint" and grandparent == "kicad_pcb" and node.name == "pad")
        if role:
            fields = node.nodes("net")
            if not fields and node.name == "pad":
                atoms = node.atoms()
                if (
                    len(atoms) != 3
                    or atoms[0].kind != AtomKind.STRING
                    or atoms[0].value != ""
                    or atoms[1].kind != AtomKind.SYMBOL
                    or atoms[1].value not in {"smd", "np_thru_hole"}
                    or atoms[2].kind != AtomKind.SYMBOL
                    or atoms[2].value not in {"circle", "rect", "roundrect", "custom"}
                ):
                    raise ValueError("omitted net is not a proved unnumbered physical pad")
                unnumbered_no_net.append(path)
                # Keep and scan every physical child. No numbered-pad binding or geometry is dropped.
                for index, child in enumerate(node.children):
                    gather(child, (*path, index), node.name, parent)
                return
            if len(fields) != 1:
                raise ValueError("electrical object net field missing or duplicated")
            field = fields[0]
            atoms = field.atoms()
            if field.nodes() or len(atoms) not in {1, 2} or len(field.children) != len(atoms):
                raise ValueError("malformed electrical net reference")
            number = code(atoms[0])
            if number not in declared:
                raise ValueError("undeclared electrical netcode")
            if len(atoms) == 2 and (atoms[1].kind != AtomKind.STRING or atoms[1].value != declared[number]):
                raise ValueError("net name contradicts declaration")
            reference_paths.add((*path, node.children.index(field), 0))
            refs.append((node.name, number))
        for index, child in enumerate(node.children):
            gather(child, (*path, index), node.name, parent)

    gather(root)
    affected = set(declared) - {0}

    def scan(node, path=()):
        if isinstance(node, Atom):
            if node.kind == AtomKind.NUMBER and Fraction(node.text) in affected:
                if path not in reference_paths and path not in proved_nonreference_occurrences:
                    raise ValueError("affected netcode outside proved structural reference roles")
            return
        for index, child in enumerate(node.children):
            scan(child, (*path, index))

    scan(root)

    def json_refs(value):
        if isinstance(value, bool):
            return
        if isinstance(value, str) and value.isdecimal() and int(value) in affected:
            raise ValueError("affected netcode string in unproved JSON context")
        if isinstance(value, _json.JsonNumber) and Fraction(value.text) in affected:
            raise ValueError("affected netcode in unproved JSON context")
        if isinstance(value, list):
            for child in value:
                json_refs(child)
        if isinstance(value, dict):
            for key, child in value.items():
                json_refs(key)
                json_refs(child)

    for name, body in (companions or {}).items():
        if name.endswith((".json", ".kicad_pro")):
            try:
                parsed = _json.loads(body.decode("utf-8"), file=name)
            except FormatError as error:
                raise ValueError("malformed or ambiguous JSON companion") from error
            json_refs(parsed)
        elif name.endswith(".kicad_dru"):
            if not re.fullmatch(rb"[ \t\r\n]*\(version[ \t]+1\)[ \t\r\n]*", body):
                raise ValueError("only the exact empty known DRU header is profiled")
        elif body.strip():
            raise ValueError("unprofiled non-JSON companion")
    result = {"declared": declared, "reference_occurrences": len(refs), "no_net_retained": True}
    if unnumbered_no_net:
        result["unnumbered_no_net_pads"] = len(unnumbered_no_net)
    return result


def exact_labelled_partitions(root: Node, expected: Mapping[str, tuple[str, ...]]) -> dict:
    """An unlabelled partition set alone cannot detect globally exchanged A/B net assignments."""
    from fenolite.cli._derived_cache import _raw_bindings

    actual = _raw_bindings(root, frozenset(expected.values()))
    if actual != dict(expected):
        raise ValueError("literal net name to complete physical partition changed")
    return actual
