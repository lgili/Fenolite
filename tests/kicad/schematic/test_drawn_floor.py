# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native floor carrier/copy-upgrade controls, not legacy grammar claims (c0347)."""

from __future__ import annotations

import dataclasses

import _erc
import _schcorpus
import pytest
from _drawn_corpus import Input, measure
from _drawn_floor import authored_original, bridge_equal, census_equal, digest, original_refusal, signature
from _probes import major, runner

from fenolite.backends.kicad.sexpr import parse_bytes
from fenolite.backends.kicad.versions import FileKind, VersionStatus, inspect
from fenolite.importer.upgrade import upgrader

pytestmark = pytest.mark.needs_kicad
FLOOR_ROWS = tuple(row for row in _schcorpus.rows() if row.origin == "kicad-demos" and "sch-old" in row.uses)


def test_authored_named_original_has_complete_native_pin_islands(tmp_path, record_property) -> None:
    root, files = authored_original()
    cli = runner()
    refusal = original_refusal(files[root])
    assert refusal["status"] == "refused"
    graph = _erc.netlist(cli, root, files)
    proof = signature(graph)
    assert proof["pins"] == proof["groups"] == 34
    assert set(graph) == {f"/AUTH_{index}" for index in range(34)}
    record_property("actual_native_version", cli.version())
    record_property("original_sha256", digest(files[root]))
    if major() == 9:
        return  # Native9 proves the original and does not pretend to implement sch upgrade.
    for name, data in files.items():
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
    before = {name: digest(data) for name, data in files.items()}
    upgraded, receipt = upgrader(cli.path)(tmp_path / root, FileKind.SCHEMATIC)
    assert receipt.sha256_before == before[root] and receipt.sha256_after == digest(upgraded)
    assert receipt.from_version == 20230121 and receipt.tool_version == cli.version()
    assert inspect(parse_bytes(upgraded)).status == VersionStatus.SUPPORTED
    assert before == {name: digest((tmp_path / name).read_bytes()) for name in files}
    changed = {**files, root: upgraded}
    assert bridge_equal(proof, signature(_erc.netlist(cli, root, changed)))
    for name, data in changed.items():
        (tmp_path / name).write_bytes(data)
    inputs = tuple(Input(name, name, digest(data)) for name, data in changed.items())
    result = measure(
        tmp_path, root, inputs, cli, ident="authored-floor-carrier", major=10, native_version=cli.version()
    )
    assert census_equal(result), result
    record_property("upgrade_receipt", str(dataclasses.asdict(receipt)))


@pytest.mark.needs_corpus
@pytest.mark.parametrize("row", FLOOR_ROWS, ids=lambda row: row.id)
def test_declared_floor_copy_evidence(row, tmp_path) -> None:
    import hashlib
    import json
    import os
    import runpy
    import shutil
    from pathlib import Path

    from _corpus import MANIFEST
    from _drawn_floor import probe

    if not row.file.is_file():
        pytest.fail(f"floor input missing: {row.id}", pytrace=False)
    harness = runpy.run_path(str(Path(__file__).with_name("test_drawn_corpus.py")))
    source_major = 9 if "9.0.9.1" in row.tags else 10
    if major() == 9 and source_major != 9:
        pytest.skip("source has no native9 declared context")
    declaration = harness["DECLARED"][row.id]
    assert digest(row.file.read_bytes()) == declaration["sha256"]
    reports = []
    owners = harness["contexts"](source_major).for_row(row.id)
    assert owners, "missing original owner context"
    for index, owner in enumerate(owners):
        assert not owner.errors and owner.data(row.id)["target_instances"]
        folder = tmp_path / f"source-{index}"
        folder.mkdir()
        try:
            from pathlib import PurePosixPath

            prefix = PurePosixPath(owner.root.path).parent
            declared_inputs = []
            for native, item in (
                harness["_schprojects"]._at_tag(harness["_schprojects"].MAJOR_TAGS[source_major]).items()
            ):
                candidate = PurePosixPath(native)
                if prefix not in candidate.parents:
                    continue
                if candidate.suffix not in harness["SUFFIXES"] and candidate.name != "sym-lib-table":
                    continue
                assert item.file.is_file(), f"missing declared floor context input: {item.id}"
                assert digest(item.file.read_bytes()) == harness["DECLARED"][item.id]["sha256"]
                declared_inputs.append(item.id)
            root, inputs = harness["materialize"](harness["BY_ID"][owner.root.id], folder, source_major)
            assert {item.id for item in inputs} == set(declared_inputs)
            relative = Path(row.path).relative_to(Path(owner.root.path).parent).as_posix()
            result = probe(
                folder,
                root,
                relative,
                inputs,
                runner(),
                ident=row.id,
                major=major(),
                code_commit=os.environ.get("GITHUB_SHA", os.environ.get("FENOLITE_DRAWN_CENSUS_SOURCE", "")),
                manifest_sha256=hashlib.sha256(MANIFEST.read_bytes()).hexdigest(),
            )
            result["context"] = owner.data(row.id)
            result["source_major"] = source_major
            reports.append(result)
        finally:
            shutil.rmtree(folder)
    (tmp_path / "drawn-floor.json").write_text(json.dumps(reports, sort_keys=True, indent=2) + "\n")
    expected = "original/refused" if major() == 9 else "upgraded/equal"
    assert all(r["status"] == expected and r["originals_unchanged"] for r in reports), reports
