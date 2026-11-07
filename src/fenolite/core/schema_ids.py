# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Version acceptance for public formats whose prepared v1 grammar equals their v0 grammar.

Call only at an explicitly versioned document boundary. Device and family versions denote different
dialects and retain their own dispatch. This helper changes neither input data nor writer IDs.
"""

from __future__ import annotations


def accepts_schema(value: object, current: str) -> bool:
    return value == current or (current.endswith(".v0") and value == current[:-1] + "1")
