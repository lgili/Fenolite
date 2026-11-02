# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Optional, bounded evidence for one authored byte guard; no producer or baseline changes."""

from __future__ import annotations

import decimal
import hashlib
import json
import os
import platform
import re
import sys
import zlib
from collections import Counter
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from fenolite.api import Reply

CASE = ("board_40parts", "altium")
OUTPUT = "board_40parts.PcbDoc"
ENV = "FENOLITE_BUILD_BYTE_DIAGNOSTICS"
DIRECTORY = "fenolite-byte-diagnostics"
MAX_BYTES = 16 * 1024 * 1024
MAX_RECEIPT_BYTES = 256 * 1024


def destination(source_root: Path) -> Path | None:
    value = os.environ.get(ENV, "")
    if not value:
        return None
    folder = Path(value)
    if not folder.is_absolute() or folder.name != DIRECTORY or folder.is_symlink():
        return None
    folder = folder.resolve()
    if folder.is_relative_to(source_root.resolve()):
        return None
    if any((folder / name).exists() or (folder / name).is_symlink() for name in (OUTPUT, "receipt.json")):
        return None
    return folder


def _digest(result: Mapping[str, object]) -> str | None:
    files = result.get("files")
    value = cast(Mapping[str, object], files).get(OUTPUT) if isinstance(files, dict) else None
    return value if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) else None


def _runtime() -> dict[str, object]:
    context = decimal.getcontext()
    packages: dict[str, str | None] = {}
    for name in ("numpy", "pyclipper", "shapely"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            packages[name] = None
    commit = os.environ.get("GITHUB_SHA", "")
    return {
        "commit": commit if re.fullmatch(r"[0-9a-f]{40}", commit) else None,
        "python": ".".join(map(str, sys.version_info[:3])),
        "implementation": sys.implementation.name,
        "machine": platform.machine(),
        "byteorder": sys.byteorder,
        "os": {"system": platform.system(), "release": platform.release(), "macos": platform.mac_ver()[0]},
        "zlib": {"build": zlib.ZLIB_VERSION, "runtime": zlib.ZLIB_RUNTIME_VERSION},
        "decimal": {
            "precision": context.prec,
            "rounding": context.rounding,
            "Emin": context.Emin,
            "Emax": context.Emax,
            "clamp": context.clamp,
        },
        "geo_packages": packages,
    }


def capture_failure(
    example: str,
    target: str,
    out: Path,
    reply: Reply,
    actual: Mapping[str, object],
    expected: Mapping[str, object],
    *,
    source_root: Path,
    seed: str,
    timestamp: str,
    geometry_trace: object = None,
) -> None:
    """Copy only the selected same-run staged file, preserving the first observation and assertion."""
    if (example, target) != CASE or actual == expected:
        return
    folder = destination(source_root)
    if folder is None:
        return
    pcb, receipt_file = folder / OUTPUT, folder / "receipt.json"
    if any(path.exists() or path.is_symlink() for path in (pcb, receipt_file)):
        return

    from fenolite.backends.altium.read.cfb import CompoundError, Limits, open_compound
    from fenolite.cli import plans
    from fenolite.core.state import state_dir

    observed = _digest(actual)
    receipt: dict[str, object] = {
        "row": "@".join(CASE),
        "output": OUTPUT,
        "expected_sha256": _digest(expected),
        "observed_sha256": observed,
        "seed": seed,
        "timestamp": timestamp,
        "runtime": _runtime(),
        "status": "unavailable",
    }
    data: bytes | None = None
    plan_id = reply.result.get("plan_id")
    try:
        staged = plans.load(state_dir(), plan_id) if isinstance(plan_id, str) else None
        if staged is None:
            receipt["reason"] = "plan-unavailable"
        elif (
            staged.command != "build"
            or staged.arguments.get("design") != str(source_root / "examples/board_40parts/design.py")
            or staged.arguments.get("out") != str(out)
            or staged.cwd != str(out.parent.resolve())
        ):
            receipt["reason"] = "plan-outside-authored-case"
        else:
            rows = [
                row
                for row in staged.writes
                if (Path(staged.cwd) / str(row.get("path", ""))).resolve() == (out / OUTPUT).resolve()
            ]
            row = rows[0] if len(rows) == 1 else None
            if row is None or row.get("kind") != "altium_pcbdoc" or row.get("sha256") != observed:
                receipt["reason"] = "selected-write-unavailable"
            elif type(row.get("bytes")) is not int or not 0 < row["bytes"] <= MAX_BYTES:
                receipt["reason"] = "selected-write-too-large"
            else:
                stored_name = str(row.get("file", ""))
                stored = staged.folder / plans.FILES / stored_name
                if (
                    not re.fullmatch(r"[0-9]{4,}", stored_name)
                    or stored.is_symlink()
                    or stored.stat().st_size != row["bytes"]
                ):
                    receipt["reason"] = "staged-data-unavailable"
                else:
                    data = staged.data(row)
                    receipt.update(
                        status="captured", bytes=len(data), sha256=hashlib.sha256(data).hexdigest()
                    )
                    counts = Counter(
                        (item["code"], item["severity"]) for item in staged.reply.get("issues", [])
                    )
                    receipt["issue_counts"] = [
                        {"code": code, "severity": severity, "count": count}
                        for (code, severity), count in sorted(counts.items())
                    ]
                    pour: Mapping[str, object] = (
                        staged.reply.get("result", {}).get("pcb", {}).get("pour") or {}
                    )
                    receipt["pour"] = {"mode": pour.get("mode"), "poured": pour.get("poured")}
    except (plans.DamagedPlan, OSError, ValueError, KeyError, TypeError):
        data = None
        receipt["status"] = "unavailable"
        receipt["reason"] = "staged-data-unavailable"

    if data is not None:
        from _buildgeometry import authored_source

        if not authored_source(source_root, out):
            return
        if geometry_trace is not None:
            from _buildgeometry import Trace

            if isinstance(geometry_trace, Trace):
                receipt["geometry_trace"] = geometry_trace.data()
        try:
            compound = open_compound(data, limits=Limits(max_file_bytes=MAX_BYTES, max_entries=16_384))
            receipt["cfb"] = {"major": compound.header.major, "sector_size": compound.header.sector_size}
            receipt["streams"] = {
                name: {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
                for name in sorted(compound.streams())
                for payload in (compound.read(name),)
            }
        except CompoundError as error:
            receipt["cfb"] = {"status": "unreadable", "rule": error.rule}
    encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if len(encoded.encode()) > MAX_RECEIPT_BYTES:
        encoded = json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n"
    if len(encoded.encode()) > MAX_RECEIPT_BYTES:
        receipt["geometry_trace"] = {"status": "unavailable", "reason": "receipt-limit"}
        encoded = json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    if len(encoded.encode()) > MAX_RECEIPT_BYTES:
        data = None
        encoded = (
            json.dumps({"row": "@".join(CASE), "status": "unavailable", "reason": "receipt-limit"}) + "\n"
        )
    folder.mkdir(parents=True, exist_ok=True)
    if data is not None:
        with pcb.open("xb") as stream:
            stream.write(data)
    with receipt_file.open("x", encoding="utf-8") as stream:
        stream.write(encoded)
