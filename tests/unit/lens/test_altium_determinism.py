# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reproducible Altium builds (capability altium-build, "Reproducible Altium builds"; change c0032), in
the binary form by default and in the ASCII form (scenario "Reproducible binary builds"; change c0033)."""

from __future__ import annotations

import os
import runpy
import subprocess
import sys
from pathlib import Path

import pytest
from _altium import EXAMPLE, HIER, SAMPLE, records, variant_script

import fenolite.cli.main as cli_main
from fenolite.backends.altium.cfb import SIGNATURE
from fenolite.dsl import Design, to_model
from fenolite.lens.altium import build_altium

LAYERS = ("board", "build", "circuit", "findings", "manufacturing", "meta", "rules")
PLANNED = {
    "altium_sample.PrjPcb",
    "altium_sample.SchDoc",
    "FenoliteSample.SchLib",
    *(f".fenolite/{n}.json" for n in LAYERS),
}


def files_under(folder: Path) -> dict[str, bytes]:
    """Every file under ``folder`` by relative path, with its bytes."""
    return {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in sorted(folder.rglob("*")) if p.is_file()
    }


@pytest.mark.parametrize(
    ("flags", "head"), [((), SIGNATURE), (("--altium-format", "ascii"), b"|HEADER=")], ids=["binary", "ascii"]
)
def test_twice_in_process_and_twice_by_subprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flags: tuple[str, ...], head: bytes
) -> None:
    before = files_under(SAMPLE.parent)
    outs = [tmp_path / "in1", tmp_path / "in2"]
    for out in outs:
        args = ["build", str(SAMPLE), "--out", str(out), "--target", "altium", *flags, "--confirm", "--json"]
        assert cli_main.main(args) == 0, capsys.readouterr().err
    capsys.readouterr()
    for seed, stamp in ((1, "2026-01-01T00:00:00Z"), (2, "2027-06-01T00:00:00Z")):
        out = tmp_path / f"sub{seed}"
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        argv = [sys.executable, "-m", "fenolite", "build", str(SAMPLE), "--out", str(out)]
        argv += [
            "--target",
            "altium",
            *flags,
            "--confirm",
            "--json",
            "--seed",
            str(seed),
            "--timestamp",
            stamp,
        ]
        proc = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(out)
    builds = [files_under(out) for out in outs]
    assert set(builds[0]) == PLANNED
    assert builds[0]["altium_sample.SchDoc"].startswith(head)
    assert all(build == builds[0] for build in builds[1:])
    assert files_under(SAMPLE.parent) == before, "the build changed the script folder"
    assert not list(SAMPLE.parent.rglob("__pycache__"))


def _unique_ids(design: Design) -> dict[str, str]:
    files = build_altium(to_model(design), name=design.name, form="ascii").files
    found = records(files[f"{design.name}.SchDoc"])
    owners = {int(r["OWNERINDEX"]): r["TEXT"] for r in found if r["RECORD"] == "34"}
    return {owners[i]: r["UNIQUEID"] for i, r in enumerate(found) if r["RECORD"] == "1"}


def test_inserting_a_part_keeps_the_other_unique_ids(tmp_path: Path) -> None:
    extra = (
        '\nr9 = Part("R9", f"{SCHLIB}:RES", footprint=f"{PCBLIB}:R0603", value="1k")\n'
        "design.add(r9)\n"
        "connect(en, r9[1])\n"
        "connect(gnd, r9[2])\n"
    )
    script = variant_script(tmp_path / "V", append=extra)
    base = _unique_ids(runpy.run_path(str(SAMPLE))["design"])
    more = _unique_ids(runpy.run_path(str(script))["design"])
    assert set(more) == set(base) | {"R9"}
    assert {ref: more[ref] for ref in base} == base


def test_a_changed_value_keeps_every_unique_id() -> None:
    design = runpy.run_path(str(SAMPLE))["design"]
    base = _unique_ids(design)
    design.parts["R2"].value = "4k7"
    assert _unique_ids(design) == base


EXAMPLE_PLANNED = {
    "altium_kicad.PrjPcb",
    "altium_kicad.SchDoc",
    "altium_kicad.SchLib",
    *(f".fenolite/{n}.json" for n in LAYERS),
}


def test_example_twice_in_process_and_twice_by_subprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The KiCad example (change c0034) resolves from its own library table, with an empty KiCad
    configuration folder, into the same bytes in every build."""
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)
    before = files_under(EXAMPLE.parent)
    outs = [tmp_path / "in1", tmp_path / "in2"]
    for out in outs:
        args = ["build", str(EXAMPLE), "--out", str(out), "--target", "altium", "--confirm", "--json"]
        assert cli_main.main(args) == 0, capsys.readouterr().err
    capsys.readouterr()
    for seed, stamp in ((3, "2026-01-01T00:00:00Z"), (4, "2027-06-01T00:00:00Z")):
        out = tmp_path / f"sub{seed}"
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        argv = [
            sys.executable,
            "-m",
            "fenolite",
            "build",
            str(EXAMPLE),
            "--out",
            str(out),
            "--target",
            "altium",
        ]
        argv += ["--confirm", "--json", "--seed", str(seed), "--timestamp", stamp]
        proc = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(out)
    builds = [files_under(out) for out in outs]
    assert set(builds[0]) == EXAMPLE_PLANNED
    assert all(build == builds[0] for build in builds[1:])
    assert files_under(EXAMPLE.parent) == before, "the build changed the script folder"


BLINK = Path(__file__).resolve().parents[3] / "examples" / "blink_2layer" / "design.py"
BLINK_PLANNED = {
    "blink.PrjPcb",
    "blink.SchDoc",
    "blink.SchLib",
    "blink.PcbLib",
    "blink.PcbDoc",
    *(f".fenolite/{n}.json" for n in LAYERS),
}


def test_blink_twice_in_process_and_twice_by_subprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The KiCad-footprint sample (change c0035) gives the same five project files in every build."""
    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)
    outs = [tmp_path / "in1", tmp_path / "in2"]
    for out in outs:
        args = ["build", str(BLINK), "--out", str(out), "--target", "altium", "--confirm", "--json"]
        assert cli_main.main(args) == 0, capsys.readouterr().err
    capsys.readouterr()
    for seed, stamp in ((5, "2026-01-01T00:00:00Z"), (6, "2027-06-01T00:00:00Z")):
        out = tmp_path / f"sub{seed}"
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        argv = [
            sys.executable,
            "-m",
            "fenolite",
            "build",
            str(BLINK),
            "--out",
            str(out),
            "--target",
            "altium",
        ]
        argv += ["--confirm", "--json", "--seed", str(seed), "--timestamp", stamp]
        proc = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(out)
    builds = [files_under(out) for out in outs]
    assert set(builds[0]) == BLINK_PLANNED
    assert all(build == builds[0] for build in builds[1:])


# --- module sheets (change c0037, "Altium sheets option", "Reproducible module sheets") --------------

HIER_PLANNED = {
    "altium_hier.PrjPcb",
    "altium_hier.SchDoc",
    "altium_hier_flash.SchDoc",
    "altium_hier_mcu.SchDoc",
    "altium_hier.Harness",
    "altium_hier_flash.Harness",
    "altium_hier_mcu.Harness",
    "FenoliteHier.SchLib",
    *(f".fenolite/{n}.json" for n in LAYERS),
}


@pytest.mark.parametrize(
    ("flags", "head"), [((), SIGNATURE), (("--altium-format", "ascii"), b"|HEADER=")], ids=["binary", "ascii"]
)
def test_hierarchy_twice_in_process_and_twice_by_subprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], flags: tuple[str, ...], head: bytes
) -> None:
    before = files_under(HIER.parent)
    common = ["--target", "altium", "--altium-sheets", "modules", *flags, "--confirm", "--json"]
    outs = [tmp_path / "in1", tmp_path / "in2"]
    for out in outs:
        assert cli_main.main(["build", str(HIER), "--out", str(out), *common]) == 0, capsys.readouterr().err
    capsys.readouterr()
    for seed, stamp in ((1, "2026-01-01T00:00:00Z"), (2, "2027-06-01T00:00:00Z")):
        out = tmp_path / f"sub{seed}"
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        argv = [sys.executable, "-m", "fenolite", "build", str(HIER), "--out", str(out), *common]
        argv += ["--seed", str(seed), "--timestamp", stamp]
        proc = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(out)
    builds = [files_under(out) for out in outs]
    harnesses = {name for name in HIER_PLANNED if name.endswith(".Harness")}
    assert set(builds[0]) == (HIER_PLANNED if not flags else HIER_PLANNED - harnesses)
    for name in ("altium_hier.SchDoc", "altium_hier_flash.SchDoc", "altium_hier_mcu.SchDoc"):
        assert builds[0][name].startswith(head)
    assert all(build == builds[0] for build in builds[1:])
    assert files_under(HIER.parent) == before, "the build changed the script folder"
    assert not list(HIER.parent.rglob("__pycache__"))


def test_copper_from_twice_in_process_and_twice_by_subprocess(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ``--copper-from`` build (change c0038) gives the same files under two ``PYTHONHASHSEED`` values,
    seeds and timestamps."""
    from _altium import blink_tree
    from _altium_copper import routed_board_text, routed_script

    config = tmp_path / "kicad-config"
    config.mkdir()
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(config))
    for name in ("KICAD10_SYMBOL_DIR", "KICAD9_SYMBOL_DIR", "KICAD10_FOOTPRINT_DIR", "KICAD9_FOOTPRINT_DIR"):
        monkeypatch.delenv(name, raising=False)
    project = blink_tree(tmp_path / "tree")
    script, board = project / "design.py", project / "routed.kicad_pcb"
    script.write_text(routed_script(), encoding="utf-8")
    board.write_text(routed_board_text(), encoding="utf-8")
    common = ["--target", "altium", "--copper-from", str(board), "--confirm", "--json"]
    outs = [tmp_path / "in1", tmp_path / "in2"]
    for out in outs:
        assert cli_main.main(["build", str(script), "--out", str(out), *common]) == 0, capsys.readouterr().err
    capsys.readouterr()
    for seed, stamp in ((7, "2026-01-01T00:00:00Z"), (8, "2027-06-01T00:00:00Z")):
        out = tmp_path / f"sub{seed}"
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        argv = [sys.executable, "-m", "fenolite", "build", str(script), "--out", str(out), *common]
        argv += ["--seed", str(seed), "--timestamp", stamp]
        proc = subprocess.run(argv, cwd=tmp_path, env=env, capture_output=True, text=True, check=False)
        assert proc.returncode == 0, proc.stderr
        outs.append(out)
    builds = [files_under(out) for out in outs]
    assert "routed.PcbDoc" in builds[0] and all(build == builds[0] for build in builds[1:])
