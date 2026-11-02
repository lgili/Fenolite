# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The authored block payload is executed by its runner, outside repository pytest discovery (c0322)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

from corpus.test_manifest import data_file_problems

ROOT = Path(__file__).resolve().parents[2]
LIBRARY = Path("tests/data/blocks/lib")
PAYLOAD = LIBRARY / "tests/test_divider.py"


def _environment() -> dict[str, str]:
    env = dict(os.environ)
    for key in ("PYTHONDONTWRITEBYTECODE", "PYTHONPYCACHEPREFIX", "PYTEST_ADDOPTS"):
        env.pop(key, None)
    return env


def _copy_library(root: Path) -> Path:
    target = root / LIBRARY
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / LIBRARY, target)
    return target


def test_default_collection_preserves_payload_with_bytecode_enabled(tmp_path: Path) -> None:
    shutil.copyfile(ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    _copy_library(tmp_path)
    for name in ("conftest.py", "_resources.py"):
        shutil.copyfile(ROOT / "tests" / name, tmp_path / "tests" / name)
    for relative, function in (
        ("tests/unit/test_public.py", "test_public"),
        ("tests/data/collection_neighbor/test_neighbor.py", "test_neighbor"),
    ):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"import sys\nassert not sys.dont_write_bytecode\ndef {function}():\n    assert True\n",
            encoding="utf-8",
        )
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q"],
        cwd=tmp_path,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "test_public.py::test_public" in done.stdout
    assert "test_neighbor.py::test_neighbor" in done.stdout
    # This positive control prevents a no-bytecode environment from hiding the original defect.
    assert list((tmp_path / "tests/unit/__pycache__").glob("test_public.*.pyc"))
    assert list((tmp_path / "tests/data/collection_neighbor/__pycache__").glob("test_neighbor.*.pyc"))
    caches = list((tmp_path / PAYLOAD.parent).rglob("*.pyc"))
    assert PAYLOAD.as_posix() not in done.stdout and not caches, (done.stdout, caches)


def test_block_runner_executes_payload_without_global_bytecode_suppression(tmp_path: Path) -> None:
    library = _copy_library(tmp_path)
    code = """import json
import sys
from pathlib import Path
from fenolite.cli.blocksrc import find_blocks
from fenolite.testing.blocks import run_block_tests

assert not sys.dont_write_bytecode
root = Path(sys.argv[1])
entries = tuple(e for e in find_blocks(files=("divider.py",), cwd=root) if e.source == "file")
passed = run_block_tests(entries, kinds=("tests",))
assert passed.exit_code == 0, passed.issues
assert passed.blocks[0]["tests"][0]["status"] == "passed"
assert not sys.dont_write_bytecode and not list(root.rglob("__pycache__"))
path = root / "tests/test_divider.py"
path.write_text(path.read_text(encoding="utf-8") + "\\ndef test_execution_witness():\\n"
                "    raise AssertionError('runner execution witness')\\n", encoding="utf-8")
failed = run_block_tests(entries, kinds=("tests",))
assert failed.exit_code == 5
assert any(t.get("message") == "runner execution witness" for t in failed.blocks[0]["tests"])
assert not sys.dont_write_bytecode and not list(root.rglob("__pycache__"))
print(json.dumps({"python": sys.version.split()[0], "bytecode_enabled": not sys.dont_write_bytecode,
                  "payload_passed": True, "planted_failure_observed": True}))
"""
    done = subprocess.run(
        [sys.executable, "-c", code, str(library)],
        cwd=tmp_path,
        env=_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    witness = json.loads(done.stdout)
    assert witness["bytecode_enabled"] and witness["payload_passed"] and witness["planted_failure_observed"]


def test_manifest_still_rejects_undeclared_fixture_bytecode(tmp_path: Path) -> None:
    _copy_library(tmp_path)
    declared = tomllib.loads((ROOT / "tests/data/MANIFEST.toml").read_text(encoding="utf-8"))["file"]
    assert data_file_problems(tmp_path, [], declared) == []
    leak = tmp_path / PAYLOAD.parent / "__pycache__/test_divider.leaked.pyc"
    leak.parent.mkdir()
    leak.write_bytes(b"undeclared bytecode witness")
    assert data_file_problems(tmp_path, [], declared) == [
        f"{leak.relative_to(tmp_path).as_posix()}: not declared in tests/data/MANIFEST.toml"
    ]
