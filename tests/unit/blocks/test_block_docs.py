# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Generated block pages contain the authored expectations, usages and layout footprints."""

import dataclasses
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def generator():
    spec = importlib.util.spec_from_file_location("block_docs", ROOT / "tools/gen_block_docs.py")
    assert spec is not None and spec.loader is not None
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


def test_pages_match_records_and_conventions():
    tool = generator()
    wanted = tool.pages(tool.shipped_records(), tool.source_titles(), tool.details())
    assert not tool.differences(wanted)
    for path, text in wanted.items():
        if path.endswith("index.md"):
            assert "## Later" in text and "ESD" in text
        else:
            assert all(title in text for title in ("## Expectations", "## Usage", "## Layout"))


def test_parameter_doc_changes_page():
    tool = generator()
    records = tool.shipped_records()
    changed = dataclasses.replace(records[0].params[0], doc="Authored changed documentation")
    records[0] = dataclasses.replace(records[0], params=(changed, *records[0].params[1:]))
    wanted = tool.pages(records, tool.source_titles(), tool.details())
    assert tool.differences(wanted)
