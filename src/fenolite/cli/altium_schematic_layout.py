# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Filesystem boundary of native schematic layout capture and replay."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from fenolite.backends.altium.adapter import NetOptions
from fenolite.backends.altium.read.project import read_project
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.output import InputRef
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.lens.altium_schematic import BASELINE_DIR, FILE_NAME, LayoutConflict, capture, digest, replay
from fenolite.lens.build import RECORD_FILE, read_record


def prepare_files(files: Mapping[str, bytes], snapshot: str | None) -> dict[str, bytes]:
    """Keep fresh baselines separately and replace only reviewed native sheets."""
    result = dict(files)
    generated = {name: data for name, data in files.items() if name.lower().endswith(".schdoc")}
    if snapshot is not None:
        result.update(replay(generated, snapshot))
    result.update({f"{BASELINE_DIR}/{name}": data for name, data in generated.items()})
    record: dict[str, Any] = json.loads(result[RECORD_FILE])
    for name in (*generated, *(f"{BASELINE_DIR}/{name}" for name in generated)):
        record["files"][name] = digest(result[name])
    result[RECORD_FILE] = (json.dumps(record, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode()
    return result


def sync_native(
    *, name: str, script: Path, out: Path, ctx: Context, check: bool, script_output: str
) -> Result:
    """Plan a complete snapshot from verified generated baselines and their edited outputs."""
    snapshot = script.resolve().parent / FILE_NAME
    record = read_record(out)
    inputs = [script, out / RECORD_FILE, snapshot]
    result: dict[str, Any] = {
        "design": name,
        "out": str(out),
        "target": "altium",
        "files": [],
        "sheets": [],
        "script_output": script_output,
    }
    issues: tuple[Issue, ...] = ()
    writes: tuple[PlannedWrite, ...] = ()
    try:
        if record is None:
            raise LayoutConflict(
                "sync.altium-unverified", "no generated build baseline is available", RECORD_FILE
            )
        generated: dict[str, bytes] = {}
        edited: dict[str, bytes] = {}
        prefix = BASELINE_DIR + "/"
        for relative, checksum in sorted(record.items()):
            if not relative.startswith(prefix):
                continue
            filename = relative.removeprefix(prefix)
            if (
                "/" in filename
                or "\\" in filename
                or ":" in filename
                or not filename.lower().endswith(".schdoc")
            ):
                raise FormatError("invalid baseline path", file=RECORD_FILE)
            baseline, native = out / relative, out / filename
            inputs.extend((baseline, native))
            if not baseline.is_file() or not native.is_file():
                raise LayoutConflict(
                    "sync.altium-unverified", "a generated or edited sheet is missing", filename
                )
            data = baseline.read_bytes()
            if digest(data) != checksum:
                raise LayoutConflict(
                    "sync.altium-unverified", "generated baseline SHA-256 mismatch", filename
                )
            generated[filename] = data
            edited[filename] = native.read_bytes()
        text = capture(generated, edited)
        project_path = out / f"{name}.PrjPcb"
        inputs.append(project_path)
        if not project_path.is_file():
            raise LayoutConflict("sync.altium-unverified", "the project file is missing", project_path.name)
        project = read_project(project_path.read_bytes(), file=project_path.name)
        listed = {d.posix for d in project.documents if d.kind == "schematic"}
        if listed != set(generated) or NetOptions.from_project(project) != NetOptions():
            raise LayoutConflict(
                "sync.altium-unverified",
                "the project sheet list or netlist options changed",
                project_path.name,
            )
        current = snapshot.read_text(encoding="utf-8") if snapshot.is_file() else None
        result["sheets"] = sorted(edited)
        if current != text:
            result["files"] = [FILE_NAME]
            if check:
                issues = (
                    Issue(
                        "sync.would-change",
                        "error",
                        "native schematic layout is not current",
                        where=FILE_NAME,
                        hint="run sync --target altium --to-source --confirm",
                    ),
                )
            else:
                writes = (PlannedWrite(str(snapshot), text.encode("utf-8"), "altium-schematic-layout"),)
    except LayoutConflict as error:
        issues = error.issues
    return Result(
        result=result,
        issues=issues,
        writes=writes,
        evidence=Evidence(Level.INFERRED),
        input=InputRef(str(script), digest(script.read_bytes()), "fenolite-dsl", None),
        depends=depends_on(ctx.cwd, *inputs),
    )
