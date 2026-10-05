# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Public codes stay aligned between the reader, its fact page and both user pages."""

from __future__ import annotations

from pathlib import Path

from fenolite.backends.altium.read.cfb import ERROR_RULES, NOTE_CODES

ROOT = Path(__file__).resolve().parents[5]


def test_note_and_error_codes_are_documented() -> None:
    pages = (
        ROOT / "docs/formats/altium/compound-file.md",
        ROOT / "docs/altium.md",
        ROOT / "docs/cli-contract.md",
    )
    texts = [page.read_text(encoding="utf-8") for page in pages]
    for code in NOTE_CODES:
        assert all(code in text for text in texts)
    for code in ERROR_RULES:
        assert all(code in text for text in texts[1:])
    assert "--streams" in texts[1] and "--streams" in texts[2]
