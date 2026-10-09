# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A design that states no height and no height limit writes the bytes it wrote before change c0140
(capability design-dsl, "Part heights in a build"; capability design-model, "Height limits in the model").

The KiCad builds of the two blink examples for targets 9 and 10 are pinned by ``test_unused_keys.py``
(change c0114), which this change leaves as it is and which still passes. ``RECORDED`` holds the SHA-256
of every file of their Altium builds with a fixed seed and timestamp, recorded on 2026-10-08 at commit
``30bbffd`` of ``v04``, the commit before task 1.1 of c0140; as there, ``fenolite_version`` of
``meta.json`` is not compared. A later change that moves a byte of these builds on purpose records the
table again and says so in its own notes. Recorded again when c0140 was stacked on v0.4 after its rebase
onto 0.3.0, on the commit before c0140 there (the c0118 commit): 0.3.0 changed the Altium build (c0146's
font table and c0148's pin bits move the ``.SchDoc`` and ``.SchLib``; c0126 stores footprint items in
``.fenolite/board.json``, and ``build.json`` follows), and the build with c0140 gives the same table."""

from __future__ import annotations

import hashlib
import io
import json
import runpy
from pathlib import Path

import pytest
from _buildhelp import build

import fenolite.cli.main as cli_main
from fenolite.dsl import Design, heights, mm, to_model
from fenolite.model import canonical

ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = ROOT / "examples"
SCRIPTS = ("blink_2layer", "blink_routed")
RECORDED: dict[str, dict[str, str]] = {
    "blink_2layer": {
        ".fenolite/board.json": "c5eda4a1cdb0bf5a03f747d3e17c6609e64a7a63f6d8a1c6a0b4762c001af202",
        ".fenolite/build.json": "e2cbc8ac1c1b4905d2e66f2676ce5e03dfec09fc22b453bafbc0a11aabe82c84",
        ".fenolite/circuit.json": "b65a512b111fb99b619e4622bd5cb7f4fb5d9107ced2d6a9425a6e178e01ee7f",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "d8f3f7c0dd8a890375cf529b249efb1e0e5c613b1c01f8320c2dd98a37895174",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink.OutJob": "0a24a3b5d6eca281058a65aad86195bc159a7635756a409f8dae7954f894b436",
        "blink.PcbDoc": "642ce93cdfd14136c421406e3ba261aab055fcdb437dff9cfc9fefebdd3e0a32",
        "blink.PcbLib": "8fca33bda63bc3846e99478aa76f20e248026aefa0addd6e6e4ce9e9314c0082",
        "blink.PrjPcb": "2c0fc10e49421372d5f65721d882751188c3eb42ee6b9fa5c43c7a45ba11b00c",
        "blink.SchDoc": "9707faf2c4ccf508e1c57256de9dfcdda838a42c2165e99c23c489133d19aca4",
        "blink.SchLib": "1c97388753b0826ae3029506aad502cc0c63b65a6a72f0d0ac3cb374a347c48d",
    },
    "blink_routed": {
        ".fenolite/board.json": "e461b091e03652df7adee52a7e8070ab479270efb12fcf9b47ab0cf7866f2ceb",
        ".fenolite/build.json": "a85dddc544b48c9f09402454755d37d4323781fccf79e617a06470a9f2db481c",
        ".fenolite/circuit.json": "b65a512b111fb99b619e4622bd5cb7f4fb5d9107ced2d6a9425a6e178e01ee7f",
        ".fenolite/findings.json": "ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356",
        ".fenolite/manufacturing.json": "2a4f17be347dc9e374fe86cb3576b7faf3d4d15113620b0578b6dfd8019fc358",
        ".fenolite/meta.json": "10f994ace2431b2cbbe721dd4bc06667aa5480683fa1e2ab50198d531e814619",
        ".fenolite/rules.json": "3b6c856c3b9cf3c2d078597ebdf90a177882f9272e8fea1cc152620561b9341a",
        "blink_routed.OutJob": "595be494ec0a3ce8edc084cd041d86b2fe4bab9cd94f05b5a7e557864f44f950",
        "blink_routed.PcbDoc": "6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a",
        "blink_routed.PcbLib": "640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce",
        "blink_routed.PrjPcb": "99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d",
        "blink_routed.SchDoc": "c1c352438adcc9e0ff6ae003fb9123f5a83bf3e06f42de6f7f448da0b56b29a6",
        "blink_routed.SchLib": "dbf42173ddc92546f5cadc049ef8b05499d98573f227a54a14d8a0e75a554166",
    },
}


def example(name: str) -> Design:
    design = runpy.run_path(str(EXAMPLES / name / "design.py"))["design"]
    assert isinstance(design, Design)
    return design


def _digests(out: Path) -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted(out.rglob("*")):
        if not path.is_file():
            continue
        rel, data = path.relative_to(out).as_posix(), path.read_bytes()
        if rel == ".fenolite/meta.json":
            meta = json.loads(data)
            meta["fenolite_version"] = ""
            data = json.dumps(meta, sort_keys=True).encode()
        found[rel] = hashlib.sha256(data).hexdigest()
    return found


@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_heights_change_no_altium_byte(
    name: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    monkeypatch.setattr("sys.stdout", io.StringIO())
    monkeypatch.setattr("sys.stderr", io.StringIO())
    script = EXAMPLES / name / "design.py"
    flags = ["--seed", "1", "--timestamp", "2026-01-01T00:00:00Z"]
    argv = ["build", str(script), "--out", str(out), "--target", "altium", "--confirm", "--json", *flags]
    assert cli_main.main(argv) == 0
    assert _digests(out) == RECORDED[name]


@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_heights_are_not_in_the_model_texts(name: str) -> None:
    design = example(name)
    assert dict(heights(design)) == {}
    texts = canonical.dump_texts(to_model(design))
    assert "heights" not in json.loads(texts["rules.json"])
    assert '"bodies"' not in "".join(texts.values())


@pytest.mark.parametrize("target", [9, 10])
@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_heights_are_not_in_the_built_cache(name: str, target: int) -> None:
    output = build(example(name), target, project_dir=EXAMPLES / name)
    assert "heights" not in json.loads(output.files[".fenolite/rules.json"])
    assert b'"bodies"' not in output.files[".fenolite/board.json"]


@pytest.mark.parametrize("name", SCRIPTS)
def test_unused_keys_heights_change_only_the_rules_layer_when_used(name: str) -> None:
    before = canonical.dump_texts(to_model(example(name)))
    design = example(name)
    design.height_limit("LID", max=mm(5))
    after = canonical.dump_texts(to_model(design))
    assert {file for file in before if before[file] != after[file]} == {"rules.json"}
    rules = json.loads(after["rules.json"])
    assert list(rules)[-1] == "heights" and rules["heights"] == [{"area": "LID", "max": 5_000_000}]
