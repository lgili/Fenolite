# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Unused keys change no byte (capability design-model, "Check severities in the rules layer", scenario
"Unused keys change no byte"; change c0114).

``net_ties``, ``waivers`` and ``severities`` are omitted at their defaults, so a design that uses none of
them builds the files it built before they existed. ``RECORDED`` holds the SHA-256 of every file that the
two blink examples build for targets 9 and 10 with a fixed seed and timestamp, recorded on 2026-10-07 at
commit ``f36e08d9``, the commit before the three fields were added. The one value that is not compared is
``fenolite_version`` of ``meta.json``, which a release changes.

A later change that moves a byte of these builds on purpose records the table again with
``FENOLITE_UNUSED_KEYS_PRINT=1 uv run pytest tests/unit/lens/test_unused_keys.py -s -p no:xdist`` and says
so in its own notes; the second assertion (no document holds one of the three keys) stays as it is.

Change c0102 signs the edge uuids of the outline, so the board file, and with its hash ``board.json`` and
``build.json``, were recorded again on 2026-10-08; the fifteen other digests of each build are unchanged.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ("blink_2layer", "blink_routed")
TARGETS = (9, 10)
KEYS = ("net_ties", "waivers", "severities")
PRINT_VARIABLE = "FENOLITE_UNUSED_KEYS_PRINT"
RECORDED: dict[str, dict[str, str]] = {
    "blink_2layer-9": {
        ".fenolite/board.json": "2dc46f96901d3bfd791cd08d8a71bac4eedcc1d05dbee9158ebccc289191ed0e",
        ".fenolite/build.json": "7ab9a6db6e85294a0c6b59abc523688a62ad1ce6187b4885e9982e7ed79f320f",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "d8f3f7c0dd8a890375cf529b249efb1e0e5c613b1c01f8320c2dd98a37895174",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink.kicad_pcb": "a6a99c747690b2620a47c3efe3edfc416492206daccbdde4a66217be273a6851",
        "blink.kicad_pro": "826f307baffa180c68a76ab55d84daf64f4d1ce764128338c8614d18ead41057",
        "blink.kicad_sch": "57a34cc31eb2a70833f61c1fd7d14525d98896bc432405c69a5b234147887fb9",
        "fp-lib-table": "e4c69c740f1d92eda60fb1e81aa65b1606b492a1e691af1fdb0f2cf540eee2bc",
        "lib/Mini.kicad_sym": "79138284b24670145d6eca2ad6863c5855de506ac405a5ba651130e8433b5f17",
        "lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod": (
            "c7b983f563898280b4c7a3d2647653a90e8688505e988dc9d23666748e9a7ee9"
        ),
        "lib/Mini.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod": (
            "796c8dbd4386d3371970294120fe4a56e0766bb1731454ef9dbd89725cd61cf1"
        ),
        "lib/Mini.pretty/Mini_R_0603.kicad_mod": (
            "8a69fd538ee10ea412e2b5cc1c3d63f4834a12c5d1ad45443697d3f3eb65a5b5"
        ),
        "lib/fenolite.kicad_sym": "1411ea9dbd4131ad86b5af2d9b3e165a68264cca8e5ab1889c28c384343c703c",
        "sym-lib-table": "c2dc154da17cded945ae64a8745e52396faa7240ef905976564d7d296716d4e4",
    },
    "blink_2layer-10": {
        ".fenolite/board.json": "03c5e887a4c54cd5186aa4676fb554280a8167a5c2f90a2c7a32242e403ce4c6",
        ".fenolite/build.json": "108924a4d33c7d9ed23df5da4cde1dc69aed3d0504ba2b7de1581b3f75f0d82a",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "d8f3f7c0dd8a890375cf529b249efb1e0e5c613b1c01f8320c2dd98a37895174",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink.kicad_pcb": "4a0471f6a5ef386fa4ddc671ce8fe6697ccd794ded23ca29c420f4994ed1d275",
        "blink.kicad_pro": "77f6a58edf1defbbfb779e406ca6a957724ec8db4b9f877e70dafbbc57777e85",
        "blink.kicad_sch": "ef23e4cc87c4b38a285da43980ba646aa8a496c5e3eabe77127bdbaaaa43a5e7",
        "fp-lib-table": "4f062e901cb3495d31f831532c4ba5978d07b5a1423e870db006f919ab92d001",
        "lib/Mini.kicad_sym": "8e14639415bd075bb21ba9da28fee8817db1ce61b057b621328059ce980f335b",
        "lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod": (
            "c7b983f563898280b4c7a3d2647653a90e8688505e988dc9d23666748e9a7ee9"
        ),
        "lib/Mini.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod": (
            "796c8dbd4386d3371970294120fe4a56e0766bb1731454ef9dbd89725cd61cf1"
        ),
        "lib/Mini.pretty/Mini_R_0603.kicad_mod": (
            "8a69fd538ee10ea412e2b5cc1c3d63f4834a12c5d1ad45443697d3f3eb65a5b5"
        ),
        "lib/fenolite.kicad_sym": "bafa1b6ee0fa27ee4e6fdbf9d652c81454cc2115a489b5765db69d61563541a3",
        "sym-lib-table": "2afe4f59fd648e9c32425bfe03b7be44eb266eee5b815e4527bd35bcdc980e12",
    },
    "blink_routed-9": {
        ".fenolite/board.json": "a60130debc5afd3c178a83ed5b941e300ea15a8d2d707f9dbf0e1cdc9625b547",
        ".fenolite/build.json": "01dd6092d6f467bea156da61ad5ed57ebbd954c138169661a64b5a4aa3f2ec40",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "10f994ace2431b2cbbe721dd4bc06667aa5480683fa1e2ab50198d531e814619",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink_routed.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink_routed.kicad_pcb": "e2de906207dcb0c083531cec53f02fc16077988a2051af5c25f98f9badc8ad06",
        "blink_routed.kicad_pro": "c2a078c5bf8b4193fea929bb1193a741fae887276b0232c47a6e15bc2d9990bb",
        "blink_routed.kicad_sch": "0be2684b76bfcf88d70ac24b61d0d8d758a1787c32088abf8a4b7f8e6ff9c460",
        "fp-lib-table": "e4c69c740f1d92eda60fb1e81aa65b1606b492a1e691af1fdb0f2cf540eee2bc",
        "lib/Mini.kicad_sym": "79138284b24670145d6eca2ad6863c5855de506ac405a5ba651130e8433b5f17",
        "lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod": (
            "c7b983f563898280b4c7a3d2647653a90e8688505e988dc9d23666748e9a7ee9"
        ),
        "lib/Mini.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod": (
            "796c8dbd4386d3371970294120fe4a56e0766bb1731454ef9dbd89725cd61cf1"
        ),
        "lib/Mini.pretty/Mini_R_0603.kicad_mod": (
            "8a69fd538ee10ea412e2b5cc1c3d63f4834a12c5d1ad45443697d3f3eb65a5b5"
        ),
        "lib/fenolite.kicad_sym": "1411ea9dbd4131ad86b5af2d9b3e165a68264cca8e5ab1889c28c384343c703c",
        "sym-lib-table": "c2dc154da17cded945ae64a8745e52396faa7240ef905976564d7d296716d4e4",
    },
    "blink_routed-10": {
        ".fenolite/board.json": "c7f00ebcba76d3ec5e349955fd611555f29bdb7a908c55c94753e2e3dfce770a",
        ".fenolite/build.json": "5cea994f985eea101b3b038f42ddf8d923d4e09663692bb9a661423185b00f6e",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "10f994ace2431b2cbbe721dd4bc06667aa5480683fa1e2ab50198d531e814619",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink_routed.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink_routed.kicad_pcb": "db659fcc223d5ec56f7650dbdacfde1889bd6a6d16f94ccd78d6d31fd820a9a7",
        "blink_routed.kicad_pro": "54cf3550b2eedf65891f47f809504e6d9e1cb9fabc25ea34a316b56edd6c6d96",
        "blink_routed.kicad_sch": "9c40acdf6a2253c3701466b5af672758858e067a53a482e15fae53033c8ddf76",
        "fp-lib-table": "4f062e901cb3495d31f831532c4ba5978d07b5a1423e870db006f919ab92d001",
        "lib/Mini.kicad_sym": "8e14639415bd075bb21ba9da28fee8817db1ce61b057b621328059ce980f335b",
        "lib/Mini.pretty/Mini_LED_THT_3mm.kicad_mod": (
            "c7b983f563898280b4c7a3d2647653a90e8688505e988dc9d23666748e9a7ee9"
        ),
        "lib/Mini.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod": (
            "796c8dbd4386d3371970294120fe4a56e0766bb1731454ef9dbd89725cd61cf1"
        ),
        "lib/Mini.pretty/Mini_R_0603.kicad_mod": (
            "8a69fd538ee10ea412e2b5cc1c3d63f4834a12c5d1ad45443697d3f3eb65a5b5"
        ),
        "lib/fenolite.kicad_sym": "bafa1b6ee0fa27ee4e6fdbf9d652c81454cc2115a489b5765db69d61563541a3",
        "sym-lib-table": "2afe4f59fd648e9c32425bfe03b7be44eb266eee5b815e4527bd35bcdc980e12",
    },
}


def _holds(value: object, key: str) -> bool:
    if isinstance(value, dict):
        return key in value or any(_holds(item, key) for item in value.values())  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    if isinstance(value, list):
        return any(_holds(item, key) for item in value)  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
    return False


def build(example: str, target: int, out: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(out.parent / "kc"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    script = ROOT / "examples" / example / "design.py"
    flags = ["--seed", "1", "--timestamp", "2026-01-01T00:00:00Z", "--kicad-version", str(target)]
    assert cli_main.main(["build", str(script), "--out", str(out), "--confirm", "--json", *flags]) == 0
    return {p.relative_to(out).as_posix(): p.read_bytes() for p in sorted(out.rglob("*")) if p.is_file()}


def digests(files: dict[str, bytes]) -> dict[str, str]:
    found: dict[str, str] = {}
    for rel, data in files.items():
        if rel == ".fenolite/meta.json":
            meta = json.loads(data)
            meta["fenolite_version"] = ""
            data = json.dumps(meta, sort_keys=True).encode()
        found[rel] = hashlib.sha256(data).hexdigest()
    return found


@pytest.mark.parametrize("target", TARGETS)
@pytest.mark.parametrize("example", EXAMPLES)
def test_unused_keys_change_no_byte(
    example: str, target: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = build(example, target, tmp_path / "out", monkeypatch)
    found = digests(files)
    if os.environ.get(PRINT_VARIABLE) == "1":
        print(f'    "{example}-{target}": {json.dumps(found, indent=8)},')  # noqa: T201
    assert found == RECORDED[f"{example}-{target}"]
    for rel, data in files.items():
        if rel.startswith(".fenolite/") and rel.endswith(".json"):
            document = json.loads(data)
            for key in KEYS:
                assert not _holds(document, key), (rel, key)


def test_unused_keys_table_covers_the_layer_documents() -> None:
    assert sorted(RECORDED) == sorted(f"{example}-{target}" for example in EXAMPLES for target in TARGETS)
    for files in RECORDED.values():
        for layer in ("board", "circuit", "findings", "manufacturing", "meta", "rules"):
            assert f".fenolite/{layer}.json" in files
