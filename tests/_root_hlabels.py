# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite-authored root hierarchical ports; no parent or hidden scope is invented (c0350)."""

from dataclasses import replace

import _bus_scope


def drawing(*, child_mismatch: bool = False, equal: bool = True):
    value = _bus_scope.scalar_labels("hierarchical" if child_mismatch else "local", equal=equal)
    root, child = value.sheets
    root = replace(
        root,
        labels=tuple(replace(label, kind="hierarchical", shape="input") for label in root.labels),
    )
    return replace(value, sheets=(root, child))
