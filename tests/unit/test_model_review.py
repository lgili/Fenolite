# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/model_review.py``: the pre-freeze list of the model (capability model-versions, "Pre-freeze review
of the model", scenario "The review lists every field"; change c0218)."""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from fenolite.backends.altium.adapter.ids import EXT_KEYS
from fenolite.model.board import Track

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools" / "model_review.py"


@pytest.fixture(scope="module")
def review() -> ModuleType:
    spec = importlib.util.spec_from_file_location("model_review", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_every_field_of_track_with_its_type_and_default(review: ModuleType) -> None:
    found = {c.id: c for c in review.classes(review._sources())}
    track = found["Track"]
    assert track.stored_in == ("board.json",)
    rows = {f.id: f for f in track.fields}
    assert list(rows) == [f"Track.{f.name}" for f in dataclasses.fields(Track)]
    assert rows["Track.width"].type == "int"
    assert rows["Track.width"].default == "required"
    assert rows["Track.net_id"].type == "str | None"
    assert rows["Track.net_id"].default == "None"
    assert rows["Track.locked"].default == "False"
    assert rows["Track.ext"].default == "{}"


def test_every_stored_dataclass_is_listed(review: ModuleType) -> None:
    found = {c.id: c for c in review.classes(review._sources())}
    stored = review._stored(review._roots())
    assert {cls.__name__ for cls in stored} <= set(found)
    assert found["Point"].module == "fenolite.core.coords"
    assert found["Design"].stored_in == ()


def test_the_list_holds_every_altium_key_and_the_kicad_keys(review: ModuleType, tmp_path: Path) -> None:
    out = tmp_path / "review.md"
    assert review.main(["--out", str(out)]) == 0
    text = out.read_text(encoding="utf-8")
    for key in EXT_KEYS:
        assert f"`ext.altium.{key}`" in text
    for key in ("number", "type", "user_name", "stored", "pintype", review.SLOT_ITEM):
        assert f"`ext.kicad.{key}`" in text
    for field in dataclasses.fields(Track):
        assert f"| `Track.{field.name}` |" in text
