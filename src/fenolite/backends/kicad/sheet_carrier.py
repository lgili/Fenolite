# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The per-sheet carriers of a converted drawing (change c0470, design D4; capability design-conversion,
"Sheet carriers").

``Fenolite.Altium.Sheet`` (schema ``fenolite.altium-sheet.v0``) rides in the title block of a written KiCad
sheet as ``(comment 9 "<canonical JSON>")``: a ``.kicad_sch`` holds no sheet property, KiCad's default
worksheet draws comments 1 to 4 only, and ``kicad-cli`` 10.0.6 keeps comment 9 when it saves a sheet
(``docs/formats/kicad/schematic.md``). It holds the Altium records that no drawn item keeps: the sheet
record and the document parameters (``sheet``), each opaque record with the uuid of its KiCad stand-in when
there is one (``opaques``), and the Altium fields of modelled items (``fields``, ``drawn_read.ITEM_FIELDS``).

The carrier is put into and taken from the sheet text, so the KiCad model readers never see it: their title
block maps comments 1 to 3 only and keeps the rest of the node as it is.
"""

# evidence: see drawn

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from pathlib import PurePosixPath
from typing import Any, cast

from fenolite.backends.kicad._fpmap import node
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.model.drawn import DrawnOpaque, DrawnSchematic, DrawnSheet

ALTIUM_SCHEMA = "fenolite.altium-sheet.v0"
ALTIUM_NAME = "Fenolite.Altium.Sheet"
COMMENT = 9
"""The title-block comment that holds the carrier."""
_UUID = re.compile(r'\(uuid "([0-9a-f-]{36})"\)')


@dataclass(frozen=True)
class AltiumSheet:
    """The carrier of one sheet: the held sheet records, the opaque records (``(uuid of the KiCad stand-in
    or "", record text)``, in drawn order) and the Altium fields of modelled items."""

    sheet: str = ""
    opaques: tuple[tuple[str, str], ...] = ()
    fields: Mapping[str, Mapping[str, str]] = field(default_factory=lambda: {})

    def text(self) -> str:
        """The canonical JSON of the carrier: sorted keys, no spaces, UTF-8 kept."""
        value = {
            "schema": ALTIUM_SCHEMA,
            "sheet": self.sheet,
            "opaques": [{"uuid": uuid, "altium": text} for uuid, text in self.opaques],
            "fields": {key: dict(sorted(found.items())) for key, found in sorted(self.fields.items())},
        }
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def parse(cls, text: str) -> AltiumSheet:
        """The carrier of ``text``; ``ValueError`` when it is not a carrier of this schema."""
        loaded: object = json.loads(text)
        if not isinstance(loaded, dict):
            raise ValueError(f"not a {ALTIUM_SCHEMA} carrier")
        value = cast(dict[str, Any], loaded)
        if value.get("schema") != ALTIUM_SCHEMA:
            raise ValueError(f"not a {ALTIUM_SCHEMA} carrier")
        items = cast(list[dict[str, Any]], value["opaques"])
        opaques = tuple((str(item["uuid"]), str(item["altium"])) for item in items)
        held = cast(dict[str, dict[str, Any]], value["fields"])
        fields = {str(k): {str(a): str(b) for a, b in v.items()} for k, v in held.items()}
        return cls(str(value["sheet"]), opaques, fields)


def stand_in_uuid(fragment: str) -> str:
    """The uuid that ends the KiCad stand-in ``fragment`` (``drawn_read.stand_in`` writes it last)."""
    found = _UUID.findall(fragment)
    return found[-1] if found else ""


def altium_sheet(
    opaques: Sequence[DrawnOpaque], sheet: str, fields: Mapping[str, Mapping[str, str]]
) -> AltiumSheet:
    """The carrier of a drawn sheet read from Altium."""
    return AltiumSheet(sheet, tuple((stand_in_uuid(o.kicad), o.altium) for o in opaques if o.altium), fields)


def put(text: str, carrier: str) -> str:
    """The sheet ``text`` with ``carrier`` as the title block's comment 9 (the title block is added when the
    sheet has none, after ``paper``); an earlier comment 9 is replaced."""
    root = parse(text)
    entry = node("comment", Atom.integer(COMMENT), Atom.string(carrier))
    children: list[Node | Atom] = []
    placed = False
    for child in root.children:
        if isinstance(child, Node) and child.name == "title_block":
            kept = [c for c in child.children if not _is_carrier(c)]
            child = child.with_children([*kept, entry])
            placed = True
        children.append(child)
    if not placed:
        at = next((i for i, c in enumerate(children) if isinstance(c, Node) and c.name == "paper"), None)
        index = (at + 1) if at is not None else len(children)
        children.insert(index, node("title_block", entry))
    return dumps(root.with_children(children))


def sheet_files(drawn: DrawnSchematic, files: Iterable[str], root_file: str) -> dict[str, str]:
    """Sheet key → written file: ``root_file`` holds the root sheet, a child file is named by its key."""
    by_stem = {PurePosixPath(file).stem: file for file in files if file != root_file}
    found = {drawn.root: root_file}
    found |= {sheet.key: by_stem[sheet.key] for sheet in drawn.sheets if sheet.key in by_stem}
    return found


TOML_PREFIX = "# fenolite.altium-sheet: "
"""Comment prefix in ``schematic.toml`` that carries ``AltiumSheet`` styling for an Altium import (c0473)."""


def put_drawing(
    texts: Mapping[str, str],
    drawn: DrawnSchematic,
    root_file: str,
    carriers: Mapping[str, AltiumSheet] | None = None,
    *,
    extra_sheets: Mapping[str, str] | None = None,
    extra_fields: Mapping[str, Mapping[str, Mapping[str, str]]] | None = None,
) -> dict[str, str]:
    """The written KiCad sheet ``texts`` (by file) of ``drawn`` with the carrier of each sheet that holds
    Altium records: ``carriers`` by sheet key, else the opaque records of the sheet."""
    out = dict(texts)
    for key, file in sheet_files(drawn, texts, root_file).items():
        sheet = next((s for s in drawn.sheets if s.key == key), None)
        if sheet is None:
            continue
        carrier = carriers.get(key) if carriers is not None else None
        params = param_lines(sheet.title_block)
        held_sheet = (extra_sheets or {}).get(key, "")
        held_fields = (extra_fields or {}).get(key, {})
        if carrier is None and (params or held_sheet or held_fields or any(o.altium for o in sheet.opaques)):
            # a build: the sheet's own document parameters travel as the sheet records a conversion
            # carries, which ``restore`` reads back (``sheet_params``; change c0470)
            combined_sheet = "\n".join(part for part in (held_sheet, params) if part)
            carrier = altium_sheet(sheet.opaques, combined_sheet, held_fields)
        if carrier is not None:
            out[file] = put(out[file], carrier.text())
    return out


def take_drawing(texts: Mapping[str, str], drawn: DrawnSchematic, root_file: str) -> DrawnSchematic:
    """``drawn`` read from the KiCad sheet ``texts`` (by file) with the Altium records of their carriers."""
    carriers: dict[str, AltiumSheet] = {}
    for key, file in sheet_files(drawn, texts, root_file).items():
        carried = take(texts[file])
        if carried is None:
            continue
        try:
            carriers[key] = AltiumSheet.parse(carried)
        except ValueError:
            continue
    return restore(drawn, carriers) if carriers else drawn


def carried_fields(
    texts: Mapping[str, str], drawn: DrawnSchematic, root_file: str
) -> dict[str, dict[str, dict[str, str]]]:
    """Per sheet key, the Altium fields that the sheet's carrier keeps (``AltiumSheet.fields``): the Altium
    drawn writer reads the ``HARNESSTYPE`` of sheet entries and the own texts of net labels from them
    (change c0470)."""
    found: dict[str, dict[str, dict[str, str]]] = {}
    for key, file in sheet_files(drawn, texts, root_file).items():
        carried = take(texts[file])
        if carried is None:
            continue
        try:
            fields = AltiumSheet.parse(carried).fields
        except ValueError:
            continue
        if fields:
            found[key] = {name: dict(value) for name, value in fields.items()}
    return found


def carried_sheets(texts: Mapping[str, str], drawn: DrawnSchematic, root_file: str) -> dict[str, str]:
    """Per sheet key, the held sheet records (``AltiumSheet.sheet``) of its carrier (change c0473)."""
    found: dict[str, str] = {}
    for key, file in sheet_files(drawn, texts, root_file).items():
        carried = take(texts[file])
        if carried is None:
            continue
        try:
            sheet_text = AltiumSheet.parse(carried).sheet
        except ValueError:
            continue
        if sheet_text:
            found[key] = sheet_text
    return found


def toml_footer(texts: Mapping[str, str], drawn: DrawnSchematic, root_file: str) -> str:
    """Comment lines at the end of ``schematic.toml`` carrying ``AltiumSheet.sheet`` and ``fields`` (c0473)."""
    lines: list[str] = []
    for key, file in sorted(sheet_files(drawn, texts, root_file).items()):
        carried = take(texts[file])
        if carried is None:
            continue
        try:
            parsed = AltiumSheet.parse(carried)
        except ValueError:
            continue
        if parsed.sheet or parsed.fields:
            payload = AltiumSheet(parsed.sheet, (), parsed.fields).text()
            lines.append(f"{TOML_PREFIX}{key} {payload}")
    return ("\n" + "\n".join(lines) + "\n") if lines else ""


def from_toml_text(text: str) -> tuple[dict[str, str], dict[str, dict[str, dict[str, str]]]]:
    """``(sheet_records_by_key, fields_by_key)`` from ``TOML_PREFIX`` lines in ``schematic.toml`` (c0473)."""
    sheets: dict[str, str] = {}
    fields: dict[str, dict[str, dict[str, str]]] = {}
    for line in text.splitlines():
        if not line.startswith(TOML_PREFIX):
            continue
        rest = line[len(TOML_PREFIX) :]
        key, sep, payload = rest.partition(" ")
        if not sep or not key or not payload:
            continue
        try:
            parsed = AltiumSheet.parse(payload)
        except ValueError:
            continue
        if parsed.sheet:
            sheets[key] = parsed.sheet
        if parsed.fields:
            fields[key] = {name: dict(value) for name, value in parsed.fields.items()}
    return sheets, fields


def take(text: str) -> str | None:
    """The comment 9 of the sheet ``text``'s title block, or ``None``."""
    found = parse(text).find("title_block")
    if found is None:
        return None
    for child in found.children:
        if _is_carrier(child):
            assert isinstance(child, Node)
            strings = [a.value for a in child.atoms() if a.kind.name == "STRING"]
            return strings[-1] if strings else None
    return None


def _is_carrier(child: Node | Atom) -> bool:
    if not isinstance(child, Node) or child.name != "comment":
        return False
    atoms = child.atoms()
    return bool(atoms) and atoms[0].text == str(COMMENT)


_TITLE_NAMES = frozenset(
    {"title", "revision", "date", "organization", "companyname", "documentnumber", "drawnby", "approvedby"}
)
"""The document parameters (folded) that are fields of KiCad's title block
(``drawn_read.TITLE_PARAMETERS``)."""


def param_lines(title_block: Sequence[tuple[str, str]]) -> str:
    """The ``param.<name>`` entries of a drawn title block that KiCad's title block has no field for, as the
    document parameter records (41, without an owner) that ``sheet_params`` reads (change c0470); a name or
    text that a record cannot hold (``|``, a line break) is left out."""
    lines: list[str] = []
    for key, text in title_block:
        name = key.removeprefix("param.")
        if name == key or not name or not text or name.casefold() in _TITLE_NAMES:
            continue
        if any(bad in name + text for bad in ("|", "\n", "\r")):
            continue
        lines.append(f"|RECORD=41|OWNERPARTID=-1|NAME={name}|TEXT={text}")
    return "\n".join(lines)


def sheet_params(lines: str) -> dict[str, str]:
    """The document parameters of the held sheet records ``lines`` that KiCad's title block has no field for
    (``SheetNumber``, ``SheetTotal``, a parameter of the user), by name, as the Altium reader takes them: a
    parameter record (41) without an owner, with a name and a text other than ``*`` (change c0470)."""
    found: dict[str, str] = {}
    for line in lines.splitlines():
        fields = dict(part.split("=", 1) for part in line.strip().strip("|").split("|") if "=" in part)
        if fields.get("RECORD") != "41" or "OWNERINDEX" in fields:
            continue
        name = fields.get("%UTF8%NAME") or fields.get("NAME", "")
        value = fields.get("%UTF8%TEXT") or fields.get("TEXT", "")
        if not name or not value or value == "*" or name.casefold() in _TITLE_NAMES:
            continue
        if name.startswith("Fenolite."):
            continue  # a carrier, never a title-block field
        found.setdefault(name, value)
    return found


def restore(drawn: DrawnSchematic, carriers: Mapping[str, AltiumSheet]) -> DrawnSchematic:
    """``drawn`` read back from KiCad with the Altium records of its carriers: each stand-in that a carrier
    names gets its record text, and each record without a stand-in is added as an opaque item."""
    sheets: list[DrawnSheet] = []
    for sheet in drawn.sheets:
        carrier = carriers.get(sheet.key)
        if carrier is None:
            sheets.append(sheet)
            continue
        by_uuid = {uuid: text for uuid, text in carrier.opaques if uuid}
        opaques = [
            replace(o, altium=by_uuid.get(stand_in_uuid(o.kicad), o.altium)) if o.kicad else o
            for o in sheet.opaques
        ]
        opaques += [DrawnOpaque("", text) for uuid, text in carrier.opaques if not uuid]
        block = list(sheet.title_block)
        held = {name for name, _ in block}
        block += [
            (f"param.{k}", v)
            for k, v in sorted(sheet_params(carrier.sheet).items())
            if f"param.{k}" not in held
        ]
        sheets.append(replace(sheet, opaques=tuple(opaques), title_block=tuple(block)))
    return replace(drawn, sheets=tuple(sheets))


__all__ = [
    "ALTIUM_NAME",
    "ALTIUM_SCHEMA",
    "COMMENT",
    "AltiumSheet",
    "altium_sheet",
    "param_lines",
    "put",
    "put_drawing",
    "restore",
    "sheet_files",
    "stand_in_uuid",
    "take",
    "take_drawing",
    "TOML_PREFIX",
    "carried_fields",
    "carried_sheets",
    "from_toml_text",
    "toml_footer",
]
