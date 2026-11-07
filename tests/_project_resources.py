# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original worksheet resource and isolated native-project cases for c0354."""

from __future__ import annotations

import json
from pathlib import Path

from _importcode import copy_project

WORKSHEET = (
    b'(kicad_wks (version 20231118) (generator "fenolite")'
    b" (setup (textsize 1.5 1.5) (linewidth 0.15) (textlinewidth 0.15)"
    b" (left_margin 10) (right_margin 10) (top_margin 10) (bottom_margin 10))"
    b' (tbtext "AUTHORED FRAME" (name "") (pos 10 10 ltcorner)))\n'
)


def source_with_resource(tmp_path: Path, target: int, scope: str) -> Path:
    source = copy_project(tmp_path, "original", native_target=target)
    resource = source.parent / "frames" / "authored.kicad_wks"
    resource.parent.mkdir()
    resource.write_bytes(WORKSHEET)
    data = json.loads(source.read_text())
    for kind in ("pcbnew", "schematic"):
        data.setdefault(kind, {})["page_layout_descr_file"] = (
            "${KIPRJMOD}/frames/authored.kicad_wks" if scope in (kind, "both") else ""
        )
    source.write_text(json.dumps(data, sort_keys=True, indent=2) + "\n")
    return source
