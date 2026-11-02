# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual Windows codec and drive boundaries retain document/CLI contracts (c0319)."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

from _checkcli import run

ROOT = Path(__file__).resolve().parents[3]
GOOD = ROOT / "tests/data/library_rules/good"
WINDOWS_NODES = (
    "tests/unit/test_legal_docs.py::test_bundle_and_lock_must_retain_reviewed_terms",
    "tests/unit/blocks/test_starter.py::test_sources_registered",
    "tests/unit/suppliers/test_policy.py::test_policies_equal_their_review_pages",
    "tests/unit/suppliers/test_policy.py::test_fixtures_are_authored_and_registered",
    "tests/unit/cli/test_library_check.py::test_findings_exit_warning_threshold_and_selection",
    "tests/unit/cli/test_library_check.py::test_compare_sheets_reuses_visual_overlay",
    "tests/unit/cli/test_library_check.py::test_manufacturer_land_detects_generator_drift",
    "tests/unit/library/test_fixtures.py::test_good_fixtures_cover_every_family_and_are_declared",
    "tests/unit/library/test_fixtures.py::test_bad_fixtures_trigger_the_named_rule",
)


def test_original_windows_nodes_under_cp1252_default(tmp_path: Path) -> None:
    plugin = tmp_path / "locale_witness.py"
    plugin.write_text(
        """import io
import json
import os
from pathlib import Path

def pytest_configure(config):
    original_open, original_encoding = io.open, io.text_encoding
    def platform_encoding(encoding, stacklevel=2):
        return "cp1252" if encoding is None else original_encoding(encoding, stacklevel)
    def platform_open(file, mode="r", buffering=-1, encoding=None, *args, **kwargs):
        if "b" not in mode and encoding in (None, "locale"):
            encoding = "cp1252"
        return original_open(file, mode, buffering, encoding, *args, **kwargs)
    io.text_encoding, io.open = platform_encoding, platform_open
    folder = Path(os.environ["FENOLITE_CODEC_WITNESS"])
    text = "Authored for Fenolite: \\u03a9 \\u6f22 \\u0101\\n"
    witness = folder / "authored-utf8.txt"
    witness.write_bytes(text.encode("utf-8"))
    try:
        witness.read_text()
    except UnicodeDecodeError:
        pass
    else:
        raise AssertionError("cp1252 negative control did not fail")
    assert witness.read_text(encoding="utf-8") == text
    result = {"default": "cp1252", "negative_control": True}
    (folder / "witness.json").write_bytes(json.dumps(result).encode())
""",
        encoding="utf-8",
    )
    env = dict(os.environ)
    env.pop("PYTHONUTF8", None)
    env.pop("PYTEST_ADDOPTS", None)
    env["PYTHONPATH"] = str(tmp_path) + os.pathsep + env.get("PYTHONPATH", "")
    env["FENOLITE_CODEC_WITNESS"] = str(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "pytest", "-p", plugin.stem, *WINDOWS_NODES, "-q", "--tb=short"],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert (tmp_path / "witness.json").exists(), done.stdout + done.stderr
    assert json.loads((tmp_path / "witness.json").read_text(encoding="utf-8")) == {
        "default": "cp1252",
        "negative_control": True,
    }
    assert done.returncode == 0, done.stdout + done.stderr
    assert "9 passed" in done.stdout


def test_cross_drive_library_inputs_keep_findings_and_sheet_scope(monkeypatch, tmp_path: Path) -> None:
    from fenolite.cli import _library_check

    assert _library_check._relative(GOOD / "packages/chip.toml", ROOT) == (
        "tests/data/library_rules/good/packages/chip.toml"
    )
    calls = []

    def different_drives(path, start):
        calls.append((path, start))
        raise ValueError("path is on mount 'D:', start on mount 'C:'")

    monkeypatch.setattr(_library_check, "os", SimpleNamespace(path=SimpleNamespace(relpath=different_drives)))
    bad = ROOT / "tests/data/library_rules/bad/pin_group_type.toml"
    code, reply, error, _ = run(monkeypatch, tmp_path, "library", "check", str(bad))
    assert code == 0, (reply, error)
    assert reply["result"]["items"][0]["file"] == bad.as_posix()
    assert "library.pin-group-type" in {row["code"] for row in reply["issues"]}
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", str(bad), "--fail-on", "warning")
    assert code == 5 and reply["issues"]
    invalid = tmp_path / "invalid.toml"
    invalid.write_text("schema = [", encoding="utf-8")
    code, reply, _, _ = run(monkeypatch, tmp_path, "library", "check", str(invalid))
    assert code == 5
    assert {row["code"] for row in reply["issues"]} == {"library.record-invalid"}
    source = tmp_path / "authored-package.toml"
    shutil.copyfile(GOOD / "packages/chip.toml", source)
    args = ("library", "check", str(source), "--sheets", "review")
    code, reply, error, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (reply, error)
    assert reply["result"]["plan"] and not (tmp_path / "review").exists()
    assert all(row["path"].startswith("review/") for row in reply["result"]["plan"])
    source.write_bytes(source.read_bytes() + b"\n# Authored edit after plan review.\n")
    code, blocked, error, _ = run(
        monkeypatch, tmp_path, *args, "--confirm", "--plan", reply["result"]["plan_id"]
    )
    assert code == 4 and error["code"] == "FEN-4002", blocked
    assert not (tmp_path / "review").exists()
    code, fresh, error, _ = run(monkeypatch, tmp_path, *args, "--dry-run")
    assert code == 0, (fresh, error)
    code, written, error, _ = run(
        monkeypatch, tmp_path, *args, "--confirm", "--plan", fresh["result"]["plan_id"]
    )
    assert code == 0 and written["receipt"], (written, error)
    assert (tmp_path / "review/sheets.json").is_file()
    assert calls
