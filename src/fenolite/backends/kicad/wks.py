# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad drawing-sheet files (``.kicad_wks``): reader, RT1 rebuild and writer (change c0012).

Facts: ``docs/formats/kicad/worksheet.md``. A read sheet keeps what the model does not hold as slots in
its ``kicad`` extension bag, one slot list per relative locator: ``.`` for the root's children,
``setup[0]`` for the setup, ``item[k]`` for the k-th modelled item and ``item[k]/font[0]`` for its font.
Each modelled child is re-emitted with this module's emitter and compared with the original; a child
that is not reproduced tree-equal becomes an opaque slot whose value stays projected into the model.
On write such a slot is re-emitted verbatim while its projection equals the model, and from the model
otherwise. Header children are modelled slots whose source fragments ride in the bag, so ``rebuild``
gives the source tree back while ``write`` writes Fenolite's own header.
"""

from __future__ import annotations

import base64
import binascii
import os
import re
import string
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import MappingProxyType

from fenolite.backends.base import WriteResult
from fenolite.backends.kicad import versions
from fenolite.backends.kicad._libread import load_source
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse_fragment, tree_equal
from fenolite.backends.kicad.slots import from_ext_all, rebuild, to_ext
from fenolite.backends.kicad.versions import DEFAULT_TARGET, FileKind, LossyWriteError
from fenolite.core.errors import FormatError, Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.core.units import Nm
from fenolite.model.base import ExtBag, Modeled, Opaque, Slot
from fenolite.model.presentation import (
    PARAM_NAME,
    Corner,
    DrawingSheet,
    PageScope,
    SheetBitmap,
    SheetItem,
    SheetPoint,
    SheetRepeat,
    SheetSetup,
    SheetShape,
    SheetText,
    SheetToken,
    join_tokens,
    split_tokens,
)

Source = str | os.PathLike[str] | Node
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-WKS-CORNER",))
WRITE_EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-WKS-CORNER",))
BAG = "kicad"
UM = 1_000
PPM = 1_000_000

ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "kicad.wks.kept-opaque": "info",
        "kicad.wks.legacy-root": "info",
        "kicad.wks.uninventoried": "error",
        "kicad.wks.unknown-value": "error",
        "kicad.wks.below-resolution": "error",
        "kicad.wks.param-reserved": "error",
        "kicad.wks.literal-variable": "error",
        "kicad.wks.dropped-item": "warning",
    }
)

KICAD_TOKENS: Mapping[str, str] = MappingProxyType(
    {
        "title": "${TITLE}",
        "doc_id": "${COMMENT1}",
        "revision": "${REVISION}",
        "sheet": "${#}",
        "sheets": "${##}",
        "date": "${ISSUE_DATE}",
        "organization": "${COMPANY}",
        "responsible": "${COMMENT2}",
        "approver": "${COMMENT3}",
        "filename": "${FILENAME}",
        "paper": "${PAPER}",
    }
)
"""Neutral token → KiCad variable; ``{param:X}`` → ``${X}``."""
_INVERSE = {kicad[2:-1]: name for name, kicad in KICAD_TOKENS.items()}
RESERVED_VARIABLES: frozenset[str] = frozenset(
    {
        "KICAD_VERSION",
        "#",
        "##",
        *(f"COMMENT{n}" for n in range(1, 10)),
        "COMPANY",
        "FILENAME",
        "ISSUE_DATE",
        "LAYER",
        "PAPER",
        "REVISION",
        "SHEETNAME",
        "SHEETPATH",
        "TITLE",
        "KIPRJMOD",
    }
)
"""The text variables of S-0075 and ``KIPRJMOD`` (S-0045): never a user parameter."""

CORNER_ATOMS: Mapping[Corner, str] = MappingProxyType(
    {"lt": "ltcorner", "lb": "lbcorner", "rt": "rtcorner", "rb": "rbcorner"}
)
SCOPE_ATOMS: Mapping[PageScope, str] = MappingProxyType(
    {"first_only": "page1only", "not_first": "notonpage1"}
)
VALUE_ATOMS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "corner": frozenset(CORNER_ATOMS.values()),
        "option": frozenset(SCOPE_ATOMS.values()),
        "justify": frozenset({"left", "center", "right", "top", "bottom"}),
        "font": frozenset({"bold", "italic"}),
    }
)
"""The value atoms KiCad loads (``H-K-WKS-VALUES``): corners of the point heads, ``option``, ``justify``
and the ``font`` flags."""
_CORNER_OF: Mapping[str, Corner] = MappingProxyType({atom: corner for corner, atom in CORNER_ATOMS.items()})
_SCOPE_OF: Mapping[str, PageScope] = MappingProxyType({atom: scope for scope, atom in SCOPE_ATOMS.items()})
POINT_HEADS = frozenset({"start", "end", "pos"})
CANONICAL_ORDER: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "kicad_wks": ("version", "generator", "generator_version", "setup", "items"),
        "setup": (
            "textsize",
            "linewidth",
            "textlinewidth",
            "left_margin",
            "right_margin",
            "top_margin",
            "bottom_margin",
        ),
        "line": ("name", "start", "end", "linewidth", "repeat", "incrx", "incry", "comment", "option"),
        "rect": ("name", "start", "end", "linewidth", "repeat", "incrx", "incry", "comment", "option"),
        "tbtext": (
            "text",
            "name",
            "pos",
            "font",
            "justify",
            "rotate",
            "maxlen",
            "maxheight",
            "repeat",
            "incrx",
            "incry",
            "incrlabel",
            "comment",
            "option",
        ),
        "bitmap": ("name", "pos", "scale", "repeat", "incrx", "incry", "comment", "option", "pngdata"),
        "font": ("flag", "size"),
    }
)
"""Child order per head (``worksheet.md``, "Fenolite choices"); the field names are the KiCad heads,
plus ``text`` (the text of a ``tbtext``), ``flag`` (a ``font`` flag) and ``items`` (the items)."""
ITEM_HEADS: Mapping[str, type] = MappingProxyType(
    {"line": SheetShape, "rect": SheetShape, "tbtext": SheetText, "bitmap": SheetBitmap}
)
HEADER_HEADS = ("version", "generator", "generator_version")
_SRC = "src:"
_ROOT = "root"
_DATA_ROW = 32


Children = list[Node | Atom]
"""The children a modelled field emits, in order."""


class _Kept(Exception):
    """An item, or a child, that the model cannot hold: kept opaque with ``reason``."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# ------------------------------------------------------------------------------------------- values


def _node(head: str, *children: Node | Atom) -> Node:
    return Node(Atom.symbol(head), tuple(children))


def _mm(nm: Nm) -> Atom:
    return Atom.from_nm(nm)


def _decimal_atom(value: int, scale: int) -> Atom:
    """``value / scale`` as the shortest exact decimal, without exponent."""
    text = format(Decimal(value) / Decimal(scale), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return Atom(text if text not in ("", "-0") else "0", AtomKind.NUMBER)


def _nm(atom: Atom, what: str) -> Nm:
    """A length in nm; ``_Kept`` unless it is a whole number of micrometres (``worksheet.md``)."""
    if atom.kind != AtomKind.NUMBER:
        raise _Kept(f"{what}: {atom.text!r} is not a number")
    try:
        value = atom.to_nm(exact=True)
    except ValueError:
        raise _Kept(f"{what}: {atom.text} mm is not a whole number of micrometres") from None
    if value % UM:
        raise _Kept(f"{what}: {atom.text} mm is not a whole number of micrometres")
    return value


def _scaled(atom: Atom, scale: int, what: str) -> int:
    """A decimal number times ``scale``; ``_Kept`` unless the result is an integer."""
    if atom.kind != AtomKind.NUMBER:
        raise _Kept(f"{what}: {atom.text!r} is not a number")
    try:
        value = Decimal(atom.text) * scale
    except InvalidOperation:
        raise _Kept(f"{what}: {atom.text!r} is not a number") from None
    if value != value.to_integral_value():
        raise _Kept(f"{what}: {atom.text} is not a whole number of {'µdeg' if scale == PPM else 'units'}")
    return int(value)


def _int(atom: Atom, what: str) -> int:
    try:
        return atom.to_int()
    except ValueError:
        raise _Kept(f"{what}: {atom.text!r} is not an integer") from None


def _string(node: Node, what: str) -> str:
    atoms = node.atoms()
    if len(atoms) != 1 or len(node.children) != 1:
        raise _Kept(f"{what}: expected one value")
    return atoms[0].value


def _one(node: Node, what: str) -> Atom:
    atoms = node.atoms()
    if len(atoms) != 1 or len(node.children) != 1:
        raise _Kept(f"{what}: expected one value")
    return atoms[0]


def _point(node: Node) -> SheetPoint:
    if node.nodes():
        raise _Kept(f"{node.name}: unexpected list child")
    atoms = node.atoms()
    if len(atoms) not in (2, 3):
        raise _Kept(f"{node.name}: expected X, Y and an optional corner")
    corner: Corner = "rb"
    if len(atoms) == 3:
        found = _CORNER_OF.get(atoms[2].text)
        if found is None or atoms[2].kind != AtomKind.SYMBOL:
            raise _Kept(f"{node.name}: value atom {atoms[2].text!r} is not a corner")
        corner = found
    return SheetPoint(corner, _nm(atoms[0], node.name), _nm(atoms[1], node.name))


def _point_node(head: str, point: SheetPoint) -> Node:
    extra = () if point.corner == "rb" else (Atom.symbol(CORNER_ATOMS[point.corner]),)
    return _node(head, _mm(point.x), _mm(point.y), *extra)


def _scope(node: Node) -> PageScope:
    atoms = node.atoms()
    if len(atoms) != 1 or node.nodes():
        raise _Kept("option: expected one value")
    found = _SCOPE_OF.get(atoms[0].text)
    if found is None:
        raise _Kept(f"option: value atom {atoms[0].text!r} is not listed")
    return found


# ------------------------------------------------------------------------------------------- texts


def neutral_text(text: str) -> str:
    """A KiCad text as neutral text; ``_Kept`` for KiCad-only variables, malformed ``${`` and legacy
    ``%`` codes (``H-K-WKS-PCT``)."""
    parts: list[str | SheetToken] = []
    literal: list[str] = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == "$" and text[i + 1 : i + 2] == "{":
            end = text.find("}", i + 2)
            if end == -1:
                raise _Kept(f"text {text!r}: malformed '${{'")
            name = text[i + 2 : end]
            if name in _INVERSE:
                token = SheetToken(_INVERSE[name])
            elif name in RESERVED_VARIABLES:
                raise _Kept(f"text {text!r}: KiCad-only variable ${{{name}}}")
            elif PARAM_NAME.fullmatch(name):
                token = SheetToken(name, param=True)
            else:
                raise _Kept(f"text {text!r}: malformed variable ${{{name}}}")
            if literal:
                parts.append("".join(literal))
                literal = []
            parts.append(token)
            i = end + 1
            continue
        if char == "%" and i + 1 < len(text) and text[i + 1] in string.ascii_letters:
            raise _Kept(f"text {text!r}: legacy '%' code")
        literal.append(char)
        i += 1
    if literal:
        parts.append("".join(literal))
    return join_tokens(parts)


_LITERAL_VARIABLE = re.compile(r"\$\{|%[A-Za-z]")


def kicad_text(text: str, where: str, errors: list[Issue]) -> str:
    """The KiCad form of a neutral text; adds ``param-reserved`` and ``literal-variable`` errors."""
    out: list[str] = []
    for part in split_tokens(text):
        if isinstance(part, SheetToken):
            if part.param and part.name in RESERVED_VARIABLES:
                message = f"{{param:{part.name}}} names the reserved KiCad variable ${{{part.name}}}"
                errors.append(_issue("kicad.wks.param-reserved", message, where))
            out.append(f"${{{part.name}}}" if part.param else KICAD_TOKENS[part.name])
        else:
            if _LITERAL_VARIABLE.search(part):
                message = f"literal text {part!r} would be resolved by KiCad as a variable"
                errors.append(_issue("kicad.wks.literal-variable", message, where))
            out.append(part)
    return "".join(out)


def _issue(code: str, message: str, where: str) -> Issue:
    return Issue(code, ISSUE_CODES[code], message, where=where)


# ------------------------------------------------------------------------------------------- emitters


def _repeat_items(repeat: SheetRepeat, *, label: bool) -> dict[str, Children]:
    out: dict[str, Children] = {}
    if repeat.count != 1:
        out["repeat"] = [_node("repeat", Atom.integer(repeat.count))]
    if repeat.step_x:
        out["incrx"] = [_node("incrx", _mm(repeat.step_x))]
    if repeat.step_y:
        out["incry"] = [_node("incry", _mm(repeat.step_y))]
    if label and repeat.label_step != 1:
        out["incrlabel"] = [_node("incrlabel", Atom.integer(repeat.label_step))]
    return out


def _common(item: SheetItem, *, label: bool) -> dict[str, Children]:
    out: dict[str, Children] = {}
    if item.name:
        out["name"] = [_node("name", Atom.string(item.name))]
    out.update(_repeat_items(item.repeat, label=label))
    if item.comment:
        out["comment"] = [_node("comment", Atom.string(item.comment))]
    if item.scope != "all":
        out["option"] = [_node("option", Atom.symbol(SCOPE_ATOMS[item.scope]))]
    return out


def _font_items(item: SheetText) -> dict[str, Children]:
    out: dict[str, Children] = {}
    flags: list[Node | Atom] = [
        Atom.symbol(f) for f, on in (("bold", item.bold), ("italic", item.italic)) if on
    ]
    if flags:
        out["flag"] = flags
    if item.size is not None:
        out["size"] = [_node("size", _mm(item.size[0]), _mm(item.size[1]))]
    return out


def _justify_atoms(item: SheetText) -> list[Atom]:
    atoms: list[Atom] = []
    if item.justify != "left":
        atoms.append(Atom.symbol(item.justify))
    if item.vjustify != "center":
        atoms.append(Atom.symbol(item.vjustify))
    return atoms


def _png_rows(png: str) -> list[Node | Atom]:
    data = base64.b64decode(png)
    hexes = [f"{b:02X}" for b in data]
    return [
        _node("data", Atom.string(" ".join(hexes[i : i + _DATA_ROW])))
        for i in range(0, len(hexes), _DATA_ROW)
    ]


def item_items(item: SheetItem, text: str = "") -> dict[str, Children]:
    """Field → children of a modelled item (``text`` is the KiCad form of a ``SheetText``'s text)."""
    out: dict[str, Children]
    if isinstance(item, SheetShape):
        out = {"start": [_point_node("start", item.start)], "end": [_point_node("end", item.end)]}
        if item.width is not None:
            out["linewidth"] = [_node("linewidth", _mm(item.width))]
        return {**_common(item, label=False), **out}
    if isinstance(item, SheetText):
        out = {
            "text": [Atom.string(text)],
            "pos": [_point_node("pos", item.pos)],
            **_common(item, label=True),
        }
        font = _font_items(item)
        if font:
            out["font"] = [_node("font", *font.get("flag", []), *font.get("size", []))]
        justify = _justify_atoms(item)
        if justify:
            out["justify"] = [_node("justify", *justify)]
        if item.rotation:
            out["rotate"] = [_node("rotate", _decimal_atom(item.rotation, PPM))]
        if item.max_len is not None:
            out["maxlen"] = [_node("maxlen", _mm(item.max_len))]
        if item.max_height is not None:
            out["maxheight"] = [_node("maxheight", _mm(item.max_height))]
        return out
    out = {"pos": [_point_node("pos", item.pos)], **_common(item, label=False)}
    if item.scale_ppm != PPM:
        out["scale"] = [_node("scale", _decimal_atom(item.scale_ppm, PPM))]
    out["pngdata"] = [_node("pngdata", *_png_rows(item.png))]
    return out


def setup_items(setup: SheetSetup) -> dict[str, Children]:
    return {
        "textsize": [_node("textsize", _mm(setup.text_size[0]), _mm(setup.text_size[1]))],
        "linewidth": [_node("linewidth", _mm(setup.line_width))],
        "textlinewidth": [_node("textlinewidth", _mm(setup.text_line_width))],
        "left_margin": [_node("left_margin", _mm(setup.left_margin))],
        "right_margin": [_node("right_margin", _mm(setup.right_margin))],
        "top_margin": [_node("top_margin", _mm(setup.top_margin))],
        "bottom_margin": [_node("bottom_margin", _mm(setup.bottom_margin))],
    }


class _Source:
    """A ``SlotSource`` over a mapping of field → children."""

    def __init__(self, items: Mapping[str, Sequence[Node | Atom]]) -> None:
        self._items = items

    def items(self, field: str) -> Sequence[Node | Atom]:
        return self._items.get(field, ())

    def fields(self) -> Iterable[str]:
        return [f for f, children in self._items.items() if children]


# ------------------------------------------------------------------------------------------- reading


@dataclass
class _ReadItem:
    item: SheetItem
    slots: dict[str, list[Slot]]


_ITEM_FIELDS = frozenset(
    {"name", "start", "end", "pos", "linewidth", "repeat", "incrx", "incry", "incrlabel", "comment", "option",
     "font", "justify", "rotate", "maxlen", "maxheight", "scale", "pngdata"}
)  # fmt: skip
_TEXT_FIELD: frozenset[str] = frozenset({"text"})
_ALLOWED: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "line": frozenset(
            {"name", "start", "end", "linewidth", "repeat", "incrx", "incry", "comment", "option"}
        ),
        "rect": frozenset(
            {"name", "start", "end", "linewidth", "repeat", "incrx", "incry", "comment", "option"}
        ),
        "tbtext": frozenset(CANONICAL_ORDER["tbtext"]) - {"text"},
        "bitmap": frozenset(CANONICAL_ORDER["bitmap"]),
    }
)


def _read_font(node: Node) -> tuple[bool, bool, tuple[Nm, Nm] | None]:
    bold = italic = False
    size: tuple[Nm, Nm] | None = None
    for child in node.children:
        if isinstance(child, Atom):
            if child.kind != AtomKind.SYMBOL or child.text not in VALUE_ATOMS["font"]:
                raise _Kept(f"font: value atom {child.text!r} is not listed")
            if (child.text == "bold" and bold) or (child.text == "italic" and italic):
                raise _Kept(f"font: repeated flag {child.text!r}")
            bold, italic = bold or child.text == "bold", italic or child.text == "italic"
        elif child.name == "size":
            if size is not None:
                raise _Kept("font: repeated size")
            atoms = child.atoms()
            if len(atoms) != 2 or child.nodes():
                raise _Kept("font size: expected width and height")
            size = (_nm(atoms[0], "font size"), _nm(atoms[1], "font size"))
    return bold, italic, size


def _read_justify(node: Node) -> tuple[str, str]:
    h, v = "left", "center"
    if node.nodes():
        raise _Kept("justify: unexpected list child")
    for atom in node.atoms():
        if atom.kind != AtomKind.SYMBOL or atom.text not in VALUE_ATOMS["justify"]:
            raise _Kept(f"justify: value atom {atom.text!r} is not listed")
        if atom.text in ("top", "bottom"):
            v = atom.text
        else:
            h = atom.text
    return h, v


def _read_png(node: Node) -> str:
    data = bytearray()
    for child in node.children:
        if not isinstance(child, Node) or child.name != "data":
            raise _Kept("pngdata: only data rows are modelled")
        try:
            data += binascii.unhexlify("".join(_string(child, "pngdata data").split()))
        except (binascii.Error, ValueError):
            raise _Kept("pngdata: a data row is not hexadecimal") from None
    return base64.b64encode(bytes(data)).decode("ascii")


def _field_value(head: str, node: Node) -> object:
    """The model value one child stands for (the reader's projection of that child)."""
    if head in POINT_HEADS:
        return _point(node)
    if head in ("name", "comment"):
        return _string(node, head)
    if head == "option":
        return _scope(node)
    if head in ("linewidth", "incrx", "incry", "maxlen", "maxheight"):
        return _nm(_one(node, head), head)
    if head in ("repeat", "incrlabel"):
        return _int(_one(node, head), head)
    if head == "rotate":
        return _scaled(_one(node, head), PPM, head)
    if head == "scale":
        return _scaled(_one(node, head), PPM, head)
    if head == "font":
        return _read_font(node)
    if head == "justify":
        return _read_justify(node)
    if head == "pngdata":
        return _read_png(node)
    raise _Kept(f"unmodelled child {head!r}")  # pragma: no cover - callers pass fields only


def _build_item(head: str, text: str | None, values: Mapping[str, object]) -> SheetItem:
    repeat = SheetRepeat(
        count=values.get("repeat", 1),  # type: ignore[arg-type]
        step_x=values.get("incrx", 0),  # type: ignore[arg-type]
        step_y=values.get("incry", 0),  # type: ignore[arg-type]
        label_step=values.get("incrlabel", 1),  # type: ignore[arg-type]
    )
    common = {
        "repeat": repeat,
        "scope": values.get("option", "all"),
        "name": values.get("name", ""),
        "comment": values.get("comment", ""),
    }
    if head in ("line", "rect"):
        if "start" not in values or "end" not in values:
            raise _Kept(f"{head}: start and end are required")
        return SheetShape(head, values["start"], values["end"], width=values.get("linewidth"), **common)  # type: ignore[arg-type]
    if head == "tbtext":
        if text is None or "pos" not in values:
            raise _Kept("tbtext: a text and pos are required")
        bold, italic, size = values.get("font", (False, False, None))  # type: ignore[misc]
        h, v = values.get("justify", ("left", "center"))  # type: ignore[misc]
        return SheetText(
            text, values["pos"], size=size, bold=bold, italic=italic, justify=h, vjustify=v,  # type: ignore[arg-type]
            rotation=values.get("rotate", 0), max_len=values.get("maxlen"),  # type: ignore[arg-type]
            max_height=values.get("maxheight"), **common,  # type: ignore[arg-type]
        )  # fmt: skip
    if "pos" not in values or "pngdata" not in values:
        raise _Kept("bitmap: pos and pngdata are required")
    return SheetBitmap(values["pos"], values["pngdata"], scale_ppm=values.get("scale", PPM), **common)  # type: ignore[arg-type]


def _read_item(node: Node, rel: str, locator: str, kept: Callable[[str, str], None]) -> _ReadItem:
    head = node.name
    allowed = _ALLOWED[head]
    text: str | None = None
    values: dict[str, object] = {}
    children = list(node.children)
    raw_text: Atom | None = None
    if head == "tbtext":
        if not children or not isinstance(children[0], Atom):
            raise _Kept("tbtext: the text is missing")
        raw_text = children[0]
        text = neutral_text(raw_text.value)
    for child in children[1:] if head == "tbtext" else children:
        if isinstance(child, Atom):
            raise _Kept(f"{head}: unexpected atom {child.text!r}")
        if child.name in allowed:
            if child.name in values:
                raise _Kept(f"{head}: repeated child {child.name!r}")
            values[child.name] = _field_value(child.name, child)
    item = _build_item(head, text, values)
    # Reproducibility: each modelled child must come back tree-equal from the emitter.
    emitted = item_items(item, raw_text.value if raw_text is not None else "")
    item_slots: list[Slot] = []
    font_slots: list[Slot] | None = None
    for child in children:
        if isinstance(child, Atom):  # the tbtext text
            if emitted["text"] and tree_equal(_wrap(emitted["text"][0]), _wrap(child)):
                item_slots.append(Modeled("text"))
            else:
                item_slots.append(Opaque(dumps(child, style="compact")))
                kept(f"{locator}: the text spelling is not reproduced; kept as written", locator)
            continue
        if child.name not in allowed:
            item_slots.append(Opaque(dumps(child, style="compact")))
            continue
        if child.name == "font":
            font_slots = _font_slots(child, emitted.get("font", []))
            item_slots.append(Modeled("font"))
            continue
        out = emitted.get(child.name, [])
        if len(out) == 1 and tree_equal(_wrap(out[0]), _wrap(child)):
            item_slots.append(Modeled(child.name))
        else:
            item_slots.append(Opaque(dumps(child, style="compact")))
            kept(f"{locator}/{child.name}: not reproduced by the writer; kept as written", locator)
    slots = {rel: item_slots}
    if font_slots is not None:
        slots[f"{rel}/font[0]"] = font_slots
    return _ReadItem(item, slots)


def _font_slots(font: Node, emitted: Sequence[Node | Atom]) -> list[Slot]:
    """Slots of a ``font``: flags and ``size`` modelled when reproduced, other children opaque."""
    first = emitted[0] if emitted else None
    children = first.children if isinstance(first, Node) else ()
    out_flags = [c for c in children if isinstance(c, Atom)]
    out_size = [c for c in children if isinstance(c, Node)]
    slots: list[Slot] = []
    for child in font.children:
        if isinstance(child, Atom):
            slots.append(Modeled("flag") if child in out_flags else Opaque(child.text))
        elif child.name == "size":
            reproduced = len(out_size) == 1 and tree_equal(out_size[0], child)
            slots.append(Modeled("size") if reproduced else Opaque(dumps(child, style="compact")))
        else:
            slots.append(Opaque(dumps(child, style="compact")))
    return slots


def _wrap(child: Node | Atom) -> Node:
    return child if isinstance(child, Node) else _node("x", child)


def _read_setup(node: Node) -> tuple[SheetSetup, list[Slot]]:
    fields = CANONICAL_ORDER["setup"]
    values: dict[str, tuple[Nm, ...]] = {}
    slots: list[Slot] = []
    for child in node.children:
        if isinstance(child, Node) and child.name in fields and child.name not in values:
            atoms = child.atoms()
            want = 2 if child.name == "textsize" else 1
            try:
                if len(atoms) != want or child.nodes():
                    raise _Kept(f"setup {child.name}: unexpected values")
                values[child.name] = tuple(_nm(a, f"setup {child.name}") for a in atoms)
            except _Kept:
                slots.append(Opaque(dumps(child, style="compact")))
                continue
            slots.append(Modeled(child.name))
        else:
            slots.append(Opaque(dumps(child, style="compact")))
    missing = [f for f in fields if f not in values]
    if missing:
        raise FormatError(f"setup lacks {', '.join(missing)}", locator="setup")
    setup = SheetSetup(
        (values["textsize"][0], values["textsize"][1]),
        *(values[f][0] for f in fields[1:]),
    )
    emitted = setup_items(setup)
    checked: list[Slot] = []
    for slot, child in zip(slots, node.children, strict=True):
        if isinstance(slot, Modeled) and not tree_equal(emitted[slot.field][0], _wrap(child)):  # type: ignore[arg-type]
            checked.append(Opaque(dumps(child, style="compact")))
        else:
            checked.append(slot)
    return setup, checked


def read_drawing_sheet(
    source: Source, *, file: str = "", name: str | None = None, issues: list[Issue] | None = None
) -> DrawingSheet:
    """A ``DrawingSheet`` from a ``.kicad_wks`` path, its text or a parsed ``Node`` (``worksheet.md``)."""
    found = issues if issues is not None else []
    loaded = load_source(source, file)
    root = loaded.node
    label = loaded.file
    info = versions.inspect(root, file=label)
    if info.kind != FileKind.WORKSHEET:
        raise FormatError(
            f"expected a drawing sheet, found {root.name!r}", file=label, locator=f"/{root.name}"
        )
    versions.require_readable(info, file=label)
    found.extend(versions.version_issues(info))
    if root.name in versions.LEGACY_WORKSHEET_ROOTS:
        found.append(_issue("kicad.wks.legacy-root", f"legacy root {root.name!r}", f"/{root.name}"))
    if name is None:
        name = Path(label).stem if label else ""
        if name.endswith(".kicad_wks"):  # pragma: no cover - Path.stem removes the suffix
            name = name[: -len(".kicad_wks")]

    def kept(message: str, where: str) -> None:
        found.append(_issue("kicad.wks.kept-opaque", message, where))

    setup: SheetSetup | None = None
    items: list[SheetItem] = []
    groups: dict[str, list[Slot]] = {}
    root_slots: list[Slot] = []
    foreign: list[tuple[str, str]] = [(_ROOT, root.name)]
    seen: dict[str, int] = {}
    for child in root.children:
        if isinstance(child, Atom):
            root_slots.append(Opaque(child.text))
            continue
        index = seen.get(child.name, 0)
        seen[child.name] = index + 1
        locator = f"/{root.name}/{child.name}[{index}]"
        if child.name in HEADER_HEADS and index == 0:
            root_slots.append(Modeled(child.name))
            foreign.append((f"{_SRC}{child.name}", dumps(child, style="compact")))
        elif child.name == "setup" and setup is None:
            try:
                setup, setup_slots = _read_setup(child)
            except FormatError as exc:
                raise FormatError(
                    str(exc.args[0]), file=label, locator=locator, offset=child.offset
                ) from None
            groups["setup[0]"] = setup_slots
            root_slots.append(Modeled("setup"))
        elif child.name in ITEM_HEADS:
            rel = f"item[{len(items)}]"
            try:
                read = _read_item(child, rel, locator, kept)
            except _Kept as exc:
                kept(f"{locator}: {exc.reason}", locator)
                root_slots.append(Opaque(dumps(child, style="compact")))
                continue
            items.append(read.item)
            groups.update(read.slots)
            root_slots.append(Modeled("items"))
        else:
            if child.name != "polygon":
                kept(f"{locator}: {child.name!r} is not modelled", locator)
            root_slots.append(Opaque(dumps(child, style="compact")))
    if setup is None:
        raise FormatError("the drawing sheet has no setup", file=label, locator=f"/{root.name}")
    groups["."] = root_slots
    bag = to_ext(groups, base=ExtBag(None, tuple(foreign)))
    return DrawingSheet(
        id=derived_id("wks", "kicad", name), name=name, setup=setup, items=tuple(items), ext={BAG: bag}
    )


def opaque_count(sheet: DrawingSheet) -> int:
    """The opaque items and opaque slots a read sheet keeps."""
    bag = sheet.ext.get(BAG)
    if bag is None:
        return 0
    return sum(isinstance(s, Opaque) for slots in from_ext_all(bag).values() for s in slots)


# ------------------------------------------------------------------------------------------- rebuild


def _foreign(bag: ExtBag | None) -> dict[str, str]:
    return {} if bag is None else {k: v for k, v in bag.payload if not k.startswith("slot:")}


def _changed(head: str, item: SheetItem, fragment: str) -> bool:
    """Whether the model value of the child ``fragment`` stands for differs from ``item``."""
    child = parse_fragment(fragment)
    if not isinstance(child, Node):
        return False
    try:
        value = _field_value(head, child)
    except _Kept:
        return False  # never a projection of the model: an unmodelled spelling stays as written
    return value != _model_value(head, item)


def _model_value(head: str, item: SheetItem) -> object:
    if head in POINT_HEADS:
        return getattr(item, "pos" if head == "pos" else head)
    simple = {
        "name": item.name,
        "comment": item.comment,
        "option": item.scope,
        "repeat": item.repeat.count,
        "incrx": item.repeat.step_x,
        "incry": item.repeat.step_y,
        "incrlabel": item.repeat.label_step,
    }
    if head in simple:
        return simple[head]
    if isinstance(item, SheetShape) and head == "linewidth":
        return item.width
    if isinstance(item, SheetText):
        text_values = {
            "font": (item.bold, item.italic, item.size),
            "justify": (item.justify, item.vjustify),
            "rotate": item.rotation,
            "maxlen": item.max_len,
            "maxheight": item.max_height,
        }
        if head in text_values:
            return text_values[head]
    if isinstance(item, SheetBitmap):
        if head == "scale":
            return item.scale_ppm
        if head == "pngdata":
            return item.png
    return None


def _resolve(
    slots: Sequence[Slot], fields: frozenset[str], changed: Callable[[Node | Atom], bool]
) -> tuple[list[Slot], set[str]]:
    """Projection reconciliation: an opaque slot standing for a modelled field becomes ``Modeled`` when
    the model changed, and is otherwise kept verbatim; the fields kept verbatim are returned so the
    source does not emit them a second time. ``text`` stands for the leading atom of a ``tbtext``."""
    resolved: list[Slot] = []
    kept: set[str] = set()
    for slot in slots:
        if isinstance(slot, Opaque):
            child = parse_fragment(slot.fragment)
            field = child.name if isinstance(child, Node) else "text"
            if field in fields:
                if changed(child):
                    resolved.append(Modeled(field))
                    continue
                kept.add(field)
        resolved.append(slot)
    return resolved, kept


def _item_node(
    item: SheetItem, rel: str, groups: Mapping[str, Sequence[Slot]], text_errors: list[Issue]
) -> Node:
    head = _item_head(item)
    where = rel.replace("item[", "items[", 1)
    text = kicad_text(item.text, where, text_errors) if isinstance(item, SheetText) else ""
    items = item_items(item, text)
    slots = list(groups.get(rel, ()))
    if not slots:
        return rebuild(Atom.symbol(head), (), _Source(items), canonical=CANONICAL_ORDER[head])
    fields = _ALLOWED[head] | _TEXT_FIELD if head == "tbtext" else _ALLOWED[head]

    def changed(child: Node | Atom) -> bool:
        if isinstance(child, Atom):
            return _text_changed(item, child)
        return _changed(child.name, item, dumps(child, style="compact"))

    resolved, kept = _resolve(slots, fields, changed)
    if isinstance(item, SheetText) and "font" in items and f"{rel}/font[0]" in groups:
        font_items = _font_items(item)
        font_slots, font_kept = _resolve(
            groups[f"{rel}/font[0]"], frozenset({"size"}), lambda c: _size_changed(item, c)
        )
        font_source = {k: v for k, v in font_items.items() if k not in font_kept}
        font = rebuild(
            Atom.symbol("font"), font_slots, _Source(font_source), canonical=CANONICAL_ORDER["font"]
        )
        items = {**items, "font": [font]}
    source = {k: v for k, v in items.items() if k not in kept}
    return rebuild(Atom.symbol(head), resolved, _Source(source), canonical=CANONICAL_ORDER[head])


def _size_changed(item: SheetItem, child: Node | Atom) -> bool:
    """Whether a kept font ``size`` child differs from the model's text size."""
    if not isinstance(child, Node) or not isinstance(item, SheetText):
        return False
    try:
        size = tuple(_nm(a, "font size") for a in child.atoms())
    except _Kept:
        return False
    return size != item.size


def _setup_node(setup: SheetSetup, slots: Sequence[Slot]) -> Node:
    items = setup_items(setup)

    def changed(child: Node | Atom) -> bool:
        if not isinstance(child, Node):
            return False
        try:
            values = tuple(_nm(a, child.name) for a in child.atoms())
        except _Kept:
            return False
        current = items[child.name][0]
        assert isinstance(current, Node)
        return values != tuple(a.to_nm() for a in current.atoms())

    resolved, kept = _resolve(slots, frozenset(CANONICAL_ORDER["setup"]), changed)
    source = {k: v for k, v in items.items() if k not in kept}
    return rebuild(Atom.symbol("setup"), resolved, _Source(source), canonical=CANONICAL_ORDER["setup"])


def _text_changed(item: SheetItem, atom: Atom) -> bool:
    assert isinstance(item, SheetText)
    try:
        return neutral_text(atom.value) != item.text
    except _Kept:
        return True


def _item_head(item: SheetItem) -> str:
    if isinstance(item, SheetShape):
        return item.kind
    return "tbtext" if isinstance(item, SheetText) else "bitmap"


def _rebuild(sheet: DrawingSheet, text_errors: list[Issue], modelled: set[int] | None = None) -> Node:
    """The sheet's tree; ``modelled`` collects the ``id`` of the setup and item nodes it emits."""
    bag = sheet.ext.get(BAG)
    groups = from_ext_all(bag) if bag is not None else {}
    foreign = _foreign(bag)
    nodes = [_item_node(item, f"item[{k}]", groups, text_errors) for k, item in enumerate(sheet.items)]
    setup = _setup_node(sheet.setup, groups.get("setup[0]", ()))
    if modelled is not None:
        modelled.update(id(n) for n in (setup, *nodes))
    fields: dict[str, Children] = {"setup": [setup], "items": list(nodes)}
    for head in HEADER_HEADS:
        fragment = foreign.get(f"{_SRC}{head}")
        if fragment is not None:
            fields[head] = [parse_fragment(fragment)]
    if not groups:
        fields["version"] = [_node("version", Atom.integer(versions.FORMAT_VERSIONS[FileKind.WORKSHEET][10]))]
        fields["generator"] = [_node("generator", Atom.string(versions.GENERATOR))]
    root_name = foreign.get(_ROOT, "kicad_wks")
    return rebuild(
        Atom.symbol(root_name), groups.get(".", ()), _Source(fields), canonical=CANONICAL_ORDER["kicad_wks"]
    )


def rebuild_drawing_sheet(sheet: DrawingSheet) -> Node:
    """The tree of ``sheet``: a read sheet's source root and header, modelled items emitted from the
    model and opaque items and slots verbatim at their positions (RT1)."""
    return _rebuild(sheet, [])


# ------------------------------------------------------------------------------------------- writing


def _lengths(sheet: DrawingSheet) -> Iterable[tuple[str, Nm]]:
    s = sheet.setup
    yield "setup.text_size", s.text_size[0]
    yield "setup.text_size", s.text_size[1]
    for name in CANONICAL_ORDER["setup"][1:]:
        field = {"linewidth": "line_width", "textlinewidth": "text_line_width"}.get(name, name)
        yield f"setup.{field}", getattr(s, field)
    for k, item in enumerate(sheet.items):
        where = f"items[{k}]"
        points = (item.start, item.end) if isinstance(item, SheetShape) else (item.pos,)
        for point in points:
            yield f"{where}.point", point.x
            yield f"{where}.point", point.y
        yield f"{where}.repeat", item.repeat.step_x
        yield f"{where}.repeat", item.repeat.step_y
        extra: list[Nm | None] = []
        if isinstance(item, SheetShape):
            extra = [item.width]
        elif isinstance(item, SheetText):
            extra = [*(item.size or ()), item.max_len, item.max_height]
        for value in extra:
            if value is not None:
                yield where, value


def _value_atom_errors(root: Node) -> list[Issue]:
    from fenolite.backends.kicad.sexpr import walk

    errors: list[Issue] = []
    for locator, current in walk(root):
        symbols = [a.text for a in current.atoms() if a.kind == AtomKind.SYMBOL]
        if current.name in POINT_HEADS:
            allowed, values = VALUE_ATOMS["corner"], symbols
        elif current.name in ("option", "justify", "font"):
            allowed, values = VALUE_ATOMS[current.name], symbols
        else:
            continue
        for value in values:
            if value not in allowed:
                message = f"value atom {value!r} of {current.name!r} is not listed"
                errors.append(_issue("kicad.wks.unknown-value", message, locator))
    return errors


def _drop(root: Node, locator: str, modelled: set[int]) -> tuple[Node, str]:
    """``root`` without the opaque item, or the opaque child of a modelled item or of the setup, that
    holds ``locator``; ``modelled`` (node ids) is updated for a trimmed modelled node."""
    parts = locator.strip("/").split("/")
    if len(parts) < 2:
        raise ValueError(f"cannot drop the root ({locator})")
    index = _locate(root, parts[1])
    target = root.children[index]
    assert isinstance(target, Node)
    children = list(root.children)
    if id(target) not in modelled or len(parts) < 3:
        del children[index]
        return root.with_children(children), f"/{root.name}/{parts[1]}"
    inner = _locate(target, parts[2])
    trimmed = target.with_children(c for i, c in enumerate(target.children) if i != inner)
    modelled.add(id(trimmed))
    children[index] = trimmed
    return root.with_children(children), f"/{root.name}/{parts[1]}/{parts[2]}"


def _locate(node: Node, part: str) -> int:
    match = re.fullmatch(r"(.+)\[(\d+)\]", part)
    if match is None:
        raise ValueError(f"bad locator part {part!r}")
    name, wanted = match.group(1), int(match.group(2))
    seen = 0
    for i, child in enumerate(node.children):
        if isinstance(child, Node) and child.name == name:
            if seen == wanted:
                return i
            seen += 1
    raise ValueError(f"no child {part!r}")


def _emit_problems(root: Node, target: int) -> list[Issue]:
    problems: list[Issue] = []
    for issue in versions.check_emittable(root, FileKind.WORKSHEET, target):
        if issue.code == "kicad.token.uninventoried":
            problems.append(_issue("kicad.wks.uninventoried", issue.message, issue.where))
        elif issue.severity == "error":
            problems.append(issue)
    return problems + _value_atom_errors(root)


def write_drawing_sheet(
    sheet: DrawingSheet, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False
) -> WriteResult:
    """The text of one ``.kicad_wks`` that KiCad 9.0 and 10.0 load (``worksheet.md``, "The writer"); the
    bytes do not depend on ``target``, which selects the emit check only."""
    if target not in versions.TARGET_MAJORS:
        raise ValueError(f"unsupported target KiCad {target}; supported targets: {versions.TARGET_MAJORS}")
    if sheet.ext.get(BAG) is not None:
        versions.require_editable(versions.inspect(rebuild_drawing_sheet(sheet)))
    errors: list[Issue] = []
    for where, value in _lengths(sheet):
        if value % UM:
            errors.append(_issue("kicad.wks.below-resolution",
                                 f"{value} nm is not a whole number of micrometres", where))  # fmt: skip
    modelled: set[int] = set()
    tree = _rebuild(sheet, errors, modelled)
    if errors:
        raise LossyWriteError(errors, droppable=False)
    header = [
        _node("version", Atom.integer(versions.FORMAT_VERSIONS[FileKind.WORKSHEET][target])),
        _node("generator", Atom.string(versions.GENERATOR)),
    ]
    body = [c for c in tree.children if not (isinstance(c, Node) and c.name in HEADER_HEADS)]
    root = Node(Atom.symbol("kicad_wks"), (*header, *body))
    warnings: list[Issue] = []
    problems = _emit_problems(root, target)
    if problems and not allow_lossy:
        raise LossyWriteError(problems, droppable=True)
    while problems:
        root, dropped = _drop(root, problems[0].where, modelled)
        warnings.append(_issue("kicad.wks.dropped-item", f"dropped {dropped} under --allow-lossy", dropped))
        problems = _emit_problems(root, target)
    return WriteResult(dumps(root, style="kicad"), tuple(warnings))


__all__ = [
    "CANONICAL_ORDER",
    "CORNER_ATOMS",
    "EVIDENCE",
    "ISSUE_CODES",
    "KICAD_TOKENS",
    "RESERVED_VARIABLES",
    "SCOPE_ATOMS",
    "VALUE_ATOMS",
    "WRITE_EVIDENCE",
    "kicad_text",
    "neutral_text",
    "opaque_count",
    "read_drawing_sheet",
    "rebuild_drawing_sheet",
    "write_drawing_sheet",
]
