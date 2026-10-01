# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identifiers of model entities: ``<prefix>_<uuid>``.

- imported objects with a native id: ``uuid5(FENOLITE_NS, "<backend>:<native id>")``;
- imported objects without one: ``uuid5(FENOLITE_NS, "<backend>:<document id>:<section>:<content hash>")``;
- created objects: ``uuid4`` drawn from an injectable seeded ``random.Random``.

A file hash never participates in an id.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import uuid

FENOLITE_NS = uuid.UUID("e59c7c86-e7fb-43e6-b058-8e03e7700b91")

PREFIXES: frozenset[str] = frozenset(
    {
        "dsn",  # Design
        "cmp", "pin", "net", "cls", "itf", "mod",  # circuit
        "brd", "lay", "stk", "sly", "fp", "pad", "pst", "trk", "arc", "via",  # board
        "zon", "kpo", "txt", "gfx", "hol", "out",  # board
        "rst", "rul",  # rules
        "mfn",  # manufacturing
        "fpd", "sym",  # library definitions
    }
)  # fmt: skip

_ID = re.compile(r"^([a-z]{2,3})_([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def _check(prefix: str) -> None:
    if prefix not in PREFIXES:
        raise ValueError(f"unknown id prefix {prefix!r} (one of {', '.join(sorted(PREFIXES))})")


def new_id(prefix: str, rng: random.Random) -> str:
    """A fresh id for an object created by Fenolite (reproducible with a seeded ``rng``)."""
    _check(prefix)
    return f"{prefix}_{uuid.UUID(int=rng.getrandbits(128), version=4)}"


def derived_id(prefix: str, backend: str, native_id: str) -> str:
    """The id of an imported object that has a native id (stable across imports)."""
    _check(prefix)
    return f"{prefix}_{uuid.uuid5(FENOLITE_NS, f'{backend}:{native_id}')}"


def content_hash(*parts: object) -> str:
    """SHA-256 of the canonical JSON of ``parts`` (ints, strings, lists, dicts)."""
    text = json.dumps(parts, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def content_id(prefix: str, backend: str, doc_native_id: str, section: str, digest: str) -> str:
    """The id of an imported object without a native id, derived from its normalised content."""
    _check(prefix)
    return f"{prefix}_{uuid.uuid5(FENOLITE_NS, f'{backend}:{doc_native_id}:{section}:{digest}')}"


def parse_id(value: str) -> tuple[str, uuid.UUID]:
    match = _ID.match(value)
    if not match or match.group(1) not in PREFIXES:
        raise ValueError(f"not a Fenolite id: {value!r}")
    return match.group(1), uuid.UUID(match.group(2))


def is_id(value: str, prefix: str | None = None) -> bool:
    try:
        found, _ = parse_id(value)
    except ValueError:
        return False
    return prefix is None or found == prefix


__all__ = [
    "FENOLITE_NS",
    "PREFIXES",
    "content_hash",
    "content_id",
    "derived_id",
    "is_id",
    "new_id",
    "parse_id",
]
