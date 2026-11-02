# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read-only F0/J observation census; counts/member names only, never native acceptance.

    uv run python tools/altium_observations.py {F0,J} FOLDER

The kit privacy scan precedes interpretation, including the decoded Draftsman chunks. Review any
refusal locally; the command never prints matched private text, overwrites a file or opens Altium.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fenolite.cli.altium_observations import ObservationError, observe_f0, observe_j
from fenolite.core.errors import FenoliteError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("round", choices=("F0", "J"))
    parser.add_argument("folder", type=Path)
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error("the observation folder does not exist")
    try:
        report = (observe_f0 if args.round == "F0" else observe_j)(args.folder)
    except (ObservationError, FenoliteError, OSError):
        print(json.dumps({"error": "observation intake refused; review the source folder locally"}))
        return 3
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
