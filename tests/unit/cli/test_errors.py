# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Supplier authentication errors keep the existing CLI external-tool exit contract."""

from fenolite.cli.errors import REGISTRY, from_exception
from fenolite.suppliers.errors import CredentialsMissing, CredentialsRejected, SupplierError


def test_supplier_error_codes() -> None:
    for exception, code in (
        (CredentialsMissing, "FEN-6001"),
        (CredentialsRejected, "FEN-6005"),
        (SupplierError, "FEN-6003"),
    ):
        found = from_exception(exception("source unavailable", hint="own account"), "pick")
        assert found.code == code and int(found.exit_code) == 6
        assert found.hint == "own account" and REGISTRY[code].code == code
