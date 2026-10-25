# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Rewrite the screenshot references of the viewer's visual tests (change c0191) after an intended change.

    uv run python tools/update_view_refs.py            # every fixture
    uv run python tools/update_view_refs.py altium_sheet kicad_board

Writes the fixtures' pages into a temporary folder, draws them in Chromium with the fonts of
``tests/visual/fonts.conf`` and copies the screenshots to ``tests/visual/refs/``. Review the images before you
commit them: they are what the tests will hold the page to.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from _visual import NAMES, REFS, browser_missing, job, pages, run  # noqa: E402


def main(argv: list[str]) -> int:
    wanted = argv or list(NAMES)
    unknown = sorted(set(wanted) - set(NAMES))
    if unknown:
        print(f"unknown fixture(s): {', '.join(unknown)}; known: {', '.join(NAMES)}", file=sys.stderr)
        return 2
    missing = browser_missing()
    if missing:
        print(missing, file=sys.stderr)
        return 6
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        built = pages(folder / "pages")
        out = folder / "shots"
        out.mkdir()
        replies = run([job(name, built[name], out, ref=out / "none.png") for name in wanted], out)
        REFS.mkdir(parents=True, exist_ok=True)
        for reply in replies:
            if reply["errors"]:
                print(f"{reply['name']}: the page reported {reply['errors']}", file=sys.stderr)
                return 1
            shutil.copyfile(out / f"{reply['name']}.png", REFS / f"{reply['name']}.png")
            print(f"wrote tests/visual/refs/{reply['name']}.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
