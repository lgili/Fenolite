# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The licence lists of ``fenolite-library`` (schema ``fenolite.library-licences.v0``; change c0279,
``docs/library-repo.md``, "Licences").

The allow-list is closed: each allowed SPDX id belongs to one family folder, which says whether it is
reciprocal and what a copy must carry. Any other id is refused with a precise reason (``non-commercial``,
``no-derivatives``, ``no-licence``, ``licence-ref`` or ``not-allowed``); an upstream on a platform whose terms
forbid copying gives ``platform-restricted``, an example bundled with commercial CAD software
``vendor-bundled``. The core ships a copy as ``fenolite/cli/data/library-licences.toml``; the library
commits its own ``licences.toml``, which the audit reads when it is there.
"""

from __future__ import annotations

import hashlib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from pathlib import Path
from types import MappingProxyType
from typing import Any, cast

LICENCES_SCHEMA = "fenolite.library-licences.v0"
SHIPPED = "library-licences.toml"
LIBRARY_FILE = "licences.toml"
CC0 = "CC0-1.0"
NO_LICENCE = frozenset({"", "NOASSERTION", "NONE"})


@dataclass(frozen=True, slots=True)
class Family:
    """A family folder: its name, ids, whether it is reciprocal and what a copy must carry."""

    name: str
    ids: tuple[str, ...]
    reciprocal: bool
    obligations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Licences:
    """The lists: families by name, aliases (an SPDX expression → its allowed id), the digests of accepted
    normalised texts per id, and the platform hosts."""

    families: Mapping[str, Family]
    aliases: Mapping[str, str]
    texts: Mapping[str, tuple[str, ...]]
    platform_hosts: tuple[str, ...]

    def canonical(self, spdx: str) -> str:
        return self.aliases.get(spdx, spdx)

    def family_of(self, spdx: str) -> Family | None:
        wanted = self.canonical(spdx)
        return next((family for family in self.families.values() if wanted in family.ids), None)

    def deny_reason(self, spdx: str) -> str | None:
        """Why ``spdx`` is refused, or ``None`` when it is allowed."""
        if self.family_of(spdx) is not None:
            return None
        text = spdx.strip()
        upper = text.upper()
        if upper in NO_LICENCE:
            return "no-licence"
        if text.startswith("LicenseRef-") or "LICENSEREF-" in upper:
            return "licence-ref"
        words = upper.replace(" ", "-").split("-")
        if "NC" in words:
            return "non-commercial"
        if "ND" in words:
            return "no-derivatives"
        return "not-allowed"

    def host_denied(self, host: str) -> bool:
        host = host.lower()
        return any(host == denied or host.endswith("." + denied) for denied in self.platform_hosts)


def normalised_digest(text: bytes) -> str:
    """The SHA-256 of a licence text in lower case with whitespace runs collapsed to one space."""
    words = text.decode("utf-8", errors="replace").lower().split()
    return hashlib.sha256(" ".join(words).encode("utf-8")).hexdigest()


def parse_licences(text: str, *, file: str = SHIPPED) -> Licences:
    """The lists in ``text``; ``ValueError`` naming the file for a malformed table."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"{file}: not valid TOML: {exc}") from None
    if data.get("schema") != LICENCES_SCHEMA:
        raise ValueError(f"{file}: schema must be {LICENCES_SCHEMA!r}")
    families: dict[str, Family] = {}
    seen: dict[str, str] = {}
    for name, raw in cast(dict[str, Any], data.get("families", {})).items():
        table = cast(dict[str, Any], raw)
        ids = tuple(cast(list[str], table.get("ids", [])))
        for spdx in ids:
            if spdx in seen:
                raise ValueError(f"{file}: {spdx} is in the families {seen[spdx]} and {name}")
            seen[spdx] = name
        families[name] = Family(
            name,
            ids,
            bool(table.get("reciprocal", False)),
            tuple(cast(list[str], table.get("obligations", []))),
        )
    aliases = {str(k): str(v) for k, v in cast(dict[str, Any], data.get("aliases", {})).items()}
    texts = {
        str(k): tuple(cast(list[str], v)) for k, v in cast(dict[str, Any], data.get("texts", {})).items()
    }
    hosts = tuple(str(h).lower() for h in cast(list[object], data.get("platform_hosts", [])))
    return Licences(MappingProxyType(families), MappingProxyType(aliases), MappingProxyType(texts), hosts)


def shipped_text() -> str:
    return resources.files("fenolite.cli").joinpath("data", SHIPPED).read_text(encoding="utf-8")


@cache
def shipped() -> Licences:
    """The lists shipped with the core."""
    return parse_licences(shipped_text())


def for_root(root: Path) -> Licences:
    """The lists of a library checkout: its ``licences.toml``, else the shipped copy."""
    path = root / LIBRARY_FILE
    if path.is_file():
        return parse_licences(path.read_text(encoding="utf-8"), file=LIBRARY_FILE)
    return shipped()


__all__ = [
    "CC0",
    "LIBRARY_FILE",
    "LICENCES_SCHEMA",
    "SHIPPED",
    "Family",
    "Licences",
    "for_root",
    "normalised_digest",
    "parse_licences",
    "shipped",
    "shipped_text",
]
