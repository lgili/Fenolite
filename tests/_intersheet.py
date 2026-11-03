# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Tiny independently authored native reference-field controls, without parts (c0348)."""

from __future__ import annotations

import json
import re
import uuid
import xml.etree.ElementTree as ET
from collections import Counter
from collections.abc import Mapping, Sequence
from decimal import Decimal


def identity(text: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "fenolite:intersheet-author:" + text))


def label(text: str, x: int, y: int, *, hidden: bool = False) -> str:
    hide = " (hide yes)" if hidden else ""
    return (
        f'(global_label "{text}" (shape input) (at {x} {y} 0) '
        f'(effects (font (size 1.27 1.27)) (justify left)) (uuid "{identity(text + str(x) + str(y))}") '
        f'(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x + 15} {y} 0) '
        f"(effects (font (size 1.27 1.27)) (justify left){hide})))"
    )


def files(
    target: int,
    pages: Sequence[str] = ("2",),
    *,
    settings: Mapping[str, object] | None = None,
    hidden: bool = False,
    same_page_labels: bool = False,
) -> dict[str, bytes]:
    """No project when settings=None; repeated instances share the one child file."""
    root = identity("root")
    children = []
    for index, page in enumerate(pages):
        x = 100 + 40 * index
        children.append(
            f"(sheet (at {x} 50) (size 30 20) (stroke (width 0) (type default)) "
            f'(fill (color 0 0 0 0)) (uuid "{identity("instance" + str(index))}") '
            f'(property "Sheetname" "PAGE{page}" (at {x} 49 0) '
            "(effects (font (size 1.27 1.27)) (justify left bottom))) "
            f'(property "Sheetfile" "child.kicad_sch" (at {x} 71 0) '
            "(effects (font (size 1.27 1.27)) (justify left top))) "
            f'(instances (project "tiny" (path "/{root}" (page "{page}")))))'
        )
    version = 20260306 if target == 10 else 20250114
    shared = label("AUTH_SHARED", 50, 50, hidden=hidden)
    if same_page_labels:
        shared += label("AUTH_SHARED", 50, 80, hidden=hidden)
    header = f'(kicad_sch (version {version}) (generator "fenolite") '
    top = (
        header
        + f'(uuid "{root}") (paper "A3") (lib_symbols) '
        + shared
        + label("AUTH_ROOT_ONLY", 50, 65, hidden=hidden)
        + " ".join(children)
        + ' (sheet_instances (path "/" (page "1"))))'
    )
    child = (
        header
        + f'(uuid "{identity("child")}") (paper "A4") (lib_symbols) '
        + shared
        + label("AUTH_CHILD_ONLY", 50, 65, hidden=hidden)
        + ")"
    )
    result = {"tiny.kicad_sch": top.encode(), "child.kicad_sch": child.encode()}
    if settings is not None:
        result["tiny.kicad_pro"] = json.dumps({"schematic": {"drawing": dict(settings)}}).encode()
    return result


def field_text(svg: bytes) -> tuple[str, ...]:
    texts = ["".join(node.itertext()) for node in ET.fromstring(svg).iter() if node.tag.endswith("}text")]
    start = texts.index("AUTH_SHARED") + 1
    end = next(index for index in range(start, len(texts)) if texts[index].startswith("AUTH_"))
    return tuple(texts[start:end])


def field_poses(outputs: Mapping[str, bytes], prefix: str) -> Counter:
    """Complete exact same-sheet field multiset; paint order cannot identify duplicate native text.

    Keep every text attribute and ancestor style/rotation, including duplicate multiplicity. Unknown
    transforms refuse instead of silently comparing coordinates in incompatible frames.
    """
    result = Counter()

    def walk(node, filename, context=(), rotations=()):
        if not any(
            child.tag.endswith("}text") and "".join(child.itertext()).startswith(prefix)
            for child in node.iter()
        ):
            return
        attrs = dict(node.attrib)
        transform = attrs.pop("transform", None)
        if transform is not None:
            number = r"([+-]?\d+(?:\.\d+)?)"
            matched = re.fullmatch(rf"rotate\(\s*{number}\s+{number}\s+{number}\s*\)", transform)
            if matched is None:
                raise ValueError("unproved native field transform")
            rotations = (*rotations, tuple(Decimal(value) for value in matched.groups()))
        local = node.tag.rsplit("}", 1)[-1]
        text = "".join(node.itertext())
        if local == "text" and text.startswith(prefix):
            x, y = Decimal(attrs.pop("x")), Decimal(attrs.pop("y"))
            result[(filename, text, x, y, tuple(sorted(attrs.items())), context, rotations)] += 1
        for child in node:
            walk(child, filename, (*context, (local, tuple(sorted(attrs.items())))), rotations)

    for filename, data in outputs.items():
        if filename.endswith(".svg"):
            walk(ET.fromstring(data), filename)
    return result


def shift_field_poses(poses: Counter, shifts: Mapping[str, tuple[Decimal, Decimal]]) -> Counter:
    """Exact expected translation of every selected field and its rotation pivots; other sheets stay."""
    result = Counter()
    for (filename, text, x, y, attrs, context, rotations), count in poses.items():
        dx, dy = shifts.get(filename, (Decimal(0), Decimal(0)))
        shifted = tuple((angle, cx + dx, cy + dy) for angle, cx, cy in rotations)
        result[(filename, text, x + dx, y + dy, attrs, context, shifted)] += count
    return result
