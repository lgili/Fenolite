# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Drawn native fonts, from public common syntax and authored field probes (c0326).

Facts and actual version scope: docs/formats/kicad/schematic.md, "Drawn field-font observations".
Native default spellings are normalized separately from the exact canonical/TOML presence contract.
"""

# evidence: see sch, drawn

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node
from fenolite.backends.kicad.sym import TILDE_UNTIL
from fenolite.core.coords import Size
from fenolite.core.errors import FormatError
from fenolite.model.drawn import JUSTIFY_WORDS, DrawnFont


def sheet_property_text(item: Node, *, version: int | None, where: str, file: str = "") -> str:
    """Validate the supported custom-property envelope and reject ambiguous legacy text."""
    try:
        atoms = item.atoms()
        if len(atoms) != 2 or any(atom.kind != AtomKind.STRING for atom in atoms):
            raise ValueError("custom sheet property name and value are strings")
        name, text = (atom.value for atom in atoms)
        if not name or not name.isprintable() or name in {"Sheetname", "Sheetfile"}:
            raise ValueError("custom sheet property name is empty or reserved")
        keys = [child.name for child in item.nodes()]
        if len(keys) != len(set(keys)) or set(keys) - {
            "at",
            "effects",
            "hide",
            "show_name",
            "do_not_autoplace",
        }:
            raise ValueError("unsupported or repeated custom sheet property attribute")
        for key in ("show_name", "do_not_autoplace"):
            flag = item.find(key)
            if flag is not None and (
                flag.nodes()
                or len(flag.atoms()) != 1
                or flag.atoms()[0].kind != AtomKind.SYMBOL
                or flag.atoms()[0].value != "no"
            ):
                raise ValueError(f"unsupported custom sheet property {key} flag")
        position = item.find("at")
        if position is None or position.nodes() or len(position.atoms()) not in (2, 3):
            raise ValueError("custom sheet property requires a supported position")
        coordinates = position.atoms()
        for coordinate in coordinates[:2]:
            coordinate.to_nm()
        if len(coordinates) == 3 and (
            coordinates[2].kind != AtomKind.NUMBER or Decimal(coordinates[2].text) not in (0, 90)
        ):
            raise ValueError("unsupported custom sheet property rotation")
        effects = item.find("effects")
        for hidden in (*item.nodes("hide"), *(effects.nodes("hide") if effects else ())):
            flags = hidden.atoms()
            if hidden.nodes() or len(flags) > 1 or (flags and flags[0].value not in {"yes", "no"}):
                raise ValueError("unsupported custom sheet property hide flag")
        if "${" in text:
            raise ValueError("custom sheet property text variables are not supported")
        if text == "~":
            if version is None:
                raise ValueError("tilde sheet text requires its source format version")
            if version < TILDE_UNTIL:
                raise ValueError("legacy custom sheet tilde has conflicting native reader meanings")
        return text
    except (TypeError, ValueError, InvalidOperation) as error:
        raise FormatError(str(error), file=file, locator=where) from error


def label_justify(rotation: int) -> str:
    return "left" if rotation in (0, 90_000_000) else "right"


def pin_justify(rotation: int) -> str:
    return "left" if rotation in (180_000_000, 270_000_000) else "right"


def read_justify(item: Node, *, where: str, file: str = "") -> str:
    """Native omission/empty justification centres text; it is not a legacy role-selected anchor."""
    effects = item.find("effects")
    justify = effects.find("justify") if effects is not None else None
    if justify is None:
        return ""
    words = [atom.value for atom in justify.atoms()]
    if (
        len(words) != len(justify.children)
        or any(atom.kind != AtomKind.SYMBOL for atom in justify.atoms())
        or any(word not in JUSTIFY_WORDS for word in words)
        or len(words) != len(set(words))
        or {"left", "right"} <= set(words)
        or {"top", "bottom"} <= set(words)
    ):
        raise FormatError("unsupported drawn text justification", file=file, locator=where)
    return " ".join(words)


def effective(font: DrawnFont | None, *, default_nm: int) -> DrawnFont | None:
    """Equivalent default spellings measured by the authored native field probes."""
    if font is None:
        return None
    size = font.size if font.size != Size(default_nm, default_nm) else None
    thickness = font.thickness if font.thickness else None
    bold, italic = (True if font.bold else None), (True if font.italic else None)
    if all(value is None for value in (size, thickness, bold, italic, font.face)):
        return None
    return DrawnFont(size, thickness, bold, italic, font.face)


def _size_supported(size: Size, where: str, file: str = "") -> None:
    if size.w < 1_000 or size.h < 1_000:
        raise FormatError(
            "sub-micrometre drawn font size has no supported faithful native/render representation",
            file=file,
            locator=f"{where}.size",
        )


def font_node(font: DrawnFont | None, *, default_nm: int) -> Node:
    size = font.size if font is not None and font.size is not None else Size(default_nm, default_nm)
    _size_supported(size, "font")
    children: list[Atom | Node] = []
    if font is not None and font.face is not None:
        children.append(node("face", Atom.string(font.face)))
    children.append(node("size", Atom.from_nm(size.h), Atom.from_nm(size.w)))
    if font is not None:
        if font.thickness is not None:
            children.append(node("thickness", Atom.from_nm(font.thickness)))
        if font.bold:
            children.append(Atom.symbol("bold"))
        if font.italic:
            children.append(Atom.symbol("italic"))
    return node("font", *children)


def read_font(item: Node, *, default_nm: int, where: str, file: str = "") -> DrawnFont | None:
    """The effective supported font of an instance item; unknown effects are explicit input errors."""
    try:
        effects = [c for c in item.children if isinstance(c, Node) and c.name == "effects"]
        if len(effects) > 1:
            raise ValueError("repeated effects")
        if not effects:
            return None
        found: dict[str, Node] = {}
        for child in effects[0].children:
            if isinstance(child, Atom):
                if child.kind != AtomKind.SYMBOL or child.value != "hide":
                    raise ValueError(f"unsupported effects atom {child.value!r}")
                continue
            if child.name not in {"font", "justify", "hide"} or child.name in found:
                raise ValueError(f"unsupported or repeated effect {child.name!r}")
            found[child.name] = child
        font = found.get("font")
        if font is None:
            return None
        attributes: dict[str, tuple[Atom, ...]] = {}
        flags: dict[str, bool] = {}
        for child in font.children:
            if isinstance(child, Atom):
                if child.kind != AtomKind.SYMBOL or child.value not in {"bold", "italic"}:
                    raise ValueError(f"unsupported font atom {child.value!r}")
                name, atoms = child.value, ()
            else:
                name, atoms = child.name, child.atoms()
                if len(atoms) != len(child.children):
                    raise ValueError(f"nested font attribute {name!r}")
            if name not in {"size", "thickness", "bold", "italic", "face"} or name in attributes:
                raise ValueError(f"unsupported or repeated font attribute {name!r}")
            attributes[name] = atoms
            if name in {"bold", "italic"}:
                if isinstance(child, Atom):
                    flags[name] = True
                elif len(atoms) == 1 and atoms[0].kind == AtomKind.SYMBOL and atoms[0].value in {"yes", "no"}:
                    flags[name] = atoms[0].value == "yes"
                else:
                    raise ValueError(f"unsupported native {name} flag")
        size = None
        if "size" in attributes:
            atoms = attributes["size"]
            if len(atoms) != 2:
                raise ValueError("font size is HEIGHT WIDTH")
            size = Size(atoms[1].to_nm(), atoms[0].to_nm())
            _size_supported(size, where, file)
        thickness = None
        if "thickness" in attributes:
            atoms = attributes["thickness"]
            if len(atoms) != 1:
                raise ValueError("font thickness has one length")
            thickness = atoms[0].to_nm()
        face = None
        if "face" in attributes:
            atoms = attributes["face"]
            if len(atoms) != 1 or atoms[0].kind != AtomKind.STRING:
                raise ValueError("font face is one name")
            face = atoms[0].value
        if all(value is None for value in (size, thickness, flags.get("bold"), flags.get("italic"), face)):
            return None
        return effective(
            DrawnFont(size, thickness, flags.get("bold"), flags.get("italic"), face), default_nm=default_nm
        )
    except (TypeError, ValueError) as error:
        raise FormatError(f"unsupported drawn font: {error}", file=file, locator=where) from error
