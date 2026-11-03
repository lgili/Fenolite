# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pre-runtime reference-closure control only; it never admits a physical correspondence (c0355)."""

from __future__ import annotations

import json
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping

from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node


def unreferenced_id_facts(root: Node, companions: Mapping[str, bytes] | None = None) -> dict:
    definitions = defaultdict(list)
    own_paths = set()

    def gather(n, path=(), parent=None):
        if isinstance(n, Atom):
            return
        if (n.name in {"via", "segment", "arc"} and parent == "kicad_pcb") or (
            n.name == "pad" and parent == "footprint"
        ):
            fields = [c for c in n.children if isinstance(c, Node) and c.name in {"uuid", "tstamp"}]
            if (
                len(fields) != 1
                or len(fields[0].atoms()) != 1
                or len(fields[0].children) != 1
                or fields[0].atoms()[0].kind != AtomKind.STRING
            ):
                raise ValueError("electrical identity is missing, duplicated or malformed")
            value = fields[0].atoms()[0]
            try:
                canonical = str(uuid.UUID(value.value))
            except ValueError as error:
                raise ValueError("electrical identity is malformed") from error
            definitions[canonical].append(n.name)
            own_paths.add((*path, n.children.index(fields[0]), 0))
        for index, child in enumerate(n.children):
            gather(child, (*path, index), n.name)

    gather(root)
    if any(len(set(kinds)) != 1 for kinds in definitions.values()):
        raise ValueError("native identity aliases different electrical kinds")
    forms = {form for uid in definitions for form in (uid.casefold(), uid.replace("-", "").casefold())}

    def check_text(value):
        if len(value) < 32:
            return
        if any(form in value.casefold() for form in forms):
            raise ValueError("affected native identity has an external or unknown reference")

    def scan(n, path=()):
        if isinstance(n, Atom):
            if path not in own_paths:
                check_text(n.value)
            return
        for index, child in enumerate(n.children):
            scan(child, (*path, index))

    scan(root)

    def strings(value):
        if isinstance(value, str):
            check_text(value)
        elif isinstance(value, dict):
            for key, child in value.items():
                check_text(str(key))
                strings(child)
        elif isinstance(value, list):
            for child in value:
                strings(child)

    for name, raw in (companions or {}).items():
        text = raw.decode("utf-8")
        check_text(text)
        if name.endswith(".kicad_pro"):
            strings(json.loads(text))
    return {
        "definition_fields": sum(map(len, definitions.values())),
        "distinct_ids": len(definitions),
        "definition_kinds": dict(Counter(kind for kinds in definitions.values() for kind in kinds)),
        "aliased_ids": sum(len(kinds) > 1 for kinds in definitions.values()),
        "external_references": 0,
        "physical_correspondence_or_runtime_admission_claimed": False,
    }
