# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Via protection of KiCad boards: the protection children of a via and of ``setup`` (change c0112).

Facts, sources and labels: ``docs/formats/kicad/board.md``, "Via protection". KiCad 10 stores five
features per via (tenting, covering and plugging per side, capping, filling), each ``yes``, ``no`` or
``none`` (the board's value), and five defaults in ``setup``; KiCad 9 stores tenting only, as the list of
the tented sides. The reader (``pcb``) reads a via's children with ``project_via`` in the form of the
file's major and projects the default with ``project_setup``, keeping ``setup`` an opaque slot; the writer
emits a via's children with ``emit_via`` in the form of the target and rewrites the protection children
of ``setup`` only when the model changed (``rewrite_setup``). ``merge_default`` decides between the
default of a design script and the one of an existing board for the layout lens. This module does not
import ``pcb``.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import ViaProtection
from fenolite.model.design import Design

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED,
    hypotheses=(
        "H-K-VIAPROT-FORMS",
        "H-K-VIAPROT-MASK",
        "H-K-VIAPROT-NINE",
        "H-K-VIAPROT-UPGRADE",
        "H-K-VIAPROT-OUTPUTS",
    ),
)
FEATURES: tuple[str, ...] = ("tenting", "capping", "covering", "plugging", "filling")
"""The protection children of a via, in the order KiCad 10 writes them."""
SETUP_ORDER: tuple[str, ...] = ("tenting", "covering", "plugging", "capping", "filling")
"""The protection children of ``setup``, in the order KiCad 10 writes them."""
SIDES: tuple[str, ...] = ("front", "back")
FEATURE_FIELDS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "tenting": ("tenting_front", "tenting_back"),
        "capping": ("capping",),
        "covering": ("covering_front", "covering_back"),
        "plugging": ("plugging_front", "plugging_back"),
        "filling": ("filling",),
    }
)
"""Feature → the fields of ``ViaProtection`` it holds (front, then back, for a feature with sides)."""
FIELDS: tuple[str, ...] = tuple(f.name for f in dataclasses.fields(ViaProtection))
SUPPORT: Mapping[str, frozenset[int]] = MappingProxyType(
    {
        "tenting": frozenset({9, 10}),
        "covering": frozenset({10}),
        "plugging": frozenset({10}),
        "capping": frozenset({10}),
        "filling": frozenset({10}),
    }
)
"""Feature → the majors whose format holds it."""
KICAD_DEFAULT = ViaProtection(True, True, False, False, False, False, False, False)
"""What both majors give a board whose ``setup`` holds no protection child: tented on both sides."""
NONE_KEY = "protection_none"
"""The pair of a via's ``kicad`` bag that names the children its source holds with ``none`` values only."""
TOO_NEW = "kicad.board.via-protection-too-new"
OVERRIDDEN = "kicad.via.protection-overridden"
FORCED = "kicad.via.protection-forced"
NOT_EXPORTED = "kicad.via.protection-not-exported"
WRITE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({TOO_NEW: "error"})
ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {FORCED: "warning", OVERRIDDEN: "info", NOT_EXPORTED: "info"}
)
"""The codes of the layout lens and of the build (layout-lens, "Via protection defaults across rebuilds")."""
SETUP_WHERE = "setup"
OVERRIDDEN_HINT = (
    "lock the default in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout"
)
NOT_EXPORTED_HINT = (
    "set the feature on the vias themselves with protection= (Design.via, via_step, Design.stitch), "
    "or state it in the fabrication notes"
)
_WORDS: Mapping[str, bool | None] = MappingProxyType({"yes": True, "no": False, "none": None})
_AFTER: tuple[str, ...] = ("allow_soldermask_bridges_in_footprints", "pad_to_mask_clearance")

Values = tuple[bool | None, ...]


def effective_default(default: ViaProtection | None) -> ViaProtection:
    """``default`` with ``None``, whole or per field, replaced by KiCad's own default."""
    if default is None:
        return KICAD_DEFAULT
    return ViaProtection(
        *(getattr(KICAD_DEFAULT, name) if getattr(default, name) is None else getattr(default, name)
          for name in FIELDS)
    )  # fmt: skip


def effective(protection: ViaProtection, default: ViaProtection | None) -> ViaProtection:
    """The eight booleans a via gets: its own values, and the board's effective default for ``None``."""
    board = effective_default(default)
    return ViaProtection(
        *(getattr(board, name) if getattr(protection, name) is None else getattr(protection, name)
          for name in FIELDS)
    )  # fmt: skip


def values_of(protection: ViaProtection, feature: str) -> Values:
    """The values of one feature, front then back for a feature with sides."""
    return tuple(getattr(protection, name) for name in FEATURE_FIELDS[feature])


def _word(value: bool | None) -> Atom:
    return Atom.symbol("none" if value is None else "yes" if value else "no")


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), tuple(children))


def ten_node(feature: str, values: Values) -> Node:
    """The 10.0 child of one feature: ``(tenting (front V) (back V))`` or ``(capping V)``."""
    if len(values) == 2:
        return _node(feature, *(_node(side, _word(v)) for side, v in zip(SIDES, values, strict=True)))
    return _node(feature, _word(values[0]))


def nine_node(front: bool, back: bool) -> Node:
    """The 9.0 ``tenting`` child: the tented sides, or ``none``."""
    names = [side for side, tented in zip(SIDES, (front, back), strict=True) if tented]
    return _node("tenting", *(Atom.symbol(name) for name in names or ["none"]))


def _symbol(node: Node) -> str | None:
    """The single symbol atom of a node without child lists, else ``None``."""
    atoms = node.atoms()
    if node.nodes() or len(atoms) != 1 or atoms[0].kind != AtomKind.SYMBOL:
        return None
    return atoms[0].value


def read_ten(child: Node) -> Values | None:
    """The values of a child in the 10.0 form, a missing side being ``None``; ``None`` when the child is
    not in that form."""
    feature = child.name
    if feature not in FEATURE_FIELDS:
        return None
    if len(FEATURE_FIELDS[feature]) == 1:
        word = _symbol(child)
        return (_WORDS[word],) if word is not None and word in _WORDS else None
    sides = child.nodes()
    if child.atoms() or not sides or len({s.name for s in sides}) != len(sides):
        return None
    found: dict[str, bool | None] = {}
    for side in sides:
        word = _symbol(side)
        if side.name not in SIDES or word is None or word not in _WORDS:
            return None
        found[side.name] = _WORDS[word]
    return tuple(found.get(side) for side in SIDES)


def read_nine(child: Node) -> tuple[bool, bool] | None:
    """The tented sides of a ``tenting`` child in the 9.0 form (``front``, ``back``, both, ``none`` or no
    atom); ``None`` when the child is not in that form."""
    if child.name != "tenting" or child.nodes():
        return None
    atoms = child.atoms()
    names = [a.value for a in atoms]
    if any(a.kind != AtomKind.SYMBOL for a in atoms) or len(set(names)) != len(names):
        return None
    if names == ["none"] or not names:
        return False, False
    if not set(names) <= set(SIDES):
        return None
    return "front" in names, "back" in names


def read_child(child: Node, *, major: int) -> Values | None:
    """The values a board of ``major`` gives one protection child of a via; ``None`` for a child that the
    forms of that major do not read. A 9.0 child names its tented sides: in a board of major 9 the other
    sides are ``False``, in a board of major 10 they are ``None``, as each KiCad reads them."""
    if major < 10:
        return read_nine(child)
    ten = read_ten(child)
    if ten is not None:
        return ten
    nine = read_nine(child)
    return None if nine is None else tuple(True if tented else None for tented in nine)


@dataclass(frozen=True)
class ViaRead:
    """What the protection children of a via say: the value, and the heads of the children that the
    source holds in the 10.0 form with ``none`` values only."""

    value: ViaProtection
    none_written: frozenset[str] = frozenset()


def project_via(children: Iterable[Node | Atom], *, major: int) -> ViaRead:
    """The protection of a via from its children, in the form of a board of ``major``. The first child of
    each head counts; a child that no form reads leaves its fields ``None``."""
    found: dict[str, bool | None] = {}
    seen: set[str] = set()
    none_written: set[str] = set()
    for child in children:
        if not isinstance(child, Node) or child.name not in FEATURE_FIELDS or child.name in seen:
            continue
        seen.add(child.name)
        values = read_child(child, major=major)
        if values is None:
            continue
        found.update(zip(FEATURE_FIELDS[child.name], values, strict=True))
        if major >= 10 and child == ten_node(child.name, (None,) * len(values)):
            none_written.add(child.name)
    return ViaRead(ViaProtection(**found), frozenset(none_written))


def emit_via(
    protection: ViaProtection,
    *,
    major: int,
    default: ViaProtection | None = None,
    none_written: Collection[str] = frozenset(),
) -> dict[str, Node]:
    """Feature → the child a via of ``protection`` holds in a board of ``major``.

    For major 10 a child is written when one of its values is not ``None``, with both sides, and a child
    named in ``none_written`` is written with ``none`` values while its values stay ``None``. For major 9
    only ``tenting`` is written, as the list of the tented sides: nothing when both sides are ``None``, and
    a side that is ``None`` beside a stated one takes its value from ``effective_default(default)``, so
    that KiCad 9 plots what the model means."""
    out: dict[str, Node] = {}
    if major < 10:
        front, back = protection.tenting_front, protection.tenting_back
        if front is None and back is None:
            return out
        board = effective_default(default)
        front = board.tenting_front if front is None else front
        back = board.tenting_back if back is None else back
        assert front is not None and back is not None
        out["tenting"] = nine_node(front, back)
        return out
    for feature in FEATURES:
        values = values_of(protection, feature)
        if any(v is not None for v in values) or feature in none_written:
            out[feature] = ten_node(feature, values)
    return out


def too_new(protection: ViaProtection | None) -> tuple[str, ...]:
    """The fields of covering, plugging, capping and filling that are ``True``: what a KiCad 9 board
    cannot hold."""
    if protection is None:
        return ()
    return tuple(
        name
        for feature in SETUP_ORDER
        if 9 not in SUPPORT[feature]
        for name in FEATURE_FIELDS[feature]
        if getattr(protection, name) is True
    )


def too_new_message(what: str, fields: Sequence[str]) -> str:
    listed = ", ".join(fields)
    return (
        f"{what} holds {listed} = True, which a KiCad 9 board cannot hold: covering, plugging, capping and "
        "filling exist from KiCad 10; build for target 10, or clear the value"
    )


# --- the board default --------------------------------------------------------------------------------


def project_setup(setup: Node | None, *, major: int) -> ViaProtection | None:
    """The default protection that the ``setup`` node of a board of ``major`` states, or ``None`` when it
    holds no protection child. ``tenting`` is read in the 10.0 form or in the 9.0 form (the named sides
    ``True``, the others ``False``, on boards of either major); covering, plugging, capping and filling
    are read on boards of major 10 only. An absent child leaves its fields ``None``."""
    if setup is None:
        return None
    found: dict[str, bool | None] = {}
    seen: set[str] = set()
    for child in setup.nodes():
        feature = child.name
        if feature not in FEATURE_FIELDS or feature in seen:
            continue
        seen.add(feature)
        values: Values | None = read_ten(child) if major >= 10 or feature == "tenting" else None
        if values is None and feature == "tenting":
            values = read_nine(child)
        if values is not None:
            found.update(zip(FEATURE_FIELDS[feature], values, strict=True))
    return ViaProtection(**found) if seen else None


def setup_children(default: ViaProtection | None, *, major: int) -> tuple[Node, ...]:
    """The protection children of ``setup`` for a board default: for major 10 the five children with the
    values of ``effective_default`` (``yes`` or ``no``), for major 9 the 9.0 ``tenting`` child."""
    board = effective_default(default)
    if major < 10:
        assert board.tenting_front is not None and board.tenting_back is not None
        return (nine_node(board.tenting_front, board.tenting_back),)
    return tuple(ten_node(feature, values_of(board, feature)) for feature in SETUP_ORDER)


def rewrite_setup(setup: Node, default: ViaProtection | None, *, major: int) -> Node:
    """``setup`` with its protection children replaced, in place, by ``setup_children(default)``, or
    removed for a ``default`` of ``None``. A child that the fragment lacks is inserted after the last
    protection child it holds; when it holds none, after ``allow_soldermask_bridges_in_footprints``, else
    after ``pad_to_mask_clearance``, else first. Every other child stays at its place."""
    new = {} if default is None else {child.name: child for child in setup_children(default, major=major)}
    children: list[Node | Atom] = []
    last = -1
    for child in setup.children:
        if isinstance(child, Node) and child.name in FEATURE_FIELDS:
            replacement = new.pop(child.name, None)
            if replacement is None:
                continue
            children.append(replacement)
            last = len(children)
        else:
            children.append(child)
    if new:
        if last < 0:
            heads = [c.name if isinstance(c, Node) else None for c in children]
            anchor = next((head for head in _AFTER if head in heads), None)
            if anchor is not None:
                last = heads.index(anchor) + 1
            else:
                last = next((k for k, c in enumerate(children) if isinstance(c, Node)), len(children))
        children[last:last] = list(new.values())
    return setup.with_children(children)


# --- the layout lens ------------------------------------------------------------------------------

DefaultSource = Literal["script", "board"]


@dataclass(frozen=True)
class DefaultMerge:
    """The default a build writes: the decided value, whose it is, and the codes of the decision."""

    default: ViaProtection | None
    source: DefaultSource | None
    issues: tuple[Issue, ...] = ()


def first_difference(script: ViaProtection | None, board: ViaProtection | None) -> str:
    """The first field in which two defaults differ in effect, with both values."""
    ours, theirs = effective_default(script), effective_default(board)
    for name in FIELDS:
        if getattr(ours, name) != getattr(theirs, name):
            return f"{name} is {getattr(ours, name)} in the script and {getattr(theirs, name)} on the board"
    return ""


def merge_default(script: ViaProtection | None, board: ViaProtection | None, *, locked: bool) -> DefaultMerge:
    """Decide between the default of a design script and the projected one of an existing board
    (layout-lens, "Via protection defaults across rebuilds"). Pure."""
    if script is None:
        return DefaultMerge(board, "board" if board is not None else None)
    if board is None:
        return DefaultMerge(script, "script")
    if effective_default(script) == effective_default(board):
        return DefaultMerge(board, "board")
    what = first_difference(script, board)
    if locked:
        message = f"the locked via protection default of the script replaced the board's: {what}"
        issue = Issue(FORCED, ISSUE_CODES[FORCED], message, where=SETUP_WHERE)
        return DefaultMerge(script, "script", (issue,))
    message = f"the board's via protection default is kept; the script's differs from it: {what}"
    issue = Issue(OVERRIDDEN, ISSUE_CODES[OVERRIDDEN], message, where=SETUP_WHERE, hint=OVERRIDDEN_HINT)
    return DefaultMerge(board, "board", (issue,))


# --- reports ------------------------------------------------------------------------------------------


def _by_default(design: Design) -> tuple[dict[str, int], dict[str, int]]:
    """Per field: the vias whose effective value is ``True``, and how many of them take it from the
    board default, their own value being ``None``."""
    board = design.board
    counts = dict.fromkeys(FIELDS, 0)
    inherited = dict.fromkeys(FIELDS, 0)
    if board is None:
        return counts, inherited
    default = effective_default(board.via_protection)
    for via in board.vias:
        for name in FIELDS:
            own = getattr(via.protection, name)
            if own is True or (own is None and getattr(default, name) is True):
                counts[name] += 1
                inherited[name] += own is None
    return counts, inherited


def summary(design: Design) -> dict[str, object]:
    """``result.via_protection`` of ``fenolite inspect`` for a KiCad board: the effective default with its
    source (``board`` when the board states one, ``kicad`` otherwise), and per field the number of vias
    whose effective value is ``True`` and how many of those take it from the default."""
    board = design.board
    stated = board.via_protection if board is not None else None
    default = effective_default(stated)
    counts, inherited = _by_default(design)
    return {
        "default": {
            "source": "board" if stated is not None else "kicad",
            **{name: getattr(default, name) for name in FIELDS},
        },
        "effective": counts,
        "by_default": inherited,
    }


def not_exported(design: Design) -> Issue | None:
    """One ``kicad.via.protection-not-exported`` when vias take a covering, plugging, capping or filling
    of ``True`` from the board default only: ``kicad-cli`` 10.0.6 writes such a value to no fabrication
    file (``H-K-VIAPROT-OUTPUTS``)."""
    _, inherited = _by_default(design)
    fields = [
        name
        for feature in SETUP_ORDER
        if feature != "tenting"
        for name in FEATURE_FIELDS[feature]
        if inherited[name]
    ]
    if not fields:
        return None
    count = max(inherited[name] for name in fields)
    message = (
        f"{count} via(s) take {', '.join(fields)} = True from the board default only; kicad-cli 10.0.6 "
        "writes a default of covering, plugging, capping or filling to no fabrication file (the drill "
        "side files and IPC-2581 hold only the vias that carry the value themselves)"
    )
    return Issue(NOT_EXPORTED, ISSUE_CODES[NOT_EXPORTED], message, where=SETUP_WHERE, hint=NOT_EXPORTED_HINT)


__all__ = [
    "EVIDENCE",
    "FEATURES",
    "FEATURE_FIELDS",
    "FIELDS",
    "ISSUE_CODES",
    "KICAD_DEFAULT",
    "NONE_KEY",
    "SETUP_ORDER",
    "SUPPORT",
    "WRITE_ISSUE_CODES",
    "DefaultMerge",
    "ViaRead",
    "effective",
    "effective_default",
    "emit_via",
    "first_difference",
    "merge_default",
    "nine_node",
    "not_exported",
    "project_setup",
    "project_via",
    "read_child",
    "read_nine",
    "read_ten",
    "rewrite_setup",
    "setup_children",
    "summary",
    "ten_node",
    "too_new",
    "too_new_message",
    "values_of",
]
