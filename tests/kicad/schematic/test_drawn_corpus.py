# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every declared demo sheet: strict drawn/native census, without retained CAD payload (c0276)."""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import time
import tomllib
from functools import cache
from pathlib import Path, PurePosixPath

import _schcorpus
import _schprojects
import pytest
from _corpus import MANIFEST, manifest_items, require
from _drawn_census_reuse import OwnerMeasurements
from _drawn_context import Contexts, SheetInput
from _drawn_corpus import Input, record
from _drawn_floor import original_refusal
from _resources import required_resources

from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.versions import FileKind, VersionStatus, inspect
from fenolite.core.errors import FenoliteError

pytestmark = [pytest.mark.needs_kicad, pytest.mark.needs_corpus, pytest.mark.slow]
ROWS = tuple(row for row in _schcorpus.rows() if row.origin == "kicad-demos")
DECLARED = {row["id"]: row for row in tomllib.loads(MANIFEST.read_text(encoding="utf-8"))["file"]}
SUFFIXES = {".kicad_sch", ".kicad_pro", ".kicad_sym", ".lib", ".dcm"}
BY_ID = {row.id: row for row in ROWS}


@cache
def contexts(running: int) -> Contexts:
    """All declared project owners at the running tag, with every byte checked before discovery."""
    for path, item in _schprojects._at_tag(_schprojects.MAJOR_TAGS[running]).items():
        native = PurePosixPath(path)
        if (native.suffix in SUFFIXES or native.name == "sym-lib-table") and item.file.is_file():
            if hashlib.sha256(item.file.read_bytes()).hexdigest() != DECLARED[item.id]["sha256"]:
                raise ValueError("context-sha256")
    rows = _schcorpus.at_tag(_schprojects.MAJOR_TAGS[running])
    return Contexts(
        tuple(
            SheetInput(
                row.id,
                row.path,
                DECLARED[row.id]["sha256"],
                row.file.read_bytes() if row.file.is_file() else None,
            )
            for row in rows.values()
        ),
        tuple(row.id for row in _schprojects.roots(running)),
    )


def materialize(row: _schcorpus.SchRow, target: Path, running: int) -> tuple[str, list[Input]]:
    """The existing manifest tree selection, excluding boards/models and copying no unchecked input."""
    prefix = PurePosixPath(row.path).parent
    inputs = []
    for path, item in sorted(_schprojects._at_tag(_schprojects.MAJOR_TAGS[running]).items()):
        native = PurePosixPath(path)
        if prefix not in native.parents or not item.file.is_file():
            continue
        if native.suffix not in SUFFIXES and native.name != "sym-lib-table":
            continue
        relative = native.relative_to(prefix).as_posix()
        assert not PurePosixPath(relative).is_absolute() and ".." not in PurePosixPath(relative).parts
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(item.file.read_bytes())
        inputs.append(Input(item.id, relative, DECLARED[item.id]["sha256"]))
    return PurePosixPath(row.path).name, inputs


@pytest.fixture(scope="module")
def native():
    from _probes import major, runner

    tool = runner()
    return tool, tool.version(), major()


@pytest.mark.parametrize("row", ROWS, ids=lambda row: row.id)
def test_demo_drawn_census(row: _schcorpus.SchRow, tmp_path: Path, native, measurements) -> None:
    tool, version, running = native
    started = time.perf_counter()
    declaration = DECLARED[row.id]
    match = re.search(r"commit ([0-9a-f]{12,40})", declaration.get("notes", ""))
    format_match = re.search(r"format (\d+)", declaration.get("notes", ""))
    observed_sha = hashlib.sha256(row.file.read_bytes()).hexdigest() if row.file.is_file() else None
    base = {
        "schema": "fenolite.drawn-census.v0",
        "id": row.id,
        "source_ref": row.ref,
        "source_commit": match.group(1) if match else "",
        "expected_sha256": declaration["sha256"],
        "manifest_sha256": hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
        "major": running,
        "running_tag": _schprojects.MAJOR_TAGS[running],
        "declared_format": int(format_match.group(1)) if format_match else None,
        "input_sha256": observed_sha,
        "native_version": version,
        "code_commit": os.environ.get("GITHUB_SHA", os.environ.get("FENOLITE_DRAWN_CENSUS_SOURCE", "")),
    }
    if observed_sha is not None and observed_sha != declaration["sha256"]:
        record(tmp_path, {**base, "status": "invalid-cache", "seconds": 0})
        pytest.fail(f"drawn census input SHA-256 changed: {row.id}", pytrace=False)
    if _schprojects.MAJOR_TAGS[running] not in row.tags:
        record(tmp_path, {**base, "status": "native-version-incompatible", "seconds": 0})
        pytest.skip(f"not a schematic row of tag {_schprojects.MAJOR_TAGS[running]}")
    item = next(item for item in manifest_items("sch") if item.id == row.id)
    if not row.file.is_file():
        record(tmp_path, {**base, "status": "missing-cache", "seconds": 0})
        if "kicad" in required_resources():
            pytest.fail(f"drawn census input missing: {row.id}", pytrace=False)
    require(item)
    # This is an explicit negative reader test, never an equality or generic-refusal allowance.
    try:
        info = inspect(parse_bytes(row.file.read_bytes()))
    except FenoliteError:
        info = None
    if info is not None and info.kind == FileKind.SCHEMATIC and info.status == VersionStatus.TOO_OLD:
        negative = original_refusal(row.file.read_bytes())
        record(tmp_path, {**base, **negative, "seconds": round(time.perf_counter() - started, 6)})
        return
    try:
        owners = contexts(running).for_row(row.id)
    except Exception as error:
        status = "refused" if isinstance(error, (FenoliteError, ValueError)) else "internal-error"
        if str(error) == "context-sha256":
            status = "invalid-cache"
        record(
            tmp_path,
            {
                **base,
                "status": status,
                "refusal": {"stage": "context", "type": type(error).__name__},
            },
        )
        pytest.fail(f"drawn census context discovery refused: {row.id}", pytrace=False)
    cases = []
    for index, owner in enumerate(owners):
        context = owner.data(row.id)
        if owner.registered:
            project_path = str(PurePosixPath(owner.root.path).with_suffix(".kicad_pro"))
            project = _schprojects._at_tag(_schprojects.MAJOR_TAGS[running])[project_path]
            actual = hashlib.sha256(project.file.read_bytes()).hexdigest() if project.file.is_file() else None
            context["project_input"] = {
                "id": project.id,
                "expected_sha256": DECLARED[project.id]["sha256"],
                "input_sha256": actual,
            }
            if actual is None:
                cases.append(
                    {
                        "status": "missing-cache",
                        "refusal": {"stage": "context", "code": "owner-project-missing"},
                        "context": context,
                    }
                )
                continue
        if owner.errors or not context["target_instances"]:
            cases.append(
                {
                    "status": "refused",
                    "refusal": {"stage": "context", "code": "owner-context-unresolved"},
                    "context": context,
                }
            )
            continue
        folder = tmp_path / f"source-{index}"
        folder.mkdir()
        try:
            root_file, inputs = materialize(BY_ID[owner.root.id], folder, running)
            result = measurements.measure(
                folder,
                root_file,
                inputs,
                tool,
                owner=owner.root.id,
                manifest_sha256=str(base["manifest_sha256"]),
                ident=row.id,
                major=running,
                native_version=version,
                code_commit=str(base["code_commit"]),
            )
        except Exception as error:
            result = {
                "status": "internal-error",
                "refusal": {"stage": "materialize", "type": type(error).__name__},
            }
        finally:
            # Reports survive failed assertions; copied/derived third-party CAD does not.
            shutil.rmtree(folder)
        cases.append({**result, "context": context})
    statuses = {case["status"] for case in cases}
    status = next(
        (
            s
            for s in ("internal-error", "invalid-cache", "missing-cache", "refused", "differs")
            if s in statuses
        ),
        "equal",
    )
    report = {
        **base,
        "status": status,
        "contexts": cases,
        "total_seconds": round(time.perf_counter() - started, 6),
    }
    record(tmp_path, report)
    assert report["status"] == "equal", (
        row.id,
        report["status"],
        [(case["context"], case.get("refusal"), case.get("partition")) for case in cases],
    )


@pytest.fixture(scope="module")
def measurements() -> OwnerMeasurements:
    return OwnerMeasurements()
