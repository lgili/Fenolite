# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The kit's files and its manifest (capability altium-verification, "Verification kit contents")."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest

from fenolite.cli._kit import SAMPLES_DIR, kit_sources
from fenolite.core.errors import FormatError
from fenolite.core.io import sha256_bytes
from fenolite.verify.kit import manifest
from fenolite.verify.kit.manifest import KitSources, SampleFiles, build_kit, kit_digest, kit_files, load_kit
from fenolite.verify.kit.steps import SAMPLES, STEPS, steps_markdown

ROOT = Path(__file__).resolve().parents[4]
ABSOLUTE = re.compile(rb"(?:[A-Za-z]:\\(?:Users|Documents and Settings)\\|/Users/|/home/|/private/|/tmp/)")
WHEN = datetime(2026, 10, 6, tzinfo=UTC)


def _files(folder: Path) -> dict[str, bytes]:
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


def test_deterministic(tmp_path: Path) -> None:
    """Scenario "Deterministic kit": two builds with one seed and timestamp hold equal files."""
    one = build_kit(tmp_path / "a", seed=1, timestamp=WHEN, sources=kit_sources())
    two = build_kit(tmp_path / "b", seed=1, timestamp=WHEN, sources=kit_sources())
    assert _files(tmp_path / "a") == _files(tmp_path / "b")
    assert one.digest == two.digest == kit_digest((tmp_path / "a" / "kit.json").read_bytes())
    assert list(one.samples) == list(SAMPLES) and len(one.samples) == 5
    data = json.loads((tmp_path / "a" / "kit.json").read_text(encoding="utf-8"))
    assert data["schema"] == manifest.KIT_SCHEMA and data["seed"] == 1
    assert data["timestamp"] == "2026-10-06T00:00:00Z"


def test_the_inputs_are_part_of_the_digest(built_kit: Path) -> None:
    files = kit_files(kit_sources(), seed=2)
    assert kit_digest(files["kit.json"]) != load_kit(built_kit).digest
    assert {k: v for k, v in files.items() if k != "kit.json"} == {
        k: v for k, v in _files(built_kit).items() if k != "kit.json"
    }


def test_contents(built_kit: Path) -> None:
    """Scenario "Nothing foreign": every file is listed with its digest, and none holds an absolute
    path."""
    kit = load_kit(built_kit)
    held = _files(built_kit)
    listed = {**kit.files, "results/form.json": kit.data["form"]["sha256"]}
    assert sorted(held) == sorted([*listed, "kit.json"])
    for path, digest in listed.items():
        assert sha256_bytes(held[path]) == digest, path
    here = str(ROOT).encode()
    for path, data in held.items():
        assert ABSOLUTE.search(data) is None and here not in data, path
        assert here.decode().encode("utf-16-le") not in data, path
    assert held["STEPS.md"].decode("utf-8") == steps_markdown(kit.steps) == steps_markdown(STEPS)
    assert b"\r" not in held["STEPS.md"] and b"\r" not in held["kit.json"]
    assert held["kit.json"].endswith(b"}\n")


def test_every_sample_has_its_project_and_its_script(built_kit: Path) -> None:
    kit = load_kit(built_kit)
    for sample in kit.data["samples"]:
        name = sample["name"]
        script = ROOT / sample["script"]
        assert script == SAMPLES_DIR / name / "design.py" and script.is_file()
        assert sample["script_sha256"] == sha256_bytes(script.read_bytes())
        assert (built_kit / name / f"{name}.PrjPcb").is_file()
        lines = script.read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0" and lines[1].startswith(
            "# Authored for Fenolite"
        )
    assert (built_kit / "flat" / "ascii" / "flat.SchDoc").read_bytes().startswith(b"|HEADER=")
    assert sorted(p.name for p in (built_kit / "tree").iterdir()) == [
        "tree.PrjPcb",
        "tree.SchDoc",
        "tree.SchLib",
        "tree_io.SchDoc",
        "tree_io.leds.SchDoc",
        "tree_power.SchDoc",
    ]
    assert (built_kit / "results" / "routed" / "expected.txt").is_file()


def test_a_changed_sample_changes_only_its_digest() -> None:
    sources = kit_sources()
    flat = sources.samples[0]
    edited = SampleFiles(flat.name, flat.script_sha256, {**flat.files, "flat.SchDoc": b"other"})
    before = manifest.read_kit(kit_files(sources)["kit.json"])
    after = manifest.read_kit(
        kit_files(KitSources((edited, *sources.samples[1:]), sources.extras, sources.fenolite_version))[
            "kit.json"
        ]
    )
    assert before.samples["flat"] != after.samples["flat"]
    assert {k: v for k, v in before.samples.items() if k != "flat"} == {
        k: v for k, v in after.samples.items() if k != "flat"
    }


def test_refused_sources() -> None:
    sources = kit_sources()
    with pytest.raises(ValueError, match="samples"):
        kit_files(KitSources(sources.samples[:4], sources.extras))
    bad = SampleFiles("flat", "0" * 64, {"../x": b""})
    with pytest.raises(ValueError, match="inside the kit"):
        kit_files(KitSources((bad, *sources.samples[1:]), sources.extras, sources.fenolite_version))
    with pytest.raises(ValueError, match="does not hold"):
        kit_files(KitSources(sources.samples, {}))


def test_a_folder_that_is_no_kit(tmp_path: Path) -> None:
    with pytest.raises(FormatError, match="not a kit"):
        load_kit(tmp_path)
    (tmp_path / "kit.json").write_text("{}", encoding="utf-8")
    with pytest.raises(FormatError, match="schema"):
        load_kit(tmp_path)


def test_no_sheet_template_and_no_built_kit_is_tracked() -> None:
    """No ``.SchDot`` file is tracked anywhere, and ``examples/kit`` holds scripts only."""
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    listed = subprocess.run(
        ["git", "ls-files"], cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout.splitlines()
    assert [name for name in listed if name.casefold().endswith(".schdot")] == []
    kit_files_tracked = sorted(name for name in listed if name.startswith("examples/kit/"))
    assert kit_files_tracked == [
        "examples/kit/README.md",
        *(f"examples/kit/{n}/design.py" for n in sorted(SAMPLES)),
    ]
