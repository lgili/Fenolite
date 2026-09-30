# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The repository itself is free of residue (private lists are used when configured)."""

from __future__ import annotations

import _scanmod

scan = _scanmod.load()


def test_repository_has_no_residue() -> None:
    config = scan.load_config()
    hits, count = scan.scan(scan.REPO, config)
    assert count > 0
    assert not hits, "residue found (path:offset:pattern):\n" + "\n".join(h.line() for h in hits)
