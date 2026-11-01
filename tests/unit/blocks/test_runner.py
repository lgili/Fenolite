# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Runner proofs use an authored block library (change c0270)."""

import json
import shutil
from pathlib import Path

import pytest

from fenolite import api
from fenolite.cli.blocksrc import find_blocks
from fenolite.core.state import using_state
from fenolite.testing.blocks import convention, convention_of_entry, run_block_tests

DATA = Path(__file__).resolve().parents[2] / "data/blocks/lib"


@pytest.fixture
def library(tmp_path):
    root = tmp_path / "lib"
    shutil.copytree(DATA, root)
    return root


def records(library):
    return tuple(entry for entry in find_blocks(files=("divider.py",), cwd=library) if entry.source == "file")


def test_paths_in_show(library):
    (entry,) = records(library)
    reply = api.run("blocks", "show", "Test:divider", "--from", "divider.py", cwd=library)
    assert reply.exit_code == 0, reply.error
    block = reply.result["block"]
    assert block["tests"] == "tests/test_divider.py"
    assert block["usage"] == "usage/divider.py"
    assert convention(entry.definition).path("golden") == library / "golden/divider.json"
    assert block["golden"] == "golden/divider.json"
    (library / "golden/divider.json").unlink()
    reply = api.run("blocks", "show", "Test:divider", "--from", "divider.py", cwd=library)
    assert reply.result["block"]["golden"] is None


def test_paths_of_static_library_entry_never_import(library):
    class StaticEntry:
        source = "library"
        id = "Vendor:divider"
        item_root = library

        @property
        def definition(self):
            raise AssertionError("static record imported its Python code")

    paths = convention_of_entry(StaticEntry()).paths()
    assert paths == {
        "tests": "tests/test_divider.py",
        "usage": "usage/divider.py",
        "golden": "golden/divider.json",
    }


def test_usage_build_passes(library):
    result = run_block_tests(records(library), kinds=("usage",))
    assert result.blocks[0]["usage"] == "passed", result.issues
    assert not [issue for issue in result.issues if issue.code == "blocks.usage-failed"]


def test_usage_failed_names_first_finding(library):
    path = library / "usage/divider.py"
    path.write_text(path.read_text().replace("connect(dut.OUT, j1[2])", ""))
    result = run_block_tests(records(library), kinds=("usage",))
    (issue,) = [issue for issue in result.issues if issue.code == "blocks.usage-failed"]
    assert issue.severity == "error" and "Test:divider" in issue.message
    assert "build.port-unused" in issue.message
    assert result.exit_code == 5 and result.blocks[0]["usage"] == "failed"


def test_usage_build_creates_no_source_lock(library):
    lock = library / "usage/divider.lock"
    lock.unlink(missing_ok=True)
    before = {p.relative_to(library): p.read_bytes() for p in library.rglob("*") if p.is_file()}
    result = run_block_tests(records(library), kinds=("usage",))
    assert result.blocks[0]["usage"] == "passed", result.issues
    assert {p.relative_to(library): p.read_bytes() for p in library.rglob("*") if p.is_file()} == before
    assert not lock.exists()


def write_golden(library):
    result = run_block_tests(records(library), kinds=("golden",), golden_plan=True)
    assert len(result.writes) == 1, result.issues
    write = result.writes[0]
    write.path.parent.mkdir(exist_ok=True)
    write.path.write_bytes(write.data)
    return write.data


def test_golden_differs_and_is_read_only(library):
    old = write_golden(library)
    path = library / "golden/divider.json"
    data = json.loads(old)
    index = next(
        index
        for index, part in enumerate(data["circuit"]["components"])
        if part.get("properties", {}).get("fenolite.path") == "sense/bot"
    )
    module = library / "divider.py"
    module.write_text(module.read_text().replace('bottom="10000"', 'bottom="9900"'))
    result = run_block_tests(records(library), kinds=("golden",))
    (issue,) = result.issues
    assert issue.code == "blocks.golden-differs"
    assert f"circuit.components[{index}].value" in result.blocks[0]["golden_paths"]
    assert "--golden --dry-run" in issue.hint
    assert path.read_bytes() == old and not result.writes


def test_golden_stability_and_version(library):
    golden = write_golden(library)
    a = run_block_tests(records(library), kinds=("golden",))
    b = run_block_tests(records(library), kinds=("golden",))
    assert a == b and a.exit_code == 0 and a.blocks[0]["golden"] == "equal"
    data = json.loads(golden)
    assert data["schema"] == "fenolite.block-golden.v0" and data["seed"] == 0
    data["version"] = "0.9.0"
    path = library / "golden/divider.json"
    from fenolite.model.canonical import dumps

    path.write_text(dumps(data))
    result = run_block_tests(records(library), kinds=("golden",))
    assert result.blocks[0]["golden_paths"] == ["version"]


def test_golden_source_version_refreshes_catalog(library):
    write_golden(library)
    module = library / "divider.py"
    module.write_text(module.read_text().replace('version="1.0.0"', 'version="1.1.0"'))
    result = run_block_tests(records(library), kinds=("golden",))
    assert result.blocks[0]["version"] == "1.1.0"
    assert "version" in result.blocks[0]["golden_paths"]
    planned = run_block_tests(records(library), kinds=("golden",), golden_plan=True)
    assert json.loads(planned.writes[0].data)["version"] == "1.1.0"


def test_committed_authored_golden(library):
    """H-G-BLOCK-GOLDEN: one committed byte reference is checked by every unit matrix job."""
    a = run_block_tests(records(library), kinds=("golden",))
    b = run_block_tests(records(library), kinds=("golden",))
    assert a == b and a.exit_code == 0, a.issues
    assert a.blocks[0]["golden"] == "equal"


def test_authored_runner_needs_no_external_tool(library, monkeypatch):
    import subprocess

    def refuse(*args, **kwargs):
        raise AssertionError("the block runner started a process")

    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)
    result = run_block_tests(records(library))
    assert result.exit_code == 0, result.issues


def test_golden_paths_are_sorted_and_bounded():
    from fenolite.testing.blocks import differing_paths

    a, b = {f"field{i:02}": 0 for i in range(30)}, {f"field{i:02}": 1 for i in range(30)}
    assert differing_paths(json.dumps(a).encode(), json.dumps(b).encode()) == tuple(sorted(a)[:20])
    assert differing_paths(b"not json", b"{}") == ("$",)


def test_golden_missing_under_only(library):
    (library / "golden/divider.json").unlink()
    result = run_block_tests(records(library), kinds=("golden",))
    assert [issue.code for issue in result.issues] == ["blocks.convention-missing", "blocks.golden-missing"]
    (library / "usage/divider.py").unlink()
    result = run_block_tests(records(library), kinds=("golden",))
    assert [issue.code for issue in result.issues] == ["blocks.convention-missing", "blocks.golden-missing"]


def test_functions_pass_fail_skip_in_name_order(library):
    path = library / "tests/test_divider.py"
    path.write_text("""def test_a_pass():
    pass
def test_b_fail():
    raise AssertionError("ratio")
def test_c_fixture(tmp_path):
    pass
def test_d_optional(value=1, *, other=2):
    assert value + other == 3
def test_e_error():
    raise ValueError("bad value")
""")
    result = run_block_tests(records(library), kinds=("tests",))
    tests = result.blocks[0]["tests"]
    assert [test["status"] for test in tests] == ["passed", "failed", "skipped", "passed", "failed"]
    assert tests[1]["message"] == "ratio" and tests[4]["message"] == "ValueError: bad value"
    assert [i.code for i in result.issues if i.code != "blocks.convention-missing"] == [
        "blocks.test-failed",
        "blocks.test-unsupported",
        "blocks.test-failed",
    ]


def test_functions_restore_state_and_imports(library, capsys):
    import os
    import random
    import sys

    path = library / "tests/test_divider.py"
    path.write_text("""from pathlib import Path
import random
import sys
from divider import divider
print("module output")
def test_pass():
    Path("temporary-only").write_text("authored")
    sys.path.append("temporary-path")
    random.seed(99)
    print("test output")
""")
    before = (Path.cwd(), list(sys.path), random.getstate(), sys.dont_write_bytecode)
    entries = records(library)
    name = entries[0].definition.function.__module__
    original = sys.modules[name]
    result = run_block_tests(entries, kinds=("tests",))
    assert result.blocks[0]["tests"][0]["status"] == "passed"
    assert (Path.cwd(), sys.path, random.getstate(), sys.dont_write_bytecode) == before
    assert not (library / "temporary-only").exists() and not Path("temporary-only").exists()
    assert "divider" not in sys.modules and not list(library.rglob("__pycache__"))
    assert sys.modules[name] is original
    assert not capsys.readouterr().out
    assert os.getcwd() == str(before[0])


def test_functions_import_error_and_message_limit(library):
    path = library / "tests/test_divider.py"
    path.write_text('raise RuntimeError("x" * 1000)')
    result = run_block_tests(records(library), kinds=("tests",))
    assert len(result.blocks[0]["tests"]) == 1
    assert len(result.blocks[0]["tests"][0]["message"]) == 500
    assert result.issues[-1].code == "blocks.test-failed"


def golden_command(library, *args):
    with using_state(library.parent / "state"):
        return api.run(
            "blocks",
            "test",
            "Test:divider",
            "--from",
            "divider.py",
            "--golden",
            *args,
            cwd=library,
        )


def test_golden_write_plan_and_replay(library, monkeypatch):
    import hashlib

    golden = library / "golden/divider.json"
    before = golden.read_bytes() if golden.exists() else None
    planned = golden_command(library, "--dry-run")
    assert planned.exit_code == 0, (planned.error, planned.envelope)
    assert (golden.read_bytes() if golden.exists() else None) == before
    (row,) = planned.result["plan"]
    assert row["path"] == "golden/divider.json"
    (hashes,) = planned.result["golden_plan"]
    assert hashes["old_sha256"] == (hashlib.sha256(before).hexdigest() if before else None)

    def refuse(*args, **kwargs):
        raise AssertionError("the reviewed runner was executed again")

    monkeypatch.setattr("fenolite.cli._blocks_test.run_block_tests", refuse)
    written = golden_command(library, "--confirm", "--plan", planned.result["plan_id"])
    assert written.exit_code == 0, written.error
    digest = hashlib.sha256(golden.read_bytes()).hexdigest()
    assert digest == hashes["new_sha256"] == row["sha256"]
    assert written.envelope["receipt"]["written"] == [{"path": "golden/divider.json", "sha256": digest}]
    assert written.result["blocks"][0]["golden"] == "written"


def test_golden_write_failing_usage_writes_nothing(library):
    path = library / "usage/divider.py"
    path.write_text(path.read_text().replace("connect(dut.OUT, j1[2])", ""))
    result = golden_command(library, "--dry-run")
    assert result.exit_code == 5
    assert not result.result.get("plan") and not result.result["golden_plan"]
    assert any(issue["code"] == "blocks.usage-failed" for issue in result.envelope["issues"])


def test_golden_write_changed_input_is_stale(library):
    planned = golden_command(library, "--dry-run")
    path = library / "divider.py"
    path.write_text(path.read_text() + "\n# changed after review\n")
    result = golden_command(library, "--confirm", "--plan", planned.result["plan_id"])
    assert result.exit_code == 4 and result.error["code"] == "FEN-4002"


def test_golden_write_warning_exit_survives_replay(library):
    path = library / "tests/test_divider.py"
    path.write_text("def test_fixture(tmp_path): pass\n")
    planned = golden_command(library, "--dry-run")
    assert planned.exit_code == 5 and planned.result["plan_id"]
    result = golden_command(library, "--confirm", "--plan", planned.result["plan_id"])
    assert result.exit_code == 5 and result.envelope["receipt"]["written"]
    assert result.envelope["issues"][0]["severity"] == "warning"


def test_golden_write_requires_review(library):
    result = golden_command(library, "--confirm")
    assert result.exit_code == 2 and result.error["code"] == "FEN-2001"
