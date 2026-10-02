# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The one error of the DSL: raised at the offending call, so the script's traceback points at it."""

from __future__ import annotations


class DslError(ValueError):
    """A design script used the DSL wrongly (a bare number as a length, a duplicate name, …)."""


__all__ = ["DslError"]
