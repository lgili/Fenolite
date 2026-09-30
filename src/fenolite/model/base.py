# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The entity header shared by every model object, extension bags and backend slots."""

from __future__ import annotations

from dataclasses import dataclass, field

from fenolite.core.provenance import Provenance

ID_PATTERN = r"^[a-z]{2,3}_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"


@dataclass(frozen=True, slots=True)
class ExtBag:
    """What a backend knows about an object and the model does not: verbatim fragments.

    ``min_version`` is the oldest target format version able to load the fragments, so a writer
    never emits something the target cannot read.
    """

    min_version: str | None = None
    payload: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True, slots=True, kw_only=True)
class Entity:
    """Header of every model entity: stable id, native ids per backend, provenance, extensions."""

    id: str = field(metadata={"pattern": ID_PATTERN})
    native_ids: dict[str, str] = field(default_factory=lambda: {})
    provenance: Provenance | None = None
    ext: dict[str, ExtBag] = field(default_factory=lambda: {})


@dataclass(frozen=True, slots=True)
class Modeled:
    """A child of a backend node that maps to a model field."""

    field: str


@dataclass(frozen=True, slots=True)
class Opaque:
    """A child of a backend node the model does not understand, re-emitted verbatim in place."""

    fragment: str
    min_version: str | None = None


Slot = Modeled | Opaque


__all__ = ["ID_PATTERN", "Entity", "ExtBag", "Modeled", "Opaque", "Slot"]
