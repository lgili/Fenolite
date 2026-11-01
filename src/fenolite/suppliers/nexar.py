# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Nexar registration; source readiness is closed (docs/formats/suppliers/nexar.md)."""

from fenolite.suppliers.base import SupplierPlugin


class Nexar(SupplierPlugin):
    name = "nexar"
