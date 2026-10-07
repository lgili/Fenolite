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
        ".fenolite/board.json": "07bc758437cbf98a29da5f70a41f03c7998cbcac17cf621a2c009b0a4ec9c33b",
        ".fenolite/build.json": "14c6cc2ad2c227bee6512b37cf439d72df66d58551b1ddce1b0f0582522b1fab",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "d8f3f7c0dd8a890375cf529b249efb1e0e5c613b1c01f8320c2dd98a37895174",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink.kicad_pcb": "22f876f76fe66a7ecbfee21a28e11862d07696f731a227993d24c7ac624f86a2",
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
        ".fenolite/board.json": "92d4403617820108b8c7dbe5e077b8b7d797ca0abf46ea8086a357916f57eaad",
        ".fenolite/build.json": "de0daf678732fa6a0ce5658cafd616c42a0a399434e23f7f1572084d5513bd43",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "d8f3f7c0dd8a890375cf529b249efb1e0e5c613b1c01f8320c2dd98a37895174",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink.kicad_pcb": "23aa2192bc9e1ba756583e6444d1b34ec9c485ba2b3644a16133a83fb9645738",
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
        ".fenolite/board.json": "4c1ec5fa22c1322209d7bf8a58db6e8e24d3521d9ebe266edcacfef0cb6face2",
        ".fenolite/build.json": "8fa1f0113b2145663387babd1c6df8ab49abe03c4aa8e2856be34d2a67712b80",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "10f994ace2431b2cbbe721dd4bc06667aa5480683fa1e2ab50198d531e814619",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink_routed.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink_routed.kicad_pcb": "2796d723eb735048e6d5e4c765bf913b6c27d9fc9c898ac403849027fdb21256",
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
        ".fenolite/board.json": "c89cdf90500c1f507dec4d15f7ed0d674aca1d86a3dd24911f96a7b3ceaa97ce",
        ".fenolite/build.json": "f9ec4c038a2267d7e9e13992b25e1938685c61f0b37a1a4c48af1b75bb2697d9",
        ".fenolite/circuit.json": "705da4a0b455069c68bf620b8079af5b8becda9800ae71c1fe3633a77f2696a3",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "10f994ace2431b2cbbe721dd4bc06667aa5480683fa1e2ab50198d531e814619",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink_routed.kicad_dru": "edd74546c3a662048c2f81cace7014020026bf6586abc6b7333db7df5644bfc7",
        "blink_routed.kicad_pcb": "879962ea43614afa4dd406ea1439e5f10c3125e2d988fd60e5976a65b70a78d6",
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
