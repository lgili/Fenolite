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

# c0344 deliberately changes only KiCad .kicad_pro identity caches to the emitted
# root UUID/name/filename and child sheet index. For all70 entries, before/after
# file comparison proved that no other unversioned file or project key changed;
# netlist/parity/BOM/PNP pins remain identical. Native10 GUI saves preserve the
# distinct repeated references with these bound caches.

from __future__ import annotations

import json

import pytest
from _buildhelp import blink, build
from _pinned import GENERATED, altium_designs, altium_pin, kicad_designs, kicad_pin

KICAD = {
    "blink@9": "fba417e2c9d5:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink@10": "08c88f83e5fe:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@9": "b0248bbcebed:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@10": "d1e911b6d7c4:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "board_40parts@9": "69a4ad7171ef:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "board_40parts@10": "2fa2b7b7a8a9:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "nested@9": "5a18c6014832:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "nested@10": "abfd4dd8b711:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "units@9": "f39ef4713995:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "units@10": "a52848f61e2b:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "gen-00@9": "18521ec2c1fb:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-00@10": "f3fdb17477a1:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-01@9": "30c8a35f2e8d:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-01@10": "00d67f9b839f:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-02@9": "3bebc60f6971:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-02@10": "ee6066f81296:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-03@9": "178610b2eea2:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-03@10": "6fe0fa77480a:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-04@9": "34bd00becb67:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-04@10": "4895ae5d170c:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-05@9": "9ef17b8302e3:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-05@10": "2f8123960301:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-06@9": "4baba0de4d05:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-06@10": "ed91a3766d59:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-07@9": "08e262fd8ab2:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-07@10": "da34200fa1ca:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-08@9": "4eb6af24c02b:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-08@10": "cfac1c2cb2df:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-09@9": "9ee8820bf041:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-09@10": "f6ce6bd015ca:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-10@9": "85a1cbab5a96:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-10@10": "ac1e386377ff:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-11@9": "608c84ffc0bc:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-11@10": "75246b959d50:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-12@9": "ceffb440e286:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-12@10": "15622ea0c966:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-13@9": "e812d8024d48:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-13@10": "52e9c996a046:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-14@9": "1bbb496480ca:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-14@10": "003dca63dc9a:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-15@9": "0097a0850e67:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-15@10": "7c75b8fde831:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-16@9": "d124833a45bc:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-16@10": "72d5d59286f5:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-17@9": "10c9b7d2c34f:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-17@10": "1aac93af8c37:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-18@9": "fa5b7d18b90a:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-18@10": "c72c064dd26b:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-19@9": "aa800792edf0:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-19@10": "3185fa5111ba:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-20@9": "c1338d08d2c7:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-20@10": "55509ec78fdf:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-21@9": "309509a1441b:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-21@10": "ec7ed48f8cfa:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-22@9": "8a9562343f39:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-22@10": "274b69828b43:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-23@9": "8ffd64dca39e:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-23@10": "5e7aeb0b18be:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-24@9": "c661dce8447a:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "gen-24@10": "bc9cea2f0239:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "genmod-00@9": "4148eadfcb15:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-00@10": "eaba2d68af42:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-01@9": "5532dd373f68:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-01@10": "0a5e070e7f1d:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-02@9": "fd0373e5a6be:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-02@10": "42c256c5d11b:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-03@9": "6785b164341b:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-03@10": "25265d2b7e69:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-04@9": "96c91e56be46:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
    "genmod-04@10": "12196ba5deb1:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
}
# c0166 refresh: SchLib model parent indices and common component footprint models.
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
    "blink@ascii": "b325ca426bf8",  # c0148: pin bit 0x20; was 720f981a0f72 (c0126; before, 1896e9b80f88)
    "blink@binary": "3c937de92dc3",  # c0148: pin bit 0x20; was 03ddd9f42c80 (c0126; before, 3b260d5d6088)
    "blink-unmarked@ascii": "5c406bcfd154",  # c0148: pin bit 0x20; was 6f52bcfc5f39 (c0126; ceee4edd66d5)
    "blink-unmarked@binary": "ee01b3e6ab19",  # c0148: pin bit 0x20; was fbdac8c68070 (c0126; b3a1f470ab5d)
    "board_40parts@ascii": "fec95fc341c8",  # c0148: pin bit 0x20; was 32d77f89673d (c0126; e49a072fc1e3)
    "board_40parts@binary": "8a9a84716f40",  # c0148: pin bit 0x20; was 079ad8e43825 (c0126; 9b9770e93ad2)
    "nested@ascii": "696df9464dce",  # c0148: pin bit 0x20; was f345113d40e8 (c0126; before, 2e848e270334)
    "nested@binary": "906f9e55de6b",  # c0148: pin bit 0x20; was 512c741fad8a (c0126; before, 37ba8f5e4210)
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
    "units@ascii": "d218a362172f",  # c0166: source unit link only; was 6f2a800d420b
    "units@binary": "afbcfae8aaf4",  # c0166: source unit link only; was 2f9aab32cdf6
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


def test_the_model_version_is_one() -> None:
    meta = json.loads(build(blink(), 10).files[".fenolite/meta.json"])
    assert meta["schema_version"] == "1.1"
