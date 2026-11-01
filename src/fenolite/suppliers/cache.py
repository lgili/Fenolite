# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A lookup-run-local memory cache; no module global, user cache or filesystem (c0267)."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, TypeVar

from fenolite.suppliers.policy import SourcePolicy

T = TypeVar("T")


class ProcessCache(Generic[T]):
    def __init__(self, policy: SourcePolicy, clock: Callable[[], float] = time.monotonic) -> None:
        self.policy, self.clock = policy, clock
        self._items: dict[str, tuple[float, T]] = {}

    def get(self, key: str) -> T | None:
        if self.policy.cache != "process":
            return None
        found = self._items.get(key)
        if found is None or self.clock() - found[0] >= self.policy.max_age_s:
            self._items.pop(key, None)
            return None
        return found[1]

    def put(self, key: str, value: T) -> None:
        if self.policy.cache == "process":
            self._items[key] = (self.clock(), value)

    def clear(self) -> None:
        self._items.clear()
