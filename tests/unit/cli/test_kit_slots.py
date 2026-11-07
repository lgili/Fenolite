# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored catalogue integrity and the existing S7 readback criterion, without native tools."""

from __future__ import annotations

import dataclasses
import importlib
import shutil
from pathlib import Path

import pytest

from fenolite.backends.altium.pcbdoc import PcbDocSpec, write_pcbdoc
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.core.ids import derived_id
from fenolite.model.board import Hole

ROOT = Path(__file__).resolve().parents[3]
MM = 1_000_000


def _module():
    return importlib.import_module("fenolite.cli._kit_slots")


def _spec() -> PcbDocSpec:
    holes = tuple(
        Hole(
            id=derived_id("hol", "formal-part-s", str(i)),
            position=Point((10 + i * 10) * MM, 25 * MM),
            drill=MM,
            length=3 * MM if i < 3 else None,
            rotation=i * 30_000_000 if i < 3 else 0,
        )
        for i in range(4)
    )
    cutouts = tuple(
        (
            Point(x * MM, 5 * MM),
            Point((x + 3) * MM, 5 * MM),
            Point((x + 3) * MM, 8 * MM),
            Point(x * MM, 8 * MM),
        )
        for x in (5, 20, 35)
    )
    return PcbDocSpec(
        outline=(Point(0, 0), Point(60 * MM, 0), Point(60 * MM, 40 * MM), Point(0, 40 * MM)),
        holes=holes,
        cutouts=cutouts,
    )


def _files(tmp_path: Path, changed: PcbDocSpec) -> tuple[Path, Path]:
    own, saved = tmp_path / "own.PcbDoc", tmp_path / "saved.PcbDoc"
    own.write_bytes(write_pcbdoc(_spec(), filename="s.PcbDoc"))
    saved.write_bytes(write_pcbdoc(changed, filename="s.PcbDoc"))
    return own, saved


def test_catalogue_contains_only_pinned_authored_inputs() -> None:
    sample = _module().part_s_sample(ROOT / "examples/kit/slots")
    assert sample.name == "slots"
    assert set(sample.files) == {
        *(
            f"{folder}/slots.{suffix}"
            for folder in ("regions", "clearance", "gate-off")
            for suffix in ("PrjPcb", "SchDoc", "PcbDoc")
        ),
        "gate-off/build-report.json",
        "clearance/slots.PcbLib",
        "clearance/slots.SchLib",
        "criteria.md",
        "PROVENANCE.md",
        "recipe.py",
    }


@pytest.mark.parametrize("change", ["missing", "tamper", "symlink"])
def test_changed_catalogue_asset_refuses(tmp_path: Path, change: str) -> None:
    folder = tmp_path / "slots"
    shutil.copytree(ROOT / "examples/kit/slots", folder)
    p = folder / "regions/slots.PcbDoc"
    if change == "missing":
        p.unlink()
    elif change == "tamper":
        p.write_bytes(p.read_bytes() + b"changed")
    else:
        data = p.read_bytes()
        p.unlink()
        target = tmp_path / "outside.PcbDoc"
        target.write_bytes(data)
        p.symlink_to(target)
    with pytest.raises(FormatError):
        _module().part_s_sample(folder)


def test_s7_accepts_authored_identity_and_submicrometre_move(tmp_path: Path) -> None:
    spec = _spec()
    a, b = _files(tmp_path, spec)
    assert _module().slots_readback_problems(a, b) == []
    h = dataclasses.replace(
        spec.holes[0], position=Point(spec.holes[0].position.x + 500, spec.holes[0].position.y)
    )
    a, b = _files(tmp_path, dataclasses.replace(spec, holes=(h, *spec.holes[1:])))
    assert _module().slots_readback_problems(a, b) == []


@pytest.mark.parametrize(
    "change",
    [
        "hole-count",
        "cutout-count",
        "extra-hole",
        "extra-cutout",
        "position",
        "drill",
        "length",
        "rotation",
        "contour",
    ],
)
def test_s7_rejects_missing_or_changed_geometry(tmp_path: Path, change: str) -> None:
    spec = _spec()
    h = spec.holes[0]
    if change == "hole-count":
        spec = dataclasses.replace(spec, holes=spec.holes[:-1])
    elif change == "cutout-count":
        spec = dataclasses.replace(spec, cutouts=spec.cutouts[:-1])
    elif change == "extra-hole":
        extra = dataclasses.replace(spec.holes[0], id=derived_id("hol", "formal-part-s", "extra"))
        spec = dataclasses.replace(spec, holes=(*spec.holes, extra))
    elif change == "extra-cutout":
        spec = dataclasses.replace(spec, cutouts=(*spec.cutouts, spec.cutouts[0]))
    elif change == "contour":
        spec = dataclasses.replace(
            spec, cutouts=(tuple(Point(p.x + 2000, p.y) for p in spec.cutouts[0]), *spec.cutouts[1:])
        )
    else:
        if change == "position":
            h = dataclasses.replace(h, position=Point(h.position.x + 2000, h.position.y))
        elif change == "drill":
            h = dataclasses.replace(h, drill=h.drill + 2000)
        elif change == "length":
            h = dataclasses.replace(h, length=(h.length or 0) + 2000)
        else:
            h = dataclasses.replace(h, rotation=h.rotation + 100_000)
        spec = dataclasses.replace(spec, holes=(h, *spec.holes[1:]))
    a, b = _files(tmp_path, spec)
    assert _module().slots_readback_problems(a, b)


@pytest.mark.parametrize("relative", ["../outside", "/outside", "C:/outside", "folder\\outside"])
def test_catalogue_paths_cannot_leave_the_root(tmp_path: Path, relative: str) -> None:
    with pytest.raises(FormatError):
        _module()._read(tmp_path, relative)


def test_recipe_is_bound_to_the_complete_sample(tmp_path: Path) -> None:
    folder = tmp_path / "slots"
    shutil.copytree(ROOT / "examples/kit/slots", folder)
    before = _module().part_s_sample(folder)
    recipe = folder / "design.py"
    recipe.write_bytes(recipe.read_bytes() + b"\n# Authored source revision.\n")
    after = _module().part_s_sample(folder)
    assert before.script_sha256 != after.script_sha256
    assert before.files["recipe.py"] != after.files["recipe.py"]
    assert {k: v for k, v in before.files.items() if k != "recipe.py"} == {
        k: v for k, v in after.files.items() if k != "recipe.py"
    }


def test_samples_root_is_portable_without_the_checkout_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from fenolite.cli import _kit

    folder = tmp_path / "external-samples"
    shutil.copytree(_kit.SAMPLES_DIR, folder)
    monkeypatch.setattr(_kit, "SAMPLES_DIR", tmp_path / "absent-checkout")
    sources = _kit.kit_sources(folder)
    slots = next(s for s in sources.samples if s.name == "slots")
    assert slots.files == _module().part_s_sample(folder / "slots").files


def test_s7_refuses_an_unreadable_saved_document(tmp_path: Path) -> None:
    own, saved = _files(tmp_path, _spec())
    saved.write_bytes(b"not a compound PCB document")
    assert _module().slots_readback_problems(own, saved)


def test_recipe_executes_original_regions_design_without_writes_or_gate_changes() -> None:
    import ast

    from fenolite.backends.altium import pcbdoc
    from fenolite.cli._script import run_design_script
    from fenolite.dsl import to_model
    from fenolite.model import canonical

    folder = ROOT / "examples/kit/slots"
    before = {p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()}
    gate = pcbdoc.CUTOUT_REGIONS
    script = folder / "design.py"
    # The example must stand alone through Fenolite helpers, with no test imports or runner.
    imports = [
        n for n in ast.walk(ast.parse(script.read_text(encoding="utf-8"))) if isinstance(n, ast.ImportFrom)
    ]
    assert imports and all(n.module == "fenolite.dsl" for n in imports)
    assert not any(isinstance(n, ast.Import) for n in ast.walk(ast.parse(script.read_text(encoding="utf-8"))))
    actual = to_model(run_design_script(script).design)
    original = to_model(run_design_script(ROOT / "tests/data/slots/altium.py").design)
    assert canonical.dump_texts(actual) == canonical.dump_texts(original)
    assert pcbdoc.CUTOUT_REGIONS is gate
    assert before == {
        p.relative_to(folder).as_posix(): p.read_bytes() for p in folder.rglob("*") if p.is_file()
    }
    assert _module().part_s_sample(folder).files["recipe.py"] == script.read_bytes()
