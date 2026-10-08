# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The stack-up of KiCad boards: the ``stackup`` child of ``setup`` (change c0101).

Facts, sources and labels: ``docs/formats/kicad/board.md``, "Stack-up"; measurements:
``docs/evidence/kicad-stackup.md``. The reader (``pcb``) projects the node into ``Board.stackup`` with
``project_stackup`` and keeps ``setup`` as an opaque slot; the writer completes a stack-up from the layer
table (``complete``), writes the node (``stackup_node``) and rewrites the ``setup`` of a read board only
when the model changed (``rewrite_setup``). ``merge_stackup`` decides between the stack-up of a design
script and the one of an existing board for the layout lens. This module does not import ``pcb``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.base import ExtBag
from fenolite.model.board import DielectricKind, Layer, StackKind, StackLayer, Stackup
from fenolite.model.design import PLAIN_DECIMAL, stackup_issues

EVIDENCE = Evidence(
    Level.KICAD_VERIFIED,
    hypotheses=("H-K-STACKUP-JOB", "H-K-STACKUP-COMPLETE", "H-K-STACKUP-DEFAULT", "H-K-STACKUP-RESAVE"),
)
"""The four hypotheses are ``KICAD-VERIFIED``: the job file, completeness and defaults on 9.0.x and 10.0.x,
the re-save on 10.0.x (``docs/formats/kicad/board.md``, "Stack-up")."""
TYPES: Mapping[str, tuple[str, StackKind]] = MappingProxyType(
    {
        "F.SilkS": ("Top Silk Screen", "silkscreen"),
        "F.Paste": ("Top Solder Paste", "solderpaste"),
        "F.Mask": ("Top Solder Mask", "soldermask"),
        "B.Mask": ("Bottom Solder Mask", "soldermask"),
        "B.Paste": ("Bottom Solder Paste", "solderpaste"),
        "B.SilkS": ("Bottom Silk Screen", "silkscreen"),
    }
)
"""Outer layer → the ``type`` text of its row and the kind of its entry, in KiCad's row order (S-0058)."""
COPPER_TYPE = "copper"
"""The ``type`` text of a copper row."""
TOP_ORDER: tuple[str, ...] = ("F.SilkS", "F.Paste", "F.Mask")
BOTTOM_ORDER: tuple[str, ...] = ("B.Mask", "B.Paste", "B.SilkS")
ROW_CHILDREN: tuple[str, ...] = ("type", "color", "thickness", "material", "epsilon_r", "loss_tangent")
"""The children of a row, in the order KiCad writes them."""
KEPT_TAIL: tuple[str, ...] = ("edge_connector", "castellated_pads", "edge_plating")
"""Children of the node that the model does not hold and that a rewritten node keeps."""
UNUSED = "kicad.board.stackup-unused"
UNMODELLED = "kicad.board.stackup-unmodelled"
THICKNESS = "kicad.board.stackup-thickness"
INVALID = "kicad.board.stackup-invalid"
REWRITTEN = "kicad.board.stackup-rewritten"
READ_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {UNUSED: "warning", UNMODELLED: "info", THICKNESS: "warning"}
)
WRITE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType({INVALID: "error", REWRITTEN: "info"})
MERGE_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {"kicad.stackup.forced": "warning", "kicad.stackup.overridden": "info"}
)
WHERE = "/kicad_pcb/setup[0]/stackup[0]"
UNUSED_HINT = (
    "KiCad's job file states no thickness for such a board; complete the stack-up in KiCad's Board Setup"
)
OVERRIDDEN_HINT = (
    "lock the stack-up in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout"
)
_DIELECTRIC_KINDS: tuple[DielectricKind, ...] = ("core", "prepreg")
_COPPER_NAME = ("F.Cu", "B.Cu")


def copper_names(layers: Sequence[Layer]) -> tuple[str, ...]:
    """The names of the copper layers of a layer table, in ordinal order."""
    return tuple(la.name for la in sorted(layers, key=lambda la: la.ordinal) if la.kind == "copper")


def _is_layer_name(name: str) -> bool:
    """True for a name that only a layer row may carry: an outer layer of ``TYPES`` or a copper layer."""
    if name in TYPES or name in _COPPER_NAME:
        return True
    return name.startswith("In") and name.endswith(".Cu") and name[2:-3].isdigit()


def _row_name(row: Node) -> str:
    first = row.children[0] if row.children else None
    return first.value if isinstance(first, Atom) else ""


def _sheets(row: Node) -> list[list[Node]]:
    """The children of a row, split at its ``addsublayer`` atoms: one list per sheet."""
    sheets: list[list[Node]] = [[]]
    for child in row.children[1:]:
        if isinstance(child, Atom):
            if child.value == "addsublayer":
                sheets.append([])
        else:
            sheets[-1].append(child)
    return sheets


def _text(children: Sequence[Node], head: str) -> str | None:
    for child in children:
        if child.name == head:
            atoms = child.atoms()
            return atoms[0].value if atoms else ""
    return None


class _NotExact(Exception):
    pass


_Found = tuple[str, StackKind, DielectricKind | None, str | None, list[Node]]


def _thickness(children: Sequence[Node], name: str, *, required: bool) -> int:
    for child in children:
        if child.name == "thickness":
            atoms = child.atoms()
            if not atoms or atoms[0].kind != AtomKind.NUMBER:
                raise _NotExact(f"row {name!r} holds a thickness that is not a number")
            try:
                return atoms[0].to_nm(exact=True)
            except ValueError as error:
                raise _NotExact(f"row {name!r}: {error}") from error
    if required:
        raise _NotExact(f"row {name!r} holds no thickness")
    return 0


def _decimal(children: Sequence[Node], head: str, name: str, *, positive: bool) -> str:
    for child in children:
        if child.name == head:
            atoms = child.atoms()
            text = atoms[0].text if atoms else ""
            if not PLAIN_DECIMAL.fullmatch(text) or (positive and not text.strip("0.")):
                what = "a plain decimal above 0" if positive else "a plain decimal"
                raise _NotExact(f"row {name!r} holds the {head} {text!r}, which is not {what}")
            return text
    return ""


def _incomplete(node: Node, layers: Sequence[Layer]) -> str | None:
    """Why KiCad does not use ``node`` for the board of ``layers`` (``H-K-STACKUP-COMPLETE``), or None."""
    table = {la.name for la in layers}
    copper = copper_names(layers)
    expected = [name for name in TYPES if name in table] + list(copper)
    rows = node.nodes("layer")
    named = [_row_name(r) for r in rows if _row_name(r) in table or _is_layer_name(_row_name(r))]
    for name in named:
        if named.count(name) > 1:
            return f"layer {name!r} has {named.count(name)} rows"
        if name not in expected:
            return f"row {name!r} is named after a layer that is not a stack-up layer of the board"
    for name in expected:
        if name not in named:
            return f"layer {name!r} has no row"
    for row in rows:
        name = _row_name(row)
        if name in expected:
            wanted = TYPES[name][0] if name in TYPES else COPPER_TYPE
            found = _text(_sheets(row)[0], "type")
            if found != wanted:
                return f"row {name!r} has the type {found!r}, not {wanted!r}"
    if tuple(n for n in named if n in copper) != copper:
        return f"the copper rows are not in the order of the layer table {list(copper)}"
    gap = 0
    above: str | None = None
    for row in rows:
        name = _row_name(row)
        if name in copper:
            if above is not None and gap != 1:
                return f"{gap} dielectric rows lie between {above!r} and {name!r}, not one"
            above, gap = name, 0
        elif name not in expected:
            gap += 1
        elif above is not None and above != copper[-1]:
            return f"row {name!r} lies between the copper rows"
    return None


def _report(issues: list[Issue] | None, code: str, message: str, hint: str = "") -> None:
    if issues is not None:
        issues.append(Issue(code, READ_ISSUE_CODES[code], message, where=WHERE, hint=hint))


def project_stackup(
    setup: Node, layers: Sequence[Layer], *, issues: list[Issue] | None = None
) -> Stackup | None:
    """``Board.stackup`` for the ``stackup`` child of ``setup`` (kicad-file-backend, "Stack-up on boards").

    ``None`` without the child; ``None`` with ``kicad.board.stackup-unused`` for a node that KiCad does not
    use; ``None`` with ``kicad.board.stackup-unmodelled`` for a complete node whose values the model
    cannot hold exactly."""
    node = setup.find("stackup")
    if node is None:
        return None
    why = _incomplete(node, layers)
    if why is not None:
        _report(issues, UNUSED, f"the stack-up of the board is not complete: {why}", UNUSED_HINT)
        return None
    copper = copper_names(layers)
    try:
        entries = _entries(node, copper)
    except _NotExact as error:
        _report(issues, UNMODELLED, f"the stack-up is kept as written and not modelled: {error}")
        return None
    finish = _text(node.nodes(), "copper_finish") or ""
    constraints = node.find("dielectric_constraints")
    return Stackup(
        id=derived_id("stk", "kicad", "stackup"),
        layers=tuple(entries),
        finish="" if finish == "None" else finish,
        impedance_controlled=constraints is not None and [a.value for a in constraints.atoms()] == ["yes"],
    )


def _entries(node: Node, copper: Sequence[str]) -> list[StackLayer]:
    top: dict[str, list[Node]] = {}
    bottom: dict[str, list[Node]] = {}
    middle: list[_Found] = []
    seen_copper = 0
    for row in node.nodes("layer"):
        name = _row_name(row)
        sheets = _sheets(row)
        if name in TYPES:
            (top if name in TOP_ORDER else bottom)[name] = sheets[0]
        elif name in copper:
            seen_copper += 1
            middle.append((name, "copper", None, None, sheets[0]))
        else:
            if seen_copper == 0 or seen_copper == len(copper):
                where = "above the first" if seen_copper == 0 else "below the last"
                raise _NotExact(f"dielectric row {name!r} lies {where} copper row")
            written = _text(sheets[0], "type")
            stated: DielectricKind | None = None
            for known in _DIELECTRIC_KINDS:
                if written == known:
                    stated = known
            other = written if stated is None and written else None
            middle.extend((name, "dielectric", stated, other, sheet) for sheet in sheets)
    found: list[_Found] = []
    for n in TOP_ORDER:
        if n in top:
            found.append((n, TYPES[n][1], None, None, top[n]))
    found += middle
    for n in BOTTOM_ORDER:
        if n in bottom:
            found.append((n, TYPES[n][1], None, None, bottom[n]))
    entries: list[StackLayer] = []
    for k, (name, kind, dielectric_kind, other, children) in enumerate(found):
        entries.append(
            StackLayer(
                id=derived_id("sly", "kicad", f"stack:{k}"),
                ext={"kicad": ExtBag(None, (("type", other),))} if other else {},
                name=name,
                kind=kind,
                thickness=_thickness(children, name, required=kind in ("copper", "dielectric", "soldermask")),
                material=_text(children, "material") or "",
                epsilon_r=_decimal(children, "epsilon_r", name, positive=True),
                loss_tangent=_decimal(children, "loss_tangent", name, positive=False),
                dielectric_kind=dielectric_kind,
                color=_text(children, "color") or "",
            )
        )
    return entries


def _type_pair(entry: StackLayer) -> str:
    bag = entry.ext.get("kicad")
    return next((v for k, v in bag.payload if k == "type"), "") if bag is not None else ""


def values(stackup: Stackup | None) -> tuple[object, ...] | None:
    """What two stack-ups are compared by: every value of the stack-up and of its entries, without ids,
    provenance and every bag pair but ``type``."""
    if stackup is None:
        return None
    rows = tuple(
        (e.name, e.kind, e.thickness, e.material, e.epsilon_r, e.loss_tangent, e.dielectric_kind, e.color,
         _type_pair(e))
        for e in stackup.layers
    )  # fmt: skip
    return (stackup.finish, stackup.impedance_controlled, rows)


def first_difference(a: Stackup, b: Stackup) -> str:
    """The first entry or value in which two stack-ups differ by ``values`` (``""`` when they are equal)."""
    for k, (x, y) in enumerate(zip(a.layers, b.layers, strict=False)):
        if values(Stackup(id=a.id, layers=(x,))) != values(Stackup(id=a.id, layers=(y,))):
            if x.name != y.name:
                return f"entry {k}: {x.name!r} and {y.name!r}"
            fields = (
                "kind",
                "thickness",
                "material",
                "epsilon_r",
                "loss_tangent",
                "dielectric_kind",
                "color",
            )
            field = next((f for f in fields if getattr(x, f) != getattr(y, f)), "type")
            return f"{x.name!r}: {field} {getattr(x, field, '')!r} and {getattr(y, field, '')!r}"
    if len(a.layers) != len(b.layers):
        return f"{len(a.layers)} and {len(b.layers)} entries"
    if a.finish != b.finish:
        return f"finish {a.finish!r} and {b.finish!r}"
    if a.impedance_controlled != b.impedance_controlled:
        return f"impedance_controlled {a.impedance_controlled} and {b.impedance_controlled}"
    return ""


# --- writing --------------------------------------------------------------------------------------


def complete(stackup: Stackup, layers: Sequence[Layer]) -> Stackup:
    """``stackup`` with one entry of thickness 0 for each silkscreen, paste and mask layer of ``layers``
    that it lacks, at its place; nothing else changes, and a stack-up that lacks none is returned as it
    is."""
    table = {la.name for la in layers}
    held = {e.name for e in stackup.layers}
    missing = [name for name in TYPES if name in table and name not in held]
    copper = [k for k, e in enumerate(stackup.layers) if e.kind == "copper"]
    if not missing or not copper:
        return stackup
    top = list(stackup.layers[: copper[0]])
    middle = list(stackup.layers[copper[0] : copper[-1] + 1])
    bottom = list(stackup.layers[copper[-1] + 1 :])
    for part, order in ((top, TOP_ORDER), (bottom, BOTTOM_ORDER)):
        for name in order:
            if name not in missing:
                continue
            rank = order.index(name)
            at = next(
                (k for k, e in enumerate(part) if e.name in order and order.index(e.name) > rank), len(part)
            )
            added = StackLayer(
                id=derived_id("sly", "kicad", f"stack-added:{stackup.id}:{name}"),
                name=name,
                kind=TYPES[name][1],
                thickness=0,
            )
            part.insert(at, added)
    return Stackup(
        id=stackup.id,
        native_ids=stackup.native_ids,
        provenance=stackup.provenance,
        ext=stackup.ext,
        layers=(*top, *middle, *bottom),
        finish=stackup.finish,
        impedance_controlled=stackup.impedance_controlled,
    )


def invalid(stackup: Stackup, layers: Sequence[Layer]) -> str | None:
    """Why ``stackup`` cannot be written as a complete node for the table ``layers``, or None: a
    ``model.stackup-*`` finding, or copper entries that are not the table's copper layers in order."""
    copper = copper_names(layers)
    found = stackup_issues(stackup, copper)
    if found:
        return f"{found[0].code}: {found[0].message}"
    names = tuple(e.name for e in stackup.layers if e.kind == "copper")
    if names != copper:
        return f"the copper entries {list(names)} are not the copper layers of the board {list(copper)}"
    return None


def _number(text: str) -> Atom:
    return Atom(text, AtomKind.NUMBER)


def _sheet_children(entry: StackLayer, *, with_thickness: bool) -> list[Node]:
    out: list[Node] = []
    if entry.color:
        out.append(Node(Atom.symbol("color"), (Atom.string(entry.color),)))
    if with_thickness:
        out.append(Node(Atom.symbol("thickness"), (Atom.from_nm(entry.thickness),)))
    if entry.material:
        out.append(Node(Atom.symbol("material"), (Atom.string(entry.material),)))
    if entry.epsilon_r:
        out.append(Node(Atom.symbol("epsilon_r"), (_number(entry.epsilon_r),)))
    if entry.loss_tangent:
        out.append(Node(Atom.symbol("loss_tangent"), (_number(entry.loss_tangent),)))
    return out


def _row_type(entry: StackLayer, top: bool) -> str:
    if entry.kind == "copper":
        return COPPER_TYPE
    if entry.kind == "dielectric":
        return entry.dielectric_kind or _type_pair(entry)
    if entry.name in TYPES:
        return TYPES[entry.name][0]
    order = TOP_ORDER if top else BOTTOM_ORDER
    return next(TYPES[name][0] for name in order if TYPES[name][1] == entry.kind)


def stackup_node(stackup: Stackup, layers: Sequence[Layer]) -> Node:
    """The ``stackup`` node of ``complete(stackup, layers)``: one row per entry, the consecutive dielectric
    entries of a gap joined by ``addsublayer``, then ``copper_finish`` and ``dielectric_constraints``."""
    done = complete(stackup, layers)
    rows: list[Node | Atom] = []
    seen_copper = False
    previous: StackLayer | None = None
    for entry in done.layers:
        thick = entry.kind in ("copper", "dielectric", "soldermask") or entry.thickness != 0
        children = _sheet_children(entry, with_thickness=thick)
        if entry.kind == "dielectric" and previous is not None and previous.kind == "dielectric":
            last = rows[-1]
            assert isinstance(last, Node)
            rows[-1] = last.with_children([*last.children, Atom.symbol("addsublayer"), *children])
        else:
            head: list[Node | Atom] = [Atom.string(entry.name)]
            kind = _row_type(entry, top=not seen_copper)
            if kind:
                head.append(Node(Atom.symbol("type"), (Atom.string(kind),)))
            rows.append(Node(Atom.symbol("layer"), (*head, *children)))
        seen_copper = seen_copper or entry.kind == "copper"
        previous = entry
    rows.append(Node(Atom.symbol("copper_finish"), (Atom.string(done.finish or "None"),)))
    flag = Atom.symbol("yes" if done.impedance_controlled else "no")
    rows.append(Node(Atom.symbol("dielectric_constraints"), (flag,)))
    return Node(Atom.symbol("stackup"), tuple(rows))


def _lost(old: Node) -> tuple[str, ...]:
    """The children of the rows of a replaced node that the model does not hold."""
    lost: list[str] = []
    for child in old.children:
        if isinstance(child, Atom):
            lost.append(child.value)
        elif child.name == "layer":
            name = _row_name(child)
            for part in child.nodes():
                if part.name not in ROW_CHILDREN:
                    lost.append(f"{name}: {part.name}")
                elif len(part.children) > 1:
                    extra = " ".join(c.value if isinstance(c, Atom) else c.name for c in part.children[1:])
                    lost.append(f"{name}: {part.name} {extra}")
        elif child.name not in ("copper_finish", "dielectric_constraints", *KEPT_TAIL):
            lost.append(child.name)
    return tuple(lost)


def rewrite_setup(
    setup: Node, stackup: Stackup | None, layers: Sequence[Layer]
) -> tuple[Node, tuple[str, ...]]:
    """``setup`` with its ``stackup`` child replaced by the node of ``stackup`` (inserted as the first
    child when there is none, removed for ``None``); every other child stays at its place, and a replaced
    node hands its ``edge_connector``, ``castellated_pads`` and ``edge_plating`` on. Also returns the
    children of the replaced rows that the model does not hold."""
    old = setup.find("stackup")
    if stackup is None:
        return setup.with_children(c for c in setup.children if c is not old), ()
    new = stackup_node(stackup, layers)
    if old is None:
        first = next((k for k, c in enumerate(setup.children) if isinstance(c, Node)), len(setup.children))
        return setup.with_children([*setup.children[:first], new, *setup.children[first:]]), ()
    kept = [c for c in old.nodes() if c.name in KEPT_TAIL]
    new = new.with_children([*new.children, *kept])
    return setup.with_children(new if c is old else c for c in setup.children), _lost(old)


# --- the layout lens ------------------------------------------------------------------------------

StackupSource = Literal["script", "board"]


@dataclass(frozen=True)
class StackupMerge:
    """The stack-up a build writes: the decided value, whose it is, and the codes of the decision."""

    stackup: Stackup | None
    source: StackupSource | None
    issues: tuple[Issue, ...] = ()


def merge_stackup(
    built: Stackup | None, board: Stackup | None, *, layers: Sequence[Layer], locked: bool
) -> StackupMerge:
    """Decide between the stack-up of a design script (``built``) and the projected one of an existing
    board (layout-lens, "Stack-up across rebuilds"). Pure."""
    if built is None:
        return StackupMerge(board, "board" if board is not None else None)
    script = complete(built, layers)
    if board is None:
        return StackupMerge(script, "script")
    if values(script) == values(board):
        return StackupMerge(board, "script")
    what = first_difference(script, board)
    if locked:
        code = "kicad.stackup.forced"
        message = f"the locked stack-up of the script replaced the board's, which differed: {what}"
        return StackupMerge(
            script, "script", (Issue(code, MERGE_ISSUE_CODES[code], message, where="stackup"),)
        )
    code = "kicad.stackup.overridden"
    message = f"the board's stack-up is kept; the script's differs from it: {what}"
    issue = Issue(code, MERGE_ISSUE_CODES[code], message, where="stackup", hint=OVERRIDDEN_HINT)
    return StackupMerge(board, "board", (issue,))


__all__ = [
    "COPPER_TYPE",
    "EVIDENCE",
    "MERGE_ISSUE_CODES",
    "READ_ISSUE_CODES",
    "ROW_CHILDREN",
    "TYPES",
    "WRITE_ISSUE_CODES",
    "StackupMerge",
    "complete",
    "copper_names",
    "first_difference",
    "invalid",
    "merge_stackup",
    "project_stackup",
    "rewrite_setup",
    "stackup_node",
    "values",
]
