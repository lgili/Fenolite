# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``[picks]`` table of the design lock (change c0254, "Picks in the lock", "Pick entry values")."""

from __future__ import annotations

from fractions import Fraction
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from fenolite.cli._script import run_design_script
from fenolite.dsl.lock import lock_text, make_lock, read_lock
from fenolite.pick.lockpicks import KEYS, PickEntry, entries, micro_text, tables
from fenolite.pick.resolve import resolve
from fenolite.pick.rows import project_rows

TEXT = st.text(st.characters(codec="utf-8", exclude_categories=("Cs",)), max_size=20)
PATH = st.from_regex(r"[A-Za-z0-9_]{1,6}(/[A-Za-z0-9_]{1,6}){0,2}", fullmatch=True)
ENTRY = st.builds(PickEntry, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT)


@settings(max_examples=60, deadline=None)
@given(st.dictionaries(PATH, ENTRY, max_size=5))
def test_round_trip(picks: dict[str, PickEntry]) -> None:
    lock = make_lock("d", {"picks": tables(picks)})
    text = lock_text(lock)
    again = read_lock(text, file="design.lock")
    assert entries(again.sections["picks"]) == picks
    assert lock_text(again) == text


def test_keys_are_written_in_order() -> None:
    entry = PickEntry("q", "D@1", "D", "fenolite-catalog 2026.10", "ab", "voltage_divider", "VOUT 1uV..2uV")
    text = lock_text(make_lock("d", {"picks": {"a/b": entry.table()}}))
    body = text.split('[picks."a/b"]\n')[1].splitlines()
    assert [line.split(" = ")[0].strip('"') for line in body] == list(KEYS)
    assert (
        micro_text("VOUT", "V", Fraction(3224694123, 10**9), Fraction(3399373001, 10**9))
        == "VOUT 3224694uV..3399374uV"
    )


def test_a_project_row_in_the_lock(tmp_path: Path) -> None:
    devices = tmp_path / "devices"
    devices.mkdir()
    (devices / "caps.toml").write_text(
        'schema = "fenolite.family.v0"\nid = "Proj:C"\nkind = "capacitor"\nsummary = "s"\n'
        'symbol = "Fenolite:Capacitor"\nfootprint = "Fenolite:Chip_0805"\ncase = "0805"\nseries = "E6"\n'
        'values = { min = "10u", max = "10u" }\ntolerance = "10%"\nevidence = "INFERRED"\n',
        encoding="utf-8",
    )
    (tmp_path / "design.py").write_text(
        "from fenolite.dsl import Design, capacitor, farad\n"
        "design = Design('p')\nc = design.part(name='C_in', device=capacitor(farad('10u')))\n",
        encoding="utf-8",
    )
    design = run_design_script(tmp_path / "design.py").design
    rows = project_rows(tmp_path)
    found = resolve({"C_in": design.parts["C_in"].query}, {}, rows)  # pyright: ignore[reportArgumentType]
    entry = found.entries["C_in"]
    assert entry.catalog == "project:devices/caps.toml" and entry.sha256 == rows[0].sha256
    assert entry.device == "Proj:C@10u" and entry.by == "query"
