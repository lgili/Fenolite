# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored-for-Fenolite CC0 model sources for c0264; generated solely by Fenolite's writers."""

from __future__ import annotations

import io
import zipfile
from decimal import Decimal
from pathlib import Path

from fenolite.backends.altium.altsym import from_symbol_def
from fenolite.backends.altium.pcblib import LibFootprint, PadExtras, write_pcblib
from fenolite.backends.altium.schlib import write_schlib
from fenolite.backends.kicad.mod import prepare_authored_definition, write_footprint
from fenolite.backends.kicad.sym import write_symbol_library
from fenolite.catalog.footprints import generate
from fenolite.catalog.generate.symbol import generate_symbol
from fenolite.model.library import PinRow, PinTable

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "tests/data/library_import"
PACKAGE = """# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite. Fictional outline; no manufacturer dimensions.
schema = "fenolite.package.v0"
family = "gullwing"
name = "EXB6202"
summary = "SPDX-License-Identifier: CC0-1.0; Authored for Fenolite; https://example.invalid/exb6202"
pins = 8
pitch = "1.27mm"
arrangement = "dual"
body = { length = "4.8mm", width = "3.8mm", height = "1.4mm" }
span = "6mm"
lead = { length = "0.6mm", width = "0.4mm", thickness = "0.2mm" }
[generate]
drawing = 1
[land]
source = "Fenolite-authored fictional land"
pad = { length = "1.5mm", width = "0.6mm" }
row_spacing = "5.5mm"
"""


def fixtures() -> dict[str, bytes]:
    table = PinTable(
        "EXB6202",
        rows=tuple(PinRow(str(n), f"IO{n}", "passive") for n in range(1, 9)),
        summary="SPDX-License-Identifier: CC0-1.0; Authored for Fenolite; https://example.invalid/exb6202",
    )
    symbol, _, _ = generate_symbol(table, library="Example")
    symbol.properties["Datasheet"] = "https://example.invalid/exb6202"
    footprint = generate(PACKAGE).footprint
    assert footprint is not None
    files = {
        "exb6202.kicad_sym": write_symbol_library([symbol]).encode(),
        "exb6202.kicad_mod": write_footprint(prepare_authored_definition(footprint)).encode(),
        "exb6202.SchLib": write_schlib(
            [from_symbol_def(symbol, lib_ref=symbol.name, footprint=None)], library="Example"
        ),
        "exb6202.PcbLib": write_pcblib(
            [
                LibFootprint(
                    footprint,
                    {
                        pad.id: PadExtras(corner_ratio=Decimal(pad.corner_ratio) / 1_000_000)
                        for pad in footprint.pads
                        if pad.corner_ratio is not None
                    },
                )
            ],
            filename="exb6202.PcbLib",
        ),
        "exb6202.step": (
            b"ISO-10303-21;\n/* SPDX-License-Identifier: CC0-1.0; Authored for Fenolite; "
            b"https://example.invalid/exb6202 */\nHEADER;\nFILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\n"
            b"ENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
        ),
        "exb6202.toml": PACKAGE.encode(),
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.comment = b"SPDX-License-Identifier: CC0-1.0; Authored for Fenolite"
        for name in ("exb6202.kicad_sym", "exb6202.kicad_mod", "exb6202.step"):
            info = zipfile.ZipInfo(f"KiCad/{name}", (2026, 11, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.comment = b"Authored for Fenolite (CC0-1.0)"
            archive.writestr(info, files[name])
        archive.writestr(
            zipfile.ZipInfo("README.txt", (2026, 11, 1, 0, 0, 0)),
            "SPDX-License-Identifier: CC0-1.0\nAuthored for Fenolite. https://example.invalid/exb6202\n",
        )
    files["exb6202.zip"] = buffer.getvalue()
    return files


if __name__ == "__main__":
    DATA.mkdir(parents=True, exist_ok=True)
    for name, data in fixtures().items():
        (DATA / name).write_bytes(data)
