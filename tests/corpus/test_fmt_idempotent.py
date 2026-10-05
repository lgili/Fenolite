# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The canonical print is a fixed point over the corpus (capability kicad-sexpr, "Canonical print check";
``H-K-FMT-IDEMPOTENT``; change c0066): what ``fenolite fmt`` writes, ``fenolite fmt --check`` accepts.

Only counts are recorded (``docs/evidence/kicad-fmt-identity.md``), never file content. Items are named by
their neutral manifest id.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pytest
from _boards import census
from _corpus import CorpusItem, heavy_enabled, manifest_items
from _resources import CORPUS_HINT, required_resources

from fenolite.backends.kicad.sexpr import canonical, parse, tree_equal
from fenolite.core.errors import FormatError

pytestmark = pytest.mark.needs_corpus
ITEMS = manifest_items("rt0")
DATA = Path(__file__).resolve().parents[1] / "data"
SUFFIXES = (".kicad_pcb", ".kicad_mod", ".kicad_sch", ".kicad_sym", ".kicad_wks")
AUTHORED = sorted(p for p in DATA.rglob("*") if p.is_file() and p.suffix in SUFFIXES)


def measure(path: Path) -> tuple[str, bool, bool]:
    """``(refusal reason or "", fixed point, tree equal)`` of one file."""
    try:
        text = path.read_bytes().decode("utf-8")
        once = canonical(text, file=path.name)
    except UnicodeDecodeError:
        return "invalid-utf8", False, False
    except FormatError:
        return "does-not-parse", False, False
    except ValueError:
        return "printer-refuses", False, False
    return "", canonical(once, file=path.name) == once, tree_equal(parse(once), parse(text))


def _tally(paths: list[tuple[str, Path]]) -> tuple[dict[str, object], list[str]]:
    kinds: Counter[str] = Counter()
    refused: Counter[str] = Counter()
    failures: list[str] = []
    for name, path in paths:
        reason, fixed, equal = measure(path)
        if reason:
            refused[reason] += 1
            continue
        kinds[path.suffix[1:] or "no-suffix"] += 1
        if not fixed:
            failures.append(f"{name}: printing the canonical print again changes it")
        if not equal:
            failures.append(f"{name}: the canonical print does not parse tree-equal to the source")
    counts: dict[str, object] = {
        "files": len(paths),
        "accepted": sum(kinds.values()),
        "accepted_by_kind": dict(sorted(kinds.items())),
        "refused_by_reason": dict(sorted(refused.items())),
        "failures": len(failures),
    }
    return counts, failures


def _cached(items: list[CorpusItem]) -> list[CorpusItem]:
    return [i for i in items if i.path.is_file() and (heavy_enabled() or not i.heavy)]


def test_corpus_is_a_fixed_point() -> None:
    cached = _cached(ITEMS)
    missing = [i.id for i in ITEMS if not i.path.is_file() and not i.heavy]
    if missing and "corpus" in required_resources():
        pytest.fail(
            f"corpus items missing from the cache: {', '.join(missing)} ({CORPUS_HINT})", pytrace=False
        )
    if not cached:
        pytest.skip(f"no rt0 corpus item is cached ({CORPUS_HINT})")
    counts, failures = _tally([(item.id, item.path) for item in cached])
    counts["manifest_rows"] = len(ITEMS)
    census("fmt_idempotent", "corpus", counts)
    print(f"fmt fixed point over the corpus: {counts}")
    assert not failures, "\n".join(failures)
    assert counts["accepted"], "no corpus file was accepted"


def test_authored_files_are_a_fixed_point() -> None:
    counts, failures = _tally([(path.relative_to(DATA).as_posix(), path) for path in AUTHORED])
    census("fmt_idempotent", "authored", counts)
    print(f"fmt fixed point over the authored files: {counts}")
    assert not failures, "\n".join(failures)
