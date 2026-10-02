# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Project files read, printed and read again (capability kicad-file-backend, "Project JSON is
preserved exactly"; change c0010): the GUI fixtures, and the cached demo projects (``needs_corpus``)
with a key-name census written only to ``FENOLITE_CENSUS_OUT``."""

from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import pytest

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.pro import TEN_ONLY_PATHS, read_project_text, write_project_text

ROOT = Path(__file__).resolve().parents[4]
FIXTURES = sorted((ROOT / "tests" / "data" / "kicad" / "project").glob("*.kicad_pro"))


def numbers(value: object) -> list[str]:
    if isinstance(value, dict):
        return [n for v in value.values() for n in numbers(v)]  # type: ignore[union-attr]
    if isinstance(value, list):
        return [n for v in value for n in numbers(v)]  # type: ignore[union-attr]
    return [value.text] if isinstance(value, _json.JsonNumber) else []


def round_trip(text: str) -> None:
    first = read_project_text(text)
    again = read_project_text(write_project_text(first))
    assert _json.structural_equal(first, again)
    assert numbers(first) == numbers(again)


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.name)
def test_fixture_round_trip(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    round_trip(text)
    assert write_project_text(read_project_text(text)) == text, "GUI saves print byte-identically"


def _rows() -> list[object]:
    from _corpus import manifest_items

    return [i for i in manifest_items("project") if i.path.suffix == ".kicad_pro"]


@pytest.mark.needs_corpus
def test_demo_projects_round_trip() -> None:
    from _corpus import require

    rows = _rows()
    if not rows:
        pytest.skip("no project rows in the corpus manifest")
    census: dict[str, Counter[str]] = {}
    for item in rows:
        text = require(item).read_text(encoding="utf-8")  # type: ignore[attr-defined]
        round_trip(text)
        data = read_project_text(text)
        tag = item.id.split("-pro-")[0]  # type: ignore[attr-defined]
        counts = census.setdefault(tag, Counter())
        counts.update(_json.key_paths(data))
        meta = _json.get(data, "/meta/version")
        settings = _json.get(data, "/net_settings/meta/version")
        counts[f"pair:{getattr(meta, 'text', None)},{getattr(settings, 'text', None)}"] += 1
        counts.update(f"ten-only:{p}" for p in _json.key_paths(data) & TEN_ONLY_PATHS)
    out = os.environ.get("FENOLITE_CENSUS_OUT")
    if out:
        Path(out).write_text(json.dumps({k: dict(sorted(v.items())) for k, v in census.items()}, indent=1))
