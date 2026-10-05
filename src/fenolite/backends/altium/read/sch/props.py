# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Property lists of Altium schematic records, kept field for field.

A property list is the text of one record: fields separated by ``|``, each field ``KEY=VALUE`` split at its
first ``=`` (``docs/formats/altium/schematic-ascii.md``, "File form"; ``schematic-records.md``, "Reader's
choices"). Every field is kept in file order with its key as written and its value as raw bytes, so
``PropertyList.to_bytes()`` gives back the parsed bytes for every input. Lookup folds letter case. Values are
decoded late, by the rules of ``schematic-records.md``, "Text": the ``%UTF8%`` twin first, then UTF-8 for an
ASCII file whose whole content is UTF-8, then the reader's single-byte code page.
"""

from __future__ import annotations

import builtins
import codecs
import re
from dataclasses import dataclass, field
from functools import lru_cache

DEFAULT_CODEPAGE = "cp1252"
"""The code page a value is decoded in when no other rule applies (S-0130, S-0150 version 1)."""
UTF8_PREFIX = "%UTF8%"
_INTEGER = re.compile(rb"^\s*[+-]?\d+\s*$")


@lru_cache(maxsize=64)
def check_codepage(codepage: str) -> str:
    """The codec name of ``codepage`` when it is a single-byte text code page of the standard library, else
    ``ValueError`` naming it (S-0280)."""
    try:
        info = codecs.lookup(codepage)
    except LookupError:
        raise ValueError(f"unknown code page {codepage!r}") from None
    if not getattr(info, "_is_text_encoding", True):
        raise ValueError(f"code page {codepage!r} is not a text encoding")
    for lead in range(256):
        if len(bytes([lead]).decode(info.name, errors="replace")) != 1:
            raise ValueError(f"code page {codepage!r} is not a single-byte code page")
        for follow in (0x41, 0x80, 0xA1):
            if len(bytes([lead, follow]).decode(info.name, errors="replace")) != 2:
                raise ValueError(f"code page {codepage!r} is not a single-byte code page")
    return info.name


def decode_value(raw: bytes, codepage: str, *, utf8: bool = False) -> tuple[str, bool]:
    """``raw`` decoded as UTF-8 when ``utf8``, else in ``codepage``; undefined bytes become U+FFFD. The flag
    is ``True`` when every byte decoded."""
    encoding = "utf-8" if utf8 else codepage
    try:
        return raw.decode(encoding), True
    except UnicodeDecodeError:
        return raw.decode(encoding, errors="replace"), False


@dataclass(frozen=True, slots=True)
class Prop:
    """One field: ``key`` as written (decoded as Latin-1) and ``raw``, the value's bytes, or ``None`` for a
    field that is not ``KEY=VALUE``, whose ``key`` is then the whole field text."""

    key: str
    raw: bytes | None

    @property
    def folded(self) -> str:
        return self.key.upper()

    def to_bytes(self) -> bytes:
        key = self.key.encode("latin-1")
        return key if self.raw is None else key + b"=" + self.raw


def _index(items: tuple[Prop, ...]) -> tuple[dict[str, int], tuple[str, ...]]:
    first: dict[str, int] = {}
    repeated: list[str] = []
    for position, item in enumerate(items):
        if item.raw is None:
            continue
        folded = item.folded
        if folded in first:
            if folded not in repeated:
                repeated.append(folded)
        else:
            first[folded] = position
    return first, tuple(repeated)


@dataclass(frozen=True, slots=True)
class PropertyList:
    """The fields of one record in file order, with case-folded lookup and late text decoding."""

    items: tuple[Prop, ...]
    codepage: str = DEFAULT_CODEPAGE
    utf8: builtins.bool = False
    _first: dict[str, builtins.int] = field(
        default_factory=dict[str, builtins.int], compare=False, hash=False, repr=False
    )
    duplicates: tuple[str, ...] = field(default=(), compare=False)

    def __post_init__(self) -> None:
        first, repeated = _index(self.items)
        object.__setattr__(self, "_first", first)
        object.__setattr__(self, "duplicates", repeated)

    # --- bytes -------------------------------------------------------------------------------------------

    def to_bytes(self) -> bytes:
        """The parsed bytes: every field joined by ``|``."""
        return b"|".join(item.to_bytes() for item in self.items)

    # --- lookup ------------------------------------------------------------------------------------------

    def keys(self) -> tuple[str, ...]:
        """The folded keys in file order, without repeats; ``%UTF8%`` twins of a present key are left out."""
        out: list[str] = []
        for folded, _position in sorted(self._first.items(), key=lambda pair: pair[1]):
            if folded.startswith(UTF8_PREFIX) and folded[len(UTF8_PREFIX) :] in self._first:
                continue
            out.append(folded)
        return tuple(out)

    def all_keys(self) -> tuple[str, ...]:
        """Every folded key in file order without repeats, twins included."""
        return tuple(folded for folded, _ in sorted(self._first.items(), key=lambda pair: pair[1]))

    def has(self, key: str) -> builtins.bool:
        return key.upper() in self._first

    def prop(self, key: str) -> Prop | None:
        position = self._first.get(key.upper())
        return None if position is None else self.items[position]

    def raw(self, key: str) -> bytes | None:
        """The raw bytes of the first field named ``key`` (any letter case), or ``None``."""
        item = self.prop(key)
        return None if item is None else item.raw

    def get(self, key: str) -> str | None:
        """The text view of ``key``, or ``None`` when the key is missing."""
        return self.text(key) if self.has(key) else None

    # --- typed views -------------------------------------------------------------------------------------

    def text_ok(self, key: str) -> tuple[str, builtins.bool]:
        """The text view of ``key`` and whether every byte decoded; ``("", True)`` when missing."""
        twin = self.raw(UTF8_PREFIX + key)
        if twin is not None:
            text, ok = decode_value(twin, self.codepage, utf8=True)
            return text.strip(), ok
        raw = self.raw(key)
        if raw is None:
            return "", True
        text, ok = decode_value(raw, self.codepage, utf8=self.utf8)
        return text.strip(), ok

    def text(self, key: str, default: str = "") -> str:
        if not self.has(key) and not self.has(UTF8_PREFIX + key):
            return default
        return self.text_ok(key)[0]

    def int(self, key: str, default: builtins.int = 0) -> builtins.int:
        """The integer value of ``key``; ``default`` when it is missing or does not parse."""
        value = parse_int(self.raw(key))
        return default if value is None else value

    def bool(self, key: str) -> builtins.bool:
        """``True`` only for the value ``T``."""
        raw = self.raw(key)
        return raw is not None and raw.strip() == b"T"


def parse_int(raw: bytes | None) -> int | None:
    """A decimal integer with optional spaces and sign, or ``None``."""
    if raw is None or _INTEGER.match(raw) is None:
        return None
    return int(raw.strip())


def parse(payload: bytes, *, codepage: str = DEFAULT_CODEPAGE, utf8: bool = False) -> PropertyList:
    """Split ``payload`` (the record text, without a final NUL or line end) into fields at ``|`` and each
    field at its first ``=``. Every field is kept, so ``to_bytes()`` returns ``payload``."""
    items: list[Prop] = []
    for part in payload.split(b"|"):
        key, equals, value = part.partition(b"=")
        items.append(Prop(key.decode("latin-1"), value if equals else None))
    return PropertyList(tuple(items), codepage, utf8)


__all__ = [
    "DEFAULT_CODEPAGE",
    "UTF8_PREFIX",
    "Prop",
    "PropertyList",
    "check_codepage",
    "decode_value",
    "parse",
    "parse_int",
]
