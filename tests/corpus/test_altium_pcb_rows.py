# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The corpus rows of the Altium PCB reader (capability altium-pcb-reader, "Altium PCB corpus rows",
change c0041): seven ``altium-pcbdoc`` and four ``altium-pcblib`` rows. Reads the manifest only, so it
needs no fetched file."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
SOURCES = ROOT / "docs" / "evidence" / "sources.md"
ROW_ID = re.compile(r"^altium-third-party-(pcbdoc|pcblib)-\d{2}$")
DOCUMENT_SOURCES = {"S-0172", "S-0174", "S-0175", "S-0176", "S-0188", "S-0199", "S-0200"}
LIBRARY_SOURCES = {"S-0170", "S-0171"}
LICENCES = {"MIT", "Apache-2.0", "BSD-2-Clause", "GPL-2.0", "LGPL-3.0"}
REUSED = {
    *(f"altium-third-party-pcbdoc-{i:02}" for i in range(1, 5)),
    *(f"altium-third-party-pcblib-{i:02}" for i in range(1, 3)),
}
"""The rows of change c0039 that this change reuses by adding its use."""


def _rows(use: str) -> list[dict[str, Any]]:
    entries = tomllib.loads(MANIFEST.read_text(encoding="utf-8")).get("file", [])
    return [entry for entry in entries if use in entry["uses"]]


def test_seven_documents_and_four_libraries() -> None:
    documents, libraries = _rows("altium-pcbdoc"), _rows("altium-pcblib")
    assert len(documents) == 7
    assert len(libraries) == 4
    assert {str(e["id"]) for e in documents} == {f"altium-third-party-pcbdoc-{i:02}" for i in range(1, 8)}
    assert {str(e["id"]) for e in libraries} == {f"altium-third-party-pcblib-{i:02}" for i in range(1, 5)}


def test_row_rules() -> None:
    registered = SOURCES.read_text(encoding="utf-8")
    for use, sources, kind in (
        ("altium-pcbdoc", DOCUMENT_SOURCES, "pcbdoc"),
        ("altium-pcblib", LIBRARY_SOURCES, "pcblib"),
    ):
        seen: set[str] = set()
        for entry in _rows(use):
            ident = str(entry["id"])
            uses = set(entry["uses"])
            assert ROW_ID.fullmatch(ident), ident
            assert {"altium", "origin:third-party"} <= uses, ident
            assert not {"rt0", "oracle"} & uses, ident
            assert entry["embeddable"] is False, ident
            assert entry["license"] in LICENCES, ident
            assert ("cfb" in uses) == (ident in REUSED), ident
            source, form, size, year = str(entry["notes"]).split("; ")
            assert source in sources and form == kind, ident
            assert re.fullmatch(r"\d+ bytes", size) and re.fullmatch(r"\d{4}\.", year), ident
            assert f"| {source} |" in registered and str(entry["sha256"]) in registered, ident
            seen.add(source)
        assert seen == sources
