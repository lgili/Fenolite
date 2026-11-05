# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Identical owner reuse preserves real pipelines and fails closed on changed dependencies."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import _drawn
import _drawn_corpus as census
import pytest
from _drawn_census_reuse import OwnerMeasurements

from fenolite.backends.kicad.cli import KicadCli


@pytest.fixture
def authored(tmp_path, monkeypatch, request):
    output = _drawn.build(getattr(request, "param", "hier"), 9)
    files = {f: b for f, b in output.files.items() if f.endswith(".kicad_sch")}
    # These authored extra inputs need not be read by the drawing, but still bind every lookup.
    files.update({"owner.kicad_pro": b"{}", "lib/Unused.kicad_sym": b"Authored unused library\n"})
    _, own, circuit = _drawn.resolved(output)
    refs = {c.properties["fenolite.path"]: c.ref for c in circuit.components}
    native = {
        net.name or f"AuthoredUnnamed{n}": {(refs[p], pin) for p, pin in net.members}
        for n, net in enumerate(own.nets)
    }
    exports = []

    def exported(cli, root, inputs):
        exports.append((root, tuple(sorted(inputs))))
        return native

    monkeypatch.setattr(census._erc, "netlist", exported)

    def source(name):
        folder = tmp_path / name
        inputs = []
        for file, data in files.items():
            path = folder / file
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            inputs.append(census.Input(file, file, hashlib.sha256(data).hexdigest()))
        return folder, _drawn.root_name(output), inputs, tool

    tool = KicadCli(Path("authored-stub"))
    return SimpleNamespace(
        source=source,
        exports=exports,
        folder=tmp_path,
        tool=tool,
        options={
            "owner": "authored-owner",
            "manifest_sha256": "a" * 64,
            "ident": "authored-child",
            "major": 9,
            "native_version": "authored-stub",
            "code_commit": "b" * 40,
        },
    )


def semantic(report):
    return {k: v for k, v in report.items() if k not in {"measurement", "seconds", "timings"}}


@pytest.mark.parametrize("authored", ("hier", "repeat"), indirect=True)
def test_real_owner_pipeline_equals_uncached_sheet_proof(authored):
    store = OwnerMeasurements()
    first = store.measure(*authored.source("first"), **{**authored.options, "ident": "root"})
    assert not first["measurement"]["reused"] and len(authored.exports) == 2
    second = store.measure(*authored.source("second"), **authored.options)
    assert second["measurement"]["reused"] and len(authored.exports) == 2
    assert second["id"] == "authored-child" and first["id"] == "root"
    uncached = census.measure(
        *authored.source("uncached"),
        **{k: v for k, v in authored.options.items() if k not in {"owner", "manifest_sha256"}},
    )
    assert semantic(second) == semantic(uncached)
    assert second["status"] == "equal" and len(authored.exports) == 4
    encoded = json.dumps(second)
    for value in ("(kicad_sch", "Authored unused library", "Mini:Mini_R", str(authored.folder)):
        assert value not in encoded


@pytest.mark.parametrize("file", ("sheet", "owner.kicad_pro", "lib/Unused.kicad_sym"))
@pytest.mark.parametrize("defect", ("changed", "missing", "declaration"))
def test_current_bytes_and_declarations_cannot_retrieve_a_previous_success(authored, file, defect):
    store = OwnerMeasurements()
    assert store.measure(*authored.source("first"), **authored.options)["status"] == "equal"
    folder, root, inputs, tool = authored.source("changed")
    index = next(n for n, item in enumerate(inputs) if file == item.relative or file == "sheet")
    target = folder / inputs[index].relative
    if defect == "changed":
        target.write_bytes(b"Authored changed payload")
    elif defect == "missing":
        target.unlink()
    else:
        inputs[index] = replace(inputs[index], sha256="0" * 64)
    report = store.measure(folder, root, inputs, tool, **authored.options)
    assert not report["measurement"]["reused"] and report["status"] != "equal"
    assert len(authored.exports) == 2


@pytest.mark.parametrize(
    "change",
    (
        "owner",
        "manifest",
        "version",
        "major",
        "commit",
        "tool",
        "path",
        "timeout",
        "env",
        "cwd",
        "input-id",
        "inventory",
    ),
)
def test_execution_and_complete_input_identity_require_new_measurements(authored, monkeypatch, change):
    store = OwnerMeasurements()
    first = store.measure(*authored.source("first"), **authored.options)
    assert first["status"] == "equal"
    args = list(authored.source("second"))
    options = dict(authored.options)
    if change in {"owner", "manifest", "version", "commit"}:
        field = {"manifest": "manifest_sha256", "version": "native_version", "commit": "code_commit"}.get(
            change, change
        )
        options[field] = "authored-other"
    elif change == "major":
        options["major"] = 10
    elif change == "tool":
        args[3] = KicadCli(Path("authored-stub"))
    elif change == "path":
        authored.tool.path = Path("authored-other-stub")
    elif change == "timeout":
        authored.tool.timeout = 60
    elif change == "env":
        monkeypatch.setenv("FENOLITE_AUTHORED_CENSUS_MODE", "other")
    elif change == "cwd":
        monkeypatch.chdir(args[0])
    elif change == "input-id":
        args[2][0] = replace(args[2][0], id="authored-other-input")
    else:
        args[2] = [i for i in args[2] if i.relative != "lib/Unused.kicad_sym"]
    second = store.measure(*args, **options)
    assert not second["measurement"]["reused"] and len(authored.exports) == 4
    assert second["status"] == "equal"


def test_export_root_is_bound_even_when_both_roots_are_in_the_same_input_inventory(authored):
    folder, root, inputs, tool = authored.source("two-roots")
    alias = "other-root.kicad_sch"
    data = (folder / root).read_bytes()
    (folder / alias).write_bytes(data)
    inputs.append(census.Input("authored-other-root", alias, hashlib.sha256(data).hexdigest()))
    store = OwnerMeasurements()
    first = store.measure(folder, root, inputs, tool, **authored.options)
    assert first["status"] == "equal"
    second = store.measure(folder, alias, inputs, tool, **authored.options)
    assert not second["measurement"]["reused"] and len(authored.exports) == 4


def test_undeclared_copied_file_cannot_retrieve_a_previous_measurement(authored):
    store = OwnerMeasurements()
    store.measure(*authored.source("first"), **authored.options)
    args = authored.source("extra-file")
    (args[0] / "unlisted.kicad_sym").write_bytes(b"Authored unlisted dependency")
    result = store.measure(*args, **authored.options)
    assert not result["measurement"]["reused"] and len(authored.exports) == 4


@pytest.mark.parametrize("status", ("refused", "differs", "internal-error"))
def test_failure_results_never_turn_into_success(authored, monkeypatch, status):
    calls = []

    def failed(*args, **kwargs):
        calls.append(1)
        return {"id": kwargs["ident"], "status": status, "issues": {"lower": {"error:authored": 1}}}

    monkeypatch.setattr(census, "measure", failed)
    store = OwnerMeasurements()
    first = store.measure(*authored.source("first"), **authored.options)
    second = store.measure(*authored.source("second"), **{**authored.options, "ident": "other-sheet"})
    assert first["status"] == second["status"] == status
    assert second["issues"] == first["issues"] and second["id"] == "other-sheet"
    assert second["measurement"]["reused"] == (status != "internal-error")
    assert len(calls) == (2 if status == "internal-error" else 1)


def test_reports_are_independent_and_input_mutation_cannot_seed_reuse(authored, monkeypatch):
    store = OwnerMeasurements()
    first = store.measure(*authored.source("first"), **authored.options)
    expected = copy.deepcopy(first)
    first["inputs"][0]["sha256"] = "changed by report consumer"
    first["counts"].clear()
    second = store.measure(*authored.source("second"), **authored.options)
    assert semantic(second) == semantic(expected)
    assert len(authored.exports) == 2

    actual = census.measure
    calls = []

    def changed(folder, root, inputs, tool, **kwargs):
        calls.append(1)
        report = actual(folder, root, inputs, tool, **kwargs)
        (folder / root).write_bytes(b"Authored changed during measurement")
        return report

    monkeypatch.setattr(census, "measure", changed)
    isolated = OwnerMeasurements()
    for name in ("mutated-first", "mutated-second"):
        result = isolated.measure(*authored.source(name), **authored.options)
        assert result["status"] == "invalid-cache" and not result["measurement"]["reused"]
        assert result["refusal"]["code"] == "measurement-changed"
    assert len(calls) == 2


@pytest.mark.parametrize("name", ("FENOLITE_STATE_DIR", "FENOLITE_LIBRARY_DIR"))
def test_only_empty_per_case_stores_may_change_locations(authored, monkeypatch, tmp_path, name):
    store = OwnerMeasurements()
    for n in range(2):
        empty = tmp_path / f"empty-store-{n}"
        empty.mkdir()
        monkeypatch.setenv(name, str(empty))
        monkeypatch.setenv("PYTEST_CURRENT_TEST", f"authored-case-{n}")
        result = store.measure(*authored.source(f"source-{n}"), **authored.options)
        assert result["measurement"]["reused"] == bool(n)
    assert len(authored.exports) == 2
    (empty / "authored-state").write_text("dependency", encoding="utf-8")
    result = store.measure(*authored.source("populated"), **authored.options)
    assert not result["measurement"]["reused"] and len(authored.exports) == 4
    uncached = []

    def without_override(*args, **kwargs):
        # Exercise refusal to reuse without allowing product code to consult a user's default store.
        uncached.append(1)
        return {"id": kwargs["ident"], "status": "equal"}

    monkeypatch.setattr(census, "measure", without_override)
    monkeypatch.delenv(name)
    result = store.measure(*authored.source("unset"), **authored.options)
    assert not result["measurement"]["reused"] and len(uncached) == 1
