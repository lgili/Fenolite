# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Token edits of a board that make it disagree with its schematic (change c0072; capability kicad-oracle,
"Parity types are probed"). Each edit changes one thing of one footprint and nothing else, on the board of
either major: a reference, a value, a library id, a pad's net, or a whole footprint added or removed."""

from __future__ import annotations

from collections.abc import Callable

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse

EDITS: tuple[str, ...] = ("none", "ref", "value", "libid", "net", "dup", "extra")
"""The edits of ``H-K-PARITY-TYPES``, in the order of the hypothesis."""
NEW_REF = "ZZ99"
NEW_VALUE = "fenolite-other-value"
NEW_LIB_ID = "Fenolite_Other:Other_Footprint"
COPY_UUID = "f3a0c0de-0072-4000-8000-000000000072"


def _property(fp: Node, name: str) -> str | None:
    for prop in fp.nodes("property"):
        atoms = prop.atoms()
        if len(atoms) >= 2 and atoms[0].value == name:
            return atoms[1].value
    return None


def reference(fp: Node) -> str | None:
    return _property(fp, "Reference")


def footprints(text: str) -> list[Node]:
    return list(parse(text).nodes("footprint"))


def references(text: str) -> list[str]:
    """The reference of every footprint, in board order."""
    return [ref for fp in footprints(text) if (ref := reference(fp)) is not None]


def _edit(text: str, ref: str, change: Callable[[Node], list[Node]]) -> str:
    """``text`` with the first footprint of reference ``ref`` replaced by ``change`` of it."""
    root = parse(text)
    out: list[Node | Atom] = []
    done = False
    for child in root.children:
        if not done and isinstance(child, Node) and child.name == "footprint" and reference(child) == ref:
            out += change(child)
            done = True
        else:
            out.append(child)
    assert done, f"no footprint {ref}"
    return dumps(root.with_children(out), style="kicad")


def _with_property(fp: Node, name: str, value: str) -> Node:
    children: list[Node | Atom] = []
    found = 0
    for child in fp.children:
        if isinstance(child, Node) and child.name == "property":
            atoms = child.atoms()
            if len(atoms) >= 2 and atoms[0].value == name:
                parts = list(child.children)
                parts[parts.index(atoms[1])] = Atom.string(value)
                child = child.with_children(parts)
                found += 1
        children.append(child)
    assert found == 1, f"{name}: {found} properties"
    return fp.with_children(children)


def rename(text: str, ref: str, new: str = NEW_REF) -> str:
    """The footprint ``ref`` with the reference ``new``."""
    return _edit(text, ref, lambda fp: [_with_property(fp, "Reference", new)])


def revalue(text: str, ref: str, new: str = NEW_VALUE) -> str:
    return _edit(text, ref, lambda fp: [_with_property(fp, "Value", new)])


def relib(text: str, ref: str, new: str = NEW_LIB_ID) -> str:
    """The footprint ``ref`` with the library id ``new`` (its first atom)."""

    def change(fp: Node) -> list[Node]:
        parts = list(fp.children)
        first = fp.atoms()[0]
        parts[parts.index(first)] = Atom.string(new)
        return [fp.with_children(parts)]

    return _edit(text, ref, change)


def _net_numbers(text: str) -> dict[str, str]:
    """Net name → number, for a board that numbers its nets (9.0)."""
    return {n.atoms()[1].value: n.atoms()[0].value for n in parse(text).nodes("net") if len(n.atoms()) == 2}


def pad_nets(text: str, ref: str) -> dict[str, str]:
    """Pad number → net name of the first footprint ``ref``; a pad on no net is left out."""
    (fp,) = [f for f in footprints(text) if reference(f) == ref][:1]
    found: dict[str, str] = {}
    for pad in fp.nodes("pad"):
        net = pad.find("net")
        if net is not None and net.atoms():
            found.setdefault(pad.atoms()[0].value, net.atoms()[-1].value)
    return found


def renet(text: str, ref: str, pad: str, net: str | None) -> str:
    """Every pad ``pad`` of the footprint ``ref`` on ``net``, a net the board holds; ``None`` takes the
    pad off its net."""
    numbers = _net_numbers(text)

    def change(fp: Node) -> list[Node]:
        children: list[Node | Atom] = []
        done = 0
        for child in fp.children:
            if isinstance(child, Node) and child.name == "pad" and child.atoms()[0].value == pad:
                kids: list[Node | Atom] = []
                for kid in child.children:
                    if isinstance(kid, Node) and kid.name == "net":
                        done += 1
                        if net is None:
                            continue
                        name = dumps(Atom.string(net)).strip()
                        number = f"{numbers[net]} " if len(kid.atoms()) == 2 else ""
                        kid = parse(f"(net {number}{name})")
                    kids.append(kid)
                child = child.with_children(kids)
            children.append(child)
        assert done >= 1, f"pad {ref}-{pad} has no net"
        return [fp.with_children(children)]

    return _edit(text, ref, change)


def duplicate(text: str, ref: str, other: str) -> str:
    """The footprint ``ref`` with the reference of ``other``: two footprints of one reference."""
    return rename(text, ref, other)


def _fresh_uuid(node: Node, uuid: str) -> Node:
    children: list[Node | Atom] = [
        parse(f'(uuid "{uuid}")') if isinstance(c, Node) and c.name == "uuid" else c for c in node.children
    ]
    return node.with_children(children)


def copy(text: str, ref: str, new: str = NEW_REF, uuid: str = COPY_UUID) -> str:
    """A copy of the footprint ``ref`` after it, with the reference ``new`` and its own uuid."""
    return _edit(text, ref, lambda fp: [fp, _fresh_uuid(_with_property(fp, "Reference", new), uuid)])


def remove(text: str, ref: str) -> str:
    return _edit(text, ref, lambda _fp: [])


def drop_pad(text: str, ref: str, pad: str) -> str:
    """The footprint ``ref`` without its pads numbered ``pad``."""

    def change(fp: Node) -> list[Node]:
        kept: list[Node | Atom] = [
            c
            for c in fp.children
            if not (isinstance(c, Node) and c.name == "pad" and c.atoms()[0].value == pad)
        ]
        assert len(kept) < len(fp.children), f"no pad {ref}-{pad}"
        return [fp.with_children(kept)]

    return _edit(text, ref, change)


def renumber_pad(text: str, ref: str, pad: str, new: str) -> str:
    """The pads ``pad`` of the footprint ``ref`` numbered ``new``."""

    def change(fp: Node) -> list[Node]:
        children: list[Node | Atom] = []
        for child in fp.children:
            if isinstance(child, Node) and child.name == "pad" and child.atoms()[0].value == pad:
                parts = list(child.children)
                parts[parts.index(child.atoms()[0])] = Atom.string(new)
                child = child.with_children(parts)
            children.append(child)
        return [fp.with_children(children)]

    return _edit(text, ref, change)


def board_only(text: str, ref: str) -> str:
    """The footprint ``ref`` with the attribute ``board_only`` ("not in schematic")."""

    def change(fp: Node) -> list[Node]:
        children: list[Node | Atom] = []
        done = False
        for child in fp.children:
            if isinstance(child, Node) and child.name == "attr":
                child = child.with_children([*child.children, Atom.symbol("board_only")])
                done = True
            children.append(child)
        if not done:
            children.append(parse("(attr board_only)"))
        return [fp.with_children(children)]

    return _edit(text, ref, change)


def other_net(text: str, ref: str, pad: str) -> str:
    """A net of the board that is not the net of ``ref``-``pad``: the net of another pad of the board, the
    first in board order."""
    own = pad_nets(text, ref).get(pad)
    for fp in footprints(text):
        for node in fp.nodes("pad"):
            net = node.find("net")
            if net is not None and net.atoms() and net.atoms()[-1].value not in ("", own):
                return net.atoms()[-1].value
    raise AssertionError("the board has one net only")


def apply(edit: str, text: str, ref: str, other: str, pad: str) -> str:
    """``text`` after the edit named ``edit`` of ``EDITS`` on the footprint ``ref``; ``other`` is the
    footprint whose reference ``dup`` gives to ``ref``, and ``pad`` the pad that ``net`` moves."""
    if edit == "none":
        return text
    if edit == "ref":
        return rename(text, ref)
    if edit == "value":
        return revalue(text, ref)
    if edit == "libid":
        return relib(text, ref)
    if edit == "net":
        return renet(text, ref, pad, other_net(text, ref, pad))
    if edit == "dup":
        return duplicate(text, ref, other)
    if edit == "extra":
        return copy(text, ref)
    raise ValueError(edit)


__all__ = [
    "EDITS",
    "NEW_LIB_ID",
    "NEW_REF",
    "NEW_VALUE",
    "apply",
    "board_only",
    "copy",
    "drop_pad",
    "duplicate",
    "footprints",
    "other_net",
    "pad_nets",
    "reference",
    "references",
    "relib",
    "remove",
    "rename",
    "renet",
    "renumber_pad",
    "revalue",
]
