# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded HTTPS, retry, host, size and redaction proofs over authored responses."""

from __future__ import annotations

from dataclasses import replace

import pytest

from fenolite.suppliers.credentials import Secret
from fenolite.suppliers.errors import CredentialsRejected, ResponseShapeError, SupplierError
from fenolite.suppliers.http import MAX_RESPONSE, Client, Request, Response, _Redirects, check_url
from fenolite.suppliers.policy import RateLimit, SourcePolicy
from tests.unit.suppliers.conftest import FakeClock, FakeTransport, response

URL = "https://api.mouser.com/authored"
CANARY = "AUTHORED-secret+credential"


@pytest.mark.parametrize(
    "url",
    [
        "http://api.mouser.com/a",
        "https://evil.invalid/a",
        "https://user:password@api.mouser.com/a",
        "https://api.mouser.com:bad/a",
        "https://api.mouser.com:444/a",
        "https://api.mouser.com.evil.invalid/a",
    ],
)
def test_forbidden_hosts_and_redirects(url: str) -> None:
    with pytest.raises(SupplierError):
        check_url(url, ("api.mouser.com",))
    with pytest.raises(SupplierError):
        _Redirects(("api.mouser.com",)).redirect_request(None, None, 302, "", {}, url)


@pytest.mark.parametrize("status", [401, 403])
def test_refused_credentials_do_not_echo_body_or_key(policy: SourcePolicy, status: int) -> None:
    transport = FakeTransport(response({"echo": CANARY}, status))
    client = Client(policy, transport)
    with pytest.raises(CredentialsRejected) as found:
        client.request_json(Request(URL + "?apiKey=" + CANARY, headers={"Authorization": CANARY}))
    assert CANARY not in str(found.value) + found.value.hint + repr(transport.requests)
    assert CANARY not in repr(Secret(CANARY))


def test_transport_exception_is_redacted(policy: SourcePolicy) -> None:
    client = Client(policy, FakeTransport(RuntimeError(CANARY)))
    with pytest.raises(SupplierError) as found:
        client.request_json(Request(URL))
    assert CANARY not in str(found.value) and found.value.__cause__ is None


def test_one_retry_after_and_repeated_429(policy: SourcePolicy) -> None:
    clock = FakeClock()
    transport = FakeTransport(response({}, 429, **{"Retry-After": "2"}), response({"ok": True}))
    client = Client(policy, transport, clock=clock, sleep=clock.sleep)
    assert client.request_json(Request(URL)) == {"ok": True}
    assert len(transport.requests) == 2 and clock.waits == [2]
    assert [i.code for i in client.issues] == ["supplier.rate-limited"]
    clock = FakeClock()
    transport = FakeTransport(response({}, 429, **{"Retry-After": "1"}), response({}, 429))
    client = Client(policy, transport, clock=clock, sleep=clock.sleep)
    with pytest.raises(SupplierError) as found:
        client.request_json(Request(URL))
    assert len(transport.requests) == 2 and len(found.value.issues) == 1


@pytest.mark.parametrize("retry", ["date unsupported", "-1", "30", "99999"])
def test_retry_must_fit_total_timeout(policy: SourcePolicy, retry: str) -> None:
    clock = FakeClock()
    transport = FakeTransport(response({}, 429, **{"Retry-After": retry}))
    with pytest.raises(SupplierError):
        Client(policy, transport, clock=clock, sleep=clock.sleep).request_json(Request(URL))
    assert len(transport.requests) == 1 and clock.waits == []


@pytest.mark.parametrize(
    "reply",
    [
        Response(200, body=b"not json"),
        Response(200, body=b"[]"),
        Response(200, body=b" " * (MAX_RESPONSE + 1)),
        Response(400),
    ],
)
def test_response_shape_and_size(policy: SourcePolicy, reply: Response) -> None:
    with pytest.raises(ResponseShapeError):
        Client(policy, FakeTransport(reply)).request_json(Request(URL))


@pytest.mark.parametrize("status", [408, 500, 503, 504])
def test_temporary_source_failure(policy: SourcePolicy, status: int) -> None:
    with pytest.raises(SupplierError):
        Client(policy, FakeTransport(Response(status))).request_json(Request(URL))


def test_rate_bucket_and_lookup_wide_timeout(policy: SourcePolicy) -> None:
    clock = FakeClock()
    transport = FakeTransport(response({}), response({}), response({}))
    client = Client(
        replace(policy, rate=RateLimit(60, 2)), transport, timeout=2, clock=clock, sleep=clock.sleep
    )
    client.request_json(Request(URL))
    client.request_json(Request(URL))
    assert clock.waits == [1] and transport.timeouts == [2, 1]
    with pytest.raises(SupplierError, match="ceiling"):
        client.request_json(Request(URL))
    clock.now = 2
    with pytest.raises(SupplierError):
        Client(policy, transport, timeout=1, clock=clock, sleep=clock.sleep).request_json(
            Request(URL), deadline=2
        )
    assert len(transport.requests) == 2


def test_slow_transport_cannot_return_a_late_success(policy: SourcePolicy) -> None:
    clock = FakeClock()

    class Slow(FakeTransport):
        def request(self, *args: object, **kwargs: object) -> Response:
            clock.now = 31
            return response({"too": "late"})

    with pytest.raises(SupplierError, match="timed out"):
        Client(policy, Slow(), clock=clock, sleep=clock.sleep).request_json(Request(URL))


def test_rate_warning_survives_a_second_rate_wait_timeout(policy: SourcePolicy) -> None:
    clock = FakeClock()
    transport = FakeTransport(response({}, 429, **{"Retry-After": "1"}))
    client = Client(replace(policy, rate=RateLimit(1)), transport, clock=clock, sleep=clock.sleep)
    with pytest.raises(SupplierError) as found:
        client.request_json(Request(URL))
    assert len(transport.requests) == 1 and found.value.issues[0].code == "supplier.rate-limited"


def test_unbounded_retry_header_is_refused(policy: SourcePolicy) -> None:
    transport = FakeTransport(response({}, 429, **{"Retry-After": "9" * 5000}))
    with pytest.raises(SupplierError, match="rate limited"):
        Client(policy, transport).request_json(Request(URL))
    assert len(transport.requests) == 1


def test_stdlib_transport_caps_reads_and_discards_error_bodies(monkeypatch: pytest.MonkeyPatch) -> None:
    import urllib.error
    import urllib.request

    from fenolite.suppliers.http import UrllibTransport

    sizes = []

    class Reply:
        status = 200
        headers = {"Content-Type": "application/json"}

        def __enter__(self) -> Reply:
            return self

        def __exit__(self, *args: object) -> None:
            pass

        def read(self, size: int) -> bytes:
            sizes.append(size)
            return b"{}"

    class Opener:
        fail = False

        def open(self, request: object, timeout: float) -> Reply:
            assert timeout == 7
            if self.fail:
                raise urllib.error.HTTPError(URL, 403, CANARY, {}, None)
            return Reply()

    opener = Opener()
    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: opener)
    transport = UrllibTransport()
    assert transport.request(Request(URL), timeout=7, hosts=("api.mouser.com",)).body == b"{}"
    assert sizes == [MAX_RESPONSE + 1]
    opener.fail = True
    refused = transport.request(Request(URL), timeout=7, hosts=("api.mouser.com",))
    assert refused.status == 403 and refused.body == b"" and CANARY not in repr(refused)
