# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The model's independent version rule, retained v0 history and migration are documented."""

from pathlib import Path


def test_model_rule_and_history() -> None:
    root = Path(__file__).resolve().parents[2]
    text = (root / "docs/design-model.md").read_text(encoding="utf-8")
    history = text.split("## Model schema versions\n", 1)[1].split("## Entity header", 1)[0]
    for phrase in (
        "MAJOR.MINOR",
        "optional fields with defaults",
        "type, meaning or name",
        "raises the major",
        "FEN-3002",
        "FEN-3004",
        "| `0` |",
        "| `1.0` |",
        "model.migrated",
        "0 -> 1.0",
        "No field is renamed or dropped",
    ):
        assert phrase in history
    assert 'stays `"0"`' not in text
    assert text.count("[version history](#model-schema-versions)") >= 10
    assert "Model folders and migrations" in (root / "docs/model-versions.md").read_text(encoding="utf-8")
