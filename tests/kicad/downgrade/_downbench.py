# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The benches of the KiCad downgrade (change c0162; ``H-K-DOWN-ROWS``; capability kicad-version-gating,
"Downgrade resolver", scenario "Each row proved on 9.0.9").

A bench holds one construct of KiCad 10 in a minimal file: the token fuzz's example of the row
(``tests/data/kicad/tokens/examples.toml``), inserted into the fuzz skeleton of its kind at the header of
10.0, or a variant of it named here. ``tests/data/kicad/downgrade/`` holds each bench as ``kicad-cli``
10.0.6 saved it (``pcb upgrade --force`` or ``sch upgrade --force``; ``sym upgrade --force`` for a symbol
library), written by a 10.0.6 run with ``FENOLITE_GOLDEN_WRITE=1``. Fenolite downgrades the saved file for
KiCad 9; a 9.0.9 run loads it and runs its DRC (ERC for a schematic), which must report the violation types
10.0.6 reports on the source (``SOURCE_TYPES``, recorded by a 10.0.6 run); a 10.0.6 run re-saves the
downgraded file, which must give the source again: the model at level 5 for a board, the tree for a
schematic or a symbol library. The probe ``down-row-<bench>`` records ``equal`` when every check of the
running major holds, ``different`` when one does not, ``reject`` when the file does not load.
"""

from __future__ import annotations

import json
import re
import tempfile
from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import _fuzzmod

from fenolite.api.conversion import ConversionResult, convert
from fenolite.backends.kicad.cli import CliRun, KicadCli
from fenolite.backends.kicad.pcb import read_board, write_board
from fenolite.backends.kicad.resolver import Edit
from fenolite.backends.kicad.sch import read_schematic, retarget_schematic
from fenolite.backends.kicad.sexpr import parse, tree_equal
from fenolite.backends.kicad.sym import retarget_symbol_library
from fenolite.backends.kicad.versions import FORMAT_VERSIONS, FileKind, load_inventory
from fenolite.checks.equivalence import compare_designs, max_level
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests" / "data" / "kicad" / "downgrade"
SKELETONS = ROOT / "tests" / "data" / "kicad" / "tokens"
WRITE_VARIABLE = "FENOLITE_GOLDEN_WRITE"
TYPES_FILE = "source_types.json"
SUFFIX: Mapping[FileKind, str] = {
    FileKind.BOARD: ".kicad_pcb",
    FileKind.SCHEMATIC: ".kicad_sch",
    FileKind.SYMBOL_LIB: ".kicad_sym",
}
SKELETON: Mapping[FileKind, str] = {
    FileKind.BOARD: "skeleton.kicad_pcb",
    FileKind.SCHEMATIC: "skeleton.kicad_sch",
    FileKind.SYMBOL_LIB: "skeleton.kicad_sym",
}


def _fuzz():  # noqa: ANN202  (a module loaded from tools/)
    return _fuzzmod.load()


def header(kind: FileKind, major: int) -> int:
    return FORMAT_VERSIONS[kind][major]


def with_header(text: str, version: int) -> str:
    """``text`` with its root's ``(version N)`` set to ``version``."""
    return re.sub(r"\(version \d+\)", f"(version {version})", text, count=1)


def skeleton(kind: FileKind, major: int) -> str:
    """The fuzz skeleton of ``kind`` at the header of ``major``."""
    return with_header((SKELETONS / SKELETON[kind]).read_text(encoding="utf-8"), header(kind, major))


def appended(text: str, fragment: str) -> str:
    """``text`` with ``fragment`` appended as the last child of its root."""
    body = text.rstrip()
    assert body.endswith(")")
    return body[:-1].rstrip() + "\n\t" + fragment + "\n)\n"


# --- task 1.2: the absent defaults of via protection and the form of a buried via ----------------------


def runner_major(runner: KicadCli) -> int:
    return runner.major()


def upgraded_board(runner: KicadCli, text: str) -> str:
    """``text`` re-saved by ``pcb upgrade --force`` (10.0 only), whitespace folded to one space."""
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        saved = runner.upgrade_board(board).decode("utf-8")
    return re.sub(r"\s+", " ", saved)


def drc_types(runner: KicadCli, text: str, name: str = "bench") -> tuple[str, ...] | None:
    """The DRC violation types with their counts, sorted; ``None`` when the board does not load."""
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / f"{name}.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        run = runner.drc(board)
    if run.report is None:
        return None
    found = (*run.report.violations, *run.report.unconnected_items)
    return tuple(f"{k}={n}" for k, n in sorted(Counter(v.type for v in found).items()))


def loads(runner: KicadCli, text: str) -> bool:
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        board = Path(tmp) / "bench.kicad_pcb"
        board.write_text(text, encoding="utf-8")
        args = ["pcb", "export", "svg", "-l", "Edge.Cuts", "--mode-single", "-o", "out.svg", board.name]
        run = runner.run(args, files={board.name: board})
    return run.returncode == 0 and "out.svg" in run.outputs


PROTECTION_CHILDREN = ("covering", "plugging", "capping", "filling")
SETUP_ABSENT_10 = (
    "(covering (front no) (back no) ) (plugging (front no) (back no) ) (capping no) (filling no)"
)
"""What 10.0.6 writes in ``setup`` for a board whose ``setup`` holds none of the four (measured on
2026-10-09): the absent default of the board is ``no``."""
VIA_ABSENT_9 = "(capping no) (covering (front no) (back no) ) (plugging (front no) (back no) ) (filling no)"
"""What 10.0.6 writes for a via of a board of format 9 (which cannot hold the four): ``no``, so what 9.0
does without them is what 10.0 does with ``no``."""
BURIED_VIA_10 = (
    '(via buried (at 22 22) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu") (net 1) '
    '(uuid "6f1d2c3e-0000-4000-8000-0000000000bb"))'
)
BURIED_VIA_9 = BURIED_VIA_10.replace("(via buried", "(via blind")
BURIED_TYPES = ("lib_footprint_issues=1", "track_dangling=1", "unconnected_items=3", "via_dangling=2")
"""The DRC violation types of the buried-via bench on 10.0.6 and of its 9 form on 9.0.9 (2026-10-09)."""


def protection_defaults(runner: KicadCli) -> str:
    """``equal`` when the running major gives the recorded absent defaults (task 1.2): on 10.0.6 a board of
    format 10 without the four children in ``setup`` or on a via is re-saved with ``SETUP_ABSENT_10`` and
    a via without them, and a board of format 9 with ``VIA_ABSENT_9`` on each via; on 9.0.9 the board of
    format 9 loads and one with ``(capping no)`` on a via does not (9.0 has no such child)."""
    nine = skeleton(FileKind.BOARD, 9)
    if runner.major() == 9:
        via = '(drill 0.3)\n\t\t(layers "F.Cu" "B.Cu")'
        capped = nine.replace(via, via + "\n\t\t(capping no)")
        assert capped != nine
        return "equal" if loads(runner, nine) and not loads(runner, capped) else "different"
    ten = upgraded_board(runner, skeleton(FileKind.BOARD, 10))
    from_nine = upgraded_board(runner, nine)
    via_ten = ten[ten.find("(via ") :].split("(zone", 1)[0]
    via_nine = from_nine[from_nine.find("(via ") :].split("(zone", 1)[0]
    ok = (
        SETUP_ABSENT_10 in ten
        and not any(f"({child}" in via_ten for child in PROTECTION_CHILDREN)
        and VIA_ABSENT_9 in via_nine
    )
    return "equal" if ok else "different"


def buried_form(runner: KicadCli) -> str:
    """``equal`` when 9's form of a buried via holds on the running major (task 1.2): on 10.0.6 the bench
    with a buried via gives ``BURIED_TYPES`` and the 9 form (``blind`` with the same span) is read back as
    a blind via of that span; on 9.0.9 the 9 form loads and gives ``BURIED_TYPES``."""
    if runner.major() == 9:
        found = drc_types(runner, appended(skeleton(FileKind.BOARD, 9), BURIED_VIA_9))
        return "equal" if found == BURIED_TYPES else "different"
    source = appended(skeleton(FileKind.BOARD, 10), BURIED_VIA_10)
    back = upgraded_board(runner, appended(skeleton(FileKind.BOARD, 9), BURIED_VIA_9))
    same_span = '(via blind (at 22 22) (size 0.6) (drill 0.3) (layers "In1.Cu" "In2.Cu")' in back
    return "equal" if drc_types(runner, source) == BURIED_TYPES and same_span else "different"


# --- the row benches (task 4.1) ------------------------------------------------------------------------

BENCH_KINDS: tuple[FileKind, ...] = (FileKind.BOARD, FileKind.SCHEMATIC, FileKind.SYMBOL_LIB)
"""The kinds a bench is written in; a row of boards and footprints is benched in a board."""
RULE_AREA = (
    "(rule_area (dnp yes) (polyline (pts (xy 10 10) (xy 20 10) (xy 20 20) (xy 10 20)) (stroke (width 0) "
    '(type default)) (fill (type none)) (uuid "00000000-0000-4000-8000-0000000000b1")))'
)
HATCH_ZONE = (
    '(zone (net 0) (net_name "") (layer "F.Cu") (hatch edge 0.5) (min_thickness 0.25) '
    '(property (layer "F.Cu") (hatch_position (xy 0 0))) (fill (thermal_gap 0.5) (thermal_bridge_width 0.5)) '
    "(polygon (pts (xy 30 20) (xy 38 20) (xy 38 28) (xy 30 28))))"
)
"""The zone of ``hatch-position`` on a copper layer: 10.0.6 saves the fuzz example's silkscreen zone with
its property on the layer ``UNDEFINED``, and then refuses to load its own save (measured on 2026-10-09)."""
VARIANTS: Mapping[str, tuple[str, FileKind, str, str]] = {
    # bench id: (row, kind, host, fragment), for a value the row's fuzz example does not hold, or in place
    # of a fuzz example that 10.0.6 does not load back
    "hatch-position": ("hatch-position", FileKind.BOARD, "kicad_pcb", HATCH_ZONE),
    "npth-front-back": (
        "npth-front-back",
        FileKind.BOARD,
        "kicad_pcb/footprint",
        '(pad "" np_thru_hole circle (at 3 3) (size 0.8 0.8) (drill 0.8) (layers "F&B.Cu" "*.Mask") '
        '(uuid "6f1d2c3e-0000-4000-8000-0000000000ee"))',
    ),
    "capping-yes": ("capping", FileKind.BOARD, "kicad_pcb/via", "(capping yes)"),
    "covering-yes": ("covering", FileKind.BOARD, "kicad_pcb/via", "(covering (front yes) (back no))"),
    "plugging-yes": ("plugging", FileKind.BOARD, "kicad_pcb/via", "(plugging (front no) (back yes))"),
    "filling-yes": ("filling", FileKind.BOARD, "kicad_pcb/via", "(filling yes)"),
    "tenting-via": ("tenting-front", FileKind.BOARD, "kicad_pcb/via", "(tenting (front yes) (back none))"),
    "tenting-pad-none": (
        "tenting-front",
        FileKind.BOARD,
        "kicad_pcb/footprint/pad",
        "(tenting (front none) (back none))",
    ),
    "tenting-pad-no": (
        "tenting-front",
        FileKind.BOARD,
        "kicad_pcb/footprint/pad",
        "(tenting (front no) (back none))",
    ),
    "footprint-duplicate-pad-numbers-are-jumpers-yes": (
        "footprint-duplicate-pad-numbers-are-jumpers",
        FileKind.BOARD,
        "kicad_pcb/footprint",
        "(duplicate_pad_numbers_are_jumpers yes)",
    ),
    "sch-symbol-in-pos-files-no": (
        "sch-symbol-in-pos-files",
        FileKind.SCHEMATIC,
        "kicad_sch/symbol",
        "(in_pos_files no)",
    ),
    "sch-lib-in-pos-files-no": (
        "sch-lib-in-pos-files",
        FileKind.SCHEMATIC,
        "kicad_sch/lib_symbols/symbol",
        "(in_pos_files no)",
    ),
    "sch-rule-area-dnp-yes": ("sch-rule-area-dnp", FileKind.SCHEMATIC, "kicad_sch", RULE_AREA),
    "sym-in-pos-files-no": (
        "sym-in-pos-files",
        FileKind.SYMBOL_LIB,
        "kicad_symbol_lib/symbol",
        "(in_pos_files no)",
    ),
    "sym-jumpers-duplicate-yes": (
        "sym-jumpers-duplicate",
        FileKind.SYMBOL_LIB,
        "kicad_symbol_lib/symbol",
        "(duplicate_pin_numbers_are_jumpers yes)",
    ),
}


@dataclass(frozen=True)
class Bench:
    """One bench: its id (the row's, or a variant's), the row, the kind of its file, and the fuzz example
    it is built from."""

    id: str
    row: str
    kind: FileKind
    example: object  # a ``kicad_token_fuzz.Example``

    @property
    def path(self) -> Path:
        return DATA / f"{self.id}{SUFFIX[self.kind]}"


@cache
def benches() -> tuple[Bench, ...]:
    """One bench per resolver row of a board, footprint, schematic or symbol kind, from the fuzz example
    that exercises that row alone (a board example for a row of boards and footprints), and the
    ``VARIANTS``, sorted by id."""
    from fenolite.backends.kicad import resolver

    fuzz = _fuzz()
    inventory = load_inventory()
    examples = fuzz.load_examples((fuzz.DATA / "examples.toml").read_text(encoding="utf-8"), inventory)
    table = resolver.load()
    newer = {row.id for row in inventory.tokens if row.since_major == 10}
    newer |= {row.id for row in inventory.forms if row.since_major == 10}
    found: dict[str, Bench] = {}
    for example in examples:
        for kind in example.kinds:
            if kind not in BENCH_KINDS or example.expect is not None:
                continue
            rows = [r for r in fuzz.exercised_rows(example, kind, inventory) if r in newer]
            if len(rows) != 1 or rows[0] not in table.rows or rows[0] in found:
                continue
            found[rows[0]] = Bench(rows[0], rows[0], kind, example)
    for ident, (row, kind, host, fragment) in VARIANTS.items():
        found[ident] = Bench(ident, row, kind, fuzz.Example(ident, (kind,), host, "append", fragment))
    return tuple(found[key] for key in sorted(found))


def bench(ident: str) -> Bench:
    return next(b for b in benches() if b.id == ident)


def authored(item: Bench) -> str:
    """The bench as authored: the example in the fuzz skeleton of its kind, at the header of 10.0."""
    files = _fuzz()._case_files(item.example, item.kind, header(item.kind, 10), SKELETONS)  # noqa: SLF001
    (data,) = files.values()
    return data.decode("utf-8")


def saved(item: Bench) -> str:
    """The bench as 10.0.6 saved it (committed)."""
    return item.path.read_text(encoding="utf-8")


def downgraded(item: Bench, text: str) -> tuple[str, tuple[Edit, ...]]:
    """The bench written for KiCad 9 by Fenolite, and the resolver's edits."""
    edits: list[Edit] = []
    if item.kind == FileKind.BOARD:
        written = write_board(read_board(text), target=9, downgrade=True, allow_lossy=True, edits=edits).text
    elif item.kind == FileKind.SCHEMATIC:
        sheet = read_schematic(text, file=f"bench{SUFFIX[item.kind]}")
        written = retarget_schematic(sheet, target=9, downgrade=True, allow_lossy=True, edits=edits)
    else:
        written = retarget_symbol_library(text, target=9, downgrade=True, allow_lossy=True, edits=edits)
    return written, tuple(edits)


def _run(runner: KicadCli, args: list[str], name: str, text: str) -> CliRun:
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return runner.run(args, files={name: path})


def resaved(runner: KicadCli, item: Bench, text: str) -> str:
    """``text`` re-saved by 10.0.6 (``pcb``, ``sch`` or ``sym upgrade --force``)."""
    name = f"bench{SUFFIX[item.kind]}"
    tool = {FileKind.BOARD: "pcb", FileKind.SCHEMATIC: "sch", FileKind.SYMBOL_LIB: "sym"}[item.kind]
    run = _run(runner, [tool, "upgrade", "--force", name], name, text)
    assert run.returncode == 0, f"{item.id}: {run.stderr}"
    return run.outputs.get(name, text.encode("utf-8")).decode("utf-8")


def check_types(runner: KicadCli, item: Bench, text: str) -> tuple[str, ...] | None:
    """The DRC (board) or ERC (schematic) violation types with their counts, sorted, or the load check of a
    symbol library as ``("load",)``; ``None`` when the file does not load."""
    name = f"bench{SUFFIX[item.kind]}"
    if item.kind == FileKind.SYMBOL_LIB:
        run = _run(runner, ["sym", "export", "svg", "-o", "out", name], name, text)
        return ("load",) if run.returncode == 0 else None
    with tempfile.TemporaryDirectory(prefix="fenolite-down-") as tmp:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        if item.kind == FileKind.BOARD:
            drc = runner.drc(path)
            if drc.report is None:
                return None
            found = [v.type for v in (*drc.report.violations, *drc.report.unconnected_items)]
        else:
            erc = runner.erc(path)
            if erc.report is None:
                return None
            found = [v.type for v in erc.report.violations]
    return tuple(f"{k}={n}" for k, n in sorted(Counter(found).items()))


def same_after_upgrade(runner: KicadCli, item: Bench, source: str, written: str) -> bool:
    """Whether 10.0.6's re-save of the downgraded file gives the source again: the model at level 5 for a
    board (the highest level both hold), for a schematic or a symbol library the tree of 10.0.6's re-save
    of the source."""
    back = resaved(runner, item, written)
    if item.kind == FileKind.BOARD:
        a, b = read_board(source), read_board(back)
        return compare_designs(a, b, level=max_level(a, b)).equivalent
    return tree_equal(parse(back), parse(resaved(runner, item, source)))


def recorded() -> dict[str, list[str]]:
    """The violation types 10.0.6 reports on each bench (``source_types.json``)."""
    path = DATA / TYPES_FILE
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


SEVERITY: tuple[str, ...] = ("rewrite", "same", "presentation", "design")
"""The actions from the least consent to the most: a bench whose construct takes several (a via's ``yes``
beside the board's ``no``) is judged by the one that needs the most."""
NINE_NAMES: Mapping[str, str] = {
    "label_dangling": "isolated_pin_label",
    "global_label_dangling": "isolated_pin_label",
}
"""ERC types of 9.0.9 under the name 10.0.6 reports them by: a label on a single pin is ``label_dangling``
or ``global_label_dangling`` in 9.0 and ``isolated_pin_label`` in 10.0 (``H-K-ERC-TYPES``,
``_erccases.SINGLE_PIN_LABEL``)."""


def action_of(item: Bench, edits: tuple[Edit, ...]) -> str | None:
    """The action of the bench's construct: the one of its row that needs the most consent."""
    taken = {e.action for e in edits if e.row == item.row}
    return max(taken, key=SEVERITY.index) if taken else None


def as_ten(found: tuple[str, ...]) -> list[str]:
    """Violation types of 9.0.9 with their counts, named as 10.0.6 names them."""
    counts: Counter[str] = Counter()
    for entry in found:
        kind, _, count = entry.partition("=")
        counts[NINE_NAMES.get(kind, kind)] += int(count) if count else 0
    if found == ("load",):
        return ["load"]
    return [f"{k}={n}" for k, n in sorted(counts.items())]


def outcome(runner: KicadCli, item: Bench) -> str:
    """The probe ``down-row-<bench>`` on the running major (see the module's docstring)."""
    from fenolite.backends.kicad import resolver

    source = saved(item)
    written, edits = downgraded(item, source)
    action = action_of(item, edits)
    if action is None:
        return "different"
    expected = recorded().get(item.id)
    if runner.major() == 9:
        found = check_types(runner, item, written)
        if found is None:
            return "reject"
        return "equal" if expected is not None and as_ten(found) == expected else "different"
    found = check_types(runner, item, source)
    if found is None or expected is None or list(found) != expected:
        return "different"
    if action in resolver.CHANGED and not same_after_upgrade(runner, item, source, written):
        return "different"
    return "equal"


def write_benches(runner: KicadCli) -> None:
    """``FENOLITE_GOLDEN_WRITE=1`` on 10.0.6: each bench as 10.0.6 saves it, and the violation types 10.0.6
    reports on it. A construct that 10.0.6 does not write back (``island no``, an empty ``zone_defaults``
    or ``group``) keeps its authored file, which 10.0.6 loads (the token fuzz)."""
    DATA.mkdir(parents=True, exist_ok=True)
    types: dict[str, list[str]] = {}
    for item in benches():
        text = resaved(runner, item, authored(item))
        if action_of(item, downgraded(item, text)[1]) is None:
            text = authored(item)
        item.path.write_text(text, encoding="utf-8")
        found = check_types(runner, item, text)
        assert found is not None, item.id
        types[item.id] = list(found)
    (DATA / TYPES_FILE).write_text(json.dumps(types, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def down_probes(runner: Callable[[], KicadCli]) -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """The probes ``down-row-<bench>`` on both majors."""
    return {
        f"down-row-{item.id}": ((lambda item=item: outcome(runner(), item)), (9, 10)) for item in benches()
    }


# --- the demo projects (task 4.2) -----------------------------------------------------------------------

DEMOS: Mapping[str, str] = {
    "CM5_MINIMA_3": "kicad-demo-10-0-6-sch-003",
    "pic_programmer": "kicad-demo-10-0-6-sch-039",
}
"""The KiCad 10.0.6 demo projects of format 10, by the corpus row of their root schematic."""
ERC_TYPES = ("footprint_link_issues", "lib_symbol_issues")
DEMO_TYPES: Mapping[str, Mapping[str, tuple[str, ...]]] = {
    "CM5_MINIMA_3": {
        "drc": (
            "copper_edge_clearance", "courtyards_overlap", "holes_co_located", "isolated_copper",
            "silk_edge_clearance", "silk_over_copper", "silk_overlap", "solder_mask_bridge", "text_height",
            "text_thickness", "via_dangling",
        ),
        "erc": ERC_TYPES,
    },
    "pic_programmer": {"drc": ("lib_footprint_issues",), "erc": ERC_TYPES},
}  # fmt: skip
"""The DRC and ERC violation types (without counts) of each demo project in 10.0.6, measured on
2026-10-09 in the pinned image with the project folder the corpus rebuilds (no global library: hence
``lib_footprint_issues``, ``footprint_link_issues`` and ``lib_symbol_issues``)."""


def npth_refs(design: Design) -> frozenset[str]:
    """The references of the footprints that hold an ``np_thru_hole`` pad on some copper layers of the
    board but not all (row ``npth-front-back``): 10.0.6 reads such a pad of a board of format 9 with every
    copper layer, a ``pad-copper`` difference at level 3 that the row's ``design`` loss names."""
    board = design.board
    assert board is not None
    refs = {component.id: component.ref for component in design.circuit.components}
    copper = {layer.name for layer in board.layers if layer.kind == "copper"}
    return frozenset(
        refs.get(fp.component_id, "")
        for fp in board.footprints
        for pad in fp.pads
        if pad.kind == "np_thru_hole" and set(pad.layers) & copper and set(pad.layers) & copper != copper
    )


def demo_folder(tmp: Path, name: str) -> Path | None:
    """The demo folder of ``name`` rebuilt from the corpus under ``tmp`` (``_schprojects``)."""
    import _schcorpus
    import _schprojects

    rows = {row.id: row for row in _schcorpus.rows()}
    return _schprojects.project_folder(tmp, rows[DEMOS[name]], 10)


def project_types(runner: KicadCli, folder: Path, name: str) -> dict[str, tuple[str, ...]] | None:
    """The DRC violation types of ``<name>.kicad_pcb`` and the ERC violation types of ``<name>.kicad_sch``
    of the project in ``folder``, without counts, sorted; ``None`` when one does not load."""
    files = {p.relative_to(folder).as_posix(): p for p in folder.iterdir()}
    board, schematic = folder / f"{name}.kicad_pcb", folder / f"{name}.kicad_sch"
    drc = runner.drc(board, files={k: v for k, v in files.items() if v != board})
    erc = runner.erc(schematic, files={k: v for k, v in files.items() if v != schematic})
    if drc.report is None or erc.report is None:
        return None
    found_drc = {v.type for v in (*drc.report.violations, *drc.report.unconnected_items)}
    return {"drc": tuple(sorted(found_drc)), "erc": tuple(sorted({v.type for v in erc.report.violations}))}


def converted(folder: Path, out: Path) -> ConversionResult:
    """The demo project converted for KiCad 9 with consent to its losses, written to ``out``."""
    result = convert(folder, to="kicad", kicad_version=9, allow_lossy=True)
    for key, data in result.conversion.files.items():
        target = out.joinpath(*key.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return result


def demo_outcome(runner: KicadCli, name: str, expected: Mapping[str, tuple[str, ...]]) -> str:
    """``equal`` when the demo project ``name`` holds on the running major: on 10.0.6 its DRC and ERC types
    are ``expected`` and the re-save of its converted board gives the source at level 5; on 9.0.9 the
    converted project loads with the DRC and ERC types ``expected``; ``reject`` when it does not load."""
    with tempfile.TemporaryDirectory(prefix="fenolite-down-demo-") as tmp:
        folder = demo_folder(Path(tmp) / "source", name)
        assert folder is not None, name
        out = Path(tmp) / "out"
        result = converted(folder, out)
        if result.unexplained:
            return "different"
        if runner.major() == 9:
            found = project_types(runner, out, name)
            if found is None:
                return "reject"
            return "equal" if found == dict(expected) else "different"
        if project_types(runner, folder, name) != dict(expected):
            return "different"
        board = out / f"{name}.kicad_pcb"
        back = runner.upgrade_board(board).decode("utf-8")
        source = read_board(folder / f"{name}.kicad_pcb")
        again = read_board(back)
        refs = npth_refs(source)
        report = compare_designs(source, again, level=5)
        left = [
            d for d in report.differences if not (d.kind == "pad-copper" and d.where.split("-", 1)[0] in refs)
        ]
        return "equal" if not left else "different"


def demo_probes(runner: Callable[[], KicadCli]) -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """The probes ``down-demo-<name>`` and ``down-demos`` (``equal`` when both are) on both majors; an
    uncached demo project is ``inconclusive``."""

    done: dict[str, str] = {}

    def one(name: str) -> str:
        if name not in done:
            with tempfile.TemporaryDirectory(prefix="fenolite-down-probe-") as tmp:
                cached = demo_folder(Path(tmp), name) is not None
            done[name] = demo_outcome(runner(), name, DEMO_TYPES[name]) if cached else "inconclusive"
        return done[name]

    found: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {
        f"down-demo-{name}": ((lambda name=name: one(name)), (9, 10)) for name in DEMOS
    }

    def both() -> str:
        outcomes = {one(name) for name in DEMOS}
        return outcomes.pop() if len(outcomes) == 1 else "different"

    found["down-demos"] = (both, (9, 10))
    return found


__all__ = [
    "DATA",
    "DEMOS",
    "Bench",
    "bench",
    "benches",
    "buried_form",
    "down_probes",
    "downgraded",
    "outcome",
    "protection_defaults",
    "write_benches",
]
