# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit step of change c0462, task 5.1 (``tools/altium_scope_oracle.py``): the script calls only names a
public source gives, and the counts it writes read back."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

import pytest

TOOL = Path(__file__).resolve().parents[2] / "tools" / "altium_scope_oracle.py"
SOURCES = Path(__file__).resolve().parents[2] / "docs" / "evidence" / "sources.md"


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("altium_scope_oracle_tool", TOOL)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


tool = _load_tool()


def test_the_script_calls_only_sourced_names() -> None:
    text = tool.script_text()
    assert tool.called_names(text) <= set(tool.SCRIPT_CALLS), tool.called_names(text) - set(tool.SCRIPT_CALLS)
    listed = set(re.findall(r"^\| (S-[0-9]+) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))
    assert set(tool.SCRIPT_CALLS.values()) | {"S-2216"} <= listed
    assert f"Procedure {tool.PROCEDURE};" in text and f"RunProcess('{tool.PROCESS}')" in text


def test_scope_lines() -> None:
    assert tool.scope_lines(["IsVia", "InNet('A') And IsPad"]) == "1 IsVia\n2 InNet('A') And IsPad\n"


def test_counts_read_back() -> None:
    text = "\n".join(
        [
            "1 board track 12", "1 board via 0", "1 child polygon track 1", "1 child polygon track 1",
            "1 child component pad 1", "1 done", "2 skipped",
        ]
    )  # fmt: skip
    found = tool.parse_counts(text, ["InNet('GND')", "IsPad || IsVia"])
    assert found == [
        {
            "scope": "InNet('GND')",
            "board": {"track": 12, "via": 0},
            "child": {"polygon/track": 2, "component/pad": 1},
            "state": "done",
        },
        {"scope": "IsPad || IsVia", "board": {}, "child": {}, "state": "skipped"},
    ]


@pytest.mark.parametrize(
    ("text", "words"),
    [("1 board track 1", "no 'done'"), ("3 done", "not in the plan"), ("1 track 4", "not one the script")],
)
def test_bad_counts(text: str, words: str) -> None:
    with pytest.raises(ValueError, match=words):
        tool.parse_counts(text, ["IsVia", "IsPad"])
