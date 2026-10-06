# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Third-party schematics are read as copies re-saved by ``kicad-cli`` 10 (capability kicad-oracle,
"Third-party schematics are read as upgraded copies"; corpus-policy, "Upgraded schematic copies keep their
origin"; hypothesis ``H-K-SCH-RT1``; change c0060).

The cached files are older than the read floor. Each is re-saved once with ``sch upgrade --force`` on a
copy, and RT0 and RT1 run on the re-saved text. The cache is never written and no copy is kept.
"""

from __future__ import annotations

import hashlib

import _probes
import pytest
from _boards import census
from _corpus import CorpusItem, manifest_items, require

from fenolite.backends.kicad import sch
from fenolite.backends.kicad.sexpr import dumps, parse, tree_equal
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, UnsupportedFormatError, detect_version

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.kicad_min_major(10)]
ROWS = [item for item in manifest_items("sch") if item.origin == "third-party"]


def test_two_third_party_rows() -> None:
    assert [item.id for item in ROWS] == ["third-party-sch-01", "third-party-sch-02"]


@pytest.mark.parametrize("item", ROWS, ids=lambda item: item.id)
def test_upgraded_copy_round_trips(item: CorpusItem) -> None:
    path = require(item)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(UnsupportedFormatError):
        sch.read_schematic(path, file=item.id)
    text = _probes.runner().upgrade_schematic(path).decode("utf-8")
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    original = parse(text, file=item.id)
    version = detect_version(original, file=item.id)
    assert version == FORMAT_VERSIONS[FileKind.SCHEMATIC][10]
    assert tree_equal(parse(dumps(original)), original), f"{item.id}: RT0"
    verdict = sch.roundtrip_schematic(text, file=item.id)
    sheet = sch.read_schematic(text, file=item.id)
    census(
        "schematic_upgraded",
        item.id,
        {
            "origin": "third-party",
            "format_version": version,
            "rt0": True,
            "rt1": verdict.passed,
            "opaque_count": verdict.opaque_count,
            "symbols": len(sheet.symbols),
            "labels": len(sheet.labels),
        },
    )
    assert verdict.passed, f"{item.id}: RT1 differs at {verdict.difference}"
