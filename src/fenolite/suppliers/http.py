# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Bounded HTTPS transport with redacted failures and one bounded Retry-After retry (c0267)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from fenolite.core.errors import Issue
from fenolite.suppliers.credentials import Secret, hint
from fenolite.suppliers.errors import CredentialsRejected, ResponseShapeError, SupplierError
from fenolite.suppliers.policy import SourcePolicy
from fenolite.suppliers.ratelimit import TokenBucket

MAX_RESPONSE = 4 * 1024 * 1024


def check_url(url: str, hosts: tuple[str, ...]) -> None:
    try:
        value = urlsplit(url)
        port = value.port
    except ValueError:
        raise SupplierError("supplier URL or redirect is outside its HTTPS host policy") from None
    if (
        value.scheme != "https"
        or value.hostname not in hosts
        or value.username is not None
        or value.password is not None
        or port not in (None, 443)
    ):
        raise SupplierError("supplier URL or redirect is outside its HTTPS host policy")


@dataclass(frozen=True, slots=True)
class Request:
    url: str = field(repr=False)
    method: str = "GET"
    headers: Mapping[str, str] = field(default_factory=lambda: {}, repr=False)
    body: bytes | None = field(default=None, repr=False)


@dataclass(frozen=True, slots=True)
class Response:
    status: int
    headers: Mapping[str, str] = field(default_factory=lambda: {}, repr=False)
    body: bytes = field(default=b"", repr=False)


class Transport(Protocol):
    def request(self, request: Request, *, timeout: float, hosts: tuple[str, ...]) -> Response: ...


class _Redirects(urllib.request.HTTPRedirectHandler):
    def __init__(self, hosts: tuple[str, ...]) -> None:
        super().__init__()
        self.hosts = hosts

    def redirect_request(self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Any:
        check_url(newurl, self.hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class UrllibTransport:
    def request(self, request: Request, *, timeout: float, hosts: tuple[str, ...]) -> Response:
        check_url(request.url, hosts)
        opener = urllib.request.build_opener(_Redirects(hosts))
        req = urllib.request.Request(
            request.url, data=request.body, headers=dict(request.headers), method=request.method
        )
        try:
            with opener.open(req, timeout=timeout) as reply:
                return Response(reply.status, dict(reply.headers), reply.read(MAX_RESPONSE + 1))
        except urllib.error.HTTPError as error:
            # Never read or echo an authentication error's response body or URL.
            return Response(error.code, dict(error.headers))


class Client:
    def __init__(
        self,
        policy: SourcePolicy,
        transport: Transport | None = None,
        *,
        timeout: float = 30,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 0 < timeout <= 300:
            raise ValueError("supplier timeout must be above zero and at most 300 seconds")
        self.policy, self.transport = policy, transport if transport is not None else UrllibTransport()
        self.timeout, self.clock, self.sleep = timeout, clock, sleep
        self.deadline = clock() + timeout
        self.bucket = TokenBucket(policy.rate, clock=clock, sleep=sleep)
        self.issues: list[Issue] = []
        self.secrets: list[Secret] = []

    def request_json(self, request: Request, *, deadline: float | None = None) -> dict[str, Any]:
        end = self.deadline if deadline is None else min(deadline, self.deadline)
        for attempt in range(2):
            check_url(request.url, self.policy.hosts)
            try:
                self.bucket.acquire(end)
            except SupplierError as error:
                raise SupplierError(str(error), issues=tuple(self.issues)) from None
            try:
                response = self.transport.request(
                    request, timeout=end - self.clock(), hosts=self.policy.hosts
                )
            except SupplierError:
                raise
            except Exception:  # noqa: BLE001 - third-party transport exceptions may contain credentials
                raise SupplierError(
                    f"{self.policy.name}: HTTPS request failed", issues=tuple(self.issues)
                ) from None
            if self.clock() >= end:
                raise SupplierError(f"{self.policy.name}: lookup timed out", issues=tuple(self.issues))
            if response.status in (401, 403):
                raise CredentialsRejected(
                    f"{self.policy.name}: credentials were refused",
                    hint=hint(self.policy.name),
                    issues=tuple(self.issues),
                )
            if response.status == 429:
                retry = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), "")
                if not attempt and len(retry) <= 9 and retry.isdecimal() and self.clock() + int(retry) < end:
                    self.issues.append(
                        Issue(
                            "supplier.rate-limited", "warning", f"{self.policy.name}: waiting for Retry-After"
                        )
                    )
                    self.sleep(int(retry))
                    continue
                raise SupplierError(f"{self.policy.name}: request rate limited", issues=tuple(self.issues))
            if response.status >= 500 or response.status in (408, 504):
                raise SupplierError(
                    f"{self.policy.name}: source temporarily unavailable", issues=tuple(self.issues)
                )
            if response.status != 200 or len(response.body) > MAX_RESPONSE:
                raise ResponseShapeError(f"{self.policy.name}: unexpected response status or size")
            try:
                data = json.loads(response.body, parse_float=str)
            except (ValueError, UnicodeDecodeError):
                raise ResponseShapeError(f"{self.policy.name}: response is not a JSON object") from None
            if not isinstance(data, dict):
                raise ResponseShapeError(f"{self.policy.name}: response is not a JSON object")
            return cast(dict[str, Any], data)
        raise SupplierError(f"{self.policy.name}: request failed", issues=tuple(self.issues))


def request_json(client: Client, request: Request) -> dict[str, Any]:
    return client.request_json(request)
