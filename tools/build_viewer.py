# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build the viewer page's bundle from ``viewer/src`` (change c0272; capability board-viewer, "Committed
viewer bundle").

    uv run python tools/build_viewer.py          # (re)write src/fenolite/view/static/
    uv run python tools/build_viewer.py --check  # exit 1 and name each file that is not a fresh build

Runs ``npm ci`` in ``viewer/`` when its packages are missing or older than ``package-lock.json``, then
``node viewer/build.mjs``. Node 22 or later is a contributor tool: a user's install carries the committed
bundle and never needs Node. ``make viewer`` and ``make viewer-check`` call this; the ``viewer`` CI job runs
``--check``.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VIEWER = ROOT / "viewer"
NODE_MAJOR = 22


def _stale_packages() -> bool:
    """``npm ci`` is due: no ``node_modules``, or a lock file newer than the one npm installed from."""
    installed = VIEWER / "node_modules" / ".package-lock.json"
    return (
        not installed.is_file() or installed.stat().st_mtime < (VIEWER / "package-lock.json").stat().st_mtime
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="build in memory and compare; write nothing")
    args = parser.parse_args(argv)
    node, npm = shutil.which("node"), shutil.which("npm")
    if node is None or npm is None:
        print(
            f"build_viewer: Node {NODE_MAJOR} or later and npm are needed to build the viewer",
            file=sys.stderr,
        )
        return 2
    version = subprocess.run([node, "--version"], capture_output=True, text=True, check=True).stdout.strip()
    if int(version.lstrip("v").split(".")[0]) < NODE_MAJOR:
        print(f"build_viewer: Node {version} is older than {NODE_MAJOR}", file=sys.stderr)
        return 2
    if _stale_packages():
        subprocess.run([npm, "ci", "--no-audit", "--no-fund"], cwd=VIEWER, check=True)
    command = [node, "build.mjs", *(["--check"] if args.check else [])]
    return subprocess.run(command, cwd=VIEWER, check=False).returncode


if __name__ == "__main__":
    sys.exit(main())
