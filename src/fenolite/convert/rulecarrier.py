# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule records of an Altium document carried through KiCad (change c0434; capability
design-conversion, "Rule records through KiCad").

A conversion of an Altium document to KiCad writes, in the board property ``Fenolite.Altium.Rules6``
(``backends.kicad.boardcarrier``), every rule record of the document (its kind number and its keys from
``RULEKIND`` on, ``adapter.rules``'s ``kept_text`` form) with the SHA-256 of each rule list of the
``.kicad_dru`` that it gave, as written (``dru.rule_text``). A conversion of that board back to Altium
writes each record whose rule lists are still in the rules file as written, or that gave none, as it was
read (name, priority, scopes, enabled state, limits), and lowers only the rules of the rules file that no
such record accounts for. A record whose rule lists were edited or removed in KiCad is not written from the
property: its rules are lowered as KiCad holds them.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

PROPERTY = "Fenolite.Altium.Rules6"
"""The board property that carries the records (``boardcarrier``)."""
SCHEMA = "fenolite.altium-rules.v0"


@dataclass(frozen=True, slots=True)
class Carried:
    """One rule record of the source document: its kind number, its keys from ``RULEKIND`` on, and the
    rule lists it gave in the rules file (rule name → the SHA-256 of the list as Fenolite writes it,
    ``digest``)."""

    number: int
    fields: tuple[tuple[str, str], ...]
    blocks: Mapping[str, str]

    @property
    def name(self) -> str:
        return dict(self.fields).get("NAME", "")

    def kept(self, current: Mapping[str, str]) -> bool:
        """True when every rule list it gave is in ``current`` (rule name → ``digest``) as written; always,
        when it gave none."""
        return all(current.get(name) == text for name, text in self.blocks.items())


def digest(text: str) -> str:
    """The SHA-256 (hex) of a rule list's text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def carrier_text(records: Sequence[Carried]) -> str:
    """The JSON text the property packs: one object, keys sorted, one record per line."""
    rows = [
        json.dumps(
            {
                "number": r.number,
                "fields": [list(p) for p in r.fields],
                "blocks": dict(sorted(r.blocks.items())),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        for r in records
    ]
    body = ",\n".join(f"  {row}" for row in rows)
    return f'{{"schema": "{SCHEMA}", "records": [\n{body}\n]}}\n'


def read_carrier(text: str) -> tuple[Carried, ...]:
    """The records of a carrier text; ``ValueError`` for another schema or a malformed record."""
    data = json.loads(text)
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:  # pyright: ignore[reportUnknownMemberType]
        raise ValueError(f"not a {SCHEMA} file")
    found: list[Carried] = []
    try:
        for row in cast(list[dict[str, Any]], data["records"]):
            pairs = cast(list[list[Any]], row["fields"])
            fields = tuple((str(key), str(value)) for key, value in pairs)
            blocks = {str(name): str(body) for name, body in cast(dict[str, Any], row["blocks"]).items()}
            found.append(Carried(int(row["number"]), fields, blocks))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"a malformed {SCHEMA} record: {error}") from None
    return tuple(found)


def dru_blocks(text: str | None) -> dict[str, str]:
    """Rule name → the ``digest`` of the rule list as Fenolite writes it (``dru.rule_text``), for every rule
    of a rules file; empty without a file or for a file that does not parse."""
    from fenolite.backends.kicad.dru import RuleItem, parse_rules, rule_text
    from fenolite.core.errors import FormatError

    if not text:
        return {}
    try:
        document = parse_rules(text)
    except FormatError:
        return {}
    found: dict[str, str] = {}
    for item in document.items:
        if not isinstance(item, RuleItem):
            continue
        atoms = item.node.atoms()
        if atoms:
            found.setdefault(str(atoms[0].value), digest(rule_text(item.node)))
    return found


__all__ = ["PROPERTY", "SCHEMA", "Carried", "carrier_text", "digest", "dru_blocks", "read_carrier"]
