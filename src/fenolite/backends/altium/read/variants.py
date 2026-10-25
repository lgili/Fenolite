# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly variants of an Altium project file (``docs/formats/altium/project.md``, "Variants"; change
c0186).

A ``[ProjectVariant<n>]`` section names a variant (``Description``) and lists its part variations
(``Variation<k>=Designator=…|UniqueId=…|Kind=…|AlternatePart=…``) and its parameter variations
(``ParamVariation<k>=ParameterName=…|VariantValue=…`` with ``ParamDesignator<k>``, the part they apply to).
``Kind`` 1 is a part not fitted, 2 a part replaced by an alternate part, 0 a part fitted with varied
parameters (``H-A-PRJ-VARIANT``, INFERRED). The reader keeps the fields it does not use in ``fields``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.backends.altium.read.ini import IniSection, parse_ini
from fenolite.core.evidence import Evidence, Level

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-PRJ-VARIANT",))

NOT_FITTED, ALTERNATE, FITTED = 1, 2, 0
KINDS = {FITTED: "fitted", NOT_FITTED: "not fitted", ALTERNATE: "alternate part"}


@dataclass(frozen=True, slots=True)
class Variation:
    """One part of a variant: its designator, its unique id path, its kind and every field of the line."""

    designator: str
    unique_id: str
    kind: int
    fields: tuple[tuple[str, str], ...] = ()

    @property
    def fitted(self) -> bool:
        return self.kind != NOT_FITTED


@dataclass(frozen=True, slots=True)
class Variant:
    """A variant: its name, its unique id, its part variations and its parameter values per designator."""

    name: str
    unique_id: str
    variations: tuple[Variation, ...]
    parameters: dict[str, dict[str, str]] = field(default_factory=lambda: {})
    unknown_kinds: int = 0

    def variation(self, designator: str, unique_id: str = "") -> Variation | None:
        """The variation of a part: by its unique id path when given and listed, else by its designator."""
        if unique_id:
            found = next((v for v in self.variations if v.unique_id == unique_id), None)
            if found is not None:
                return found
        return next((v for v in self.variations if v.designator == designator), None)


def _fields(value: str) -> tuple[tuple[str, str], ...]:
    out: list[tuple[str, str]] = []
    for part in value.split("|"):
        key, sep, text = part.partition("=")
        if sep:
            out.append((key.strip(), text.rstrip()))
    return tuple(out)


def _variant(section: IniSection) -> Variant:
    variations: list[Variation] = []
    unknown = 0
    params: dict[str, dict[str, str]] = {}
    pending: dict[str, tuple[str, str]] = {}
    for entry in section.entries:
        if entry.key.startswith("Variation") and entry.key[len("Variation") :].isdigit():
            fields = _fields(entry.value)
            values = dict(fields)
            try:
                kind = int(values.get("Kind", ""))
            except ValueError:
                kind = -1
            if kind not in KINDS:
                unknown += 1
            variations.append(
                Variation(values.get("Designator", ""), values.get("UniqueId", ""), kind, fields)
            )
        elif entry.key.startswith("ParamVariation") and entry.key[len("ParamVariation") :].isdigit():
            values = dict(_fields(entry.value))
            pending[entry.key[len("ParamVariation") :]] = (
                values.get("ParameterName", ""),
                values.get("VariantValue", ""),
            )
        elif entry.key.startswith("ParamDesignator") and entry.key[len("ParamDesignator") :].isdigit():
            found = pending.pop(entry.key[len("ParamDesignator") :], None)
            if found is not None and found[0]:
                params.setdefault(entry.value.strip(), {})[found[0]] = found[1]
    return Variant(
        section.get("Description") or "", section.get("UniqueID") or "", tuple(variations), params, unknown
    )


def read_variants(data: bytes, *, file: str = "") -> tuple[Variant, ...]:
    """The variants of a project file, in section order."""
    ini = parse_ini(data, file=file)
    return tuple(_variant(section) for _n, section in ini.numbered("ProjectVariant"))


__all__ = ["ALTERNATE", "FITTED", "KINDS", "NOT_FITTED", "Variant", "Variation", "read_variants"]
