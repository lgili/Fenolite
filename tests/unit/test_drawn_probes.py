# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The five required drawn probe records, with no external CAD or corpus execution."""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

IDS = frozenset({"drawn-connect", "drawn-names", "drawn-bus", "drawn-repeat", "drawn-write"})
TESTS = Path(__file__).resolve().parents[1]


def oracle_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    root = TESTS / "kicad"
    folders = sorted(p for p in root.iterdir() if p.is_dir() and any(p.glob("_*.py")))
    for folder in (root, *folders, TESTS):
        monkeypatch.syspath_prepend(str(folder))


def test_five_probes_registered_without_native_execution(monkeypatch: pytest.MonkeyPatch) -> None:
    oracle_paths(monkeypatch)
    from fenolite.backends.kicad.cli import KicadCli

    def no_native(*args: object, **kwargs: object) -> None:
        raise AssertionError("registration must not execute any native probe")

    monkeypatch.setattr(KicadCli, "run", no_native)
    probes = importlib.import_module("_probes")
    assert IDS <= probes.PROBES.keys(), sorted(IDS - probes.PROBES.keys())
    assert all(probes.PROBES[pid].majors == (9, 10) for pid in IDS)


@pytest.fixture
def bench(monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Original fake physical pins/export packets; never invokes an external tool."""
    import copy
    from collections import Counter
    from types import SimpleNamespace

    oracle_paths(monkeypatch)
    from fenolite.backends.kicad.cli import KicadCli

    def no_native(*args: object, **kwargs: object) -> None:
        raise AssertionError("hermetic fixture attempted native execution")

    monkeypatch.setattr(KicadCli, "run", no_native)
    helper = importlib.import_module("_drawn_probe")
    erc = importlib.import_module("_erc")
    draw = importlib.import_module("_drawn")
    helper.clear_native_cache()
    state = SimpleNamespace(
        helper=helper,
        cli=SimpleNamespace(path=Path("authored-native-tool")),
        native={"N": {("R1", "1"), ("R2", "1")}},
        name="N",
        members=(("r1", "1"), ("r2", "1")),
        inputs=b"authored",
        erc_code=0,
        erc_data={"sheets": [{"violations": []}]},
        netlist_fail=False,
        calls=Counter(),
    )
    components = tuple(SimpleNamespace(ref=f"R{i}", properties={"fenolite.path": f"r{i}"}) for i in (1, 2, 3))
    circuit = SimpleNamespace(components=components)

    def build(name: str, target: int):  # type: ignore[no-untyped-def]
        return SimpleNamespace(
            files={
                f"{name}.kicad_sch": state.inputs,
                "child/sheet.kicad_sch": b"child",
                "sym-lib-table": b"table",
            },
            design=SimpleNamespace(circuit=circuit),
        )

    def resolved(output):  # type: ignore[no-untyped-def]
        return (
            None,
            SimpleNamespace(
                pins=(("r1", "1"), ("r2", "1"), ("r3", "1")),
                nets=(SimpleNamespace(name=state.name, members=state.members),),
                open=(("r3", "1"),),
            ),
            circuit,
        )

    def netlist(*args, **kwargs):  # type: ignore[no-untyped-def]
        state.calls["netlist"] += 1
        if state.netlist_fail:
            raise AssertionError("authored failed native export")
        return copy.deepcopy(state.native)

    def report(*args, **kwargs):  # type: ignore[no-untyped-def]
        state.calls["erc"] += 1
        return erc.Report(state.erc_code, copy.deepcopy(state.erc_data), "authored stderr")

    monkeypatch.setattr(helper, "build", build)
    monkeypatch.setattr(draw, "resolved", resolved)
    monkeypatch.setattr(erc, "netlist", netlist)
    monkeypatch.setattr(erc, "run_erc", report)
    state.probes = helper.drawn_probes(lambda: state.cli, lambda: "10.0.6")
    yield state
    helper.clear_native_cache()


def test_native_omitted_open_singleton_remains_accepted(bench) -> None:  # type: ignore[no-untyped-def]
    assert bench.probes["drawn-connect"][0]() == "equal"
    found = bench.helper.observe("flat", 10, bench.cli, version="10.0.6")
    assert frozenset({("R3", "1")}) in found.ours == found.theirs


def test_missing_connected_pin_is_not_hidden_as_an_open_singleton(bench) -> None:  # type: ignore[no-untyped-def]
    bench.native = {"N": {("R1", "1")}}
    assert bench.probes["drawn-connect"][0]() == "different"
    found = bench.helper.observe("flat", 10, bench.cli, version="10.0.6")
    assert frozenset({("R2", "1")}) in found.theirs
    assert frozenset({("R1", "1"), ("R2", "1")}) in found.ours


def test_native_extra_pin_outside_the_original_drawn_domain_is_unchanged(bench) -> None:  # type: ignore[no-untyped-def]
    bench.native["N"].add(("UNRELATED", "9"))
    assert bench.probes["drawn-connect"][0]() == "equal"


def test_names_differ_without_changing_connectivity_or_its_warning_policy(bench) -> None:  # type: ignore[no-untyped-def]
    bench.native = {"OTHER": {("R1", "1"), ("R2", "1")}}
    assert bench.probes["drawn-connect"][0]() == "equal"
    assert bench.probes["drawn-names"][0]() == "different"
    assert bench.probes["drawn-bus"][0]() == bench.probes["drawn-repeat"][0]() == "equal"


def test_comparisons_are_fresh_even_when_native_io_is_reused(bench) -> None:  # type: ignore[no-untyped-def]
    first = bench.helper.observe("flat", 10, bench.cli, version="10.0.6")
    bench.name = "EDITED"
    second = bench.helper.observe("flat", 10, bench.cli, version="10.0.6")
    assert not first.differing_names and second.differing_names == {"EDITED": "N"}
    assert bench.calls["netlist"] == 1


def test_five_probes_share_only_native_io_and_do_not_call_unrelated_probes(bench, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    probes = importlib.import_module("_probes")

    def no_aggregate(*args: object, **kwargs: object) -> None:
        raise AssertionError("full probe aggregator/DIFAT is forbidden")

    monkeypatch.setattr(probes, "outcomes", no_aggregate)
    for pid in IDS:
        assert bench.probes[pid][0]() == "equal"
    assert bench.calls == {"netlist": 6, "erc": 6}


def test_complete_native_input_tool_and_root_identity_is_in_the_cache_key(bench) -> None:  # type: ignore[no-untyped-def]
    call = bench.helper.native_netlist
    files = {"root.kicad_sch": b"root", "child/sheet.kicad_sch": b"child", "sym-lib-table": b"table"}
    call(bench.cli, "root.kicad_sch", files, version="10.0.6")
    call(bench.cli, "root.kicad_sch", files, version="10.0.6")
    assert bench.calls["netlist"] == 1
    for changed in (
        {**files, "root.kicad_sch": b"edited root"},
        {**files, "child/sheet.kicad_sch": b"edited child"},
        {**files, "sym-lib-table": b"edited table"},
        {**files, "added": b"new"},
    ):
        call(bench.cli, "root.kicad_sch", changed, version="10.0.6")
    call(bench.cli, "child/sheet.kicad_sch", files, version="10.0.6")
    call(bench.cli, "root.kicad_sch", files, version="9.0.9")
    bench.cli.path = Path("different-pinned-image")
    call(bench.cli, "root.kicad_sch", files, version="10.0.6")
    assert bench.calls["netlist"] == 8


def test_returned_native_maps_cannot_mutate_cached_io(bench) -> None:  # type: ignore[no-untyped-def]
    call = bench.helper.native_netlist
    first = call(bench.cli, "root.kicad_sch", {"a": b"a"}, version="10.0.6")
    first["N"].clear()
    second = call(bench.cli, "root.kicad_sch", {"a": b"a"}, version="10.0.6")
    assert second["N"] == {("R1", "1"), ("R2", "1")}
    assert bench.calls["netlist"] == 1


def test_failed_export_is_never_a_positive_cache_entry(bench) -> None:  # type: ignore[no-untyped-def]
    bench.netlist_fail = True
    with pytest.raises(AssertionError, match="failed native export"):
        bench.helper.observe("flat", 10, bench.cli, version="10.0.6")
    bench.netlist_fail = False
    assert bench.helper.observe("flat", 10, bench.cli, version="10.0.6").ours
    assert bench.calls["netlist"] == 2


@pytest.mark.parametrize("code", [1, None])
def test_failed_or_timed_out_erc_cannot_pass_or_fill_positive_cache(bench, code) -> None:  # type: ignore[no-untyped-def]
    bench.erc_code = code
    assert bench.probes["drawn-write"][0]() == "different"
    bench.erc_code = 0
    assert bench.probes["drawn-write"][0]() == "equal"
    assert bench.calls["erc"] == 7


def test_absent_or_malformed_erc_is_not_cached(bench) -> None:  # type: ignore[no-untyped-def]
    bench.erc_data = None
    assert bench.probes["drawn-write"][0]() == "different"
    bench.erc_data = ["malformed"]
    with pytest.raises(ValueError, match="ERC report"):
        bench.probes["drawn-write"][0]()
    bench.erc_data = {"sheets": [{"violations": []}]}
    assert bench.probes["drawn-write"][0]() == "equal"
    assert bench.calls["erc"] == 8


def test_erc_cache_returns_independent_report_data(bench) -> None:  # type: ignore[no-untyped-def]
    first = bench.helper.native_erc(bench.cli, "root", {"a": b"a"}, version="10.0.6")
    first.data["sheets"].append({"violations": [{"type": "wire_dangling"}]})
    second = bench.helper.native_erc(bench.cli, "root", {"a": b"a"}, version="10.0.6")
    assert second.data == {"sheets": [{"violations": []}]}
    assert bench.calls["erc"] == 1


@pytest.mark.parametrize("kind,expected", [("wire_dangling", "different"), ("pin_not_connected", "equal")])
def test_original_erc_connectivity_policy_is_unchanged(bench, kind, expected) -> None:  # type: ignore[no-untyped-def]
    bench.erc_data = {"sheets": [{"violations": [{"type": kind}]}]}
    assert bench.probes["drawn-write"][0]() == expected


def test_pinned_docker_images_with_the_same_version_have_separate_io(bench) -> None:  # type: ignore[no-untyped-def]
    from fenolite.backends.kicad.cli import DockerCli

    first = DockerCli("authored/image@sha256:" + "1" * 64)
    second = DockerCli("authored/image@sha256:" + "2" * 64)
    for cli in (first, second):
        bench.helper.native_netlist(cli, "root", {"a": b"a"}, version="10.0.6")
    assert bench.calls["netlist"] == 2


def test_observe_and_write_use_the_isolated_source_builder(bench, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    def unsafe_original(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise AssertionError("original source builder must not run")

    monkeypatch.setattr(bench.helper._drawn, "build", unsafe_original)
    assert bench.probes["drawn-connect"][0]() == "equal"
    assert bench.probes["drawn-write"][0]() == "equal"


@pytest.mark.parametrize("name", ("flat", "full", "hier", "bus", "repeat", "example"))
@pytest.mark.parametrize("target", (9, 10))
def test_source_builder_keeps_all_original_bytes_and_is_deterministic(
    monkeypatch: pytest.MonkeyPatch, name: str, target: int
) -> None:
    oracle_paths(monkeypatch)
    helper = importlib.import_module("_drawn_probe")
    original = helper._drawn.folder(name)

    def contents() -> dict[str, bytes]:
        return {
            p.relative_to(original).as_posix(): p.read_bytes() for p in original.rglob("*") if p.is_file()
        }

    before = contents()
    assert "design.lock" not in before
    first = helper.build(name, target)
    second = helper.build(name, target)
    assert dict(first.files) == dict(second.files)
    assert contents() == before
    assert not (original / "design.lock").exists()


@pytest.mark.parametrize("kind", ("pin_not_connected", "pin_not_driven", "lib_symbol_issues"))
@pytest.mark.parametrize("severity", ("warning", "error"))
def test_successful_erc_keeps_nonconnective_findings_accepted(bench, kind, severity) -> None:  # type: ignore[no-untyped-def]
    bench.erc_data = {"sheets": [{"violations": [{"type": kind, "severity": severity}]}]}
    assert bench.probes["drawn-write"][0]() == "equal"


@pytest.mark.parametrize("code", (2, 3, 4, 5))
def test_unrequested_violation_exit_flag_does_not_turn_execution_errors_into_success(bench, code) -> None:  # type: ignore[no-untyped-def]
    # run_erc has exit_code=False: native findings return0; exit5 requires the flag.
    bench.erc_code = code
    assert bench.probes["drawn-write"][0]() == "different"


@pytest.mark.parametrize(
    "data",
    (
        {},
        {"sheets": {}},
        {"sheets": [None]},
        {"sheets": [{}]},
        {"sheets": [{"violations": {}}]},
        {"sheets": [{"violations": [None]}]},
        {"sheets": [{"violations": [{"type": 7}]}]},
    ),
)
def test_invalid_erc_structure_is_refused_and_never_cached(bench, data) -> None:  # type: ignore[no-untyped-def]
    bench.erc_data = data
    with pytest.raises(ValueError, match="ERC report"):
        bench.probes["drawn-write"][0]()
    bench.erc_data = {"sheets": [{"violations": []}]}
    assert bench.probes["drawn-write"][0]() == "equal"
    assert bench.calls["erc"] == 7
