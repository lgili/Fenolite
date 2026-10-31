# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The ``[blocks]`` section of the design lock (capability design-dsl, "Block versions in the design lock",
"Locked block versions in a build" and "Deprecated blocks in a build"; change c0268)."""

from __future__ import annotations

import runpy
from pathlib import Path
from typing import Any

import pytest

from fenolite.core.errors import FormatError
from fenolite.dsl import Design, block, connect, moves
from fenolite.dsl.block import BlockDef
from fenolite.dsl.lock import SECTIONS, assign_refs, lock_text, make_lock, needs_lock, read_lock

ROOT = Path(__file__).resolve().parents[3]
R, FP = "Fenolite:Resistor", "Fenolite:Chip_0603"


def divider(version: str = "1.0.0", *, block_id: str = "Acme:divider", deprecated: object = None) -> BlockDef:
    @block(id=block_id, version=version, summary="A divider", licence="CC0-1.0", deprecated=deprecated)  # type: ignore[arg-type]
    def made(b: Any) -> None:
        hi = b.port("HI", direction="in")
        top = b.part("top", R, footprint=FP, value="10k")
        connect(hi, top[1])

    return made


def design_of(*names: str, definition: BlockDef | None = None) -> Design:
    design = Design("sensor")
    made = definition or divider()
    for name in names:
        design.use(made, name)
    return design


def blocks_of(design: Design, lock: Any = None) -> Any:
    return assign_refs(design, lock or make_lock(design.name), moves=moves(design))


def test_section_order() -> None:
    names = [section.name for section in SECTIONS]
    assert names.index("blocks") == names.index("pins") + 1
    assert names.index("library") > names.index("blocks")


def test_first_build_pins_the_versions() -> None:
    """Scenario "First build pins the versions"."""
    found = blocks_of(design_of("sense_a", "sense_b"))
    assert dict(found.lock.sections["blocks"]) == {
        "sense_a": "Acme:divider@1.0.0",
        "sense_b": "Acme:divider@1.0.0",
    }
    reasons = [(c.key, c.reason) for c in found.changes if c.section == "blocks"]
    assert reasons == [("sense_a", "block-locked"), ("sense_b", "block-locked")]
    text = lock_text(found.lock)
    assert '[blocks]\n"sense_a" = "Acme:divider@1.0.0"\n"sense_b" = "Acme:divider@1.0.0"\n' in text
    assert read_lock(text, file="sensor.lock") == found.lock


def test_same_version_changes_nothing() -> None:
    first = blocks_of(design_of("sense_a")).lock
    again = blocks_of(design_of("sense_a"), first)
    assert again.lock == first and not [c for c in again.changes if c.section == "blocks"]


def test_newer_block_version_is_not_taken() -> None:
    """Scenario "Newer block version is not taken"."""
    first = blocks_of(design_of("sense_a")).lock
    found = blocks_of(design_of("sense_a", definition=divider("1.1.0")), first)
    (issue,) = [i for i in found.issues if i.code == "lock.block-version"]
    assert issue.severity == "error" and all(t in issue.message for t in ("sense_a", "1.0.0", "1.1.0"))
    assert "fenolite blocks show Acme:divider" in issue.hint
    assert found.lock.sections["blocks"]["sense_a"] == "Acme:divider@1.0.0"


def test_other_id_replaces_the_entry() -> None:
    first = blocks_of(design_of("sense_a")).lock
    found = blocks_of(design_of("sense_a", definition=divider(block_id="Acme:div2")), first)
    assert found.lock.sections["blocks"]["sense_a"] == "Acme:div2@1.0.0"
    assert [i.code for i in found.issues if i.code.startswith("lock.block")] == ["lock.block-replaced"]
    assert [c.reason for c in found.changes if c.section == "blocks"] == ["block-replaced"]


def test_entry_of_no_instance_is_released() -> None:
    first = blocks_of(design_of("sense_a", "sense_b")).lock
    found = blocks_of(design_of("sense_a"), first)
    assert dict(found.lock.sections["blocks"]) == {"sense_a": "Acme:divider@1.0.0"}
    (issue,) = [i for i in found.issues if i.code == "lock.block-released"]
    assert issue.severity == "info" and issue.where == "sense_b"


def test_moved_instance_keeps_its_entry() -> None:
    """Scenario "Moved instance keeps its entry"."""
    first = blocks_of(design_of("sense_a")).lock
    renamed = design_of("adc_a")
    renamed.moved("sense_a", "adc_a")
    found = blocks_of(renamed, first)
    assert dict(found.lock.sections["blocks"]) == {"adc_a": "Acme:divider@1.0.0"}
    assert [c.reason for c in found.changes if c.section == "blocks"] == ["moved"]


def test_nested_instances_are_pinned() -> None:
    inner = divider()

    @block
    def outer(b: Any) -> None:
        b.use(inner, "div")

    design = Design("sensor")
    design.use(outer, "ch0")
    assert dict(blocks_of(design).lock.sections["blocks"]) == {"ch0/div": "Acme:divider@1.0.0"}


def test_deprecated_block_used_twice() -> None:
    """Scenario "Deprecated block used twice"."""
    gone = divider(deprecated={"by": "Acme:div2", "since": "1.1.0", "reason": "port renamed"})
    found = blocks_of(design_of("a", "b", definition=gone))
    (issue,) = [i for i in found.issues if i.code == "block.deprecated"]
    assert issue.severity == "warning" and "Acme:div2" in issue.message


def test_project_blocks_get_no_section() -> None:
    """Scenario "Project block unchanged": the c0251 example gets no ``[blocks]`` section, and its committed
    lock is unchanged."""
    example = ROOT / "examples" / "blocks"
    design: Design = runpy.run_path(str(example / "design.py"))["design"]
    old = read_lock((example / "design.lock").read_text(encoding="utf-8"), file="design.lock")
    found = blocks_of(design, old)
    assert found.lock.sections["blocks"] == {} and "[blocks]" not in lock_text(found.lock)
    assert lock_text(found.lock) == (example / "design.lock").read_text(encoding="utf-8")


def test_recorded_block_needs_a_lock() -> None:
    @block(id="Acme:empty", version="1.0.0", summary="Empty", licence="CC0-1.0")
    def empty(b: Any) -> None: ...

    design = Design("sensor")
    assert not needs_lock(design)
    design.use(empty, "e")
    assert needs_lock(design)


@pytest.mark.parametrize("entry", ['"a b" = "Acme:x@1.0.0"', '"a" = "Acme:x"', '"a" = "x@1.0.0"', '"a" = 1'])
def test_bad_entries_are_refused(entry: str) -> None:
    text = f'schema = "fenolite.lock.v0"\ndesign = "sensor"\n\n[blocks]\n{entry}\n'
    with pytest.raises(FormatError, match="blocks"):
        read_lock(text, file="sensor.lock")
