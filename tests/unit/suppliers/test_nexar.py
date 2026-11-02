# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored Nexar basic fields and strict errors; no account or add-on entitlement is assumed."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from fenolite.pick.query import parse_query
from fenolite.suppliers import base, credentials
from fenolite.suppliers.cache import ProcessCache
from fenolite.suppliers.errors import (
    CredentialsMissing,
    CredentialsRejected,
    ResponseShapeError,
    SupplierError,
)
from fenolite.suppliers.http import Client
from fenolite.suppliers.nexar import Nexar
from fenolite.suppliers.policy import SourcePolicy
from tests.unit.suppliers.conftest import FakeClock, FakeTransport, response

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/suppliers/nexar"


def enabled(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> Nexar:
    plugin = Nexar()
    plugin.policy = replace(policy, name="nexar", hosts=plugin.policy.hosts, cache="none", max_age_s=0)
    plugin.cache = ProcessCache(plugin.policy)
    monkeypatch.setenv("FENOLITE_NEXAR_CLIENT_ID", "AUTHORED-ID+space canary")
    monkeypatch.setenv("FENOLITE_NEXAR_CLIENT_SECRET", "AUTHORED-SECRET+space canary")
    return plugin


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_unverified_source_cannot_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("readiness must be checked first")

    monkeypatch.setattr(credentials, "lookup", forbidden)
    plugin = Nexar()
    with pytest.raises(CredentialsMissing, match="unverified|verified"):
        plugin.lookup(parse_query("capacitor(100nF)"), timestamp="2026-11-01T00:00:00Z")
    assert not plugin.available() and plugin.policy.cache == "none" and plugin.policy.persist == ()


def test_authored_basic_query_omits_addons_and_limits_results(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["data"]["supSearch"]["results"] *= 2
    transport = FakeTransport(response(fixture("auth-reply")), response(data))
    query = parse_query("capacitor(100nF, rating>=25V, case=0603)")
    result = enabled(policy, monkeypatch).lookup(
        query, limit=1, timeout=5, timestamp="2026-11-01T00:00:00Z", transport=transport
    )
    assert len(result.drafts) == 1 and result.drafts[0].display["mpn"] == "EX03R104KAT"
    assert result.drafts[0].display["datasheet"] == "" and result.drafts[0].display["reported"] == {}
    assert result.drafts[0].display["offer"]["sellers"][0]["offers"][0]["prices"][0]["price"] == "0.25"
    token, search = transport.requests
    assert token.url == "https://identity.nexar.com/connect/token" and token.method == "POST"
    assert parse_qs(token.body.decode("ascii")) == {
        "client_id": ["AUTHORED-ID+space canary"],
        "client_secret": ["AUTHORED-SECRET+space canary"],
        "grant_type": ["client_credentials"],
        "scope": ["supply.domain"],
    }
    assert search.url == "https://api.nexar.com/graphql" and search.method == "POST"
    assert search.headers["Authorization"] == "Bearer AUTHORED-NEXAR-TOKEN"
    document = json.loads(search.body)["query"]
    assert json.dumps(query.text()) in document and "limit: 1" in document
    assert all(name not in document for name in ("specs", "bestDatasheet", "cad", "lifecycle", "design"))
    assert "secret-board" not in str(search.body) + search.url
    for value in ("AUTHORED-ID", "AUTHORED-SECRET", "AUTHORED-NEXAR-TOKEN"):
        assert value not in repr(transport.requests) + str(result)


def test_query_text_stays_one_graphql_literal(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> None:
    query = replace(parse_query("capacitor(100nF)"), canonical='quoted"\\\n} query malicious {')
    transport = FakeTransport(
        response(fixture("auth-reply")), response({"data": {"supSearch": {"results": []}}})
    )
    enabled(policy, monkeypatch).lookup(query, limit=1, timestamp="2026-11-01T00:00:00Z", transport=transport)
    document = json.loads(transport.requests[1].body)["query"]
    tail = document.split("q: ", 1)[1]
    value, end = json.JSONDecoder().raw_decode(tail)
    assert value == query.text() and tail[end:].startswith(", limit: 1)")


@pytest.mark.parametrize("code", ["AuthInvalidToken", "AuthExpiredToken"])
def test_graphql_auth_error_never_uses_partial_data(
    code: str, policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["errors"] = [{"message": "AUTHORED-NEXAR-TOKEN", "extensions": {"code": code}}]
    with pytest.raises(CredentialsRejected) as caught:
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response(fixture("auth-reply")), response(data)),
        )
    assert caught.value.cli_code == "FEN-6005" and "AUTHORED" not in str(caught.value)


@pytest.mark.parametrize("errors", [None, "invalid", ["invalid"], [{"message": "AUTHORED-NEXAR-TOKEN"}]])
def test_unknown_graphql_errors_do_not_become_success(
    errors: object, policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["errors"] = errors
    with pytest.raises(ResponseShapeError) as caught:
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response(fixture("auth-reply")), response(data)),
        )
    assert "AUTHORED" not in str(caught.value)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"data": None},
        {"data": {"supSearch": {"results": "invalid"}}},
        {"data": {"supSearch": {"results": [{"part": None}]}}},
    ],
)
def test_undocumented_shape_is_refused(
    data: dict[str, object], policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ResponseShapeError):
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response(fixture("auth-reply")), response(data)),
        )


def test_selected_seller_price_array_is_validated(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["data"]["supSearch"]["results"][0]["part"]["sellers"][0]["offers"][0]["prices"] = "invalid"
    with pytest.raises(ResponseShapeError):
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response(fixture("auth-reply")), response(data)),
        )


def test_received_token_is_redacted_from_offers(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["data"]["supSearch"]["results"][0]["part"]["sellers"][0]["company"]["name"] = "AUTHORED-NEXAR-TOKEN"
    result = enabled(policy, monkeypatch).lookup(
        parse_query("capacitor(100nF)"),
        timestamp="2026-11-01T00:00:00Z",
        transport=FakeTransport(response(fixture("auth-reply")), response(data)),
    )
    assert result.drafts[0].display["offer"]["sellers"][0]["company"]["name"] == "***"
    assert "AUTHORED-NEXAR-TOKEN" not in str(result)


def test_empty_results_are_no_results(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> None:
    result = enabled(policy, monkeypatch).lookup(
        parse_query("capacitor(100nF)"),
        timestamp="2026-11-01T00:00:00Z",
        transport=FakeTransport(
            response(fixture("auth-reply")), response({"data": {"supSearch": {"results": []}}})
        ),
    )
    assert not result.drafts and [issue.code for issue in result.issues] == ["supplier.no-results"]


@pytest.mark.parametrize("code", ["AuthInvalidToken", "AuthoredUnknownError"])
def test_retry_warning_survives_a_graphql_error(
    code: str, policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    clock = FakeClock()
    monkeypatch.setattr(
        base,
        "Client",
        lambda policy, transport, *, timeout: Client(
            policy, transport, timeout=timeout, clock=clock, sleep=clock.sleep
        ),
    )
    transport = FakeTransport(
        response(fixture("auth-reply")),
        response({}, status=429, **{"Retry-After": "1"}),
        response({"errors": [{"extensions": {"code": code}}]}),
    )
    with pytest.raises(SupplierError) as caught:
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timeout=5,
            timestamp="2026-11-01T00:00:00Z",
            transport=transport,
        )
    assert [issue.code for issue in caught.value.issues] == ["supplier.rate-limited"]
    assert len(transport.requests) == 3 and 1 in clock.waits
