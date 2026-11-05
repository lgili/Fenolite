# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 numeric-netcode/table-order controls, never a Royal normalizer (c0355)."""

from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path

import _kicad
import pytest
from _drawn_curve import curve_project
from _native_netcode_refs import exact_labelled_partitions, netcode_reference_facts
from _native_numeric_roles import (
    NONREFERENCE_PLOT_NUMBERS,
    NONREFERENCE_PROJECT_NUMBERS,
    SCHEMA_VERSION_PROJECT_NUMBERS,
)

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.derived_teardrops import regions
from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse, parse_bytes

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("no_net_shape", ("npth-circle", "smd-rect", "smd-roundrect", "smd-custom"))
def test_authored_netcode_renumber_and_table_order(tmp_path: Path, no_net_shape: str):
    if not _kicad.supported_version().startswith("10."):
        pytest.skip("actual native10 refill control only")
    source = curve_project(tmp_path / "source", 9, 10_000)
    path = source / "font_probe.kicad_pcb"
    original = parse_bytes(path.read_bytes())
    assert {n.atoms()[0].value for n in original.nodes("net")} == {"0", "1"}

    def renumber(root, old, new):
        def walk(node, parent=None, grandparent=None):
            if isinstance(node, Atom):
                return node
            electrical = parent in {"segment", "via", "zone", "arc"} and grandparent == "kicad_pcb"
            electrical |= parent == "pad" and grandparent == "footprint"
            if node.name == "net" and (parent == "kicad_pcb" or electrical):
                atoms = node.atoms()
                if atoms[0].value == str(old):
                    return node.with_children((Atom.integer(new), *node.children[1:]))
            return node.with_children(tuple(walk(c, node.name, parent) for c in node.children))

        return walk(root)

    # Add a second independently routed original physical pair, 5mm below the first. All clone IDs
    # are new authored UUIDs; thereafter every measured variant preserves the exact same identities.
    fp = original.nodes("footprint")[0]
    track = original.nodes("segment")[0]

    def clone(node, parent=None):
        if isinstance(node, Atom):
            return node
        children = tuple(clone(c, node.name) for c in node.children)
        if node.name in {"uuid", "tstamp"}:
            children = (
                Atom.string(
                    str(uuid.uuid5(uuid.NAMESPACE_URL, "Fenolite c0355 second pair " + node.atoms()[0].value))
                ),
            )
        elif node.name == "net":
            children = (
                (Atom.integer(2), Atom.string("SECOND_PROBE"))
                if len(node.atoms()) == 2
                else (Atom.integer(2),)
            )
        elif node.name == "property" and node.atoms()[:1] and node.atoms()[0].value == "Reference":
            children = (children[0], Atom.string("R2"), *children[2:])
        elif (parent == "footprint" and node.name == "at") or (
            parent == "segment" and node.name in {"start", "end"}
        ):
            children = (children[0], Atom.from_nm(node.atoms()[1].to_nm() + 5_000_000), *children[2:])
        return node.with_children(children)

    declaration = original.nodes("net")[1].with_children((Atom.integer(2), Atom.string("SECOND_PROBE")))
    kind, shape = no_net_shape.split("-", 1)
    kind = "np_thru_hole" if kind == "npth" else kind
    settings = (
        '(drill 0.5) (layers "*.Cu" "*.Mask")'
        if kind == "np_thru_hole"
        else '(layers "F.Cu" "F.Paste" "F.Mask")'
    )
    if shape == "roundrect":
        settings += " (roundrect_rratio 0.25)"
    elif shape == "custom":
        settings += (
            " (options (clearance outline) (anchor rect)) (primitives (gr_poly "
            "(pts (xy -0.5 -0.5) (xy 0.5 -0.5) (xy 0.5 0.5) (xy -0.5 0.5)) (width 0) (fill yes)))"
        )
    no_net = parse(
        f'(pad "" {kind} {shape} (at 5 -5) (size 1 1) {settings} '
        '(uuid "00000000-0000-4000-8000-000000003556"))'
    )
    first = fp.with_children((*fp.children, no_net))
    original = original.with_children(
        (
            *(first if child is fp else child for child in original.children),
            declaration,
            clone(fp),
            clone(track),
        )
    )
    expected = {"FONT_PROBE": ("R1-1", "R1-2"), "SECOND_PROBE": ("R2-1", "R2-2")}
    assert exact_labelled_partitions(original, expected) == expected

    # Original authored baseline chooses a high code to avoid mistaking known coordinate/enum values
    # for references. No exemptions are inferred or needed; every affected numeric occurrence is bound.
    baseline = renumber(renumber(original, 1, 100_003), 2, 100_007)
    table = iter(reversed(baseline.nodes("net")))
    reordered = baseline.with_children(
        tuple(next(table) if isinstance(c, Node) and c.name == "net" else c for c in baseline.children)
    )
    changed_code = renumber(renumber(baseline, 100_003, 100_019), 100_007, 100_021)
    assert renumber(renumber(changed_code, 100_019, 100_003), 100_021, 100_007) == baseline
    assert tuple(c for c in reordered.children if not isinstance(c, Node) or c.name != "net") == tuple(
        c for c in baseline.children if not isinstance(c, Node) or c.name != "net"
    )
    # The only native companion requested in this narrow board-only control is its explicit project.
    # No schematic parity, external library loading or non-JSON companion acceptance is claimed.
    files = {
        "font_probe.kicad_pro": (source / "font_probe.kicad_pro").read_bytes(),
        "font_probe.kicad_dru": b"(version 1)\n",
    }
    native = KicadCli(Path(_kicad.cli()))
    receipts = []
    exact = []
    for label, root in (
        ("baseline", baseline),
        ("table-order-only", reordered),
        ("netcode-only", changed_code),
    ):
        facts = netcode_reference_facts(root, files)
        assert facts["unnumbered_no_net_pads"] == 1
        assert exact_labelled_partitions(root, expected) == expected
        folder = tmp_path / label
        folder.mkdir()
        board = folder / path.name
        body = dumps(root).encode()
        board.write_bytes(body)
        result = native.refill(board, files=files)
        assert result.run.ok and result.board is not None
        (folder / "native-saved.kicad_pcb").write_bytes(result.board)
        parsed = parse_bytes(result.board)
        physical = [pad for foot in parsed.nodes("footprint") for pad in foot.nodes("pad")]
        assert len(physical) == 5
        assert len([pad for pad in physical if pad.atoms()[0].value == "" and not pad.nodes("net")]) == 1
        labelled = exact_labelled_partitions(parsed, expected)
        assert labelled == expected
        geometry = regions(parsed, labelled)
        assert geometry
        exact.append(geometry)
        receipts.append(
            {
                "case": label,
                "input_sha256": hashlib.sha256(body).hexdigest(),
                "native_saved_sha256": hashlib.sha256(result.board).hexdigest(),
                "geometry_sha256": hashlib.sha256(repr(geometry).encode()).hexdigest(),
                "geometry_regions": len(geometry),
                "reference_facts": facts,
                "literal_name_to_complete_physical_terminals": labelled,
                "physical_pad_count": len(physical),
                "unnumbered_omitted_no_net_pads": 1,
            }
        )
    (tmp_path / "native-netcode-order-proof.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "authored_no_net_shape": no_net_shape,
                "cases": receipts,
                "table_order_geometry_equal": exact[0] == exact[1],
                "netcode_geometry_equal": exact[0] == exact[2],
                "royal_transformed_or_runtime_claimed": False,
            },
            sort_keys=True,
            indent=2,
        )
        + "\n"
    )


def _set_pointer(data: dict, pointer: str, value: object) -> None:
    """Create the authored leaf; ``*`` makes a one-element array of objects (or of numbers at the end)."""
    parts = pointer.split("/")
    node: object = data
    for index, part in enumerate(parts):
        last = index == len(parts) - 1
        following = None if last else parts[index + 1]
        if part == "*":
            assert isinstance(node, list)
            if last:
                node[:] = [value]
                return
            if not node or not isinstance(node[0], dict):
                node[:] = [{}]
            node = node[0]
            continue
        assert isinstance(node, dict)
        if last:
            node[part] = value
            return
        if following == "*":
            if not isinstance(node.get(part), list):
                node[part] = []
        elif not isinstance(node.get(part), dict):
            node[part] = {}
        node = node[part]


def test_project_and_plot_numbers_are_not_netcode_references(tmp_path: Path):
    """c0384 0.4: every listed project/plot numeric equals a board netcode, then only the netcode changes."""
    if not _kicad.supported_version().startswith("10."):
        pytest.skip("actual native10 refill control only")
    source = curve_project(tmp_path / "source", 9, 10_000)
    path = source / "font_probe.kicad_pcb"
    original = parse_bytes(path.read_bytes())
    assert {n.atoms()[0].value for n in original.nodes("net")} == {"0", "1"}
    collision = 1  # the authored board's only nonzero netcode
    plot = parse(
        "(pcbplotparams " + " ".join(f"({name} {collision})" for name in NONREFERENCE_PLOT_NUMBERS) + ")"
    )
    setup = original.nodes("setup")[0]
    kept = tuple(c for c in setup.children if not (isinstance(c, Node) and c.name == "pcbplotparams"))
    baseline = original.with_children(
        tuple(setup.with_children((*kept, plot)) if c is setup else c for c in original.children)
    )

    def renumber(root: Node, old: int, new: int) -> Node:
        def walk(node, parent=None, grandparent=None):
            if isinstance(node, Atom):
                return node
            electrical = parent in {"segment", "via", "zone", "arc"} and grandparent == "kicad_pcb"
            electrical |= parent == "pad" and grandparent == "footprint"
            if (
                node.name == "net"
                and (parent == "kicad_pcb" or electrical)
                and node.atoms()[0].value == str(old)
            ):
                return node.with_children((Atom.integer(new), *node.children[1:]))
            return node.with_children(tuple(walk(c, node.name, parent) for c in node.children))

        return walk(root)

    moved = renumber(baseline, collision, 100_009)
    assert {n.atoms()[0].value for n in moved.nodes("net")} == {"0", "100009"}
    project = json.loads((source / "font_probe.kicad_pro").read_text())
    versions = {}
    for pointer in NONREFERENCE_PROJECT_NUMBERS:
        _set_pointer(project, pointer, collision)
    for pointer in SCHEMA_VERSION_PROJECT_NUMBERS:
        node: object = project
        for part in pointer.split("/"):
            node = node.get(part) if isinstance(node, dict) else None
        versions[pointer] = node  # the native-written value is kept; a changed version is a migration
    project_bytes = (json.dumps(project, indent=2, sort_keys=True) + "\n").encode()
    files = {"font_probe.kicad_pro": project_bytes, "font_probe.kicad_dru": b"(version 1)\n"}
    expected = {"FONT_PROBE": ("R1-1", "R1-2")}
    native = KicadCli(Path(_kicad.cli()))
    observed = []
    for label, root in (("netcode-equals-every-setting", baseline), ("renumbered-netcode", moved)):
        folder = tmp_path / label
        folder.mkdir()
        board = folder / path.name
        board.write_bytes(dumps(root).encode())
        result = native.refill(board, files=files)
        assert result.run.ok and result.board is not None
        saved = parse_bytes(result.board)
        labelled = exact_labelled_partitions(saved, expected)
        assert labelled == expected
        report = json.loads(result.run.outputs["drc.json"].decode())
        violations = sorted(
            (v.get("type"), v.get("severity"), v.get("description"), len(v.get("items", [])))
            for key in ("violations", "unconnected_items", "schematic_parity")
            for v in report.get(key, [])
        )
        plot_saved = {
            child.name: child.atoms()[0].value
            for params in saved.nodes("setup")[0].nodes("pcbplotparams")
            for child in params.nodes()
            if child.name in NONREFERENCE_PLOT_NUMBERS
        }
        rewritten = {name: data == files[name] for name, data in result.run.outputs.items() if name in files}
        observed.append((regions(saved, labelled), violations, plot_saved, rewritten))
    assert observed[0][0] == observed[1][0]  # exact refilled derived geometry
    assert observed[0][1] == observed[1][1]  # DRC findings under the colliding project rules
    assert observed[0][2] == observed[1][2]  # native-saved plot values
    assert observed[0][3] == observed[1][3]  # companion files: never rewritten differently
    assert all(value is not None for value in versions.values())
    (tmp_path / "project-plot-nonreference-proof.json").write_text(
        json.dumps(
            {
                "native_version": _kicad.supported_version(),
                "project_numeric_leaves": len(NONREFERENCE_PROJECT_NUMBERS),
                "schema_versions_kept": versions,
                "plot_numbers": len(NONREFERENCE_PLOT_NUMBERS),
                "collision_value": collision,
                "geometry_regions": len(observed[0][0]),
                "drc_findings": len(observed[0][1]),
                "plot_saved": observed[0][2],
                "companions_returned": observed[0][3],
                "renumbering_admitted": False,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
