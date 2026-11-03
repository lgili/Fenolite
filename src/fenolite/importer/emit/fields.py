# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Preserve declared custom property presentation through ordinary field requests."""

from __future__ import annotations

from collections.abc import Collection

from fenolite.backends.kicad import slots as slotlib
from fenolite.backends.kicad.fields import field_anchor, field_angle
from fenolite.backends.kicad.replace import field_font
from fenolite.backends.kicad.sexpr import Atom, Node
from fenolite.core.errors import FormatError
from fenolite.geometry.transform import Transform
from fenolite.importer.emit.printer import Call, Expr, Raw, angle, length, text
from fenolite.model.base import Opaque
from fenolite.model.board import FootprintInstance


def _check_font(footprint: FootprintInstance, name: str, ref: str) -> None:
    field = next(f for f in footprint.fields if f.name == name)
    bag = field.ext.get("kicad")
    for slot in slotlib.from_ext(bag) if bag is not None else ():
        if not isinstance(slot, Opaque):
            continue
        effects = slotlib.opaque_child(slot)
        if not isinstance(effects, Node) or effects.name != "effects":
            continue
        fonts = effects.nodes("font")
        valid = len(fonts) == 1 and all(
            isinstance(c, Node)
            and c.name in {"font", "justify", "hide"}
            or isinstance(c, Atom)
            and c.value == "hide"
            for c in effects.children
        )
        justifications = effects.nodes("justify")
        valid &= len(justifications) <= 1
        for justify in justifications:
            tokens = [a.value for a in justify.atoms()]
            valid &= (
                not justify.nodes()
                and len(tokens) == len(set(tokens))
                and set(tokens) <= {"left", "right", "top", "bottom", "mirror"}
                and not {"left", "right"} <= set(tokens)
                and not {"top", "bottom"} <= set(tokens)
            )
        if valid:
            font = fonts[0]
            keys = [c.name for c in font.children if isinstance(c, Node)]
            valid = len(keys) == len(set(keys)) and all(
                isinstance(c, Node)
                and c.name in {"size", "thickness", "bold", "italic", "face"}
                or isinstance(c, Atom)
                and c.value in {"bold", "italic"}
                for c in font.children
            )
            for flag in ("bold", "italic"):
                child = font.find(flag)
                if child is not None:
                    valid &= not child.nodes() and [a.value for a in child.atoms()] in ([], ["yes"], ["no"])
            face = font.find("face")
            if face is not None:
                valid &= not face.nodes() and len(face.atoms()) == 1 and bool(face.atoms()[0].value.strip())
        if not valid:
            raise FormatError("unsupported custom property font/effects", locator=f"{ref}:{name}")


def requests(footprint: FootprintInstance, names: Collection[str], receiver: str, ref: str) -> list[Call]:
    """Exact source field requests for properties the generated Part declares."""
    out: list[Call] = []
    prefix = "B." if footprint.side == "bottom" else "F."
    layers = {prefix + "Fab": "fab", prefix + "SilkS": "silk"}
    transform = Transform.placement(footprint.position, footprint.rotation)
    for field in sorted(footprint.fields, key=lambda f: f.name):
        if field.name not in names:
            continue
        anchor = field_anchor(footprint, field)
        reason = ""
        if field.size.w != field.size.h:
            reason = "anisotropic font size"
        elif field.layer not in layers:
            reason = "unsupported layer"
        elif field.size.w <= 0 or field.thickness is None or field.thickness <= 0:
            reason = "unspecified/non-positive font size or thickness"
        elif transform.inverse().apply(anchor) != field.position:
            reason = "inexact board-frame anchor"
        if reason:
            raise FormatError(
                f"custom property pose cannot be represented: {reason}", locator=f"{ref}:{field.name}"
            )
        assert field.thickness is not None
        _check_font(footprint, field.name, ref)
        if field.mirrored != (footprint.side == "bottom"):
            # This exact native field stays in its vendored definition (c0358).
            # All other representability checks above still apply.
            continue
        justify = " ".join(value for value in (field.h_justify, field.v_justify) if value != "center")
        kwargs: list[tuple[str, Expr]] = [
            ("dx", length(anchor.x - footprint.position.x)),
            ("dy", length(anchor.y - footprint.position.y)),
            ("rot", angle(field_angle(footprint, field))),
            ("layer", text(layers[field.layer])),
            ("visible", Raw(str(field.visible))),
            ("size", length(field.size.w)),
            ("thickness", length(field.thickness)),
        ]
        if justify:
            kwargs.append(("justify", text(justify)))
        styles = field_font(field)
        for name in ("bold", "italic"):
            value = getattr(field, name)
            value = styles.get(name) if value is None else value
            if isinstance(value, bool):
                kwargs.append((name, Raw(str(value))))
        face = field.face if field.face is not None else styles.get("face")
        if isinstance(face, str):
            kwargs.append(("face", text(face)))
        out.append(Call(f"{receiver}.field", (text(field.name),), tuple(kwargs)))
    return out
