# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``kicad-cli`` candidates for ``doctor`` (capability cli-contract, "Doctor command"; change c0013)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from _fakecli import fake_kicad_cli

from fenolite.backends.kicad import cli as kicad_cli
from fenolite.backends.kicad.cli import CliCandidate, kicad_cli_candidates


@pytest.fixture(autouse=True)
def _isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.delenv("FENOLITE_KICAD_CLI", raising=False)
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", tmp_path / "missing" / "kicad-cli")


def test_order_and_sources(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    explicit = fake_kicad_cli(tmp_path / "a")
    env = fake_kicad_cli(tmp_path / "b")
    on_path = fake_kicad_cli(tmp_path / "c")
    app = fake_kicad_cli(tmp_path / "d")
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(env))
    monkeypatch.setenv("PATH", f"{tmp_path / 'empty'}{os.pathsep}{on_path.parent}")
    monkeypatch.setattr(kicad_cli, "MACOS_KICAD_CLI", app)
    assert kicad_cli_candidates([explicit]) == (
        CliCandidate(explicit, "explicit"),
        CliCandidate(env, "env"),
        CliCandidate(on_path, "path"),
        CliCandidate(app, "macos-app"),
    )


def test_one_entry_per_binary(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    fake = fake_kicad_cli(tmp_path / "real")
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "kicad-cli").symlink_to(fake)
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(fake))
    monkeypatch.setenv("PATH", str(linked))
    assert kicad_cli_candidates() == (CliCandidate(fake, "env"),)


def test_missing_files_are_left_out(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("FENOLITE_KICAD_CLI", str(tmp_path / "nowhere"))
    assert kicad_cli_candidates([tmp_path / "missing-too"]) == ()
