# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""One lookup object owns one bounded memory cache; nothing reaches disk or another object."""

from dataclasses import replace
from pathlib import Path

import pytest

from fenolite.suppliers.cache import ProcessCache
from fenolite.suppliers.policy import SourcePolicy
from tests.unit.suppliers.conftest import FakeClock


def test_age_and_instance_scope(policy: SourcePolicy, tmp_path: Path) -> None:
    clock = FakeClock()
    cache: ProcessCache[str] = ProcessCache(policy, clock)
    cache.put("q", "authored answer")
    assert cache.get("q") == "authored answer"
    other: ProcessCache[str] = ProcessCache(policy, clock)
    assert other.get("q") is None
    clock.now = 10
    assert cache.get("q") is None
    cache.put("q", "again")
    cache.clear()
    assert cache.get("q") is None and list(tmp_path.iterdir()) == []


def test_none_never_retains(policy: SourcePolicy) -> None:
    cache: ProcessCache[str] = ProcessCache(replace(policy, cache="none", max_age_s=0))
    cache.put("q", "authored answer")
    assert cache.get("q") is None and not cache._items


def test_process_requires_known_terms_age(policy: SourcePolicy) -> None:
    for values in (
        {"terms_max_age_s": None},
        {"max_age_s": 11},
        {"max_age_s": 0},
        {"persist": ("price",)},
        {"terms": ()},
    ):
        with pytest.raises(ValueError):
            replace(policy, **values)


def test_lookup_cache_is_redacted_and_never_shared_between_runs(
    policy: SourcePolicy,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from fenolite.pick.query import parse_query
    from fenolite.suppliers.mouser import Mouser
    from tests.unit.suppliers.conftest import FakeTransport, response

    secret = "AUTHORED-CACHE-CANARY"
    monkeypatch.setenv("FENOLITE_MOUSER_API_KEY", secret)
    clock = FakeClock()
    body = {
        "SearchResults": {
            "Parts": [{"ManufacturerPartNumber": "EX03R104KAT", "Manufacturer": "Example " + secret}]
        }
    }
    transport = FakeTransport(response(body), response(body), response(body))
    plugin = Mouser()
    plugin.policy = policy
    plugin.cache = ProcessCache(policy, clock)
    query = parse_query("capacitor(100nF)")
    for _ in range(2):
        plugin.lookup(query, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert len(transport.requests) == 1 and secret not in repr(plugin.cache._items)
    other = Mouser()
    other.policy = policy
    other.cache = ProcessCache(policy, clock)
    other.lookup(query, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert len(transport.requests) == 2
    clock.now = 10
    plugin.lookup(query, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert len(transport.requests) == 3
