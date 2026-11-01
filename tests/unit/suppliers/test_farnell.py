# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Farnell authored response mapping under a test-only permission; production stays unavailable."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from fenolite.pick.query import parse_query
from fenolite.suppliers.cache import ProcessCache
from fenolite.suppliers.errors import CredentialsMissing, ResponseShapeError
from fenolite.suppliers.farnell import Farnell
from fenolite.suppliers.policy import SourcePolicy
from tests.unit.suppliers.conftest import FakeTransport, response

ROOT = Path(__file__).resolve().parents[3]


def test_authored_keyword_response_only_query_leaves(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = Farnell()
    assert not plugin.available()
    plugin.policy = replace(policy, name="farnell", hosts=plugin.policy.hosts, cache="none", max_age_s=0)
    plugin.cache = ProcessCache(plugin.policy)
    monkeypatch.setenv("FENOLITE_FARNELL_API_KEY", "AUTHORED-KEY+space canary")
    data = json.loads((ROOT / "tests/fixtures/suppliers/farnell/keyword_mlcc.json").read_text())
    transport = FakeTransport(response(data))
    query = parse_query("capacitor(100nF, rating>=25V, case=0603)")
    result = plugin.lookup(query, limit=1, timeout=5, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert len(result.drafts) == 1 and result.drafts[0].display["mpn"] == "EX03R104KAT"
    assert result.drafts[0].display["offer"] and result.drafts[0].display["reported"]
    request = transport.requests[0]
    assert "secret-board" not in request.url + str(request.body)
    assert "AUTHORED-KEY" not in repr(request) + str(result)
    parameters = parse_qs(urlsplit(request.url).query)
    assert parameters["term"] == ["any:" + query.text()]
    assert parameters["callInfo.apiKey"] == ["AUTHORED-KEY+space canary"]
    assert parameters["resultsSettings.numberOfResults"] == ["1"] and request.body is None


def test_undocumented_shape_is_refused(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> None:
    plugin = Farnell()
    plugin.policy = replace(policy, name="farnell", hosts=plugin.policy.hosts)
    monkeypatch.setenv("FENOLITE_FARNELL_API_KEY", "AUTHORED-KEY")
    with pytest.raises(ResponseShapeError):
        plugin.lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response({"unexpected": []})),
        )


def test_production_permission_stays_closed() -> None:
    with pytest.raises(CredentialsMissing):
        Farnell().lookup(parse_query("capacitor(100nF)"), timestamp="2026-11-01T00:00:00Z")
