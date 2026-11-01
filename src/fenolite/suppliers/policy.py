# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable policy constraints; an unknown permission never becomes an enabled policy (c0267)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fenolite.pick.supplier_policy import metadata


@dataclass(frozen=True, slots=True)
class RateLimit:
    per_minute: int
    per_day: int | None = None

    def __post_init__(self) -> None:
        if self.per_minute <= 0 or (self.per_day is not None and self.per_day <= 0):
            raise ValueError("a rate limit is positive")


CacheScope = Literal["none", "process"]


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    name: str
    title: str
    terms: tuple[str, ...]
    attribution: str
    cache: CacheScope
    max_age_s: int
    terms_max_age_s: int | None
    rate: RateLimit
    sends: tuple[str, ...]
    persist: tuple[str, ...]
    evidence: str
    hosts: tuple[str, ...]
    ready: bool = False
    reason: str = "source permissions have not been verified"

    def __post_init__(self) -> None:
        if self.cache not in ("none", "process") or self.max_age_s < 0:
            raise ValueError("cache scope is none or process, with a nonnegative age")
        if self.cache == "none" and self.max_age_s:
            raise ValueError("a disabled cache has zero age")
        if self.cache == "process" and (
            self.terms_max_age_s is None or self.max_age_s > self.terms_max_age_s or not self.max_age_s
        ):
            raise ValueError("a process cache needs a verified age within its terms")
        if set(self.persist) - {"manufacturer", "mpn", "datasheet"}:
            raise ValueError("only identity fields can persist")
        if self.ready and (not self.terms or not self.attribution):
            raise ValueError("an enabled source needs recorded terms and attribution")


def policy_for(name: str) -> SourcePolicy:
    values = metadata(name)
    values.pop("credentials")
    values["rate"] = RateLimit(**values["rate"])
    return SourcePolicy(**values)
