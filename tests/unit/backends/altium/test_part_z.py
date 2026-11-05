# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The files of Part Z of the maintainer's check (``docs/evidence/altium-pcb.md``, "Part Z: component
bodies"; change c0387, task 1.1, and change c0175, task 10.4).

``part_z(folder)`` writes the kit into ``folder``:

- ``body2/``: the committed project of step X8 (``tests/data/altium/body2/``), as it is;
- ``Box_2x1.step``: the authored CC0 model of ``tests/data/models/Fenolite.3dshapes/``;
- ``expected.md``: the bodies of ``body2.PcbDoc`` as Fenolite's reader reads them;
- ``README.md``: the steps Z1 to Z4 of the evidence page; ``SHA256SUMS``: the SHA-256 of every other file.

With ``FENOLITE_ALTIUM_PART_Z=<folder outside the repository>`` the kit is written there; without it, under
the test's own folder. ``FENOLITE_ALTIUM_PART_Z_SAVED=<folder>`` reads the files that Altium saved, after
the kit privacy scan, and prints their bodies and models. No file that Altium wrote is in the repository.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from fenolite.backends.altium.models3d import model_records
from fenolite.backends.altium.read.bodies import read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.cli.altium_observations import checked_files

ROOT = Path(__file__).resolve().parents[4]
SAMPLE = ROOT / "tests" / "data" / "altium" / "body2"
MODEL = ROOT / "tests" / "data" / "models" / "Fenolite.3dshapes" / "Box_2x1.step"
CASES = ("Z1", "Z2", "Z3", "Z4")
BODY_KEYS = (
    "BODYPROJECTION",
    "MODEL.MODELTYPE",
    "STANDOFFHEIGHT",
    "OVERALLHEIGHT",
    "MODEL.NAME",
    "MODEL.EMBED",
    "MODEL.3D.ROTZ",
    "V7_LAYER",
)
"""The keys of a body that the cases measure: side, model type, the two heights, the model and its turn."""
MODEL_KEYS = ("ID", "NAME", "EMBED", "ROTX", "ROTY", "ROTZ", "DZ")
"""The keys of an entry of the ``Models`` storage that case Z4 compares (the checksum is left out)."""


def body_rows(data: bytes) -> list[dict[str, str]]:
    """One row per framed body of a PCB document: its component's designator and side, then ``BODY_KEYS``."""
    doc = read_pcbdoc(data)
    stream = doc.storages.get("ComponentBodies6", {}).get("Data", b"")
    rows: list[dict[str, str]] = []
    for record in read_bodies(stream, storage="ComponentBodies6"):
        if not record.framed:
            continue
        part = doc.components[record.component] if record.component is not None else None
        row = {
            "component": (part.source_designator or "") if part is not None else "",
            "side": (part.layer or "") if part is not None else "",
        }
        row.update({key: record.properties.text(key) for key in BODY_KEYS})
        rows.append(row)
    return rows


def model_rows(data: bytes) -> list[dict[str, str]]:
    """The entries of the document's ``Models`` storage, ``MODEL_KEYS`` of each, in stream order."""
    doc = read_pcbdoc(data)
    records = model_records(doc.storages.get("Models", {}).get("Data", b""))
    return [{key: record.get(key, "") for key in MODEL_KEYS} for record in records]


def _table(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["(none)"]
    keys = list(rows[0])
    lines = ["| " + " | ".join(keys) + " |", "|" + "---|" * len(keys)]
    lines += ["| " + " | ".join(row[key] or "-" for key in keys) + " |" for row in rows]
    return lines


def part_z(folder: Path) -> dict[str, str]:
    """Write the kit into ``folder``; the SHA-256 of every file by its path relative to ``folder``."""
    files = {f"body2/{path.name}": path.read_bytes() for path in sorted(SAMPLE.iterdir()) if path.is_file()}
    files["Box_2x1.step"] = MODEL.read_bytes()
    expected = ["# Part Z: the bodies of body2.PcbDoc as Fenolite reads them", ""]
    expected += _table(body_rows(files["body2/body2.PcbDoc"]))
    expected += ["", "Models storage entries:", "", *_table(model_rows(files["body2/body2.PcbDoc"])), ""]
    files["expected.md"] = "\n".join(expected).encode()
    page = (ROOT / "docs" / "evidence" / "altium-pcb.md").read_text(encoding="utf-8")
    start = page.index("## Part Z")
    files["README.md"] = page[start : page.index("\n## ", start + 1)].encode()
    folder.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    sums = {name: hashlib.sha256(data).hexdigest() for name, data in sorted(files.items())}
    (folder / "SHA256SUMS").write_text("".join(f"{digest}  {name}\n" for name, digest in sums.items()))
    return sums


def test_kit(tmp_path: Path) -> None:
    given = os.environ.get("FENOLITE_ALTIUM_PART_Z")
    folder = Path(given).expanduser() if given else tmp_path / "Z-bodies"
    assert ROOT not in folder.resolve().parents, "the kit is written outside the repository"
    sums = part_z(folder)
    assert {"body2/body2.PcbDoc", "body2/body2.PrjPcb", "Box_2x1.step", "README.md", "expected.md"} <= set(
        sums
    )
    readme = (folder / "README.md").read_text(encoding="utf-8")
    assert [case for case in CASES if f"**{case}**" in readme] == list(CASES)
    assert all(f"`{case}.PcbDoc`" in readme for case in CASES)
    expected = (folder / "expected.md").read_text(encoding="utf-8")
    assert "| D1 | BOTTOM | 1 | 0 |" in expected and expected.count("| TOP | 0 | 0 |") == 2


def test_body_rows_of_the_sample() -> None:
    """The committed sample: one bottom body projected from the bottom, two top bodies from the top, all
    extruded (model type 0); its ``Models`` storage holds no entry."""
    data = (SAMPLE / "body2.PcbDoc").read_bytes()
    rows = body_rows(data)
    assert [
        (row["component"], row["side"], row["BODYPROJECTION"], row["MODEL.MODELTYPE"]) for row in rows
    ] == [
        ("D1", "BOTTOM", "1", "0"),
        ("R1", "TOP", "0", "0"),
        ("U1", "TOP", "0", "0"),
    ]
    assert rows[1]["STANDOFFHEIGHT"] == "19.685mil" and rows[1]["OVERALLHEIGHT"] == "157.4803mil"
    assert model_rows(data) == []


@pytest.mark.skipif(
    not os.environ.get("FENOLITE_ALTIUM_PART_Z_SAVED"), reason="no folder of files that Altium saved is given"
)
def test_saved(capsys: pytest.CaptureFixture[str]) -> None:
    """Print the bodies and models of each saved case file, after the kit privacy scan."""
    folder = Path(os.environ["FENOLITE_ALTIUM_PART_Z_SAVED"]).expanduser()
    files = checked_files(folder)
    found = {Path(name).stem: data for name, data in files.items() if Path(name).stem in CASES}
    assert found, "no saved case file Z1 to Z4"
    lines: list[str] = []
    for case in CASES:
        if case not in found:
            lines += [f"## {case}: not saved", ""]
            continue
        lines += [f"## {case}", "", *_table(body_rows(found[case])), "", "Models:", ""]
        lines += [*_table(model_rows(found[case])), ""]
    with capsys.disabled():
        print("\n".join(lines))
