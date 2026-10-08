# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parallel ``kicad-cli`` runs share no state (change c0153, capability kicad-oracle, "Private state per
kicad-cli run"; ``docs/formats/kicad/cli.md``, "Per-run state").

Eight runs of the package runner at once, then eight raw runs of the tests' helper at once, all succeed
and none reports a lock file. A ninth run, with ``TMPDIR`` given, measures where the tool keeps its
instance lock folder."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import _erccases as cases
import pytest
from _kicad import run_raw
from _probes import major, runner

from fenolite.backends.kicad.cli import ErcRun, KicadCli

pytestmark = pytest.mark.needs_kicad

RUNS = 8
LOCK_WORDS = ("lock file", "Invalid lock")


def _clean(text: str) -> bool:
    return not any(word in text for word in LOCK_WORDS)


def test_parallel_versions() -> None:
    """Eight ``kicad-cli version`` runs at once, each on its own runner: the same version, no lock."""
    path = runner().path

    def one(_: int) -> tuple[str, str]:
        run = KicadCli(path, timeout=600).run(["version"], files={})
        assert run.ok, run.stdout + run.stderr
        return run.stdout.strip(), run.stderr

    with ThreadPoolExecutor(max_workers=RUNS) as pool:
        found = list(pool.map(one, range(RUNS)))
    assert len({out for out, _ in found}) == 1
    assert all(_clean(out + err) for out, err in found), found


def test_parallel_unloadable_erc() -> None:
    """Eight ``sch erc`` runs at once on a schematic KiCad refuses: each says it cannot load the file,
    writes no report and reports no lock (the failure of the kicad-9 job of 2026-10-08)."""
    files = cases.unloadable(cases.blink_files(major()))

    def one(_: int) -> ErcRun:
        return cases.run_erc(files)

    with ThreadPoolExecutor(max_workers=RUNS) as pool:
        runs = list(pool.map(one, range(RUNS)))
    for erc in runs:
        text = erc.run.stdout + erc.run.stderr
        assert erc.report is None and erc.run.returncode == 3, text
        assert "Failed to load schematic" in text and _clean(text), text


def test_parallel_raw_helper_runs() -> None:
    """Eight raw ``kicad-cli version`` runs of the tests' helper at once (``_kicad.run_raw``)."""
    with ThreadPoolExecutor(max_workers=RUNS) as pool:
        found = list(pool.map(lambda _: run_raw("version"), range(RUNS)))
    assert all(r.returncode == 0 and _clean(r.stdout + r.stderr) for r in found), found


def test_instance_folder_follows_tmpdir(tmp_path: Path) -> None:
    """``H-K-CLI-STATE``: with ``TMPDIR`` (and ``TMP``, ``TEMP``) naming a folder, the tool's instance
    folder ``org.kicad.kicad/instances`` is created there, not in the shared ``/tmp``."""
    folder = tmp_path / "t"
    folder.mkdir(mode=0o700)
    files = cases.write(cases.unloadable(cases.blink_files(major())), tmp_path / "project")
    env = {"TMPDIR": str(folder), "TMP": str(folder), "TEMP": str(folder)}
    erc = runner().erc(files / cases.SHEET, files=cases.tops(files, without=cases.SHEET), env=env)
    assert erc.run.returncode == 3, erc.run.stdout + erc.run.stderr
    assert (folder / "org.kicad.kicad" / "instances").is_dir(), sorted(p.name for p in folder.rglob("*"))
