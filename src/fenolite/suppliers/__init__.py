# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Optional per-user supplier lookups; production readiness follows recorded source evidence (c0267).

Only explicit supplier proposals load this package. Importing it reads no credential and opens no
connection. Policy metadata used by capabilities lives in ``fenolite.pick.supplier_policy``.
"""
