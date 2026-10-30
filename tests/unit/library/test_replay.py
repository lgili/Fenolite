# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library replay`` (capability fenolite-library, "Replay from the pinned upstream"; c0281's
"Replayable conversion steps"; change c0279). The upstream is the authored KiCad project
``tests/data/fidelity/sensor``; the item is converted from it here, its steps recorded as the library
records them (a dry run, then ``--confirm`` alone), and replayed in a fresh folder."""

from __future__ import annotations

import io
import json
import shutil
import subprocess
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

import fenolite
from fenolite.cli import main as cli_main
from fenolite.library.items import ITEM_SCHEMA, canonical_json, folder_files, tree_digest

ROOT = Path(__file__).resolve().parents[3]
SENSOR = ROOT / "tests" / "data" / "fidelity" / "sensor"
COMMIT = "2" * 40
ARGV = [
    "import",
    "upstream/sensor/sensor.kicad_pro",
    "--to",
    "python",
    "--out",
    "out",
    "--licence",
    "CC0-1.0",
    "--timestamp",
    "2026-10-30T00:00:00Z",
]


def _cli(
    monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str
) -> tuple[int, dict[str, Any], dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = cli_main.main([*args, "--json"])
    return (
        code,
        json.loads(out.getvalue() or "{}"),
        json.loads(err.getvalue().splitlines()[-1] if err.getvalue() else "{}"),
    )


@pytest.fixture
def converted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    """``(upstream checkout, item folder)``: the sensor converted once, as a library board item."""
    upstream = tmp_path / "checkout"
    shutil.copytree(SENSOR, upstream / "sensor")
    work = tmp_path / "work"
    shutil.copytree(upstream, work / "upstream")
    for flag in ("--dry-run", "--confirm"):
        code, envelope, error = _cli(monkeypatch, work, *ARGV, flag)
        assert code == 0, (envelope, error)
    out = work / "out"
    imported = json.loads((out / "PROVENANCE.json").read_text(encoding="utf-8"))
    payload = {name: data for name, data in folder_files(out).items() if name != "PROVENANCE.json"}
    item = tmp_path / "item"
    for name, data in payload.items():
        (item / name).parent.mkdir(parents=True, exist_ok=True)
        (item / name).write_bytes(data)
    (item / "item.json").write_bytes(
        canonical_json(
            {
                "schema": ITEM_SCHEMA,
                "kind": "board",
                "id": "demo-src/sensor",
                "version": "1.0.0",
                "title": "Sensor",
                "summary": "",
                "spdx": "CC0-1.0",
                "tags": [],
                "files": sorted(payload),
                "depends": [],
                "executes": True,
            }
        )
    )
    record = {
        "schema": "fenolite.provenance.v0",
        "kind": "board",
        "id": "demo-src/sensor",
        "version": "1.0.0",
        "origin": "converted",
        "spdx": "CC0-1.0",
        "authors": ["Fenolite contributors"],
        "copyright": [],
        "modification_notice": "2026-10-30: converted to the Fenolite DSL; format change only",
        "upstream": {
            "url": (tmp_path / "remote").as_uri(),
            "path": "sensor",
            "commit": COMMIT,
            "archive_sha256": None,
            "retrieved": "2026-10-30",
            "spdx_expression": "CC0-1.0",
            "source_location": "",
        },
        "conversion": {
            "tools": [{"name": "fenolite", "version": fenolite.__version__}],
            "steps": [
                {"tool": "fenolite", "argv": [*ARGV, "--dry-run"]},
                {"tool": "fenolite", "argv": [*ARGV, "--confirm"]},
            ],
            "outputs_tree": tree_digest(payload),
        },
        "import": imported,
        "fidelity": {"accepted": [], "proof": {"levels": {"1": "equal"}}},
    }
    (item / "PROVENANCE.json").write_bytes(canonical_json(record))
    return upstream, item


def _edit(item: Path, **changes: Any) -> None:
    record = json.loads((item / "PROVENANCE.json").read_text(encoding="utf-8"))
    record["conversion"].update(changes)
    (item / "PROVENANCE.json").write_bytes(canonical_json(record))


def test_replay_reproduces_an_authored_conversion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, converted: tuple[Path, Path]
) -> None:
    """Scenario "Replay reproduces an authored conversion" (and c0281's fresh-folder replay)."""
    upstream, item = converted
    before = folder_files(item)
    code, envelope, error = _cli(
        monkeypatch, tmp_path, "library", "replay", str(item), "--upstream", str(upstream)
    )
    assert code == 0, (envelope, error)
    record = json.loads((item / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert envelope["result"]["outputs_tree"] == record["conversion"]["outputs_tree"]
    assert envelope["result"]["equal"] is True and [s["exit"] for s in envelope["result"]["steps"]] == [0, 0]
    assert envelope["evidence"]["hypotheses"] == ["H-G-LIBRARY-REPLAY"]
    assert folder_files(item) == before


def test_replay_fetches_the_pinned_commit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, converted: tuple[Path, Path]
) -> None:
    upstream, item = converted
    remote = tmp_path / "remote"
    shutil.copytree(upstream, remote)
    git = [
        "git",
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.invalid",
        "-c",
        "commit.gpgsign=false",
        "-C",
        str(remote),
    ]
    subprocess.run(["git", "init", "-q", str(remote)], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", "upstream"], check=True)
    subprocess.run([*git, "config", "uploadpack.allowReachableSHA1InWant", "true"], check=True)
    commit = subprocess.run(
        [*git, "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    record = json.loads((item / "PROVENANCE.json").read_text(encoding="utf-8"))
    record["upstream"]["commit"] = commit
    (item / "PROVENANCE.json").write_bytes(canonical_json(record))
    code, envelope, error = _cli(monkeypatch, tmp_path, "library", "replay", str(item))
    assert code == 0, (envelope, error)
    assert envelope["result"]["equal"] is True


def test_replay_reports_a_difference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, converted: tuple[Path, Path]
) -> None:
    upstream, item = converted
    (item / "design.py").write_text(
        (item / "design.py").read_text(encoding="utf-8") + "# edited\n", encoding="utf-8"
    )
    code, envelope, _ = _cli(
        monkeypatch, tmp_path, "library", "replay", str(item), "--upstream", str(upstream)
    )
    assert code == 5
    assert envelope["result"]["differs"] == ["design.py"]
    assert [i["code"] for i in envelope["issues"]] == ["library.replay-differs"]


@pytest.mark.parametrize(
    ("step", "words"),
    [
        ({"tool": "sh", "argv": ["-c", "true"]}, "'sh'"),
        ({"tool": "fenolite", "argv": [*ARGV, "--confirm", "--plan", "0123456789abcdef"]}, "--plan"),
    ],
)
def test_unknown_tool_refused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    converted: tuple[Path, Path],
    step: dict[str, Any],
    words: str,
) -> None:
    """Scenario "Unknown tool refused" (and c0281: a recorded --plan is refused before a step runs)."""
    upstream, item = converted
    record = json.loads((item / "PROVENANCE.json").read_text(encoding="utf-8"))
    _edit(item, steps=[record["conversion"]["steps"][0], step])
    ran: list[object] = []
    monkeypatch.setattr("fenolite.cli.main.invoke", lambda *a, **k: ran.append(a) or (0, None, None))
    code, _, error = _cli(monkeypatch, tmp_path, "library", "replay", str(item), "--upstream", str(upstream))
    assert code == 3 and error["code"] == "FEN-3004"
    assert "conversion.steps[2]" in error["message"] and words in error["message"] and ran == []


def test_keep_plans_the_work_folder(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, converted: tuple[Path, Path]
) -> None:
    upstream, item = converted
    code, envelope, _ = _cli(
        monkeypatch,
        tmp_path,
        "library",
        "replay",
        str(item),
        "--upstream",
        str(upstream),
        "--keep",
        "kept",
        "--dry-run",
    )
    assert code == 0 and not (tmp_path / "kept").exists()
    paths = [row["path"] for row in envelope["result"]["plan"]]
    assert "kept/out/design.py" in paths and "kept/upstream/sensor/sensor.kicad_pro" in paths
