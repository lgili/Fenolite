# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Conservative one-token bucket and run-local daily ceiling (c0267)."""

from __future__ import annotations

import time
from collections.abc import Callable

from fenolite.suppliers.errors import SupplierError
from fenolite.suppliers.policy import RateLimit


class TokenBucket:
    def __init__(
        self,
        rate: RateLimit,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.rate, self.clock, self.sleep = rate, clock, sleep
        self.next = clock()
        self.count = 0

    def acquire(self, deadline: float) -> None:
        if self.rate.per_day is not None and self.count >= self.rate.per_day:
            raise SupplierError("supplier request ceiling reached for this lookup run")
        delay = max(0, self.next - self.clock())
        if self.clock() + delay >= deadline:
            raise SupplierError("supplier rate wait exceeds the request timeout")
        if delay:
            self.sleep(delay)
        self.count += 1
        self.next = self.clock() + 60 / self.rate.per_minute
