# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The via protection benches of the oracle (capability kicad-oracle, "Via protection passes the oracle";
change c0112; hypotheses ``H-K-VIAPROT-FORMS``, ``-MASK``, ``-NINE``, ``-UPGRADE`` and ``-OUTPUTS``).

A bench is a created two-layer board written by ``write_board``: one row of vias of 0.8 mm with a 0.4 mm
drill on one net, joined by an ``F.Cu`` track, one via per case. The *facts* benches set each via's
protection children and the ``setup`` default by token edit, so they do not depend on the writer under
test; the *written* bench sets the same cases through the model. The sizes are authored round values.

What KiCad does with a bench is read from its outputs: a side of a via is open when the mask plot of that
side holds a flash near the via's centre (``_gerber.flashes``); the drill side files and the IPC-2581
layers list the vias that carry a feature.
"""

from __future__ import annotations

import dataclasses
import re
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from _gerber import flashes

from fenolite.backends.kicad import via_protection as vp
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.layers import created_layers
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.sexpr import Node, dumps, parse, parse_fragment
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.model.board import Board, Outline, Track, Via, ViaProtection
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design

STEM = "viabench"
PROJECT = "{}\n"
MM = 1_000_000
DIAMETER, DRILL = 800_000, 400_000
PITCH, FIRST_X, ROW_Y = 3 * MM, 10 * MM, 15 * MM
NEAR = 450_000
"""A flash within this distance of a via's centre is that via's opening (the vias are 3 mm apart)."""
P = ViaProtection

TEN_FORMS: tuple[str, ...] = (
    "",
    "(tenting (front no) (back no))",
    "(tenting (front yes) (back yes))",
    "(tenting (front no) (back yes))",
    "(tenting (front yes) (back no))",
    "(tenting (front no))",
    "(covering (front yes) (back yes))",
    "(plugging (front yes) (back yes))",
    "(capping yes)",
    "(filling yes)",
    "(covering (front yes) (back no))",
    "(plugging (front no) (back yes))",
    "(tenting (front no) (back no)) (covering (front yes) (back yes))",
    "(tenting (front no) (back no)) (plugging (front yes) (back yes))",
    "(tenting (front no) (back no)) (filling yes)",
    "(tenting (front yes) (back yes)) (capping yes) (covering (front yes) (back yes))"
    " (plugging (front yes) (back yes)) (filling yes)",
)
"""The protection children of the vias of a 10.0 facts bench, one via per entry."""
TEN_SETUPS: Mapping[str, str] = {
    "tented": "",
    "open": "(tenting (front no) (back no))",
    "front": "(tenting (front yes) (back no))",
}
"""The ``setup`` children of the 10.0 facts benches, by the name of the default they state."""
ALL_TRUE_SETUP = (
    "(tenting (front yes) (back yes)) (covering (front yes) (back yes)) (plugging (front yes) (back yes))"
    " (capping yes) (filling yes)"
)
NINE_FORMS: tuple[str, ...] = (
    "",
    "(tenting front back)",
    "(tenting front)",
    "(tenting back)",
    "(tenting none)",
    "(tenting)",
)
"""The ``tenting`` child of the vias of a 9.0 facts bench, one via per entry."""
NINE_SETUPS: Mapping[str, str] = {
    "absent": "",
    "both": "(tenting front back)",
    "none": "(tenting none)",
    "front": "(tenting front)",
}
UPGRADE_ROWS = frozenset({"(tenting front)", "(tenting back)", "(tenting none)", "(tenting)"})
"""The 9.0 children that KiCad 10 reads otherwise than KiCad 9: it leaves the unnamed sides to the default."""
TEN_CASES: tuple[ViaProtection, ...] = (
    P(),
    P(tenting_front=False, tenting_back=False),
    P(tenting_front=True, tenting_back=True),
    P(tenting_front=False, tenting_back=True),
    P(tenting_front=True, tenting_back=False),
    P(tenting_front=False),
    P(tenting_back=False),
    P(covering_front=True, covering_back=True),
    P(plugging_front=True, plugging_back=True),
    P(capping=True),
    P(filling=True),
    P(covering_front=True, covering_back=False),
    P(plugging_front=False, plugging_back=True),
    P(tenting_front=False, tenting_back=False, filling=True, capping=True),
    P(True, True, True, True, True, True, True, True),
    P(False, False, False, False, False, False, False, False),
)
"""The protections of the vias of the written bench for target 10."""
NINE_CASES: tuple[ViaProtection, ...] = (
    P(),
    P(tenting_front=True, tenting_back=True),
    P(tenting_front=True, tenting_back=False),
    P(tenting_front=False, tenting_back=True),
    P(tenting_front=False, tenting_back=False),
    P(tenting_front=False),
    P(tenting_back=False),
    P(tenting_front=True),
    P(tenting_front=False, tenting_back=False, capping=False, filling=False),
)
"""The protections of the written bench for target 9: what a KiCad 9 board can hold."""
DEFAULTS: Mapping[str, ViaProtection | None] = {
    "kicad": None,
    "tented": P(tenting_front=True, tenting_back=True),
    "open": P(tenting_front=False, tenting_back=False),
    "front": P(tenting_front=True, tenting_back=False),
}
"""The board defaults of the written benches."""
SIDE_FILES: Mapping[str, tuple[str, ...]] = {
    "tenting-front": ("tenting_front",),
    "tenting-back": ("tenting_back",),
    "covering-front": ("covering_front",),
    "covering-back": ("covering_back",),
    "plugging-front": ("plugging_front",),
    "plugging-back": ("plugging_back",),
    "filling-front-back": ("filling",),
    "capping-front-back": ("capping",),
}
"""Suffix of a drill side file of ``pcb export drill --format gerber --generate-tenting`` → the field
whose vias it holds."""
Openings = list[tuple[bool, bool]]
"""Per via, in row order: whether it is open on the front and on the back mask plot."""


def position(index: int) -> Point:
    return Point(FIRST_X + index * PITCH, ROW_Y)


def bench(
    protections: Sequence[ViaProtection], default: ViaProtection | None = None, name: str = "bench"
) -> Design:
    """The created bench board: one via per protection, in a row, on the net ``GND``."""
    count = len(protections)
    design = Design.new(STEM, seed=112)
    net = Net(id=derived_id("net", "viabench", "GND"), name="GND")
    width = FIRST_X * 2 + (count - 1) * PITCH
    corners = (Point(0, 0), Point(width, 0), Point(width, 2 * ROW_Y), Point(0, 2 * ROW_Y))
    vias = tuple(
        Via(id=derived_id("via", "viabench", f"{name}:{k}"), position=position(k), diameter=DIAMETER,
            drill=DRILL, layers=("F.Cu", "B.Cu"), net_id=net.id, protection=protection)
        for k, protection in enumerate(protections)
    )  # fmt: skip
    track = Track(
        id=derived_id("trk", "viabench", name), start=position(0), end=position(count - 1), width=250_000,
        layer="F.Cu", net_id=net.id,
    )  # fmt: skip
    board = Board(
        id=derived_id("brd", "viabench", name),
        outline=Outline(id=derived_id("out", "viabench", name), points=corners),
        layers=created_layers(2),
        tracks=(track,),
        vias=vias,
        via_protection=default,
    )
    return dataclasses.replace(design, circuit=Circuit(nets=(net,)), board=board)


def _children(text: str) -> list[Node]:
    if not text:
        return []
    wrapped = parse_fragment(f"(x {text})")
    assert isinstance(wrapped, Node)
    return list(wrapped.nodes())


def facts_text(forms: Sequence[str], setup: str, target: int) -> str:
    """A facts bench: the plain bench written for ``target``, then each via given the children of its
    form after ``layers`` and ``setup`` given its children after ``pad_to_mask_clearance``, by token
    edit."""
    root = parse(write_board(bench([P()] * len(forms)), target=target).text)
    vias = iter(forms)
    children: list[Node | object] = []
    for child in root.children:
        if isinstance(child, Node) and child.name == "via":
            inner = list(child.children)
            at = next(k for k, c in enumerate(inner) if isinstance(c, Node) and c.name == "layers") + 1
            inner[at:at] = _children(next(vias))
            child = child.with_children(inner)  # type: ignore[arg-type]
        elif isinstance(child, Node) and child.name == "setup":
            child = child.with_children([*child.children, *_children(setup)])
        children.append(child)
    return dumps(root.with_children(children))  # type: ignore[arg-type]


def written_text(cases: Sequence[ViaProtection], default: ViaProtection | None, target: int) -> str:
    """The written bench: the cases set through the model and written by ``write_board``."""
    return write_board(bench(cases, default), target=target).text


def expected(text: str) -> Openings:
    """What Fenolite's reader says of a bench: a side is open when the via's effective tenting there is
    ``False`` (``via_protection.effective`` of its read protection and the board's default)."""
    design = read_board(text)
    assert design.board is not None
    vias = sorted(design.board.vias, key=lambda v: v.position.x)
    found = [vp.effective(v.protection, design.board.via_protection) for v in vias]
    return [(e.tenting_front is False, e.tenting_back is False) for e in found]


def model_openings(cases: Sequence[ViaProtection], default: ViaProtection | None) -> Openings:
    """What the model means for the written bench."""
    found = [vp.effective(case, default) for case in cases]
    return [(e.tenting_front is False, e.tenting_back is False) for e in found]


def _files(tmp: str, text: str) -> tuple[Path, dict[str, Path]]:
    board = Path(tmp) / f"{STEM}.kicad_pcb"
    board.write_text(text, encoding="utf-8", newline="\n")
    project = board.with_suffix(".kicad_pro")
    project.write_text(PROJECT, encoding="utf-8")
    return board, {project.name: project}


def _near(points: Sequence[tuple[int, int]], count: int) -> list[bool]:
    """Per via of a row of ``count``: whether a point lies within ``NEAR`` of its centre (the plot's Y
    values are the board's negated)."""
    out: list[bool] = []
    for index in range(count):
        centre = position(index)
        out.append(any((x - centre.x) ** 2 + (abs(y) - centre.y) ** 2 <= NEAR * NEAR for x, y in points))
    return out


def mask_openings(cli: KicadCli, text: str, count: int) -> Openings | None:
    """The openings KiCad plots for a bench of ``count`` vias: ``pcb export gerbers -l F.Mask,B.Mask``,
    a flash near a via's centre being its opening. ``None`` when a plot is missing (the board did not
    load)."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        run = cli.export(
            ["pcb", "export", "gerbers", "-l", "F.Mask,B.Mask", "-o", "out/"], board, files=files, out="out"
        )
    sides: list[list[bool]] = []
    for layer in ("F_Mask", "B_Mask"):
        data = next((d for name, d in run.outputs.items() if f"{STEM}-{layer}." in name), None)
        if data is None:
            return None
        sides.append(_near(flashes(data.decode("utf-8")), count))
    return list(zip(sides[0], sides[1], strict=True))


def loads(cli: KicadCli, text: str) -> int | None:
    """The exit code of ``pcb drc`` on a bench (0: the board loads; 3: KiCad cannot load it)."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        return cli.drc(board, files=files).run.returncode


def resaved(cli: KicadCli, text: str) -> Node:
    """A bench after ``pcb upgrade --force`` (10.0 only)."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        return parse(cli.upgrade_board(board, files=files).decode("utf-8"))


def protection_children(node: Node) -> list[str]:
    return [dumps(c, style="compact") for c in node.nodes() if c.name in vp.FEATURE_FIELDS]


def _by_place(root: Node) -> dict[str, list[str]]:
    """The protection children of each via, by the text of its ``at`` child (a re-save orders the vias
    its own way)."""
    found: dict[str, list[str]] = {}
    for via in root.nodes("via"):
        at = via.find("at")
        assert at is not None
        found[dumps(at, style="compact")] = protection_children(via)
    return found


def resave_differences(cli: KicadCli, text: str) -> list[str]:
    """Where the re-save of a written target-10 bench holds other protection children than Fenolite
    wrote, per via and for ``setup`` (none: ``equal``)."""
    before, after = parse(text), resaved(cli, text)
    old_vias, new_vias = _by_place(before), _by_place(after)
    out = [
        f"via {place}: {old_vias.get(place)} -> {new_vias.get(place)}"
        for place in sorted(set(old_vias) | set(new_vias))
        if old_vias.get(place) != new_vias.get(place)
    ]
    old_setup, new_setup = before.find("setup"), after.find("setup")
    assert old_setup is not None and new_setup is not None
    if protection_children(old_setup) != protection_children(new_setup):
        out.append(f"setup: {protection_children(old_setup)} -> {protection_children(new_setup)}")
    return out


ORDER_FORMS: tuple[str, ...] = ("(free yes)", "(locked yes) (free yes)", "(locked yes)", "")
"""The children of the vias of the order bench before a protection is added through the model."""
ORDER_PROTECTION = P(tenting_front=False, tenting_back=True, capping=True, filling=True)


def order_text() -> str:
    """The order bench: a target-10 facts bench whose vias hold ``free`` and ``locked`` children, read
    with ``read_board``, each via then given ``ORDER_PROTECTION`` through the model, and written again."""
    design = read_board(facts_text(ORDER_FORMS, "", 10))
    assert design.board is not None
    vias = tuple(dataclasses.replace(via, protection=ORDER_PROTECTION) for via in design.board.vias)
    changed = dataclasses.replace(design, board=dataclasses.replace(design.board, vias=vias))
    return write_board(changed, target=10).text


def _child_heads(root: Node) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for via in root.nodes("via"):
        at = via.find("at")
        assert at is not None
        found[dumps(at, style="compact")] = [c.name for c in via.nodes()]
    return found


def order_differences(cli: KicadCli, text: str) -> list[str]:
    """Where a re-save by 10.0.6 orders the children of a via otherwise than Fenolite wrote them."""
    before, after = _child_heads(parse(text)), _child_heads(resaved(cli, text))
    return [
        f"{place}: {before.get(place)} -> {after.get(place)}"
        for place in sorted(before)
        if before[place] != after.get(place)
    ]


def own_true(text: str, field: str) -> list[int]:
    """The row indexes of the vias of a bench whose own value of ``field`` is ``True``."""
    design = read_board(text)
    assert design.board is not None
    vias = sorted(design.board.vias, key=lambda v: v.position.x)
    return [k for k, via in enumerate(vias) if getattr(via.protection, field) is True]


def drill_side_files(cli: KicadCli, text: str, count: int) -> dict[str, list[int]] | None:
    """Suffix of each drill side file of ``pcb export drill --format gerber --generate-tenting`` → the
    row indexes of the vias it holds a flash for. ``None`` when the command fails."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        run = cli.export(
            ["pcb", "export", "drill", "--format", "gerber", "--generate-tenting", "-o", "out/"],
            board, files=files, out="out",
        )  # fmt: skip
    if not run.ok:
        return None
    found: dict[str, list[int]] = {}
    for name, data in run.outputs.items():
        match = re.search(rf"{STEM}-([a-z-]+)\.gbr$", name)
        if match is None or match.group(1) not in SIDE_FILES:
            continue
        near = _near(flashes(data.decode("utf-8")), count)
        found[match.group(1)] = [k for k, hit in enumerate(near) if hit]
    return found


def side_file_differences(text: str, found: Mapping[str, Sequence[int]]) -> list[str]:
    """Where the drill side files hold other vias than those whose own value is ``True`` (a file that
    is not written holds none)."""
    out: list[str] = []
    for suffix, (field,) in SIDE_FILES.items():
        wanted = own_true(text, field)
        if list(found.get(suffix, ())) != wanted:
            out.append(f"{suffix}: {list(found.get(suffix, ()))}, expected {wanted}")
    return out


IPC_FUNCTIONS: Mapping[str, tuple[str, ...]] = {
    "COATINGNONCOND": ("tenting_front", "tenting_back", "covering_front", "covering_back"),
    "HOLEFILL": ("plugging_front", "plugging_back", "filling"),
    "COATINGCOND": ("capping",),
}
"""IPC-2581 layer function → the fields whose vias its layers hold (``board.md``, "Via protection")."""
_LAYER = re.compile(r'<Layer\b[^>]*\bname="([^"]+)"[^>]*\blayerFunction="([^"]+)"')
_LAYER_REVERSED = re.compile(r'<Layer\b[^>]*\blayerFunction="([^"]+)"[^>]*\bname="([^"]+)"')
_FEATURE = re.compile(r'<LayerFeature\b[^>]*\blayerRef="([^"]+)"[^>]*>(.*?)</LayerFeature>', re.S)
_LOCATION = re.compile(r'<Location\b[^>]*\bx="([-0-9.]+)"[^>]*\by="([-0-9.]+)"')


def ipc_layers(cli: KicadCli, text: str, count: int) -> dict[str, list[list[int]]] | None:
    """Layer function → for each layer of ``IPC_FUNCTIONS`` in ``pcb export ipc2581``, the row indexes of
    the vias with a feature located at their centre (sorted lists, the layers sorted). ``None`` when the
    command writes no file."""
    with tempfile.TemporaryDirectory() as tmp:
        board, files = _files(tmp, text)
        run = cli.export(["pcb", "export", "ipc2581", "-o", "out/bench.xml"], board, files=files, out="out")
    data = next((d for name, d in run.outputs.items() if name.endswith(".xml")), None)
    if data is None:
        return None
    xml = data.decode("utf-8", "replace")
    functions = {name: function for name, function in _LAYER.findall(xml)}
    functions.update({name: function for function, name in _LAYER_REVERSED.findall(xml)})
    found: dict[str, list[list[int]]] = {function: [] for function in IPC_FUNCTIONS}
    for layer, body in _FEATURE.findall(xml):
        function = functions.get(layer)
        if function not in found:
            continue
        points = [(round(float(x) * MM), round(float(y) * MM)) for x, y in _LOCATION.findall(body)]
        near = _near(points, count)
        found[function].append([k for k, hit in enumerate(near) if hit])
    return {function: sorted(layers) for function, layers in found.items()}


def ipc_expected(text: str) -> dict[str, list[list[int]]]:
    """What ``ipc_layers`` gives when each layer holds exactly the vias whose own value for its feature
    and side is ``True``: one layer per field that some via carries."""
    out: dict[str, list[list[int]]] = {}
    for function, fields in IPC_FUNCTIONS.items():
        layers = [own_true(text, field) for field in fields]
        out[function] = sorted(layer for layer in layers if layer)
    return out


Probes = dict[str, tuple[Callable[[], str], tuple[int, ...]]]


def via_probes(runner: Callable[[], KicadCli]) -> Probes:
    """The ``via-prot-*`` probes of the running ``kicad-cli``."""

    def mask() -> str:
        major = runner().major()
        forms, setups = (NINE_FORMS, NINE_SETUPS) if major < 10 else (TEN_FORMS, TEN_SETUPS)
        for setup in setups.values():
            text = facts_text(forms, setup, major)
            found = mask_openings(runner(), text, len(forms))
            if found is None:
                return "inconclusive"
            if found != expected(text):
                return "different"
        return "equal"

    def upgrade() -> str:
        text = facts_text(NINE_FORMS, NINE_SETUPS["both"], 9)
        found = mask_openings(runner(), text, len(NINE_FORMS))
        if found is None:
            return "inconclusive"
        nine = expected(text)  # the 9.0 file read as 9.0.9 reads it
        differing = {form for form, a, b in zip(NINE_FORMS, found, nine, strict=True) if a != b}
        if not differing:
            return "equal"
        tented_there = all(
            found[k] == (False, False) for k, form in enumerate(NINE_FORMS) if form in differing
        )
        return "different" if differing == UPGRADE_ROWS and tented_there else "inconclusive"

    def outputs(setup: str) -> list[str] | None:
        text = facts_text(TEN_FORMS, setup, 10)
        count = len(TEN_FORMS)
        files = drill_side_files(runner(), text, count)
        layers = ipc_layers(runner(), text, count)
        if files is None or layers is None:
            return None
        out = side_file_differences(text, files)
        wanted = ipc_expected(text)
        out += [f"{f}: {layers[f]}, expected {wanted[f]}" for f in IPC_FUNCTIONS if layers[f] != wanted[f]]
        return out

    def own_outputs() -> str:
        found = outputs(TEN_SETUPS["tented"])
        return "inconclusive" if found is None else "equal" if not found else "different"

    def default_outputs() -> str:
        found = outputs(ALL_TRUE_SETUP)
        return "inconclusive" if found is None else "absent" if not found else "present"

    def load_nine() -> str:
        forms = ("", "(plugging (front yes) (back yes))")
        return "reject" if loads(runner(), facts_text(forms, "", 9)) == 3 else "load"

    def resave() -> str:
        for default in DEFAULTS.values():
            if default is None:
                continue  # a re-save gives a board without a default the five children of KiCad's
            if resave_differences(runner(), written_text(TEN_CASES, default, 10)):
                return "different"
        return "equal"

    return {
        "via-prot-mask": (mask, (9, 10)),
        "via-prot-upgrade": (upgrade, (10,)),
        "via-prot-outputs": (own_outputs, (10,)),
        "via-prot-default-outputs": (default_outputs, (10,)),
        "via-prot-load-nine": (load_nine, (9,)),
        "via-prot-resave": (resave, (10,)),
        "via-prot-order": (
            lambda: "equal" if not order_differences(runner(), order_text()) else "different",
            (10,),
        ),
    }


__all__ = [
    "DEFAULTS",
    "NINE_CASES",
    "NINE_FORMS",
    "NINE_SETUPS",
    "TEN_CASES",
    "TEN_FORMS",
    "TEN_SETUPS",
    "bench",
    "drill_side_files",
    "expected",
    "facts_text",
    "ipc_layers",
    "loads",
    "mask_openings",
    "model_openings",
    "order_differences",
    "order_text",
    "resave_differences",
    "via_probes",
    "written_text",
]
