# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library audit`` (capability fenolite-library: "Library repository layout", "Library item
manifest", "Provenance record", "Licence allow-list", "Licence deny reasons", "Licence text and notices",
"Library use statement"; c0281's "Replayable conversion steps"; change c0279). Each scenario edits a copy of
the authored demo library."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli import main as cli_main
from fenolite.library.audit import audit

BOARD = "boards/cern-ohl-s/demo-src/blink"
DEVICE = "devices/cc0/Demo/EXB"


def _cli(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def _codes(root: Path) -> list[tuple[str, str]]:
    return [(i.code, i.message) for i in audit(root).issues]


def _edit_json(path: Path, **changes: Any) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    for dotted, value in changes.items():
        node = data
        keys = dotted.split("__")
        for key in keys[:-1]:
            node = node[key]
        node[keys[-1]] = value
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def test_demo_passes(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    code, envelope = _cli(monkeypatch, demo, "library", "audit", ".")
    assert code == 0, envelope["issues"]
    assert envelope["result"]["counts"] == {"block": 1, "board": 1, "device": 1, "footprint": 2, "symbol": 1}
    assert envelope["evidence"]["level"] == "INFERRED"


def test_item_in_the_wrong_family(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Item in the wrong family"."""
    target = demo / "footprints" / "cc0" / "Demo" / "SA_PAD"
    shutil.move(demo / "footprints" / "cc-by-sa" / "Demo" / "SA_PAD", target)
    code, envelope = _cli(monkeypatch, demo, "library", "audit", ".")
    assert code == 5
    found = [i for i in envelope["issues"] if i["code"] == "library.family-mismatch"]
    assert found and "footprints/cc0/Demo/SA_PAD" in found[0]["message"] and "cc-by-sa" in found[0]["message"]


def test_one_id_in_two_families(demo: Path) -> None:
    """Scenario "One id in two families"."""
    shutil.copytree(demo / DEVICE, demo / "devices" / "mit" / "Demo" / "EXB")
    found = [m for c, m in _codes(demo) if c == "library.duplicate-id"]
    assert found and "devices/cc0/Demo/EXB" in found[0] and "devices/mit/Demo/EXB" in found[0]


def test_unlisted_file(demo: Path) -> None:
    """Scenario "Unlisted file"."""
    (demo / DEVICE / "notes.txt").write_text("x\n", encoding="utf-8")
    assert any(c == "library.item-extra-file" and "notes.txt" in m for c, m in _codes(demo))


def test_block_items_execute(demo: Path) -> None:
    """Scenario "Block items execute"."""
    _edit_json(demo / "blocks/apache/Demo/buck/item.json", executes=False)
    assert any(
        c == "library.provenance-invalid" and "block and board items execute" in m for c, m in _codes(demo)
    )


def test_converted_item_without_a_commit(demo: Path) -> None:
    """Scenario "Converted item without a commit"."""
    _edit_json(demo / BOARD / "PROVENANCE.json", upstream__commit="main")
    assert any(c == "library.provenance-invalid" and "upstream.commit" in m for c, m in _codes(demo))


def test_provenance_and_manifest_disagree(demo: Path) -> None:
    """Scenario "Provenance and manifest disagree"."""
    _edit_json(demo / DEVICE / "PROVENANCE.json", spdx="MIT")
    found = [m for c, m in _codes(demo) if c == "library.provenance-invalid" and "spdx:" in m]
    assert found and "'MIT'" in found[0] and "'CC0-1.0'" in found[0]


def test_allowed_id_accepted(demo: Path) -> None:
    """Scenario "Allowed id accepted": the CERN-OHL-S-2.0 board with its listed text."""
    board = [(c, m) for c, m in _codes(demo) if BOARD in m]
    assert not [c for c, _ in board if c.startswith("library.licence")]


def test_non_commercial_licence_refused(demo: Path) -> None:
    """Scenario "Non-commercial licence refused"."""
    for name in ("item.json", "PROVENANCE.json"):
        _edit_json(demo / BOARD / name, spdx="CC-BY-NC-SA-4.0")
    found = [m for c, m in _codes(demo) if c == "library.licence-denied"]
    assert found and "non-commercial" in found[0]


def test_platform_restricted_origin_refused(demo: Path) -> None:
    """Scenario "Platform-restricted origin refused"."""
    _edit_json(demo / BOARD / "PROVENANCE.json", upstream__url="https://oshwlab.com/someone/board")
    found = [m for c, m in _codes(demo) if c == "library.licence-denied"]
    assert found and "platform-restricted" in found[0]


def test_vendor_bundled_refused(demo: Path) -> None:
    _edit_json(demo / BOARD / "PROVENANCE.json", upstream__vendor_bundled=True)
    assert any(c == "library.licence-denied" and "vendor-bundled" in m for c, m in _codes(demo))


def test_licence_text_needs_a_listed_digest_or_a_review(demo: Path) -> None:
    (demo / DEVICE / "LICENSE").write_text("Another text.\n", encoding="utf-8")
    assert any(c == "library.licence-text" for c, _ in _codes(demo))
    _edit_json(
        demo / DEVICE / "PROVENANCE.json",
        licence_review={"by": "maintainer", "date": "2026-10-30", "note": "variant"},
        licence_text_sha256=None,
    )
    assert not any(c == "library.licence-text" for c, _ in _codes(demo))


def test_notice_without_modification_line(demo: Path) -> None:
    """Scenario "Notice without modification line"."""
    (demo / BOARD / "NOTICE").write_text("Upstream notices, verbatim:\n\nnone\n", encoding="utf-8")
    found = [m for c, m in _codes(demo) if c == "library.notice-missing"]
    assert found and BOARD in found[0]


def test_readme_without_the_use_statement(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "README without the use statement"."""
    readme = demo / "README.md"
    readme.write_text(
        readme.read_text(encoding="utf-8").replace("machine-learning", "statistical"), encoding="utf-8"
    )
    code, envelope = _cli(monkeypatch, demo, "library", "audit", ".")
    assert code == 5
    assert any(
        i["code"] == "library.provenance-invalid" and i["where"] == "README.md" for i in envelope["issues"]
    )


def test_depends_unknown_and_cycle(demo: Path) -> None:
    _edit_json(
        demo / DEVICE / "item.json", depends=[{"kind": "symbol", "id": "Demo:EXB", "version": "9.0.0"}]
    )
    assert any(c == "library.provenance-invalid" and "9.0.0" in m for c, m in _codes(demo))
    _edit_json(
        demo / DEVICE / "item.json", depends=[{"kind": "symbol", "id": "Demo:EXB", "version": "1.0.0"}]
    )
    _edit_json(
        demo / "symbols/cc0/Demo/EXB/item.json",
        depends=[{"kind": "device", "id": "Demo:EXB", "version": "1.2.0"}],
    )
    assert any(c == "library.provenance-invalid" and "cycle" in m for c, m in _codes(demo))


def test_plan_step_refused(demo: Path) -> None:
    """c0281 scenario "Step with a plan id": a recorded --plan is refused, --confirm alone passes."""
    path = demo / BOARD / "PROVENANCE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    step = data["conversion"]["steps"][0]
    data["conversion"]["steps"] = [
        {**step, "argv": [*step["argv"][:-1], "--dry-run"]},
        {**step, "argv": [*step["argv"], "--plan", "0123456789abcdef"]},
    ]
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    found = [m for c, m in _codes(demo) if c == "library.provenance-invalid" and "--plan" in m]
    assert found and "conversion.steps[2]" in found[0]
    data["conversion"]["steps"][1]["argv"] = step["argv"]
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    assert not [m for c, m in _codes(demo) if "--plan" in m]


def test_version_rule_against_a_base(demo: Path, tmp_path: Path) -> None:
    base = tmp_path / "base"
    shutil.copytree(demo, base)
    (demo / DEVICE / "EXB.toml").write_text("# changed\n", encoding="utf-8")
    report = audit(demo, base=str(base))
    assert any(i.code == "library.version-rule" and DEVICE in i.message for i in report.issues)
    _edit_json(demo / DEVICE / "item.json", version="1.3.0")
    _edit_json(demo / DEVICE / "PROVENANCE.json", version="1.3.0")
    assert not any(i.code == "library.version-rule" for i in audit(demo, base=str(base)).issues)


def test_version_rule_against_a_git_ref(demo: Path) -> None:
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", "init", "-q", str(demo)], check=True)
    subprocess.run([*git, "-C", str(demo), "add", "-A"], check=True)
    subprocess.run([*git, "-C", str(demo), "commit", "-q", "-m", "base"], check=True)
    (demo / DEVICE / "EXB.toml").write_text("# changed\n", encoding="utf-8")
    assert any(i.code == "library.version-rule" for i in audit(demo, base="HEAD").issues)


def test_item_option_limits_the_audit(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    (demo / DEVICE / "notes.txt").write_text("x\n", encoding="utf-8")
    code, envelope = _cli(monkeypatch, demo, "library", "audit", ".", "--item", BOARD)
    assert code == 0 and [row["path"] for row in envelope["result"]["items"]] == [BOARD]
    code, _ = _cli(monkeypatch, demo, "library", "audit", ".", "--item", "nowhere")
    assert code == 2
