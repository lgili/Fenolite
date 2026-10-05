# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Census of the schematic rows of the corpus (capability corpus-policy, "Schematic corpus rows"; c0060).

The four content tags of every ``sch`` row are recomputed from the cached files and compared with the
manifest. Counts only, keyed by tag, format version, origin and head name; results go to the JSON file
named by ``FENOLITE_CENSUS_OUT`` and nowhere else.
"""

from __future__ import annotations

from collections import Counter
from functools import cache
from pathlib import Path

import _schcorpus
import pytest
from _boards import census
from _corpus import manifest_items, require

from fenolite.backends.kicad.sexpr import Node, parse_bytes

pytestmark = pytest.mark.needs_corpus


@cache
def rows() -> tuple[_schcorpus.SchRow, ...]:
    found = _schcorpus.rows()
    by_id = {item.id: item for item in manifest_items("sch")}
    for row in found:
        require(by_id[row.id])  # skips, or fails in required-resource mode
    return found


def tag_problems(rows_: tuple[_schcorpus.SchRow, ...], computed: dict[str, set[str]]) -> list[str]:
    problems: list[str] = []
    for row in rows_:
        want = computed.get(row.id)
        if want is None:
            continue
        for tag in sorted(want - row.content):
            problems.append(f"{row.id}: the manifest lacks {tag}")
        for tag in sorted(row.content - want):
            problems.append(f"{row.id}: the manifest has {tag}, which the file does not show")
    return problems


def test_content_tags_match_the_files(tmp_path: Path) -> None:
    computed = _schcorpus.computed_tags(tmp_path, rows())
    assert len(computed) == len(rows())
    problems = tag_problems(rows(), computed)
    assert not problems, "\n".join(problems)


def test_a_missing_tag_is_named(tmp_path: Path) -> None:
    import dataclasses

    victim = next(r for r in rows() if "sch-bus" in r.uses)
    edited = tuple(
        dataclasses.replace(r, uses=tuple(u for u in r.uses if u != "sch-bus")) if r.id == victim.id else r
        for r in rows()
    )
    problems = tag_problems(edited, _schcorpus.computed_tags(tmp_path, edited))
    assert problems == [f"{victim.id}: the manifest lacks sch-bus"]


def test_row_rules() -> None:
    for row in rows():
        assert {"rt0", "sch"} <= set(row.uses), row.id
        assert sum(u.startswith("origin:") for u in row.uses) == 1, row.id
        if row.ref == "9.0.9.1":
            assert _schcorpus.SHARED in row.uses, row.id
    ids = [r.id for r in rows()]
    assert "kicad-demo-10-0-6-sch-01" in ids and {"third-party-sch-01", "third-party-sch-02"} <= set(ids)


def test_census_counts() -> None:
    per_tag: Counter[str] = Counter()
    per_version: Counter[str] = Counter()
    per_origin: Counter[str] = Counter()
    per_ref: Counter[str] = Counter()
    heads: Counter[str] = Counter()
    plain = 0
    for row in rows():
        per_origin[row.origin] += 1
        per_ref[row.ref if row.origin == "kicad-demos" else "third-party"] += 1
        for tag in (*_schcorpus.CONTENT_TAGS, _schcorpus.SHARED):
            per_tag[tag] += tag in row.uses
        root = parse_bytes(row.file.read_bytes(), file=row.id)
        per_version[str(_schcorpus.version_of(row.file))] += 1
        heads.update(c.name for c in root.children if isinstance(c, Node))
        plain += not ({"sch-bus", "sch-multi", "sch-old"} & set(row.uses))
    data = {
        "rows": len(rows()),
        "per_tag": dict(sorted(per_tag.items())),
        "per_format_version": dict(sorted(per_version.items())),
        "per_origin": dict(sorted(per_origin.items())),
        "per_ref": dict(sorted(per_ref.items())),
        "root_heads": dict(sorted(heads.items())),
        "without_bus_multi_old": plain,
        "bytes": sum(row.file.stat().st_size for row in rows()),
    }
    census("schematic", "census", data)
    print("schematic census:", data)
    assert plain > 0
