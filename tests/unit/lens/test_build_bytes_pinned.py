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
"""

from __future__ import annotations

import json

import pytest
from _buildhelp import blink, build
from _pinned import GENERATED, altium_designs, altium_pin, kicad_designs, kicad_pin

KICAD = {
    "blink@9": "0608879703e4:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink@10": "9823ca1a69d9:f7b0acf4424f:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@9": "5e7b124e9d10:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "blink-unmarked@10": "a5680027e942:ed744ee2cb63:810a13bd679f:1574d29ae6c0:b0a47c48ec0c",
    "board_40parts@9": "19b87bdbc8b2:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "board_40parts@10": "ad186ae647db:f04b90eb6000:810a13bd679f:51175ece668c:a5acdc67329e",
    "nested@9": "692b225e5112:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "nested@10": "465cee224705:a06b3fd3486b:810a13bd679f:892eaa0e01c2:4f2246bf324d",
    "units@9": "c6c200996543:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "units@10": "9fb768b11bdb:65a6425e6d34:708c31689bb3:3af5f3d79dd8:b972a2ac1e5e",
    "gen-00@9": "1a6a86949558:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-00@10": "9960da301b91:a8b1364c16d9:810a13bd679f:fa4383128842:14731ea416fb",
    "gen-01@9": "f097f6367651:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-01@10": "2d6cd6dceacd:7cfdbde095bc:c20f83d782c2:cc57f27ca785:beffb7dbde26",
    "gen-02@9": "e991372f2366:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-02@10": "2dbd42ab9422:1da2d897c785:02e287cfa4b2:b0663b5ebb09:59eb0267cb6f",
    "gen-03@9": "866bb9229718:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-03@10": "7f5c83f6b841:f89a2ca72095:d28935f6d87e:c784d33c6787:5597b9313339",
    "gen-04@9": "b0f2e193e3ef:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-04@10": "0d9a3da2d65f:ba9a8f4d9ba7:02e287cfa4b2:654eee3f5729:a2b2f7cd1e77",
    "gen-05@9": "b4df62025ba5:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-05@10": "737b5c19b094:151d0f5056d6:12409c44f1a0:7e49c676c277:de139a1e7d40",
    "gen-06@9": "137a47f13df3:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-06@10": "c721603238e7:5c76f8418552:708c31689bb3:b81fdf5397f6:8006af1fe52b",
    "gen-07@9": "75231b23ceea:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-07@10": "992d0373a58f:21f296ed6f67:f356a9d74d6c:8d75d572c47e:7581134746de",
    "gen-08@9": "0878bbf63d7f:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-08@10": "3149a0cb29fc:75492d991a2a:708c31689bb3:76dd101df67a:a56ca41af2b1",
    "gen-09@9": "74a2874af918:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-09@10": "8cafcf9ea43b:a959a7baa83b:02e287cfa4b2:803aaf55c9d9:499bb0eb0254",
    "gen-10@9": "55b39d884297:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-10@10": "65282f8558e6:0a7fa4e25787:f356a9d74d6c:de86d29e867c:2dfd932222a8",
    "gen-11@9": "f66062e0368e:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-11@10": "5edea5afbd15:bf0a65af737b:810a13bd679f:32fa66993327:df2eef2e5931",
    "gen-12@9": "76cdc4fea2e2:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-12@10": "621d510116c4:f0f94e8418e8:12409c44f1a0:82aa066bb9b3:7258d0a484bb",
    "gen-13@9": "21b8c08b5120:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-13@10": "1096c04f5df8:4010213bdee5:810a13bd679f:079698373e6d:3ceb777e2fee",
    "gen-14@9": "beff41584308:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-14@10": "85fdff6df00c:44dad8830bd6:02e287cfa4b2:e0b91e8e21e9:ca70be51a4e4",
    "gen-15@9": "8b0915ad8e34:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-15@10": "b934aa0156e0:bf4357582910:810a13bd679f:dc991d9b9c6b:4071a697170f",
    "gen-16@9": "521a5f7cfb24:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-16@10": "36adace5a58a:34af963e2787:12409c44f1a0:a935cfb671bf:9a7b83067559",
    "gen-17@9": "368fd10e69ca:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-17@10": "15d0c596c327:7f919c0c0cb8:f356a9d74d6c:8d75d572c47e:50d5079eedb9",
    "gen-18@9": "1f4fa3da2e48:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-18@10": "04c300da3f91:4dc9cf4e6190:810a13bd679f:e3ae803df81f:985493d8fb4d",
    "gen-19@9": "fa237ab0f927:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-19@10": "d561b3633df6:e5cceec40114:f356a9d74d6c:603a561b9a33:f44c3b416e7e",
    "gen-20@9": "4fce27db5a73:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-20@10": "ac82b77874fa:88417a7d9546:f356a9d74d6c:d07796fbce8f:bb3502a49b86",
    "gen-21@9": "2f468b68cb9f:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-21@10": "2c297c737fc0:aa7531ee9b63:708c31689bb3:bb611d2d3478:27fc1c7c4e30",
    "gen-22@9": "c4cd3e13b7a9:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-22@10": "25d67f2b938d:e12c39100855:f356a9d74d6c:c407c34fd61f:6c6c40c5ca23",
    "gen-23@9": "0331a2612250:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-23@10": "1f3c0aeaa27a:8ec0335723b7:f356a9d74d6c:c619712be9e8:b06c32f1875a",
    "gen-24@9": "1d85521e338b:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "gen-24@10": "778525e28bc1:cb36c7ef8bff:810a13bd679f:584d0da9c919:87caee2c2234",
    "genmod-00@9": "69e3049f4a1d:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-00@10": "b8622ee6f476:4dad264512c8:810a13bd679f:fa4383128842:14731ea416fb",
    "genmod-01@9": "5595beea6b41:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-01@10": "f74c2c3a657f:22042b723b0b:f6387ab8afd4:2f8824f76090:7460bd40f2ba",
    "genmod-02@9": "861e7461eb17:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-02@10": "fdad9eb5dd3e:32ded95dfa79:12409c44f1a0:82aa066bb9b3:7b86e4df8795",
    "genmod-03@9": "d8711fe906c0:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-03@10": "6b8444478936:866695877092:98c5fba7152e:c4427361fc4b:0cdeab773043",
    "genmod-04@9": "8babaedea35e:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
    "genmod-04@10": "61b4067a94f8:546f73d38742:f356a9d74d6c:4e16d068e1ac:973511f5cf2f",
}
ALTIUM = {
    "blink@ascii": "1896e9b80f88",
    "blink@binary": "3b260d5d6088",
    "blink-unmarked@ascii": "ceee4edd66d5",
    "blink-unmarked@binary": "b3a1f470ab5d",
    "board_40parts@ascii": "e49a072fc1e3",
    "board_40parts@binary": "9b9770e93ad2",
    "nested@ascii": "2e848e270334",
    "nested@binary": "37ba8f5e4210",
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
    "units@ascii": "9b7b311ae714",
    "units@binary": "d7a85c5bec0e",
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
