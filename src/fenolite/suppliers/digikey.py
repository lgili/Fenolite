# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""DigiKey registration; source readiness is closed (docs/formats/suppliers/digikey.md)."""

from fenolite.suppliers.base import SupplierPlugin


class DigiKey(SupplierPlugin):
    name = "digikey"
