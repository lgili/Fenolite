# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""How far ``dumps(parse(f))`` is from the layout that ``kicad-cli`` 10.0.6 writes (capability kicad-sexpr,
"Printer layout measured on 10.0 writes"; the 10.0 parts of ``H-K-FMT-INDENT``, ``H-K-FMT-XYWRAP``,
``H-K-FMT-ATOMWRAP`` and ``H-K-FMT-MIXED``; change c0020).

A measurement: byte identity with KiCad's printer is not a goal, so a difference never fails the test and
never changes the printer. The files are ``pcb upgrade --force`` copies made in memory; only counts are
recorded, through ``census``, for ``docs/evidence/kicad-fmt-identity.md``.
"""

from __future__ import annotations

import difflib
import importlib.util
import tempfile
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pytest
from _boards import FIXTURE, census
from _corpus import manifest_items
from _triad import triad
from _upgrade import runner, upgraded

from fenolite.backends.kicad import sexpr
from fenolite.backends.kicad.pcb import write_board

pytestmark = [
    pytest.mark.needs_kicad,
    pytest.mark.needs_corpus,
    pytest.mark.kicad_min_major(10),
    pytest.mark.slow,
]
NINE = Path(__file__).resolve().parents[1] / "corpus" / "test_fmt_identity_9.py"
XY = "xy-packing"


def _line_class() -> Callable[[str], str]:
    """``line_class`` of the 9.0 measurement, loaded from its file (``tests/corpus`` is no package)."""
    spec = importlib.util.spec_from_file_location("_fmt_identity_9", NINE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.line_class


def authored() -> dict[str, str]:
    """``two_layer.kicad_pcb`` and the target-10 triad, each re-saved once by ``pcb upgrade --force``."""
    with tempfile.TemporaryDirectory() as tmp:
        board = Path(tmp) / "triad.kicad_pcb"
        board.write_text(write_board(triad(10), target=10).text, encoding="utf-8")
        written = runner().upgrade_board(board).decode("utf-8")
    return {"two_layer": upgraded(FIXTURE), "triad-10": written}


def corpus() -> dict[str, str]:
    boards = [
        i
        for i in manifest_items("oracle")
        if i.path.suffix == ".kicad_pcb" and not i.heavy and i.path.is_file()
    ]
    return {item.id: upgraded(item.path) for item in boards}


def measure(files: dict[str, str]) -> dict[str, int]:
    """Files compared, files byte-identical, and each original line of a differing block, by class."""
    classify = _line_class()
    counts: Counter[str] = Counter()
    identical = 0
    for text in files.values():
        ours = sexpr.dumps(sexpr.parse(text))
        if ours == text:
            identical += 1
            continue
        original, printed = text.splitlines(), ours.splitlines()
        matcher = difflib.SequenceMatcher(None, original, printed, autojunk=False)
        for tag, i1, i2, _, _ in matcher.get_opcodes():
            if tag != "equal":
                for line in original[i1:i2]:
                    counts[XY if "(xy " in line else classify(line)] += 1
    return {"files": len(files), "identical": identical, **dict(sorted(counts.items()))}


def test_byte_identity_kicad10() -> None:
    files = corpus() | authored()
    measured = measure(files)
    census("fmt_identity_10", "counts", measured)
    print("10.0-written boards:", measured)
    assert measured["files"] > 0, "no file could be compared"


def test_differences_never_fail(monkeypatch: pytest.MonkeyPatch) -> None:
    files = authored()
    real = sexpr.dumps
    monkeypatch.setattr(sexpr, "dumps", lambda node: "\n".join(f"{ln} " for ln in real(node).splitlines()))
    measured = measure(files)
    lines = sum(len(text.splitlines()) for text in files.values())
    assert measured["identical"] == 0
    assert sum(v for k, v in measured.items() if k not in ("files", "identical")) == lines
