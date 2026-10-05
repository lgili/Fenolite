# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The projects ``build`` writes are accepted by KiCad's ERC and by its schematic parity test (capability
kicad-oracle, "Generated schematics pass ERC and parity"; hypotheses ``H-K-SCH-MINIMAL``,
``H-K-SCH-PARITY`` and ``H-K-SCH-RESAVE``; change c0061). Each design is built for the running major."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path

import _erc
import _gencases as gen
import _probes
import pytest
from _boards import census
from _buildhelp import blink, build
from _checkrun import check, stage
from _projects import tree_snapshot
from _schbuild import built_units, write_files

from fenolite.backends.kicad.sexpr import Atom, Node, dumps, parse
from fenolite.lens.build import BuildOutput

pytestmark = pytest.mark.needs_kicad
DESIGNS = ("blink", "units")


def output(name: str) -> BuildOutput:
    target = _probes.major()
    return build(blink(), target) if name == "blink" else built_units(target)


def edited(name: str, file: str, change: Callable[[Node], Node]) -> Mapping[str, bytes]:
    """The built files of ``name`` with ``change`` applied to the tree of ``file``."""
    files = dict(gen.built(name, _probes.major()))
    files[file] = dumps(change(parse(files[file].decode("utf-8")))).encode("utf-8")
    return files


def erc_types(files: Mapping[str, bytes], schematic: str = "blink.kicad_sch") -> Counter[str]:
    report = _erc.run_erc(_probes.runner(), schematic, files)
    return _erc.types(_erc.violations(report))


def parity_types(files: Mapping[str, bytes], board: str = "blink.kicad_pcb") -> Counter[str]:
    report = _erc.run_parity(_probes.runner(), board, files)
    return _erc.types(_erc.parity(report))


def fields(item: Node) -> dict[str, str]:
    return {p.atoms()[0].value: p.atoms()[1].value for p in item.nodes("property")}


def without(root: Node, drop: Callable[[Node], bool], count: int = 1) -> Node:
    """``root`` without its first ``count`` children that ``drop`` names."""
    kept: list[Node | Atom] = []
    left = count
    for child in root.children:
        if left and isinstance(child, Node) and drop(child):
            left -= 1
            continue
        kept.append(child)
    assert left == 0, "the item to remove was not found"
    return root.with_children(kept)


def footprint_edit(ref: str, change: Callable[[Node], Node]) -> Callable[[Node], Node]:
    def apply(root: Node) -> Node:
        hits = 0
        children: list[Node | Atom] = []
        for child in root.children:
            if (
                isinstance(child, Node)
                and child.name == "footprint"
                and fields(child).get("Reference") == ref
            ):
                child = change(child)
                hits += 1
            children.append(child)
        assert hits == 1, ref
        return root.with_children(children)

    return apply


def set_property(key: str, text: str) -> Callable[[Node], Node]:
    def apply(footprint: Node) -> Node:
        children: list[Node | Atom] = []
        for child in footprint.children:
            if isinstance(child, Node) and child.name == "property" and child.atoms()[0].value == key:
                parts = list(child.children)
                parts[parts.index(child.atoms()[1])] = Atom.string(text)
                child = child.with_children(parts)
            children.append(child)
        return footprint.with_children(children)

    return apply


def pad_net(root: Node, ref: str, number: str) -> Node:
    (footprint,) = [f for f in root.nodes("footprint") if fields(f).get("Reference") == ref]
    (pad,) = [p for p in footprint.nodes("pad") if p.atoms()[0].value == number]
    net = pad.find("net")
    assert net is not None
    return net


# -- ERC (H-K-SCH-MINIMAL)


@pytest.mark.parametrize("name", DESIGNS)
def test_erc_clean(name: str) -> None:
    report = gen.built_erc(name, exit_code=True)
    assert report.loaded, report.stderr
    found = _erc.violations(report)
    assert report.returncode == 0 and found == [], [(v["type"], v["description"]) for v in found]
    assert _probes.run(f"sch-gen-erc-{name}") == "equal"
    print(f"sch-gen-erc-{name}: equal; ERC exit 0, 0 violations on kicad-cli {_probes.version()}")


def test_erc_controls() -> None:
    """Each edit of the built blink gives its violation, so a silent ERC is not an empty check."""
    sheet = "blink.kicad_sch"

    def is_label(text: str) -> Callable[[Node], bool]:
        return lambda item: item.name == "global_label" and item.atoms()[0].value == text

    unlabelled = erc_types(edited("blink", sheet, lambda root: without(root, is_label("LED_DRV"))))
    assert unlabelled["pin_not_connected"] == 1, unlabelled

    def no_flag(root: Node) -> Node:
        flags = [s for s in root.nodes("symbol") if fields(s).get("Reference", "").startswith("#FLG")]
        at = {tuple(a.value for a in s.find("at").atoms()[:2]) for s in flags}  # type: ignore[union-attr]
        vin = [
            label
            for label in root.nodes("global_label")
            if label.atoms()[0].value == "VIN" and tuple(a.value for a in label.find("at").atoms()[:2]) in at  # type: ignore[union-attr]
        ]
        assert len(vin) == 1
        point = tuple(a.value for a in vin[0].find("at").atoms()[:2])  # type: ignore[union-attr]

        def here(item: Node) -> bool:
            placed = item.find("at")
            return (
                item.name in ("symbol", "global_label")
                and placed is not None
                and tuple(a.value for a in placed.atoms()[:2]) == point
            )

        return without(root, here, count=2)

    undriven = erc_types(edited("blink", sheet, no_flag))
    assert undriven["power_pin_not_driven"] == 1, undriven
    files = {k: v for k, v in gen.built("blink", _probes.major()).items() if k != "sym-lib-table"}
    assert erc_types(files)["lib_symbol_issues"] >= 1


# -- parity (H-K-SCH-PARITY)


@pytest.mark.parametrize("name", DESIGNS)
def test_parity(name: str) -> None:
    report = gen.built_parity(name)
    assert report.loaded, report.stderr
    found = _erc.parity(report)
    assert found == [], [(v["type"], v["description"]) for v in found]
    print(f"schematic_parity of {name}: 0 issues on kicad-cli {_probes.version()}")


def test_parity_controls() -> None:
    board = "blink.kicad_pcb"

    def moved(root: Node) -> Node:
        other = pad_net(root, "D1", "1")  # GND

        def on_other_net(footprint: Node) -> Node:
            children: list[Node | Atom] = []
            for child in footprint.children:
                if isinstance(child, Node) and child.name == "pad" and child.atoms()[0].value == "2":
                    parts = [other if isinstance(k, Node) and k.name == "net" else k for k in child.children]
                    child = child.with_children(parts)
                children.append(child)
            return footprint.with_children(children)

        return footprint_edit("R1", on_other_net)(root)

    assert parity_types(edited("blink", board, moved))["net_conflict"] >= 1
    value = parity_types(edited("blink", board, footprint_edit("R1", set_property("Value", "331"))))
    assert value["footprint_symbol_mismatch"] >= 1, value
    renamed = parity_types(edited("blink", board, footprint_edit("R1", set_property("Reference", "R9"))))
    assert renamed["missing_footprint"] == 1 and renamed["extra_footprint"] == 1, renamed

    def exchanged(root: Node) -> Node:
        paths = {
            fields(f)["Reference"]: f.find("path")
            for f in root.nodes("footprint")
            if f.find("path") is not None
        }
        assert paths["R1"] != paths["D1"]

        def swap(ref: str, other: str) -> Callable[[Node], Node]:
            return footprint_edit(
                ref,
                lambda fp: fp.with_children(
                    [paths[other] if isinstance(c, Node) and c.name == "path" else c for c in fp.children]  # type: ignore[misc]
                ),
            )

        return swap("D1", "R1")(swap("R1", "D1")(root))

    assert parity_types(edited("blink", board, exchanged)) == Counter()


# -- the netlist


@pytest.mark.parametrize("name", DESIGNS)
def test_netlist(name: str) -> None:
    """The nets KiCad derives from the sheet are the circuit's, pins mapped to pads, plus one single-pin
    net per unconnected pad with the name the board carries."""
    built = output(name)
    assert built.schematic is not None
    design = built.design
    refs = {c.id: c.ref for c in design.circuit.components}
    pads = {c.id: dict(c.pin_pad_map) for c in design.circuit.components}
    wanted: dict[str, set[tuple[str, str]]] = {}
    for net in design.circuit.nets:
        members = {(refs[m.component_id], pads[m.component_id].get(m.pin, m.pin)) for m in net.members}
        if members:
            wanted[net.name.replace("/", "{slash}")] = members
    for (component_id, pad), net_name in built.schematic.pad_nets.items():
        wanted[net_name] = {(refs[component_id], pad)}
    sheet = f"{gen.stem(name)}.kicad_sch"
    found = _erc.netlist(_probes.runner(), sheet, gen.built(name, _probes.major()))
    found = {net: {n for n in nodes if not n[0].startswith("#")} for net, nodes in found.items()}
    assert found == wanted
    if name == "units":
        assert ("D1", "2") in found["GND"] and ("D1", "1") in found["mod{slash}LED_A"]


# -- check


@pytest.mark.parametrize("name", DESIGNS)
def test_check(name: str, tmp_path: Path) -> None:
    folder = write_files(output(name), tmp_path / name)
    before = tree_snapshot(folder)
    _, env, _, err = check(folder)
    assert env, err
    errors = [
        i for i in env["issues"] if i["severity"] == "error" and i["code"] != "kicad.drc.unconnected-items"
    ]
    assert errors == [], errors
    compare = stage(env, "netlist.assignment_compare")
    assert compare["status"] == "ok" and all(p["differences"] == 0 for p in compare["summary"]["pairs"])
    assert [(p["a"], p["b"]) for p in compare["summary"]["pairs"]] == [
        ("model", "board"),
        ("model", "schematic"),  # c0063: KiCad's netlist of the generated sheet
        ("board", "export"),
    ]
    assert stage(env, "roundtrip")["status"] == "ok"
    differs = [i for i in env["issues"] if i["code"] == "netlist.assignment-differs"]
    assert not differs and not [i for i in env["issues"] if "unconnected-(" in i.get("where", "")]
    assert tree_snapshot(folder) == before


# -- re-save (H-K-SCH-RESAVE)


def _heads(text: bytes) -> list[str]:
    return [child.name for child in parse(text.decode("utf-8")).nodes()]


def _census(node: Node, found: Counter[str], chain: str = "") -> None:
    for child in node.nodes():
        found[f"{chain}/{child.name}"] += 1
        _census(child, found, f"{chain}/{child.name}")


def test_resave() -> None:
    """``sch upgrade --force`` of a generated sheet: ERC stays clean and a second re-save changes nothing.
    What the first re-save changes is counted, never judged."""
    if _probes.major() < 10:
        pytest.skip("sch upgrade is a 10.0 command")
    files = gen.built("blink", 10)
    written = files["blink.kicad_sch"]
    first = gen.resave(written, files)
    second = gen.resave(first, files)
    after = _erc.run_erc(_probes.runner(), "blink.kicad_sch", {**files, "blink.kicad_sch": first})
    assert _erc.violations(after) == []
    assert second == first
    assert _probes.run("sch-gen-resave") == "equal"
    before_counts, after_counts = Counter[str](), Counter[str]()
    _census(parse(written.decode("utf-8")), before_counts)
    _census(parse(first.decode("utf-8")), after_counts)
    added = {k: v - before_counts[k] for k, v in sorted(after_counts.items()) if v > before_counts[k]}
    dropped = {k: v - after_counts[k] for k, v in sorted(before_counts.items()) if v > after_counts[k]}
    data = {
        "version": _probes.version(),
        "bytes_written": len(written),
        "bytes_resaved": len(first),
        "identical": first == written,
        "root_order_kept": _heads(first) == _heads(written),
        "added": added,
        "dropped": dropped,
    }
    census("schematic-resave", "blink", data)
    print(f"sch-gen-resave: equal; added {added}; dropped {dropped}; order kept {data['root_order_kept']}")
