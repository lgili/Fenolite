# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Line layout of Fenolite's printer against 9.0-written demo boards (H-K-FMT-ATOMWRAP, H-K-FMT-MIXED).

Only counts are recorded (docs/evidence/kicad-fmt-identity.md), never file content.
"""

from __future__ import annotations

import difflib
import re
from collections import Counter
from pathlib import Path

import pytest
from _corpus import manifest_items

from fenolite.backends.kicad import dumps, load

pytestmark = pytest.mark.needs_corpus
DOC = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "kicad-fmt-identity.md"
CLASSES = ("atom-list-wrap", "atom-after-list", "glued-lists", "other")


def line_class(line: str) -> str:
    text = line.strip()
    if ")(" in text:
        return "glued-lists"
    if text and text[0] not in "()":
        return "atom-list-wrap"
    if re.fullmatch(r"\(.*\)\s+[^\s()\"]+", text):
        return "atom-after-list"
    return "other"


def measure() -> tuple[int, int, Counter[str]]:
    """(files compared, byte-identical files, differing original lines per class)."""
    counts: Counter[str] = Counter()
    files = identical = 0
    for item in manifest_items("rt0"):
        if (
            item.heavy
            or not item.path.is_file()
            or item.path.suffix != ".kicad_pcb"
            or item.origin != "kicad-demos"
        ):
            continue
        text = item.path.read_text(encoding="utf-8")
        if '(generator_version "9.0")' not in text[:300] or "(version 20241229)" not in text[:200]:
            continue
        files += 1
        ours = dumps(load(item.path))
        if ours == text:
            identical += 1
            continue
        original, printed = text.splitlines(), ours.splitlines()
        glued = any(")(" in ln for ln in original)
        for tag, i1, i2, _, _ in difflib.SequenceMatcher(
            None, original, printed, autojunk=False
        ).get_opcodes():
            if tag != "equal":
                for line in original[i1:i2]:
                    counts["glued-lists" if glued else line_class(line)] += 1
    return files, identical, counts


def recorded() -> dict[str, int]:
    table = dict(re.findall(r"^\| `([a-z-]+)` \| (\d+) \|", DOC.read_text(encoding="utf-8"), re.MULTILINE))
    return {k: int(v) for k, v in table.items()}


def test_fmt_identity_9() -> None:
    files, identical, counts = measure()
    if not files:
        pytest.skip("no 9.0-written demo board cached")
    measured = {"files": files, "identical": identical, **{c: counts[c] for c in CLASSES}}
    print("9.0-written demo boards:", measured)
    assert recorded() == measured, "update docs/evidence/kicad-fmt-identity.md with the measured counts"


def test_line_classes() -> None:
    assert line_class('\t\t\t"1b1d2885-3aa3" "1c9793fa"') == "atom-list-wrap"
    assert line_class("\t\t\t(loss_tangent 0.02) addsublayer") == "atom-after-list"
    assert line_class("\t\t(curved_edges no)(filter_ratio 0.9)") == "glued-lists"
    assert line_class("\t\t)") == "other"
