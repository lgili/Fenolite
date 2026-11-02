# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Review block-version changes through the existing lock/build/mutation protocols (c0273).

The script runs once. Build validation uses an in-memory lock with the used versions, then its
output writes are discarded. The only exposed target preserves the old lock's other sections.
"""

from __future__ import annotations

import argparse
import dataclasses
import tempfile
from pathlib import Path
from typing import Any, cast

from fenolite.cli._lock import check_library, lock_location
from fenolite.cli._script import run_design_script
from fenolite.cli.api import Context, PlannedWrite, Result, depends_on
from fenolite.cli.blockvendored import EVIDENCE, find_vendored, input_files
from fenolite.cli.errors import CliError
from fenolite.core.errors import Issue
from fenolite.dsl.block import blocks
from fenolite.dsl.lock import LockValue, lock_text, make_lock, read_lock
from fenolite.dsl.record import record_data
from fenolite.model import canonical
from fenolite.model.circuit import Circuit, Component


def register_upgrade(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--block",
        dest="upgrade_blocks",
        action="append",
        default=[],
        metavar="ID",
        help="upgrade: only instances of this block id (repeatable)",
    )
    parser.add_argument("--allow-major", action="store_true", help="upgrade: accept a reviewed MAJOR step")


def _step(before: str, after: str) -> str:
    old, new = tuple(int(v) for v in before.split(".")), tuple(int(v) for v in after.split("."))
    if new < old:
        return "downgrade"
    if new[0] != old[0]:
        return "major"
    return "minor" if new[1] != old[1] else "patch"


def _part(component: Component) -> dict[str, str]:
    return {
        "value": component.value,
        "device": component.properties.get("fenolite.device", ""),
        "symbol": component.lib_symbol_ref,
        "footprint": component.lib_footprint_ref,
    }


def _circuit_diff(before: Circuit, after: Circuit, instance: str) -> list[dict[str, object]]:
    def parts(circuit: Circuit) -> dict[str, dict[str, str]]:
        # Built cache circuits come through the board reader, which preserves the lens path as a
        # property even when Component.path is absent. Both are literal hierarchical identities.
        found: dict[str, dict[str, str]] = {}
        for part in circuit.components:
            path = part.path or part.properties.get("fenolite.path", "")
            if path.startswith(instance + "/"):
                found[path] = _part(part)
        return found

    old, new = parts(before), parts(after)
    found: list[dict[str, object]] = []
    for path in sorted(old.keys() | new.keys()):
        a, b = old.get(path), new.get(path)
        if a == b:
            continue
        found.append(
            {
                "path": path,
                "change": "added" if a is None else "removed" if b is None else "changed",
                "before": a,
                "after": b,
            }
        )
    return found


def run_upgrade(args: argparse.Namespace, ctx: Context) -> Result:
    from fenolite.cli import cmd_build

    if len(args.target) != 1:
        raise CliError("FEN-2001", "blocks upgrade takes one design script", where="SCRIPT")
    given = str(args.target[0])
    script = Path(given) if Path(given).is_absolute() else ctx.cwd / given
    lock_given, lock_path = lock_location(given, None, ctx.cwd)
    old = read_lock(lock_path.read_text(encoding="utf-8"), file=lock_given) if lock_path.is_file() else None
    if old is not None:
        check_library(old, script, given)
    catalog_issues: list[Issue] = []
    find_vendored(script.parent, issues=catalog_issues)
    if any(issue.severity == "error" for issue in catalog_issues):
        return Result(issues=tuple(catalog_issues), evidence=EVIDENCE)
    run = run_design_script(script, describe_blocks=True)
    if old is None:
        old = make_lock(run.design.name)
    used = {item.path: item for item in blocks(run.design) if item.definition.header is not None}
    selected = set(args.upgrade_blocks)
    unknown = selected - {
        item.definition.header.id for item in used.values() if item.definition.header is not None
    }
    if unknown:
        raise CliError(
            "FEN-2001", "--block names no used block: " + ", ".join(sorted(unknown)), where="--block"
        )
    upgraded: dict[str, LockValue] = dict(old.sections["blocks"])
    virtual: dict[str, LockValue] = dict(old.sections["blocks"])
    rows: list[dict[str, Any]] = []
    issues: list[Issue] = []
    for path, instance in sorted(used.items()):
        header = instance.definition.header
        assert header is not None
        virtual[path] = header.pin
        pin = old.sections["blocks"].get(path)
        if not isinstance(pin, str) or pin == header.pin or (selected and header.id not in selected):
            continue
        before_id, _, before = pin.rpartition("@")
        if before_id != header.id:
            continue  # c0268 handles id replacements in a normal build, not a version upgrade
        record = record_data(run.block_records[id(instance.definition)])
        step = _step(before, header.version)
        rows.append(
            {
                "path": path,
                "id": header.id,
                "before": before,
                "after": header.version,
                "step": step,
                "record": record,
                "deprecated": record["deprecated"],
                "issues": [],
            }
        )
        upgraded[path] = header.pin
        if step == "major" and not args.allow_major:
            issues.append(
                Issue(
                    "blocks.upgrade-major",
                    "error",
                    f"{path}: {header.id} changes MAJOR from {before} to {header.version}",
                    where=path,
                    hint="review the interface change and use --allow-major only if intended",
                )
            )
    result: dict[str, Any] = {"upgrades": rows, "lock": lock_given}
    inputs: list[Path] = [*run.source_files, *input_files(script.parent)]
    inputs += [script.parent / file.path for file in run.device_files]
    if lock_path.is_file():
        inputs.append(lock_path)
    baseline: Circuit | None = None
    if args.out is not None:
        folder = Path(args.out) if Path(args.out).is_absolute() else ctx.cwd / args.out
        circuit = folder / ".fenolite/circuit.json"
        if not circuit.is_file():
            raise CliError(
                "FEN-3001",
                "--out has no previous .fenolite/circuit.json",
                where=str(args.out),
                hint="name the directory of a confirmed build",
            )
        baseline = cast(
            Circuit, canonical.loads(circuit.read_text(encoding="utf-8"), Circuit, file=circuit.name)
        )
        inputs.extend(path for path in folder.rglob("*") if path.is_file())
    if not rows:
        return Result(
            result=result, issues=run.block_issues, evidence=EVIDENCE, depends=depends_on(ctx.cwd, *inputs)
        )
    with tempfile.TemporaryDirectory(prefix="fenolite-block-upgrade-") as temporary:
        parser = argparse.ArgumentParser(add_help=False)
        cmd_build.COMMAND.register(parser)
        build_args = parser.parse_args([given, "--out", args.out or temporary])
        # This override is in memory only. Build validation still reads the actual item pins.
        validated = cmd_build._built(  # pyright: ignore[reportPrivateUsage]
            build_args,
            ctx,
            script_run=run,
            previous_lock=make_lock(old.design, {**old.sections, "blocks": virtual}),
        )
    issues.extend(validated.issues)
    for row in rows:
        path = str(row["path"])
        row["issues"] = [
            dataclasses.asdict(i)
            for i in validated.issues
            if i.where == path or i.where.startswith(path + "/")
        ]
    if baseline is not None:
        for row in rows:
            row["circuit"] = None  # unavailable when the validated build has errors
        source = next(
            (
                write.data
                for write in validated.writes
                if write.path.replace("\\", "/").endswith("/.fenolite/circuit.json")
            ),
            None,
        )
        if source is not None:
            after = cast(Circuit, canonical.loads(source.decode("utf-8"), Circuit, file="circuit.json"))
            for row in rows:
                row["circuit"] = _circuit_diff(baseline, after, str(row["path"]))
    updated = make_lock(old.design, {**old.sections, "blocks": upgraded})
    writes = (
        ()
        if any(i.severity == "error" for i in issues)
        else (PlannedWrite(lock_given, lock_text(updated).encode("utf-8"), "lock"),)
    )
    return Result(
        result=result,
        issues=tuple(issues),
        evidence=EVIDENCE,
        writes=writes,
        depends=depends_on(ctx.cwd, *inputs, *validated.depends),
    )
