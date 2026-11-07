# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A genuine failed build reply for the c0250 workbench tests; all inputs are authored for Fenolite."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from _layout_edit import edit_properties

from fenolite.api import run

ROOT = Path(__file__).resolve().parents[1]


def build_conflict(folder: Path, *, major: int = 10) -> tuple[Path, Path, Path, dict[str, Any]]:
    """An authored script, its board and saved conflict reply; the output lies below the authoring root."""
    folder.mkdir(parents=True)
    script = folder / "design.py"
    source = (ROOT / "tests/data/lens/edit_merge/design.py").read_text(encoding="utf-8")
    source = source.replace(
        '"R1",\n    "Fenolite:Resistor",', 'None,\n    "Fenolite:Resistor",\n    name="R1", prefix="R",'
    )
    script.write_text(source, encoding="utf-8")
    out = folder / "B"
    words = ("build", str(script), "--out", str(out), "--kicad-version", str(major))
    first = run(*words, "--confirm", cwd=folder)
    assert first.exit_code == 0, first.error
    board = out / "edit_merge.kicad_pcb"
    text, _ = edit_properties(board.read_text(encoding="utf-8"), None, {"R1": {"value": "4k7"}})
    assert text is not None
    board.write_text(text, encoding="utf-8")
    script.write_text(script.read_text().replace('value="330"', 'value="470"'), encoding="utf-8")
    # Canonicalizing an existing lock is a real source-side write with a backup for reviewed undo.
    lock = script.with_suffix(".lock")
    assert lock.is_file()
    lock.write_bytes(lock.read_bytes() + b"\n")
    failed = run(*words, "--dry-run", cwd=folder)
    assert failed.exit_code == 5, failed.error
    assert failed.envelope is not None
    reply = folder / "conflict.json"
    reply.write_text(json.dumps(failed.envelope), encoding="utf-8")
    return script, board, reply, failed.envelope


__all__ = ["build_conflict"]
