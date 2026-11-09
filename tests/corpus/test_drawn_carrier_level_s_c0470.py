# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Level S compares a carried Altium record by its record, not by the uuid of its KiCad stand-in, which a
conversion makes anew (change c0470): the KiCad drawing of a public Altium set, and a copy whose stand-in
has another uuid, are the same drawing."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from _altium_sets import SETS, lay_out

from fenolite.api import convert, equivalent

pytestmark = pytest.mark.long_flow

_STAND_IN = re.compile(r'\\"uuid\\":\\"([0-9a-f]{8}-[0-9a-f-]{27})\\"')


def test_a_new_stand_in_uuid_is_the_same_drawing(tmp_path: Path) -> None:
    project = next(lay_out(SETS["altium-set:02"], tmp_path / "src").rglob("*.PrjPcb"))
    written = convert(project, to="kicad", allow_lossy=True).conversion.files
    one = tmp_path / "one"
    for name, data in written.items():
        (one / name).parent.mkdir(parents=True, exist_ok=True)
        (one / name).write_bytes(data)
    two = tmp_path / "two"
    shutil.copytree(one, two)
    changed = 0
    for sheet in two.glob("*.kicad_sch"):
        text = sheet.read_text(encoding="utf-8")
        for uuid in dict.fromkeys(_STAND_IN.findall(text)):
            text = text.replace(uuid, "00000000-0000-4000-8000-" + f"{changed:012x}")
            changed += 1
        sheet.write_text(text, encoding="utf-8")
    assert changed
    found = equivalent(next(one.glob("*.kicad_pro")), next(two.glob("*.kicad_pro")), level="S")
    assert found.report is not None
    assert [d for level in found.report.levels for d in level.differences] == []
