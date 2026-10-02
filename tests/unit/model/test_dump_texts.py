# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layer texts in memory (capability canonical-serialization, "Layer texts in memory"; change c0011)."""

from __future__ import annotations

from pathlib import Path

from fenolite.model import canonical
from fenolite.model.design import Design


def test_texts_equal_the_files(tmp_path: Path) -> None:
    design = Design.new("t", seed=1)
    texts = canonical.dump_texts(design)
    written = canonical.dump_dir(design, tmp_path)
    assert [p.name for p in written] == list(texts) == [name for name, _, _ in canonical.LAYER_FILES]
    for path in written:
        assert path.read_text(encoding="utf-8") == texts[path.name]


def test_texts_round_trip(tmp_path: Path) -> None:
    design = Design.new("t", seed=2)
    for name, text in canonical.dump_texts(design).items():
        (tmp_path / name).write_text(text, encoding="utf-8")
    assert canonical.load_dir(tmp_path) == canonical.load_dir(tmp_path)
    assert canonical.dump_texts(canonical.load_dir(tmp_path)) == canonical.dump_texts(design)
