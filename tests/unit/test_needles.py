# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tests/_needles.absent`` finds a value in every spelling a text can give it."""

from __future__ import annotations

import json

from _needles import absent, spellings

WINDOWS = "D:\\work\\project"
POSIX = "/srv/work/project"


def test_a_windows_path_is_found_in_json_text_and_in_repr() -> None:
    reply = json.dumps({"error": f"cannot read {WINDOWS}\\board.kicad_pcb"})
    assert WINDOWS not in reply, "the plain search is blind here: JSON doubles each backslash"
    assert not absent(WINDOWS, reply)
    assert not absent(WINDOWS, repr({"file": WINDOWS}))
    assert not absent(WINDOWS, "nothing here", reply)


def test_plain_text_and_posix_paths() -> None:
    assert not absent(POSIX, json.dumps({"file": POSIX + "/a"})) and not absent(WINDOWS, f"at {WINDOWS}")
    assert absent(POSIX, json.dumps({"file": "a"})) and absent(WINDOWS, json.dumps({"file": "D:\\other"}))
    assert spellings(POSIX) == (POSIX,) and len(spellings(WINDOWS)) == 2
