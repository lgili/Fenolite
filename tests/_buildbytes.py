# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What the byte guard of change c0277 measures (``tests/unit/test_build_bytes.py``, task 0.1).

Every example script under ``examples/`` that builds without KiCad's libraries is built with ``--dry-run``
for targets 9, 10 and ``altium``, with a fixed ``--seed`` and ``--timestamp``, and each planned file is
recorded by its path inside the build folder and its SHA-256. The two built files that hold the package
version are left out. A change that adds a DSL call must leave every recorded digest unchanged: an
example that uses none of the new calls builds the same bytes.

Run ``uv run python tests/_buildbytes.py > tests/data/build_bytes.json`` to measure the table again; a
digest is changed only by the change that changes the writer, with the reason in its commit.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TABLE = ROOT / "tests" / "data" / "build_bytes.json"
TARGETS = ("9", "10", "altium")
SEED = "1"
TIMESTAMP = "2026-01-01T00:00:00Z"
VERSIONED = (".fenolite/meta.json", ".fenolite/build.json")
"""The two built files that hold the package version."""
NEEDS_LIBRARIES = frozenset({"blink_official", "yardstick"})
"""Examples whose build reads KiCad's own libraries, which the unit tests do not have."""


def examples() -> tuple[str, ...]:
    """The example folders that hold a ``design.py``, in name order, without ``NEEDS_LIBRARIES``."""
    return tuple(
        sorted(
            path.parent.name
            for path in (ROOT / "examples").glob("*/design.py")
            if path.parent.name not in NEEDS_LIBRARIES
        )
    )


def _isolate() -> None:
    os.environ["KICAD_CONFIG_HOME"] = tempfile.mkdtemp(prefix="fenolite-kicad-config-")
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        os.environ.pop(name, None)


def measure(example: str, target: str, out: Path) -> dict[str, object]:
    """``{"exit": code, "files": {path: sha256}}`` of the dry-run build of ``example`` for ``target`` into
    ``out``; the paths are relative to ``out``."""
    from fenolite.api import run

    script = ROOT / "examples" / example / "design.py"
    flag = ["--target", "altium"] if target == "altium" else ["--kicad-version", target]
    reply = run(
        "build", str(script), "--out", str(out), *flag, "--dry-run", cwd=out.parent, seed=int(SEED),
        timestamp=TIMESTAMP,
    )  # fmt: skip
    files: dict[str, str] = {}
    if reply.exit_code == 0:
        result = (reply.envelope or {}).get("result") or {}
        for row in result.get("plan") or []:
            path = Path(row["path"])
            relative = (path if path.is_absolute() else out.parent / path).relative_to(out).as_posix()
            if relative not in VERSIONED:
                files[relative] = row["sha256"]
    return {"exit": reply.exit_code, "files": dict(sorted(files.items()))}


def table() -> dict[str, Mapping[str, object]]:
    """``"<example>@<target>"`` → the measure of that build, every example and target."""
    _isolate()
    found: dict[str, Mapping[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="fenolite-build-bytes-") as folder:
        for example in examples():
            for target in TARGETS:
                found[f"{example}@{target}"] = measure(example, target, Path(folder) / f"{example}-{target}")
    return found


def main() -> int:
    sys.stdout.write(json.dumps(table(), indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
