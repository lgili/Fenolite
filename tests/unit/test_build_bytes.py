# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Every example builds the bytes recorded before change c0277 (design-dsl, "Coverage items keep existing
builds", scenario "Examples keep their bytes"; task 0.1 records the table, task 4.5 guards it).

The active table was remeasured from the clean integration base ``7c2f1df2`` before merging c0277.
All 72 pre-existing example/target rows were independently compared with the merged implementation.
The six families/picks circuit.json digests use root checkpoint 51c877b8: the complete planned-file maps
match that clean base independently, and only those six canonical circuit digests differ from 7c2f1df2.
Every native output and all other recorded digests remain unchanged. Only the three ``board_coverage``
rows come from c0277's new example. The original
``8dab89d6`` snapshot remains in Git history; concurrent catalog, lock and library changes explain its
differences from this integration base. A digest moves only with a documented writer change.

c0276 preserves hidden power pins in drawn schematics instead of making them visible as generated
schematics do. Only drawn@9 and drawn@10 were remeasured for that writer change; all other157 focused
example and generated-design guards passed unchanged before the two rows were refreshed.
The authored import_python snapshot now also carries the source drawing and native symbols; only its
three example rows were remeasured for that explicit source change (c0276 task 4.6).
The native drawn Altium writer moves only drawn@altium and import_python@altium: the project/root
schematic, their new native child sheets and removal of the generated-layout cache. Both examples
retain their exact Altium PCB and library digests (c0276 task 6.1).

c0276 task6.4 corrects only the authored drawn example: R3-2 returns to GND, the unused inputs are
explicit and IN labels its existing wire. Complete original plans matched this table before the change;
only drawn@9, drawn@10 and drawn@altium were remeasured. Their circuit/board/PCB and root/child schematic
bytes intentionally change with that source circuit. All library/project/rule/manufacturing hashes and
every unrelated row remain fixed. This is no native-writer change or assertion relaxation.

c0344 binds native project sheet identity caches to the emitted drawings. A complete clean
75-plan/1172-file comparison changes only41 KiCad project files and their41 build manifests;
all other1090 files and ten strict refusals remain identical. The41 recorded project digests
were reviewed against that explicit writer change and the independent native GUI proof.
See docs/evidence/project-sheet-identity-plan-delta.json.

c0351 refreshes only the three explicitly imported-example rows after a complete
75-plan/1172-file before comparison. All72 other complete plans match exactly.
The native10 example retains all native bytes; only canonical circuit.json adds
its actual Default class. Its explicit native10 sidecar refuses target9 and Altium
before staging. Target-specific identity positives and independent refusal tests
retain both compatibility directions. Full maps are in c0351/carrier-regression-proof.json.

c0332's exact final neck cut is no longer called (maintainer decision, 2026-11-04): the floating
final cut returns, and with it the one measured platform difference of c0323. Linux writes
7f49a78f for board_40parts.PcbDoc, macOS writes 01fdc848 (only the Regions6 and ShapeBasedRegions6
streams differ) and Windows writes 94c3fb4b (CI run 41829443943, 2026-11-04). That single file of that
single row has its own macOS and Windows digests; every other digest stays the same on every platform.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest
from _buildbytes import TABLE, TARGETS, examples, measure

RECORDED: dict[str, dict[str, object]] = json.loads(TABLE.read_text(encoding="utf-8"))
# The measured macOS and Windows digests of the floating final neck cut (c0323, c0332); see the docstring.
PLATFORM: dict[str, dict[str, dict[str, str]]] = {
    "darwin": {
        "board_40parts@altium": {
            "board_40parts.PcbDoc": "01fdc8486cd05e964850311b2e473487759ee11f81891da0bfe43220f8698911"
        }
    },
    "win32": {
        "board_40parts@altium": {
            "board_40parts.PcbDoc": "94c3fb4bd790fa2ad152e0095f2640834ee1beca65707f715ad40d37a8fad06d"
        }
    },
}


def expected_bytes(row: str, platform: str = sys.platform) -> dict[str, object]:
    """The recorded row, with the digest of a file listed for ``platform`` in ``PLATFORM``."""
    expected = copy.deepcopy(RECORDED[row])
    override = PLATFORM.get(platform, {}).get(row, {})
    files = expected["files"]
    assert isinstance(files, dict)
    for name, digest in override.items():
        assert name in files, (row, name)
        files[name] = digest
    return expected


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def test_table_covers_every_example() -> None:
    assert sorted(RECORDED) == sorted(f"{e}@{t}" for e in examples() for t in TARGETS)


@pytest.mark.parametrize("row", sorted(RECORDED))
def test_example_keeps_its_bytes(row: str, tmp_path: Path) -> None:
    example, target = row.split("@")
    expected = expected_bytes(row)
    found = measure(example, target, tmp_path / f"{example}-{target}", expected=expected)
    assert found == expected


def test_only_one_file_has_a_platform_digest() -> None:
    assert {p: {row: sorted(files) for row, files in rows.items()} for p, rows in PLATFORM.items()} == {
        "darwin": {"board_40parts@altium": ["board_40parts.PcbDoc"]},
        "win32": {"board_40parts@altium": ["board_40parts.PcbDoc"]},
    }
    assert expected_bytes("board_40parts@altium", "linux") == RECORDED["board_40parts@altium"]
    recorded = RECORDED["board_40parts@altium"]["files"]
    assert isinstance(recorded, dict)
    for platform in ("darwin", "win32"):
        changed = expected_bytes("board_40parts@altium", platform)["files"]
        assert isinstance(changed, dict)
        assert {k for k in recorded if recorded[k] != changed[k]} == {"board_40parts.PcbDoc"}
