# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden assertions are exact, deterministic and never rewrite references."""

import shlex
from pathlib import Path

import pytest

from fenolite.api import run
from fenolite.testing import TestingError, assert_render
from fenolite.testing.svgdiff import compare


def test_same_and_moved(script: Path, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    text = script.read_text().replace('connect(Net("GND"),', 'gnd = Net("GND")\nconnect(gnd,')
    text = text.replace("r1.place(mm(5), mm(5))", "r1.place(mm(5), mm(5), rot=90)")
    text = text.replace("r2.place(mm(15), mm(5))", "r2.place(mm(15), mm(5), rot=90)")
    text += '\ndesign.track("ground", r1.pad(1), r2.pad(1), width=mm("0.2"))\n'
    script.write_text(text)
    folder = tmp_path / "golden"
    reply = run(
        "render",
        str(script),
        "--net",
        "GND",
        "-o",
        str(folder),
        "--confirm",
        seed=0,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert reply.exit_code == 0, reply.error
    golden = folder / "net-GND.svg"
    before = golden.read_bytes()
    assert_render(script, golden, net="GND")
    assert_render(script, golden, net="GND")
    script.write_text(text.replace("r2.pad(1), width=", '(mm(14), mm("4.2")), net=gnd, width='))
    with pytest.raises(TestingError, match="1 changed") as error:
        assert_render(script, golden, net="GND")
    assert "fenolite render" in str(error.value) and "--confirm --plan" in str(error.value)
    assert golden.read_bytes() == before


def test_missing_does_not_write(script: Path, tmp_path: Path):
    golden = tmp_path / "missing/net-GND.svg"
    with pytest.raises(TestingError, match="is missing"):
        assert_render(script, golden, net="GND")
    assert not golden.parent.exists()


def test_moved_track_is_one_changed_element():
    old = b'<svg><path class="track net-hi" data-item="track-a" data-layer="F.Cu" d="M1 1 L2 1"/></svg>'
    new = old.replace(b"L2 1", b"L3 1")
    diff = compare(old, new)
    assert (diff.added, diff.removed, diff.changed) == (0, 0, 1)
    assert "track-a" in diff.lines[0]


@pytest.mark.parametrize("negative", ["region", "net"])
def test_regeneration_command_accepts_negative_values(script: Path, tmp_path: Path, monkeypatch, negative):
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    golden = tmp_path / "golden/region.svg"
    if negative == "net":
        script.write_text(script.read_text().replace('Net("GND")', 'Net("-GND")'))
        options = {"net": "-GND"}
    else:
        options = {"region": (-1_000_000, -1_000_000, 31_000_000, 21_000_000)}
    with pytest.raises(TestingError) as error:
        assert_render(script, golden, **options)
    command = next(
        line.strip()
        for line in str(error.value).splitlines()
        if line.strip().startswith("fenolite render") and line.endswith("--dry-run")
    )
    args = shlex.split(command)
    reply = run(args[1], *args[2:])
    assert reply.exit_code == 0, reply.error
    assert not golden.parent.exists()
