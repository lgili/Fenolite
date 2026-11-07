# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Per-user credentials and refusal messages never disclose credential bytes."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from urllib.parse import quote, quote_plus

import pytest

from fenolite.cli.errors import from_exception
from fenolite.suppliers.credentials import Secret, hint, lookup, redact
from fenolite.suppliers.errors import CredentialsMissing, CredentialsRejected

CANARY = 'AUTHORED-canary-quote" space\n/plus+'


def test_secret_repr_and_all_encodings() -> None:
    secret = Secret(CANARY)
    assert repr(secret) == str(secret) == "***" and secret.reveal() == CANARY
    for encoded in (CANARY, quote(CANARY, safe=""), quote_plus(CANARY), json.dumps(CANARY)[1:-1]):
        assert CANARY not in redact(encoded, [secret]) and redact(encoded, [secret]) == "***"


def test_environment_precedes_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FENOLITE_MOUSER_API_KEY", CANARY)

    def forbidden(*args: object) -> None:
        raise AssertionError("keyring must not be read when the environment supplies the credential")

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=forbidden))
    assert lookup("mouser")["API_KEY"].reveal() == CANARY


def test_keyring_fallback_and_missing_hint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_MOUSER_API_KEY", raising=False)
    calls = []

    def get_password(service: str, name: str) -> str:
        calls.append((service, name))
        return CANARY

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=get_password))
    assert lookup("mouser")["API_KEY"].reveal() == CANARY
    assert calls == [("fenolite.suppliers.mouser", "API_KEY")]
    monkeypatch.setitem(sys.modules, "keyring", None)
    with pytest.raises(CredentialsMissing) as found:
        lookup("mouser")
    assert "FENOLITE_MOUSER_API_KEY" in found.value.hint
    assert "fenolite.suppliers.mouser" in found.value.hint
    assert CANARY not in str(found.value) + found.value.hint


def test_backend_exception_is_suppressed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FENOLITE_MOUSER_API_KEY", raising=False)

    def backend(*args: object) -> None:
        raise RuntimeError(CANARY)

    monkeypatch.setitem(sys.modules, "keyring", SimpleNamespace(get_password=backend))
    with pytest.raises(CredentialsMissing) as found:
        lookup("mouser")
    assert CANARY not in str(found.value)
    assert found.value.__cause__ is None


def test_rejected_credentials_code() -> None:
    error = from_exception(
        CredentialsRejected("mouser: credentials were refused", hint=hint("mouser")), "pick"
    )
    assert error.code == "FEN-6005" and int(error.exit_code) == 6 and not error.retryable
    assert CANARY not in str(error.info())


@pytest.mark.parametrize(
    "encoded",
    [
        "AUTHORED%2bCANARY%2fcredential",
        "AUTHORED%2BCANARY%2fcredential",
        "AUTHORED%2bCANARY%2Fcredential",
    ],
)
def test_percent_escape_hex_casing_is_redacted(encoded: str) -> None:
    secret = Secret("AUTHORED+CANARY/credential")
    assert redact("https://example.invalid/" + encoded, [secret]) == "https://example.invalid/***"


def test_percent_escape_matching_keeps_secret_letters_case_sensitive() -> None:
    secret = Secret("AUTHORED+CANARY/credential")
    for other in (
        "authored%2bCANARY%2fcredential",
        "AUTHORED%2bcanary%2fcredential",
        "AUTHORED%2bCANARY%2fCredential",
    ):
        assert redact(other, [secret]) == other
