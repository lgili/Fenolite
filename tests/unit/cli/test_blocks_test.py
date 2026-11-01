# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Block tests expose deterministic per-block results and findings (change c0270)."""

import shutil
from pathlib import Path

import pytest

from fenolite import api
from fenolite.cli.blocksrc import find_blocks
from fenolite.core.state import using_state
from fenolite.testing.blocks import run_block_tests

DATA = Path(__file__).resolve().parents[2] / "data/blocks/lib"


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "lib"
    shutil.copytree(DATA, root)
    entries = tuple(e for e in find_blocks(files=("divider.py",), cwd=root) if e.source == "file")
    result = run_block_tests(entries, kinds=("golden",), golden_plan=True)
    for write in result.writes:
        write.path.parent.mkdir(exist_ok=True)
        write.path.write_bytes(write.data)
    return root


def invoke(library, *args):
    with using_state(library.parent / "state"):
        return api.run("blocks", "test", *args, "--from", "divider.py", cwd=library)


def snapshot(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def test_one_block_read_only(library):
    before = snapshot(library)
    reply = invoke(library, "Test:divider")
    assert reply.exit_code == 0, (reply.error, reply.envelope)
    (block,) = reply.result["blocks"]
    assert block["id"] == "Test:divider" and block["version"] == "1.0.0"
    assert block["usage"] == "passed" and block["golden"] == "equal"
    assert block["tests"] and all(test["status"] == "passed" for test in block["tests"])
    assert "seconds" not in block and snapshot(library) == before


def test_unknown_id_has_closest_hint(library):
    reply = invoke(library, "Test:dividr")
    assert reply.exit_code == 2 and reply.error["code"] == "FEN-2001"
    assert "Test:divider" in reply.error["hint"]


@pytest.mark.parametrize("kind", ("usage", "golden", "tests"))
def test_only_selects_one_kind(library, kind):
    reply = invoke(library, "Test:divider", "--only", kind)
    assert reply.exit_code == 0, reply.error
    block = reply.result["blocks"][0]
    assert bool(block["tests"]) == (kind == "tests")
    if kind == "usage":
        assert block["golden"] == "missing"


def test_warning_is_exit_five(library):
    path = library / "tests/test_divider.py"
    path.write_text("def test_fixture(tmp_path): pass\n")
    reply = invoke(library, "Test:divider", "--only", "tests")
    assert reply.exit_code == 5 and reply.error["code"] == "FEN-5001"
    assert reply.envelope["issues"][0]["code"] == "blocks.test-unsupported"
    assert reply.envelope["issues"][0]["severity"] == "warning"


def test_project_convention_discovered(library):
    with using_state(library.parent / "state"):
        reply = api.run("blocks", "test", cwd=library)
    assert reply.exit_code == 0 and any(row["id"] == "Test:divider" for row in reply.result["blocks"])


def test_category_filters_selected_blocks(library):
    reply = invoke(library, "--category", "analog", "--only", "tests")
    assert reply.exit_code == 0 and any(row["id"] == "Test:divider" for row in reply.result["blocks"])
    reply = invoke(library, "--category", "power", "--only", "tests")
    assert reply.exit_code == 0 and reply.result["blocks"] == []


@pytest.mark.parametrize("verb", ("list", "capture", "index", "upgrade"))
def test_test_flags_rejected_on_other_verbs(library, verb):
    reply = api.run("blocks", verb, "--only", "tests", cwd=library)
    assert reply.exit_code == 2 and "belong to blocks test" in reply.error["message"]
    reply = invoke(library, "--golden", "--only", "usage")
    assert reply.exit_code == 2
