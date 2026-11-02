# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored DigiKey OAuth/search proofs grant no production rights or live-access claim."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from urllib.parse import parse_qs

import pytest

from fenolite.pick.query import parse_query
from fenolite.suppliers import credentials
from fenolite.suppliers.cache import ProcessCache
from fenolite.suppliers.digikey import DigiKey
from fenolite.suppliers.errors import CredentialsMissing, CredentialsRejected, ResponseShapeError
from fenolite.suppliers.policy import SourcePolicy
from tests.unit.suppliers.conftest import FakeTransport, response

FIXTURES = Path(__file__).resolve().parents[3] / "tests/fixtures/suppliers/digikey"


def enabled(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> DigiKey:
    plugin = DigiKey()
    plugin.policy = replace(policy, name="digikey", hosts=plugin.policy.hosts, cache="none", max_age_s=0)
    plugin.cache = ProcessCache(plugin.policy)
    monkeypatch.setenv("FENOLITE_DIGIKEY_CLIENT_ID", "AUTHORED-ID+space canary")
    monkeypatch.setenv("FENOLITE_DIGIKEY_CLIENT_SECRET", "AUTHORED-SECRET+space canary")
    return plugin


def fixture(name: str) -> dict[str, object]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def test_unverified_source_cannot_request(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object) -> None:
        raise AssertionError("readiness must be checked first")

    monkeypatch.setattr(credentials, "lookup", forbidden)
    plugin = DigiKey()
    with pytest.raises(CredentialsMissing, match="unverified|verified"):
        plugin.lookup(parse_query("capacitor(100nF)"), timestamp="2026-11-01T00:00:00Z")
    assert not plugin.available() and plugin.policy.cache == "none" and plugin.policy.persist == ()


def test_authored_keyword_response_only_query_leaves(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    plugin = enabled(policy, monkeypatch)
    data = fixture("keyword_mlcc")
    data["Products"] *= 2
    transport = FakeTransport(response(fixture("auth-reply")), response(data))
    query = parse_query("capacitor(100nF, rating>=25V, case=0603)")
    result = plugin.lookup(query, limit=1, timeout=5, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert len(result.drafts) == 1 and result.drafts[0].display["mpn"] == "EX03R104KAT"
    assert result.drafts[0].display["offer"]["UnitPrice"] == "0.25"
    assert result.drafts[0].display["reported"] == {"Parameters": []}
    token, search = transport.requests
    assert token.url == "https://api.digikey.com/v1/oauth2/token" and token.method == "POST"
    assert parse_qs(token.body.decode("ascii")) == {
        "client_id": ["AUTHORED-ID+space canary"],
        "client_secret": ["AUTHORED-SECRET+space canary"],
        "grant_type": ["client_credentials"],
    }
    assert search.url == "https://api.digikey.com/products/v4/search/keyword" and search.method == "POST"
    assert search.headers["Authorization"] == "Bearer AUTHORED-DIGIKEY-TOKEN"
    assert search.headers["X-DIGIKEY-Client-Id"] == "AUTHORED-ID+space canary"
    assert json.loads(search.body) == {"Keywords": query.text(), "Limit": 1, "Offset": 0}
    assert "secret-board" not in str(transport.requests) + str(search.body)
    for value in ("AUTHORED-ID", "AUTHORED-SECRET", "AUTHORED-DIGIKEY-TOKEN"):
        assert value not in repr(transport.requests) + str(result)


@pytest.mark.parametrize(
    "data",
    [
        {},
        {"access_token": "", "token_type": "Bearer"},
        {"access_token": "AUTHORED\r\nheader", "token_type": "Bearer"},
        {"access_token": "AUTHORED", "token_type": "Basic"},
    ],
)
def test_invalid_token_never_reaches_search(
    data: dict[str, object], policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    transport = FakeTransport(response(data))
    with pytest.raises(ResponseShapeError) as caught:
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"), timestamp="2026-11-01T00:00:00Z", transport=transport
        )
    assert len(transport.requests) == 1 and "AUTHORED" not in str(caught.value)


@pytest.mark.parametrize("stage", ["token", "search"])
def test_authentication_failure_has_no_remote_message(
    stage: str, policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    replies = [] if stage == "token" else [response(fixture("auth-reply"))]
    replies.append(response({"echo": "AUTHORED-SECRET+space canary"}, status=401))
    with pytest.raises(CredentialsRejected) as caught:
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(*replies),
        )
    assert caught.value.cli_code == "FEN-6005" and "canary" not in str(caught.value)


@pytest.mark.parametrize(
    "part",
    [
        None,
        {"ManufacturerProductNumber": "EXAMPLE", "Manufacturer": "invalid"},
        {"ManufacturerProductNumber": "EXAMPLE", "Parameters": None},
        {"ManufacturerProductNumber": "EXAMPLE", "ProductStatus": "invalid"},
    ],
)
def test_malformed_selected_product_is_refused(
    part: object, policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    with pytest.raises(ResponseShapeError):
        enabled(policy, monkeypatch).lookup(
            parse_query("capacitor(100nF)"),
            timestamp="2026-11-01T00:00:00Z",
            transport=FakeTransport(response(fixture("auth-reply")), response({"Products": [part]})),
        )


def test_empty_products_are_no_results(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> None:
    result = enabled(policy, monkeypatch).lookup(
        parse_query("capacitor(100nF)"),
        timestamp="2026-11-01T00:00:00Z",
        transport=FakeTransport(response(fixture("auth-reply")), response({"Products": []})),
    )
    assert not result.drafts and [issue.code for issue in result.issues] == ["supplier.no-results"]


def test_oversize_query_sends_no_token_request(policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch) -> None:
    query = parse_query('capacitor(100nF, series="' + "X" * 251 + '")')
    transport = FakeTransport()
    with pytest.raises(ValueError, match="250-character"):
        enabled(policy, monkeypatch).lookup(query, timestamp="2026-11-01T00:00:00Z", transport=transport)
    assert transport.requests == []


def test_received_token_is_redacted_before_any_draft(
    policy: SourcePolicy, monkeypatch: pytest.MonkeyPatch
) -> None:
    data = fixture("keyword_mlcc")
    data["Products"][0]["Manufacturer"]["Name"] = "AUTHORED-DIGIKEY-TOKEN"
    result = enabled(policy, monkeypatch).lookup(
        parse_query("capacitor(100nF)"),
        timestamp="2026-11-01T00:00:00Z",
        transport=FakeTransport(response(fixture("auth-reply")), response(data)),
    )
    assert result.drafts[0].display["manufacturer"] == "***"
    assert "AUTHORED-DIGIKEY-TOKEN" not in str(result)
