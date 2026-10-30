# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The design lock: reading, canonical text, reserved sections and the assignment of refs (capability
design-dsl, "Design lock file", "Lock reading", "Reserved lock sections", "Automatic reference
designators", "Natural path order" and "Lock entries follow path aliases"; change c0249)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from fenolite.cli.errors import from_exception
from fenolite.core.errors import FormatError
from fenolite.dsl import Design, Module, Part, moves
from fenolite.dsl.lock import (
    HEADER,
    SCHEMA,
    SECTIONS,
    LockChange,
    LockVersionError,
    assign_refs,
    lock_text,
    make_lock,
    natural_key,
    read_lock,
)

HAND = """# my lock
design = "sensor"
schema = "fenolite.lock.v0"

[refs]
"buck/c_out" =   "C2"
"Y" = "Y1"
  "buck/U" = "U1"
'R5' = "R5"
"buck/c_in" = "C1"

[pins]
"""


def code(error: Exception) -> str:
    return from_exception(error, "").code


# -- reading and writing


def test_read_canonical_bytes() -> None:
    lock = read_lock(HAND, file="design.lock")
    first = lock_text(lock)
    assert lock_text(read_lock(first, file="design.lock")) == first
    assert first == (
        f"{HEADER}\n"
        'schema = "fenolite.lock.v0"\n'
        'design = "sensor"\n'
        "\n"
        "[refs]\n"
        '"R5" = "R5"\n'
        '"Y" = "Y1"\n'
        '"buck/U" = "U1"\n'
        '"buck/c_in" = "C1"\n'
        '"buck/c_out" = "C2"\n'
    )
    assert "[pins]" not in first and "\r" not in first and first.endswith('C2"\n')


def test_text_of_an_empty_lock_and_escapes() -> None:
    assert lock_text(make_lock("x")) == f'{HEADER}\nschema = "{SCHEMA}"\ndesign = "x"\n'
    assert [section.name for section in SECTIONS] == ["refs", "picks", "pins"]


def test_read_two_paths_with_one_ref() -> None:
    text = f'schema = "{SCHEMA}"\ndesign = "d"\n[refs]\n"a/R" = "R1"\n"b/R" = "R1"\n'
    with pytest.raises(FormatError) as caught:
        read_lock(text, file="design.lock")
    assert code(caught.value) == "FEN-3004"
    assert "a/R" in str(caught.value) and "b/R" in str(caught.value) and "design.lock" in str(caught.value)


@pytest.mark.parametrize(
    ("text", "key"),
    [
        (f'schema = "{SCHEMA}"\ndesign = "d"\nextra = 1\n', "extra"),
        ('schema = 1\ndesign = "d"\n', "schema"),
        ('schema = "other.v0"\ndesign = "d"\n', "schema"),
        (f'schema = "{SCHEMA}"\n', "design"),
        (f'schema = "{SCHEMA}"\ndesign = "d"\nrefs = 3\n', "refs"),
        (f'schema = "{SCHEMA}"\ndesign = "d"\n[refs]\n"R" = 1\n', "refs.R"),
        (f'schema = "{SCHEMA}"\ndesign = "d"\n[refs]\n"R" = "R 1"\n', "refs.R"),
        (f'schema = "{SCHEMA}"\ndesign = "d"\n[refs]\n"a b/R" = "R1"\n', "refs.a b/R"),
        ("schema = \n", ""),
    ],
)
def test_read_malformed(text: str, key: str) -> None:
    with pytest.raises(FormatError) as caught:
        read_lock(text, file="design.lock")
    assert code(caught.value) == "FEN-3004" and caught.value.locator == key


def test_read_newer_schema() -> None:
    with pytest.raises(LockVersionError) as caught:
        read_lock('schema = "fenolite.lock.v1"\ndesign = "d"\n', file="design.lock")
    assert code(caught.value) == "FEN-3002"


def test_picks_are_read() -> None:
    # c0254 registers the picks resolver: an incomplete pick is malformed (FEN-3004)
    text = f'schema = "{SCHEMA}"\ndesign = "d"\n[picks."buck/c_in"]\ndevice = "Fenolite:C_0805"\n'
    with pytest.raises(FormatError) as caught:
        read_lock(text, file="design.lock")
    assert code(caught.value) == "FEN-3004" and "picks" in str(caught.value)


def test_pins_section_is_read_since_c0257() -> None:
    """``[pins]`` is defined by change c0257: a malformed entry is FEN-3004, a valid one is read and written
    canonically, its ``choice`` text written again from the other fields."""
    with pytest.raises(FormatError) as caught:
        read_lock(f'schema = "{SCHEMA}"\ndesign = "d"\n[pins]\n"x" = "y"\n', file="design.lock")
    assert code(caught.value) == "FEN-3004"
    text = (
        f'schema = "{SCHEMA}"\ndesign = "d"\n[pins."mcu/i2c#0"]\nkind = "i2c"\noption = "I2C1"\n'
        'alternative = 1\npins = { sda = "PB9", scl = "PB8" }\nchoice = "edited by hand"\n'
    )
    lock = read_lock(text, file="design.lock")
    assert lock_text(lock).endswith(
        '\n[pins."mcu/i2c#0"]\nkind = "i2c"\noption = "I2C1"\nalternative = 1\n'
        'pins = { scl = "PB8", sda = "PB9" }\nchoice = "I2C1 on PB8/PB9"\n'
    )
    assert read_lock(lock_text(lock), file="design.lock") == lock


def test_every_section_has_a_resolver() -> None:
    assert {section.name: section.resolve is None for section in SECTIONS} == {
        "refs": False,
        "picks": False,
        "pins": False,
    }


# -- natural path order


def test_natural_order() -> None:
    paths = ["ch10/R", "ch2/R", "ch02/R", "R", "ch2/Ra", "a", "B", "ch/R", "1x", "ch1/R"]
    assert sorted(paths, key=natural_key) == [
        "1x",
        "B",
        "R",
        "a",
        "ch1/R",
        "ch2/R",
        "ch2/Ra",
        "ch02/R",  # the digit runs decide before the runs after them: 2 before 02
        "ch10/R",
        "ch/R",  # its first run "ch/R" sorts after the run "ch" of the others
    ]


# -- assignment


def channels(*names: str, explicit: tuple[str, ...] = ()) -> Design:
    design = Design("t")
    for ref in explicit:
        design.add(Part(ref, "Fenolite:Resistor"))
    for name in names:
        module = Module(name)
        design.add(module)
        module.part(lib_id="Fenolite:Resistor")
    return design


def test_first_assignment() -> None:
    design = channels("ch10", "ch2", explicit=("R1",))
    found = assign_refs(design, make_lock("t"), moves={})
    assert dict(found.refs) == {"R1": "R1", "ch10/R": "R3", "ch2/R": "R2"}
    assert dict(found.lock.refs) == dict(found.refs) and found.issues == ()
    assert [c.as_json() for c in found.changes] == [
        {"section": "refs", "key": "R1", "before": None, "after": "R1", "reason": "assigned"},
        {"section": "refs", "key": "ch10/R", "before": None, "after": "R3", "reason": "assigned"},
        {"section": "refs", "key": "ch2/R", "before": None, "after": "R2", "reason": "assigned"},
    ]


def test_locked_refs_are_kept() -> None:
    design = channels("ch10", "ch3")
    found = assign_refs(design, make_lock("t", {"refs": {"ch10/R": "R7"}}), moves={})
    assert dict(found.refs) == {"ch10/R": "R7", "ch3/R": "R1"} and found.issues == ()
    assert [c.reason for c in found.changes] == ["assigned"]


def test_explicit_ref_takes_a_locked_number() -> None:
    design = channels("ch2", explicit=("R2",))
    found = assign_refs(design, make_lock("t", {"refs": {"ch2/R": "R2"}}), moves={})
    assert found.refs["R2"] == "R2" and found.refs["ch2/R"] == "R1"
    assert [(i.code, i.severity, i.where) for i in found.issues] == [("lock.ref-taken", "warning", "ch2/R")]
    assert LockChange("refs", "ch2/R", "R2", "R1", "taken") in found.changes


def test_explicit_ref_replaces_its_locked_ref() -> None:
    design = channels(explicit=("R4",))
    lock = make_lock("t", {"refs": {"R4": "R9"}})
    found = assign_refs(design, lock, moves={})
    assert dict(found.refs) == {"R4": "R4"}
    assert [(i.code, i.severity) for i in found.issues] == [("lock.ref-explicit", "info")]
    assert found.changes == (LockChange("refs", "R4", "R9", "R4", "explicit"),)


def test_prefix_changed() -> None:
    design = Design("t")
    design.add(Part(lib_id="Fenolite:Resistor", name="x", prefix="RV"))
    found = assign_refs(design, make_lock("t", {"refs": {"x": "C3"}}), moves={})
    assert dict(found.refs) == {"x": "RV1"}
    assert [i.code for i in found.issues] == ["lock.ref-prefix-changed"]
    assert found.changes == (LockChange("refs", "x", "C3", "RV1", "prefix-changed"),)


def test_released_and_lowest_free() -> None:
    design = channels("a", "b")
    lock = make_lock("t", {"refs": {"a/R": "R2", "old/R": "R1"}})
    found = assign_refs(design, lock, moves={})
    assert dict(found.refs) == {"a/R": "R2", "b/R": "R1"}
    assert [(i.code, i.severity, i.where) for i in found.issues] == [
        ("lock.ref-released", "warning", "old/R")
    ]
    assert "R1" in found.issues[0].message
    assert [c.as_json() for c in found.changes] == [
        {"section": "refs", "key": "b/R", "before": None, "after": "R1", "reason": "assigned"},
        {"section": "refs", "key": "old/R", "before": "R1", "after": None, "reason": "released"},
    ]


def test_a_hand_edit_is_honoured() -> None:
    design = channels("a", "b")
    found = assign_refs(design, make_lock("t", {"refs": {"a/R": "R7", "b/R": "R1"}}), moves={})
    assert dict(found.refs) == {"a/R": "R7", "b/R": "R1"} and found.changes == () and found.issues == ()
    assert found.lock == make_lock("t", {"refs": {"b/R": "R1", "a/R": "R7"}})


def test_module_renamed_with_moved() -> None:
    design = Design("t")
    reg = Module("reg")
    design.add(reg)
    reg.part(lib_id="Fenolite:Resistor")
    design.moved("buck", "reg")
    found = assign_refs(design, make_lock("t", {"refs": {"buck/R": "R4"}}), moves=moves(design))
    assert dict(found.refs) == {"reg/R": "R4"} and dict(found.lock.refs) == {"reg/R": "R4"}
    assert [(i.code, i.severity) for i in found.issues] == [("lock.ref-moved", "info")]
    assert found.changes == (LockChange("refs", "reg/R", "R4", "R4", "moved", origin="buck/R"),)


def test_renamed_without_moved() -> None:
    design = Design("t")
    reg = Module("reg")
    design.add(reg)
    reg.part(lib_id="Fenolite:Resistor")
    found = assign_refs(design, make_lock("t", {"refs": {"buck/R": "R4"}}), moves={})
    assert [(i.code, i.where) for i in found.issues] == [("lock.ref-released", "buck/R")]
    assert dict(found.refs) == {"reg/R": "R1"}


def test_design_renamed() -> None:
    design = channels("a")
    found = assign_refs(design, make_lock("old", {"refs": {"a/R": "R1"}}), moves={})
    assert found.lock.design == "t" and [i.code for i in found.issues] == ["lock.design-renamed"]
    assert found.changes == (LockChange("design", "design", "old", "t", "design-renamed"),)


def test_new_refs_skip_explicit_and_kept_refs() -> None:
    design = channels("a", "b", "c", explicit=("R1", "R3"))
    found = assign_refs(design, make_lock("t", {"refs": {"c/R": "R2"}}), moves={})
    assert dict(found.refs) == {"R1": "R1", "R3": "R3", "a/R": "R4", "b/R": "R5", "c/R": "R2"}


# -- order independent of the script

ORDER_SCRIPT = """
import json, sys
from fenolite.dsl import Design, Module
from fenolite.dsl.lock import assign_refs, make_lock
names = ["ch10", "ch2", "ch1", "a", "ch02"]
if sys.argv[1] == "reverse":
    names.reverse()
design = Design("t")
for name in names:
    module = Module(name)
    design.add(module)
    module.part(lib_id="Fenolite:Resistor")
    module.part(lib_id="Fenolite:Capacitor")
print(json.dumps(dict(assign_refs(design, make_lock("t"), moves={}).refs), sort_keys=True))
"""


def test_order_independent_of_the_script(tmp_path: Path) -> None:
    script = tmp_path / "order.py"
    script.write_text(ORDER_SCRIPT, encoding="utf-8")
    found = []
    for seed, order in (("1", "forward"), ("2", "reverse"), ("1", "reverse"), ("2", "forward")):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(
            [sys.executable, str(script), order], env=env, capture_output=True, text=True, check=True
        )
        found.append(json.loads(out.stdout))
    assert all(item == found[0] for item in found)
    assert found[0]["a/R"] == "R1" and found[0]["ch1/R"] == "R2" and found[0]["ch2/R"] == "R3"
    assert found[0]["ch02/R"] == "R4" and found[0]["ch10/R"] == "R5"
