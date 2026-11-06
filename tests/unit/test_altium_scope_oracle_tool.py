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


def test_the_count_procedure_runs_no_process() -> None:
    """``FenoliteCountSelection`` counts the selection a PCB Filter step made by hand: it reads the key from
    ``.current.txt``, writes ``.counts-<n>.txt`` and starts no process."""
    text = tool.script_text()
    body = text[text.index(f"Procedure {tool.COUNT_PROCEDURE};") :]
    assert "RunProcess" not in body and tool.CURRENT in body and "'.counts-' + Key + '.txt'" in body
    assert body.index("Writeln(OutFile, Key + ' done')") < body.index("ClearAll(Board)")


def test_per_scope_counts(tmp_path: Path) -> None:
    scopes = ["IsVia", "IsPad || IsVia", "InNet('A')"]
    assert tool.per_scope_counts(tmp_path, "b.PcbDoc", scopes) is None
    (tmp_path / "b.PcbDoc.counts-1.txt").write_text("1 board via 8\r\n1 done\r\n", encoding="utf-8")
    (tmp_path / "b.PcbDoc.counts-3.txt").write_text("3 board track 2\n3 done\n", encoding="utf-8")
    text = tool.per_scope_counts(tmp_path, "b.PcbDoc", scopes)
    assert text == "1 board via 8\n1 done\n2 skipped\n3 board track 2\n3 done\n"
    assert [entry["state"] for entry in tool.parse_counts(text, scopes)] == ["done", "skipped", "done"]
    (tmp_path / "b.PcbDoc.counts-3.txt").write_text("1 board track 2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not of scope 3"):
        tool.per_scope_counts(tmp_path, "b.PcbDoc", scopes)


def test_a_scope_not_counted_by_hand_is_missing(tmp_path: Path) -> None:
    (tmp_path / "b.PcbDoc.counts-1.txt").write_text("1 done\n", encoding="utf-8")
    text = tool.per_scope_counts(tmp_path, "b.PcbDoc", ["IsVia", "IsPad"])
    with pytest.raises(ValueError, match=r"scopes \[2\]"):
        tool.parse_counts(text, ["IsVia", "IsPad"])
