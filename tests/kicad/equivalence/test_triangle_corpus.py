# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The equivalence triangle on the public PCB documents (capability design-equivalence, "Triangle
evidence over the corpus" and "Importer exclusion list per version"; change c0045; S-0020, S-0022,
S-0166; ``H-G-EQ-L1`` to ``H-G-EQ-L4``, ``H-G-EQ-SHIFT``, ``H-G-EQ-ROUND-2``, ``H-G-EQ-REF``,
``H-G-EQ-FPNAME``, ``H-G-EQ-VALUE``, ``H-G-EQ-ROT``, ``H-G-EQ-PADSHAPE``, ``H-G-EQ-FREE-2``).

Each ``altium-pcbdoc`` row is read by Fenolite's Altium backend and converted by ``kicad-cli pcb import
--format altium`` (a subprocess, on a copy in a temporary folder), whose board is read by the KiCad
backend. The two models are compared at levels 1 to 4 under the ``kicad-import`` profile of the running
version line (``src/fenolite/backends/kicad/data/altium_import_exclusions.toml``): no difference may
remain outside its rules. A reference that a document holds several times cannot be paired; such
references are listed per row in ``IGNORED_REFS`` and in ``docs/evidence/equivalence-triangle.md``, and
get no rule. The test writes counts only.
"""

from __future__ import annotations

from collections import Counter

import pytest
from _corpus import manifest_items, require
from _triangle import KNOWN_IMPORT_FAILURES, Sides, counts_line, measure, profile_for, report, sides

from fenolite.checks.equivalence import EquivalenceReport

pytestmark = [pytest.mark.needs_kicad, pytest.mark.kicad_min_major(10), pytest.mark.needs_corpus]
ROWS = [item for item in manifest_items("altium-pcbdoc") if not item.heavy]
IDS = [item.id for item in ROWS]
IGNORED_REFS: dict[str, tuple[str, ...]] = {
    "altium-third-party-pcbdoc-01": ("",),
    "altium-third-party-pcbdoc-03": ("[*]",),
    "altium-third-party-pcbdoc-04": ("",),
    "altium-third-party-pcbdoc-05": ("",),
    "altium-third-party-pcbdoc-07": ("",),
}
"""Row id → the globs of the references that the document itself holds several times: the empty
reference of pads that belong to no component (each is a footprint without a reference in both reads), and
on one row the designator ``*`` of three components."""
AMBIGUOUS: dict[str, dict[str, tuple[str, str]]] = {
    "altium-third-party-pcbdoc-01": {"": ("12", "4")},
    "altium-third-party-pcbdoc-03": {"*": ("3", "3")},
    "altium-third-party-pcbdoc-04": {"": ("2", "2")},
    "altium-third-party-pcbdoc-05": {"": ("4", "4")},
    "altium-third-party-pcbdoc-07": {"": ("2", "2")},
}
"""Row id → each such reference with its count in Fenolite's read and in KiCad's. The counts of the first
row differ because KiCad imports no pad on a paste layer (8 of its 12 free pads)."""
SHAPES_NOT_DECIDED = {("custom", "roundrect")}
"""The shape pairs ``(Fenolite, KiCad)`` that the profile's ``undecided`` rule covers: an octagonal pad."""


def _sides(row: str) -> Sides:
    item = next(i for i in ROWS if i.id == row)
    return sides(require(item), row)


def _report(row: str, *, rules: bool = True, ignore: bool = True) -> EquivalenceReport:
    return report(_sides(row), rules=rules, ignore_refs=IGNORED_REFS.get(row, ()) if ignore else ())


def _kinds(found: EquivalenceReport, *, excluded: bool = False) -> Counter[str]:
    kinds = Counter(d.kind for d in found.differences)
    if excluded:
        kinds.update(e.difference.kind for e in found.excluded)
    return kinds


def _level(row: str, level: int, capsys: pytest.CaptureFixture[str]) -> None:
    """No difference of ``level`` remains outside the profile's rules; one line of counts is printed."""
    found = _report(row)
    result = found.levels[level - 1]
    with capsys.disabled():
        print("\n" + counts_line(row, found).splitlines()[level - 1])
    assert result.compared > 0
    assert result.differences == (), [(d.kind, d.where) for d in result.differences][:10]


@pytest.mark.parametrize("row", IDS)
def test_level1(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``H-G-EQ-L1``: the same components (references, values, fitted state)."""
    _level(row, 1, capsys)


@pytest.mark.parametrize("row", IDS)
def test_level2(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``H-G-EQ-L2``: the same partition of ``REF-PIN`` elements into nets."""
    _level(row, 2, capsys)


@pytest.mark.parametrize("row", IDS)
def test_level3(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``H-G-EQ-L3``: the same pads per footprint, in the footprint's frame."""
    _level(row, 3, capsys)


@pytest.mark.parametrize("row", IDS)
def test_level4(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``H-G-EQ-L4``: the same side, rotation and, after one translation, position."""
    _level(row, 4, capsys)


@pytest.mark.parametrize("row", IDS)
def test_translation(row: str, capsys: pytest.CaptureFixture[str]) -> None:
    """``H-G-EQ-SHIFT``: one translation per document; every footprint agrees within the tolerance."""
    found = _sides(row)
    got = measure(found, IGNORED_REFS.get(row, ()))
    result = _report(row)
    with capsys.disabled():
        print(f"\n{row}: translation {result.translation.x},{result.translation.y}; {got}")
    assert got.footprints == result.levels[3].compared > 0
    assert got.position <= profile_for(found.version).tolerance_nm
    assert "position" not in _kinds(_report(row, rules=False))


@pytest.mark.parametrize("row", IDS)
def test_rounding(row: str) -> None:
    """``H-G-EQ-ROUND-2``: KiCad holds a converted length in steps of 10 nm, so no length differs by 10 nm
    or more; the profile's tolerance is the smallest multiple of 10 that covers the measurement."""
    found = _sides(row)
    got = measure(found, IGNORED_REFS.get(row, ()))
    tolerance = profile_for(found.version).tolerance_nm
    assert tolerance == 10 and got.length < tolerance
    assert not {"pad-size", "pad-drill", "pad-position"} & set(_kinds(_report(row, rules=False)))


@pytest.mark.parametrize("row", IDS)
def test_keys(row: str) -> None:
    """``H-G-EQ-REF``: references and pad numbers pair without a mapping. The only references that do not
    pair are those the document holds several times, and the only pins without a twin are the pads that
    the profile's rules name."""
    bare = _report(row, rules=False, ignore=False)
    ambiguous = {d.where: (d.a, d.b) for d in bare.differences if d.kind == "ref-ambiguous"}
    assert ambiguous == AMBIGUOUS.get(row, {})
    assert "component-missing" not in _kinds(bare)
    found = _report(row)
    assert not {"component-missing", "ref-ambiguous", "pin-missing"} & set(_kinds(found))
    assert found.levels[0].summary["ignored"] == len(AMBIGUOUS.get(row, {}))


@pytest.mark.parametrize("row", IDS)
def test_footprint_name(row: str) -> None:
    """``H-G-EQ-FPNAME``: the footprint names after the last ``:`` are equal, with no rule."""
    assert "footprint-name" not in _kinds(_report(row, rules=False), excluded=True)


@pytest.mark.parametrize("row", IDS)
def test_value(row: str) -> None:
    """``H-G-EQ-VALUE``: the values are equal, but for the one component of the ``undecided`` rule."""
    bare = _report(row, rules=False)
    values = [d.where for d in bare.differences if d.kind == "value"]
    excluded = [e.difference.where for e in _report(row).excluded if e.difference.kind == "value"]
    assert values == excluded and len(values) <= 1
    assert "dnp" not in _kinds(bare)


@pytest.mark.parametrize("row", IDS)
def test_rotation(row: str) -> None:
    """``H-G-EQ-ROT``: side, rotation and the local pad frame agree for top and bottom components."""
    bare = _report(row, rules=False)
    assert not {"side", "rotation", "pad-rotation", "pad-position"} & set(_kinds(bare))
    got = measure(_sides(row), IGNORED_REFS.get(row, ()))
    assert (got.rotation, got.pad_rotation) == (0, 0)


@pytest.mark.parametrize("row", IDS)
def test_pad_shape(row: str) -> None:
    """``H-G-EQ-PADSHAPE``: round, rectangular and rounded-rectangle pads keep their shape; an octagonal
    pad is ``custom`` in Fenolite's read and ``roundrect`` in KiCad's."""
    bare = _report(row, rules=False)
    shapes = {(d.a, d.b) for d in bare.differences if d.kind == "pad-shape"}
    assert shapes <= SHAPES_NOT_DECIDED
    assert not {"pad-kind", "pad-copper"} & set(_kinds(bare))
    assert bare.levels[2].summary["copper_unknown"] == 0


@pytest.mark.parametrize("row", IDS)
def test_free_pads(row: str) -> None:
    """``H-G-EQ-FREE-2``: a pad that belongs to no component is a footprint without a reference in both
    reads, so no generated reference appears on one side only."""
    found = _sides(row)
    empty = tuple(sum(1 for c in side.circuit.components if not c.ref) for side in (found.a, found.b))
    expected = AMBIGUOUS.get(row, {}).get("")
    assert empty == ((int(expected[0]), int(expected[1])) if expected else (0, 0))
    assert "component-missing" not in _kinds(_report(row, rules=False, ignore=False))


def test_rules_are_live() -> None:
    """Every rule of the running version's profile matches on each row its ``corpus`` list names, and on
    no other row. A row that ``kicad-cli`` cannot import here (``KNOWN_IMPORT_FAILURES``) is not judged."""
    matched: dict[str, set[str]] = {}
    judged: set[str] = set()
    version = ""
    for item in ROWS:
        try:
            found = _report(item.id)
        except pytest.skip.Exception:
            assert item.id in KNOWN_IMPORT_FAILURES
            continue
        judged.add(item.id)
        version = _sides(item.id).version
        for excluded in found.excluded:
            matched.setdefault(excluded.rule_id, set()).add(item.id)
    assert judged, "no row was imported"
    profile = profile_for(version)
    assert profile.frame == "relative"
    for rule in profile.rules:
        assert rule.corpus, f"{rule.id}: names no corpus row"
        assert set(rule.corpus) <= set(IDS), rule.id
        assert matched.get(rule.id, set()) == set(rule.corpus) & judged, rule.id
    assert set(matched) <= {rule.id for rule in profile.rules}
