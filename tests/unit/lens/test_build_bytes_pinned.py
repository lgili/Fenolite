# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Builds of designs whose pins have one pad each, pinned by digest (capability kicad-schematic, "Pins with
several pads on a generated sheet", scenario "Builds of one pad per pin are pinned"; ``H-G-PINMAP-BYTES``;
change c0123).

The digests were measured on the commit before any product code of change c0123 (ba21a109, the release
0.2.0 with the changes of the Altium write side, now named v0.3, up to c0090). A pin is
``files:netlist:parity:bom:pnp`` for a KiCad build
and one digest of the files for an Altium build (``tests/_pinned.py``). The units design and most of the
generated designs hold a ``pad_map`` of one pad per pin; no committed golden does.

A pin that moves is changed only by the change that changes the writer, with the reason beside it, never
to make a test pass: ``uv run python tests/_pinned.py`` prints the tables.

Change c0102 moved the files digest of every KiCad pin, and nothing else: the board writer signs the uuids
of the outline's edge lines with the outline's digest (``kicad-file-backend``, "Outline lowering"), where
it wrote position uuids before. The netlist, parity, BOM and position digests of each pin kept their
values, and no Altium pin moved.
"""

from __future__ import annotations

import json

import pytest
from _buildhelp import blink, build
from _pinned import GENERATED, altium_designs, altium_pin, kicad_designs, kicad_pin

KICAD = {
    "blink@9": "1940b085e92a:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink@10": "e1ca0da824a4:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@9": "126bd91ba587:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@10": "024cc199bc7d:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "board_40parts@9": "a89901038177:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "board_40parts@10": "f366d3d3ebfa:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "nested@9": "6182c80ea14d:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "nested@10": "5b7f6d1545db:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "units@9": "196a955d2ef8:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "units@10": "353ef77e505f:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "gen-00@9": "f7e7b86b8ab0:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-00@10": "45b04c6dbf1d:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-01@9": "21d2fe67cb14:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-01@10": "1e3970205c77:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-02@9": "57d2a8ebdb54:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-02@10": "30edb88c1d4e:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-03@9": "79d43379843d:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-03@10": "2fb3740bcb76:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-04@9": "b2ce87636abb:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-04@10": "8cad3ee120bf:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-05@9": "c1075ac98095:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-05@10": "b337bae0a646:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-06@9": "726ec3744e84:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-06@10": "a0b560698931:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-07@9": "0266a281a2d0:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-07@10": "f62d1326539d:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-08@9": "a587b314a1a3:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-08@10": "a71fbe8c9bc4:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-09@9": "1276a73c8e25:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-09@10": "6241dc6e802f:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-10@9": "db4a2640bdfe:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-10@10": "213699898435:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-11@9": "9dce111c060b:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-11@10": "db226fdc0a43:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-12@9": "01dbb831b8df:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-12@10": "a90b5471cb43:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-13@9": "9fb50893edc2:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-13@10": "7b9e568bb03f:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-14@9": "ecabd083a282:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-14@10": "c2e509db2449:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-15@9": "648df16b995c:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-15@10": "cde107b85468:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-16@9": "1b6fea13f1cf:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-16@10": "25afebedf4b2:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-17@9": "9b6a045a325f:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-17@10": "bdbd01ca2636:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-18@9": "48dc2e6249f0:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-18@10": "87d1bcc7f530:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-19@9": "2bf59ede6b27:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-19@10": "3574f05f7491:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-20@9": "261b05260612:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-20@10": "1d270e76e21d:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-21@9": "58a62475dda8:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-21@10": "f2f533f7ec52:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-22@9": "b3741b06e389:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-22@10": "77858650b47e:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-23@9": "c140a26d40f4:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-23@10": "81de777243bc:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-24@9": "373ca1042af0:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "gen-24@10": "7b2c11094c5d:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "genmod-00@9": "a9cb8cc71654:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-00@10": "560405dd39e4:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-01@9": "2a68516bdf8e:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-01@10": "c86ab02cba03:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-02@9": "1120df9134a4:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-02@10": "3f2b0afcf927:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-03@9": "55d6bf7d6640:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-03@10": "de8357b989f5:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-04@9": "69120d658097:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
    "genmod-04@10": "2b79cb7212ec:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
}
ALTIUM = {
    # Changed by change c0148 (all ten entries, each marked with its former pin): every pin of the
    # schematic document and of the library has bit 0x20 added to its ``PINCONGLOMERATE`` (as Altium saves
    # pins; 0x08 and 0x10 are then show flags), and ``.fenolite/build.json`` names the two new digests.
    # Measured on 2026-10-08 against builds with the base code: no other file changed, and the two
    # schematic files differ record by record in that bit alone (``tests/_pin_bits.py``).
    # Changed by change c0126 (all ten entries): ``.fenolite/board.json``
    # holds the footprint graphics and corner ratios that the build wrote (c0126); no project file changed.
    # Measured on 2026-10-08: for every entry the digest of the files outside ``.fenolite/`` is the one
    # measured on the base before the change (``tests/_pinned.py::files_digest``), file by file.
    "blink@ascii": "52b5bc9a3e02",  # c0148: pin bit 0x20; was 720f981a0f72 (c0126; before, 1896e9b80f88)
    "blink@binary": "1906149ef653",  # c0148: pin bit 0x20; was 03ddd9f42c80 (c0126; before, 3b260d5d6088)
    "blink-unmarked@ascii": "a021e2f4c771",  # c0148: pin bit 0x20; was 6f52bcfc5f39 (c0126; ceee4edd66d5)
    "blink-unmarked@binary": "4f97399a5ab7",  # c0148: pin bit 0x20; was fbdac8c68070 (c0126; b3a1f470ab5d)
    "board_40parts@ascii": "6f39adb8496b",  # c0148: pin bit 0x20; was 32d77f89673d (c0126; e49a072fc1e3)
    "board_40parts@binary": "7ba896421a04",  # c0148: pin bit 0x20; was 079ad8e43825 (c0126; 9b9770e93ad2)
    "nested@ascii": "f7bc73941f73",  # c0148: pin bit 0x20; was f345113d40e8 (c0126; before, 2e848e270334)
    "nested@binary": "1f39dae3f8fb",  # c0148: pin bit 0x20; was 512c741fad8a (c0126; before, 37ba8f5e4210)
    # Changed by the change that changes the writer: the units design holds a ``pad_map`` that renames
    # the pads of ``D1``, and an Altium build ignored it (releases 0.1.0 and 0.2.0). The PCB document
    # now has the nets on the mapped pads, and the sheet and the library hold the map as records 47.
    # The pins before were ``cc3e51c47b9a`` (ASCII) and ``e350e453dd70`` (binary); no other pin moved.
    # The fix reached this line with the release 0.2.1 (change c0135), before change c0123: measured on
    # 2026-10-07 on the base 9322ff2f without c0123 and with it, all ten Altium pins and all 70 KiCad
    # pins are equal, so c0123 moves no pin on this base (c0121 moved none either: bodies are off by
    # default). The two did not move when the writer went from a record for every pin to a record for
    # the mapped pins only (``altsym.MAP_RECORDS_FOR_EVERY_PIN``): the map of
    # ``D1`` names both of its pins, so both forms are the same two records. An Altium ``build`` envelope
    # is no file of the build, so the hypothesis row added with that switch moves no pin.
    "units@ascii": "9b08e518e8ba",  # c0148: pin bit 0x20; was f2b8914b1662 (c0126; before, 9b7b311ae714)
    "units@binary": "0bb2e04b8472",  # c0148: pin bit 0x20; was 572f5eb0bfdc (c0126; before, d7a85c5bec0e)
}


def test_the_generated_designs_hold_one_pad_maps() -> None:
    """The proof needs designs with a map of one pad per pin: the units design and the generated ones."""
    mapped = [
        name for name, make in kicad_designs().items() if any(p.pad_map for p in make()[0].parts.values())
    ]  # type: ignore[attr-defined]
    assert "units" in mapped and len([name for name in mapped if name.startswith("gen-")]) >= GENERATED // 2


@pytest.mark.parametrize("key", list(KICAD))
def test_kicad_build_is_pinned(key: str) -> None:
    name, target = key.rsplit("@", 1)
    design, project_dir = kicad_designs()[name]()
    assert kicad_pin(design, project_dir, int(target)) == KICAD[key], (
        f"{key}: files:netlist:parity:bom:pnp moved; a pin is changed only by the change that changes "
        "the writer"
    )


@pytest.mark.parametrize("key", list(ALTIUM))
def test_altium_build_is_pinned(key: str) -> None:
    name, form = key.rsplit("@", 1)
    design, project_dir = altium_designs()[name]()
    assert altium_pin(design, project_dir, form) == ALTIUM[key], f"{key}: the files of the build moved"


def test_every_design_is_pinned_for_both_targets() -> None:
    assert sorted(KICAD) == sorted(f"{name}@{target}" for name in kicad_designs() for target in (9, 10))
    assert sorted(ALTIUM) == sorted(
        f"{name}@{form}" for name in altium_designs() for form in ("ascii", "binary")
    )


def test_the_model_version_is_zero() -> None:
    meta = json.loads(build(blink(), 10).files[".fenolite/meta.json"])
    assert meta["schema_version"] == "0"
