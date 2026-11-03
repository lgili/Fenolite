# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authorial common-tool cache proof negatives; mocked runs are not native evidence."""

from __future__ import annotations

from dataclasses import replace
from typing import cast
from unittest.mock import Mock

import pytest

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.sexpr import parse
from fenolite.cli import _derived_cache as cache
from fenolite.cli.errors import CliError

PARENT = """(footprint "Own" (at 1 1) (layer "F.Cu") (property "Reference" "R1")
 (pad "1" smd circle (at 0 0) (size 1 1) (layers "F.Cu")
 (net "N") (teardrops (enabled yes))))
 (segment (start 1 1) (end 1 3) (width 0.2) (layer "F.Cu") (net "N"))"""
ZONE = """(zone (net "N") (layer "F.Cu") (priority 1)
 (attr (teardrop (type padvia)))
 (polygon (pts (xy 0 0) (xy 2 0) (xy 1 2)))
 (filled_polygon (layer "F.Cu") (pts (xy 0 0) (xy 2 0) (xy 1 2))))"""


def board(zones: str = ZONE) -> bytes:
    return f"(kicad_pcb {PARENT} {zones})".encode()


def item(zones: str = ZONE) -> cache.CacheInput:
    config = pro.template(10)
    return cache.CacheInput(
        "own.kicad_pcb",
        {"own.kicad_pcb": board(zones), "own.kicad_pro": pro.write_project_text(config).encode()},
        {"N": ("R1-1",)},
        config,
    )


def tool(outputs: list[dict[str, bytes]], *, code: int = 0, major: int = 10) -> KicadCli:
    mock = Mock(spec=KicadCli)
    mock.major.return_value = major
    mock.version.return_value = "10.0.6" if major == 10 else "9.0.9"
    mock.run.side_effect = [CliRun("exit", code, "authorial mocked output", "", output) for output in outputs]
    return cast(KicadCli, mock)


def test_exact_regenerated_proof_retains_raw_count_delta_and_input_hashes():
    a, b = item(), item("")
    assert cache.eligible(a, b)
    summary, differences = cache.prove(a, b, tool([{"own.kicad_pcb": board()}, {"own.kicad_pcb": board()}]))
    assert differences == () and summary["status"] == "equal"
    assert summary["raw_cache_equality_claimed"] is False
    assert summary["whole_project_json_equality_claimed"] is False
    sides = summary["sides"]
    assert isinstance(sides, dict)
    assert [sides[k]["raw_caches"] for k in ("a", "b")] == [1, 0]
    assert [sides[k]["regenerated_caches"] for k in ("a", "b")] == [1, 1]
    assert a.files["own.kicad_pcb"] == board() and b.files["own.kicad_pcb"] == board("")


@pytest.mark.parametrize(
    "changed",
    [
        ZONE + ZONE,
        ZONE.replace("(xy 1 2)", "(xy 1 2.000000001)"),
        ZONE.replace('(layer "F.Cu")', '(layer "B.Cu")'),
    ],
)
def test_regenerated_full_geometry_duplicate_or_layer_change_fails(changed):
    summary, differences = cache.prove(
        item(), item(""), tool([{"own.kicad_pcb": board()}, {"own.kicad_pcb": board(changed)}])
    )
    assert summary["status"] in {"differs", "native-cache-unqualified"}
    assert len(differences) == 1 and differences[0].level == 7


@pytest.mark.parametrize(
    "output,code,status",
    [
        ({}, 0, "native-failed"),
        ({"own.kicad_pcb": board()}, 1, "native-failed"),
        ({"own.kicad_pcb": board(), "own.kicad_pro": b"changed"}, 0, "native-config-changed"),
        ({"own.kicad_pcb": board().replace(b'"1" smd', b'"2" smd')}, 0, "native-cache-unqualified"),
    ],
)
def test_failed_native_missing_saved_output_config_or_pin_change_never_passes(output, code, status):
    summary, differences = cache.prove(item(), item(""), tool([output], code=code))
    assert summary["status"] == status and len(differences) == 1


def test_native9_refuses_instead_of_claiming_regeneration():
    with pytest.raises(CliError) as error:
        cache.prove(item(), item(""), tool([], major=9))
    assert error.value.code == "FEN-6002"


def test_configuration_missing_or_different_is_not_eligible():
    a, b = item(), item("")
    b.project["board"]["design_settings"].pop("teardrop_options")
    assert not cache.eligible(a, b)
    b = item("")
    b.project["board"]["design_settings"]["rules"]["max_error"] = pro.JsonNumber("0.02")
    assert not cache.eligible(a, b)
    b = item("")
    b.project["board"]["design_settings"]["rules"].pop("min_clearance")
    assert not cache.eligible(a, b)
    b = item("")
    assert not cache.eligible(a, replace(b, bindings={"N": ("R2-1",)}))


def test_raw_native_spelling_binds_only_by_exact_pin_partition():
    source = parse(board().replace(b'net "N"', b'net "{slash}A"').decode())
    assert cache._raw_bindings(source, frozenset({("R1-1",)})) == {"{slash}A": ("R1-1",)}
    with pytest.raises(ValueError, match="partitions changed"):
        cache._raw_bindings(source, frozenset({("R2-1",)}))
    with pytest.raises(ValueError, match="ambiguous"):
        split = PARENT.replace('(net "N")', '(net "Conflicting")')
        cache._raw_bindings(parse(f"(kicad_pcb {PARENT} {split})"), frozenset({("R1-1",)}))


@pytest.mark.parametrize(
    "mutate",
    [
        lambda settings: settings["teardrop_options"][0].update(td_onvia=1),
        lambda settings: settings["teardrop_parameters"][0].update(td_maxlen=True),
        lambda settings: settings["teardrop_parameters"][0].update(td_curve_segcount=pro.JsonNumber("0.5")),
        lambda settings: settings["teardrop_parameters"][0].update(td_maxlen=pro.JsonNumber("0.0000001")),
        lambda settings: settings["teardrop_parameters"][0].update(td_target_name="unknown"),
        lambda settings: settings["teardrop_parameters"][1].update(td_target_name="td_round_shape"),
        lambda settings: settings["teardrop_parameters"][0].update(mystery_effect=True),
        lambda settings: settings["rules"].update(min_clearance=pro.JsonNumber("-1")),
        lambda settings: settings["rules"].update(min_clearance=pro.JsonNumber("0.0000001")),
    ],
)
def test_matching_but_malformed_native_configuration_never_uses_silent_native_defaults(mutate):
    a, b = item(), item("")
    for source in (a, b):
        mutate(source.project["board"]["design_settings"])
    assert not cache.eligible(a, b)


def test_stacked_physical_same_number_same_net_binds_one_electrical_element():
    source = parse(board().decode())
    footprint = source.nodes("footprint")[0]
    pad = footprint.nodes("pad")[0]
    duplicate = footprint.with_children((*footprint.children, pad))
    stacked = source.with_children(
        tuple(duplicate if child is footprint else child for child in source.children)
    )
    assert len(stacked.nodes("footprint")[0].nodes("pad")) == 2
    assert cache._raw_bindings(stacked, frozenset({("R1-1",)})) == {"N": ("R1-1",)}
    conflict = parse(PARENT.split("(segment")[0].replace('(net "N")', '(net "Other")'))
    conflict_pad = conflict.nodes("pad")[0]
    ambiguous = footprint.with_children((*footprint.children, conflict_pad))
    bad = source.with_children(tuple(ambiguous if child is footprint else child for child in source.children))
    with pytest.raises(ValueError, match="ambiguous"):
        cache._raw_bindings(bad, frozenset({("R1-1",)}))


def test_model_stacked_partition_collapses_only_same_net_and_preserves_physical_pads(tmp_path):
    import _drawn_fonts

    from fenolite.api.sides import read_side
    from fenolite.core.ids import derived_id

    source = _drawn_fonts.original(tmp_path / "original", target=10)
    design = read_side(source).design
    assert design.board is not None
    footprint = design.board.footprints[0]
    pad = footprint.pads[0]
    copied = replace(pad, id=derived_id("pad", "authorial-stacked", "second"))
    stacked_fp = replace(footprint, pads=(*footprint.pads, copied))
    stacked_board = replace(design.board, footprints=(stacked_fp, *design.board.footprints[1:]))
    stacked = replace(design, board=stacked_board)
    assert cache._bindings(stacked) == cache._bindings(design)
    assert len(stacked.board.footprints[0].pads) == len(footprint.pads) + 1
    conflicting = replace(copied, net_id=derived_id("net", "authorial-stacked", "other"))
    bad_fp = replace(footprint, pads=(*footprint.pads, conflicting))
    with pytest.raises(ValueError, match="ambiguous"):
        cache._bindings(replace(design, board=replace(design.board, footprints=(bad_fp,))))


@pytest.mark.parametrize("connected", (False, True))
def test_parallel_physical_copies_bind_only_an_identical_complete_electrical_signature(connected):
    from fenolite.backends.kicad.sexpr import dumps

    second = (
        PARENT.replace("(at 1 1)", "(at 4 4)", 1)
        if connected
        else '(footprint "OwnLogo" (layer "F.Cu") (property "Reference" "G***"))'
    )
    duplicates = second if connected else second + second
    root = parse(f"(kicad_pcb {PARENT} {duplicates})")
    before = dumps(root)
    footprints = root.nodes("footprint")
    pads = sum(len(fp.nodes("pad")) for fp in footprints)
    assert cache._raw_bindings(root, frozenset({("R1-1",)})) == {"N": ("R1-1",)}
    assert dumps(root) == before
    assert len(root.nodes("footprint")) == len(footprints)
    assert sum(len(fp.nodes("pad")) for fp in root.nodes("footprint")) == pads


@pytest.mark.parametrize(
    "second", (PARENT.replace('"1" smd', '"2" smd'), PARENT.replace('(net "N")', '(net "Other")'))
)
def test_repeated_reference_requires_the_complete_same_terminal_to_net_mapping(second):
    root = parse(f"(kicad_pcb {PARENT} {second})")
    with pytest.raises(ValueError, match="ambiguous"):
        cache._raw_bindings(root, frozenset({("R1-1",)}))


def test_ambiguous_ref_pad_delimiter_identity_is_not_collapsed():
    first = PARENT.replace('"R1"', '"R-1"')
    second = PARENT.replace('"R1"', '"R"').replace('"1" smd', '"1-1" smd')
    root = parse(f"(kicad_pcb {first} {second})")
    with pytest.raises(ValueError, match="spelling is ambiguous"):
        cache._raw_bindings(root, frozenset({("R-1-1",)}))
