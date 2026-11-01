# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored offline machinery; no provider permission is asserted by the test policy."""

from __future__ import annotations

import json
import socket
import sys
from dataclasses import replace
from typing import Any

import pytest

from fenolite.suppliers.http import Request, Response
from fenolite.suppliers.policy import RateLimit, SourcePolicy, policy_for


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.waits: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.waits.append(seconds)
        self.now += seconds


class FakeTransport:
    def __init__(self, *responses: Response | Exception) -> None:
        self.responses = list(responses)
        self.requests: list[Request] = []
        self.timeouts: list[float] = []

    def request(self, request: Request, *, timeout: float, hosts: tuple[str, ...]) -> Response:
        self.requests.append(request)
        self.timeouts.append(timeout)
        value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        return value


def response(value: Any, status: int = 200, **headers: str) -> Response:
    return Response(status, headers, json.dumps(value).encode())


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("supplier proofs must not open sockets")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setitem(sys.modules, "keyring", None)
    for source in ("DIGIKEY", "MOUSER", "NEXAR", "FARNELL"):
        for name in ("CLIENT_ID", "CLIENT_SECRET", "API_KEY"):
            monkeypatch.delenv(f"FENOLITE_{source}_{name}", raising=False)


@pytest.fixture
def policy() -> SourcePolicy:
    return replace(
        policy_for("mouser"),
        terms=("AUTHORED-TEST-POLICY",),
        attribution="Authored fixture acknowledgement",
        ready=True,
        persist=("manufacturer", "mpn", "datasheet"),
        cache="process",
        max_age_s=10,
        terms_max_age_s=10,
        rate=RateLimit(120, 1000),
    )
