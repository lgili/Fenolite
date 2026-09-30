# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""No list of private identifiers is committed, in clear or hashed form."""

from __future__ import annotations

import re
from pathlib import Path

import _scanmod

scan = _scanmod.load()
ALLOWED_IN_RESIDUE = {"README.md", "patterns.regex", "blobs.sha256", "scope.toml", "scan.py"}
LISTY_NAME = re.compile(
    r"(?i)(token|denylist|blocklist|deny-list|block-list)[^/]*\.(txt|sha256|lst|list|json|toml|csv)$"
)


def offending(files: list[str]) -> list[str]:
    bad = []
    for rel in files:
        parts = Path(rel).parts
        if parts[:2] == ("tools", "residue") and len(parts) == 3 and parts[2] not in ALLOWED_IN_RESIDUE:
            bad.append(rel)
        elif LISTY_NAME.search(rel):
            bad.append(rel)
    return bad


def test_no_token_list_in_repository() -> None:
    bad = offending(scan.tree_files(scan.REPO))
    assert not bad, "token lists must never be committed:\n" + "\n".join(bad)


def test_detector() -> None:
    assert offending(["tools/residue/tokens.sha256", "docs/private-tokens.txt", "tools/residue/scan.py"]) == [
        "tools/residue/tokens.sha256",
        "docs/private-tokens.txt",
    ]
