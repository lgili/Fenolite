# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Supplier failures carry only source names and local diagnostics (c0267)."""

from fenolite.core.errors import FenoliteError, Issue


class SupplierError(FenoliteError):
    cli_code = "FEN-6003"

    def __init__(
        self,
        message: str,
        *,
        hint: str = "check supplier documentation and readiness; keep credentials out of reports",
        issues: tuple[Issue, ...] = (),
    ) -> None:
        super().__init__(message)
        self.hint = hint
        self.issues = issues


class CredentialsMissing(SupplierError):
    cli_code = "FEN-6001"


class CredentialsRejected(SupplierError):
    cli_code = "FEN-6005"


class ResponseShapeError(SupplierError):
    cli_code = "FEN-3004"
