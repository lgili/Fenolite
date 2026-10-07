# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The steps of the Altium verification kit (capability altium-verification, "Kit steps settle
hypotheses"; ``docs/altium-kit.md``).

``STEPS`` is the closed list. A step ends in a file that Altium writes under ``results/`` (kind ``file``) or
in a value typed into ``results/form.json`` (kind ``form``). The instructions are written for Fenolite and
name Altium's menus only by their names; ``STEPS.md`` of a kit is ``steps_markdown()`` of the same list, so
the checklist and ``kit.json`` cannot differ.

Stdlib only.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Literal

StepKind = Literal["file", "form"]
ValueType = Literal["bool", "int", "text"]
Check = Literal[
    "resave", "netlist", "parity", "poured", "copper.clearance", "messages", "listing", "present"
]  # fmt: skip

STEP_ID = re.compile(r"K([1-9])\.([1-9][0-9]?)")
RESULTS = "results"
"""The folder of a kit that a run fills."""
SAMPLES: tuple[str, ...] = ("flat", "tree", "routed", "board6", "libs")
"""The kit's samples, each built from ``examples/kit/<name>/design.py``."""
KIT_SAMPLE = "kit"
"""The sample name of a step that uses a file of the kit that belongs to no sample (the sheet template)."""

CHECKS: Mapping[str, str] = MappingProxyType(
    {
        "resave": "the re-saved document passes RT-A0 and RT-A1, and its import equals the import of "
        "the kit's own document at every level of `equivalent` that the document holds",
        "netlist": "the document's import equals the import of the kit's own document at levels 1 and 2 "
        "of `equivalent` (components and nets)",
        "parity": "the stage `parity` of `fenolite check`, run on the sample's project with the saved "
        "document in the place of the kit's own, reports what it reports on the kit's own project",
        "poured": "every polygon of the re-saved board holds poured copper",
        "copper.clearance": "Fenolite's copper check finds the one planted clearance violation between "
        "`VIN` and `LED_A`, no other and no short: on the kit's own board when the step leaves a report, "
        "and on the re-saved board, with no polygon left out, when the step leaves the board",
        "messages": "the file holds at least one line and no line of the class Error or Fatal Error",
        "listing": "the file holds at least one line, and no line holds a folder",
        "present": "the file exists and is not empty",
    }
)
"""What ``kit verify`` does for each machine check of a ``file`` step."""
PENDING_REASONS: Mapping[str, str] = MappingProxyType(
    {
        "c0090": "the write-back of an imported Altium board (change c0090) is not implemented",
    }
)
"""The changes a pending check waits for. A pending check is skipped with its reason, never passed."""


@dataclass(frozen=True, slots=True)
class Step:
    """One step of the kit.

    ``result`` is a path under ``results/`` (kind ``file``) or the name of a field of ``form.json`` (kind
    ``form``); ``document`` is the file of the kit that a ``file`` step opens, relative to the kit;
    ``checks`` are the machine checks of a ``file`` step, in order; ``pending`` maps a check that is not
    run yet to the change it waits for; ``expected`` is the value a ``form`` step must hold.
    """

    id: str
    sample: str
    instruction: str
    kind: StepKind
    result: str
    hypotheses: tuple[str, ...]
    document: str = ""
    checks: tuple[Check, ...] = ()
    pending: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    value_type: ValueType | None = None
    expected: bool | int | str | None = None
    scripted: bool = False

    @property
    def group(self) -> int:
        match = STEP_ID.fullmatch(self.id)
        assert match is not None, self.id
        return int(match.group(1))

    def to_json(self) -> dict[str, object]:
        return {
            "id": self.id,
            "sample": self.sample,
            "instruction": self.instruction,
            "kind": self.kind,
            "result": self.result,
            "document": self.document,
            "checks": list(self.checks),
            "pending": dict(sorted(self.pending.items())),
            "value_type": self.value_type,
            "expected": self.expected,
            "hypotheses": list(self.hypotheses),
            "scripted": self.scripted,
        }


@dataclass(frozen=True, slots=True)
class Group:
    """A group of steps: its title, what it covers, and how long it takes by estimate (never measured)."""

    number: int
    title: str
    about: str
    minutes: int


GROUPS: tuple[Group, ...] = (
    Group(
        1,
        "Open and save each document kind",
        "A file that Fenolite wrote is loaded and written again in Altium's own bytes.",
        10,
    ),  # fmt: skip
    Group(2, "Compile and messages", "Each sample project is validated and its messages are kept.", 8),
    Group(3, "Change order into an empty board", "The schematic of `flat` fills a new PCB document.", 8),
    Group(4, "Rules editor and rule check", "The rules of `routed` and its two planted violations.", 8),
    Group(
        5,
        "Layer stack, vias, texts, keep-outs",
        "The board items of `board6`. Component bodies are written on request only and `board6` holds none: "
        "no step of the kit reads them (step X8 of the author report does, on the sample `body2`).",
        10,
    ),  # fmt: skip
    Group(6, "Repour", "The polygon of `routed` is poured by Altium.", 4),
    Group(7, "Output job", "The output job of `routed` opens and generates its containers.", 6),
    Group(8, "Sheet template and special strings", "The sheet template and the title block of `flat`.", 5),
    Group(9, "Libraries", "The schematic of `libs` is updated from the libraries that Fenolite wrote.", 5),
)

_WRITE = ("H-A-WRITE-SCHDOC", "H-A-WRITE-PCBDOC", "H-A-WRITE-SCHLIB", "H-A-WRITE-PCBLIB")
_RESAVE = "H-A-KIT-RESAVE"
_MESSAGES = (
    "With `{name}.PrjPcb` open and focused, run Project » Validate PCB Project. Then select every row of "
    "the Messages panel, copy the rows into `results/{name}/messages.txt`, one per line with the class "
    "first, or write the one line `no messages` when the panel is empty."
)


def _file(
    ident: str,
    sample: str,
    instruction: str,
    result: str,
    hypotheses: Sequence[str],
    *,
    document: str = "",
    checks: Sequence[Check] = ("resave",),
    pending: Mapping[str, str] | None = None,
    scripted: bool = False,
) -> Step:
    return Step(
        id=ident,
        sample=sample,
        instruction=instruction,
        kind="file",
        result=result,
        hypotheses=tuple(hypotheses),
        document=document,
        checks=tuple(checks),
        pending=MappingProxyType(dict(pending or {})),
        scripted=scripted,
    )


def _form(
    ident: str,
    sample: str,
    instruction: str,
    value_type: ValueType,
    expected: bool | int | str,
    hypotheses: Sequence[str],
) -> Step:
    return Step(
        id=ident,
        sample=sample,
        instruction=instruction,
        kind="form",
        result=ident,
        hypotheses=tuple(hypotheses),
        value_type=value_type,
        expected=expected,
    )


def _compile(ident: str, name: str, more: Sequence[str] = ()) -> Step:
    return _file(
        ident,
        name,
        _MESSAGES.format(name=name),
        f"{name}/messages.txt",
        ("H-A-KIT-COMPILE", "H-A-KIT-SCRIPT", "H-A-PH-NO-CACHE", *more),
        document=f"{name}/{name}.PrjPcb",
        checks=("messages",),
        scripted=True,
    )


STEPS: tuple[Step, ...] = (
    _file(
        "K1.1",
        "flat",
        "Open `flat/flat.PrjPcb` with File » Open Project and open `flat.SchDoc`. Save it with File » Save "
        "As as `results/flat/flat.SchDoc`.",
        "flat/flat.SchDoc",
        (_RESAVE, "H-A-WRITE-SCHDOC", "H-A-PH-ZERO-FIELDS"),
        document="flat/flat.SchDoc",
        checks=("resave", "parity"),
    ),
    _file(
        "K1.2",
        "flat",
        "Open `flat.PcbDoc` of the same project. Save it with File » Save As as `results/flat/flat.PcbDoc`.",
        "flat/flat.PcbDoc",
        (_RESAVE, "H-A-WRITE-PCBDOC", "H-A-PH-ZERO-FIELDS"),
        document="flat/flat.PcbDoc",
        checks=("resave", "parity"),
    ),
    _file(
        "K1.3",
        "libs",
        "Open `libs/libs.PrjPcb` and open `libs.SchLib`. Save it with File » Save As as "
        "`results/libs/libs.SchLib`.",
        "libs/libs.SchLib",
        (_RESAVE, "H-A-WRITE-SCHLIB", "H-A-PH-ZERO-FIELDS"),
        document="libs/libs.SchLib",
    ),
    _file(
        "K1.4",
        "libs",
        "Open `libs.PcbLib` of the same project. Save it with File » Save As as `results/libs/libs.PcbLib`.",
        "libs/libs.PcbLib",
        (_RESAVE, "H-A-WRITE-PCBLIB", "H-A-PH-ZERO-FIELDS"),
        document="libs/libs.PcbLib",
    ),
    _file(
        "K1.5",
        "flat",
        "With `flat.PrjPcb` focused, save the project with File » Save Project As as "
        "`results/flat/flat.PrjPcb`. Then close the project without saving anything else.",
        "flat/flat.PrjPcb",
        (_RESAVE,),
        document="flat/flat.PrjPcb",
    ),
    _file(
        "K1.6",
        "flat",
        "Open `flat/ascii/flat.SchDoc` with File » Open. Save it with File » Save As as "
        "`results/flat/flat_ascii.SchDoc`, in the format that Altium offers first.",
        "flat/flat_ascii.SchDoc",
        (_RESAVE, "H-A-WRITE-SCHDOC"),
        document="flat/ascii/flat.SchDoc",
        checks=("resave", "parity"),
    ),
    _file(
        "K1.7",
        "tree",
        "Open `tree/tree.PrjPcb` and its four schematic documents. Save each with File » Save As under its "
        "own name in `results/tree/`; this step's file is `results/tree/tree.SchDoc`.",
        "tree/tree.SchDoc",
        (_RESAVE, "H-A-WRITE-SCHDOC", "H-A-SCHX-TREE"),
        document="tree/tree.SchDoc",
    ),
    _form(
        "K1.8",
        "flat",
        "Type whether any document of the steps K1.1 to K1.7 showed a repair prompt, an upgrade prompt or an "
        "error dialog when it was opened or saved.",
        "bool",
        False,
        (*_WRITE, "H-A-PH-CHECKSUM", "H-A-PH-LAYOUT", "H-A-PH-ZERO-FIELDS"),
    ),
    _compile("K2.1", "flat", ("H-A-WRITE-SCHDOC",)),
    _compile("K2.2", "tree", ("H-A-SCHX-TREE",)),
    _compile("K2.3", "routed", ("H-A-WRITE-PCBDOC",)),
    _compile("K2.4", "board6"),
    _compile("K2.5", "libs", ("H-A-WRITE-SCHLIB", "H-A-WRITE-PCBLIB")),
    _file(
        "K3.1",
        "flat",
        "Add a PCB document to the project `flat` with File » New » PCB and save it as "
        "`results/flat/eco.PcbDoc`. Run Design » Update PCB Document eco.PcbDoc, validate and execute the "
        "changes, and save the document.",
        "flat/eco.PcbDoc",
        ("H-A-KIT-COMPILE",),
        document="flat/flat.PcbDoc",
        checks=("netlist", "parity"),
    ),
    _form(
        "K3.2",
        "flat",
        "Type the number of changes of the change order of step K3.1 that were marked invalid.",
        "int",
        0,
        ("H-A-KIT-COMPILE",),
    ),
    _form(
        "K4.1",
        "routed",
        "Open `routed/routed.PcbDoc` and Design » Rules. Type whether the editor lists the five rules of the "
        "table below with the values of the table, and no second rule of the kinds Clearance and Width.",
        "bool",
        True,
        ("H-A-RULE-KINDS",),
    ),
    _file(
        "K4.2",
        "routed",
        "Run Tools » Design Rule Check with the report file enabled and press Run Design Rule Check. Save "
        "the report that Altium writes as `results/routed/drc.html`.",
        "routed/drc.html",
        ("H-A-KIT-DRC",),
        document="routed/routed.PcbDoc",
        checks=("present", "copper.clearance"),
    ),
    _form(
        "K4.3",
        "routed",
        "Type the number of violations of the report of step K4.2 that name the Width rule of the class "
        "`PWR`.",
        "int",
        1,
        ("H-A-KIT-DRC", "H-A-RULE-SCOPE"),
    ),
    _form(
        "K4.4",
        "routed",
        "Type the number of violations of the same report that name the Clearance rule between the nets "
        "`VIN` and `LED_A`.",
        "int",
        1,
        ("H-A-KIT-DRC", "H-A-RULE-SCOPE"),
    ),
    _file(
        "K5.1",
        "board6",
        "Open `board6/board6.PrjPcb` and `board6.PcbDoc`. Save the document with File » Save As as "
        "`results/board6/board6.PcbDoc`.",
        "board6/board6.PcbDoc",
        (_RESAVE, "H-A-WRITE-PCBDOC"),
        document="board6/board6.PcbDoc",
        checks=("resave", "parity"),
    ),
    _form(
        "K5.2",
        "board6",
        "Open Design » Layer Stack Manager. Type the number of copper layers it lists.",
        "int",
        6,
        ("H-A-PCBX-STACK",),
    ),
    _form(
        "K5.3",
        "board6",
        "Select each of the three vias. Type whether they span the layers of the table below: one through, "
        "one blind, one buried.",
        "bool",
        True,
        ("H-A-PCBX-VIASPAN",),
    ),
    _form(
        "K5.4",
        "board6",
        "Select the keep-out. Type whether its restrictions are vias and tracks, and no other.",
        "bool",
        True,
        ("H-A-PCBX-KEEPOUT",),
    ),
    _form(
        "K5.5",
        "board6",
        "Read the four texts. Type whether each has the string, the layer and the rotation of the table "
        "below.",
        "bool",
        True,
        ("H-A-PCBX-TEXT",),
    ),
    _file(
        "K6.1",
        "routed",
        "In `routed.PcbDoc` run Tools » Polygon Pours » Repour All. Save the document with File » Save As as "
        "`results/routed/routed.PcbDoc`.",
        "routed/routed.PcbDoc",
        ("H-A-KIT-REPOUR", _RESAVE, "H-A-PCBX-REPOUR"),
        document="routed/routed.PcbDoc",
        checks=("resave", "parity", "poured", "copper.clearance"),
    ),
    _form(
        "K7.1",
        "routed",
        "Open `routed.OutJob` from the Projects panel. Type whether it opens without a message and lists "
        "the six outputs of the table below.",
        "bool",
        True,
        ("H-A-OUTJOB-OPEN",),
    ),
    _file(
        "K7.2",
        "routed",
        "Generate the container `fab`, then the container `doc`. Write the names of the generated files, "
        "one per line and without their folders, into `results/routed/outputs.txt`.",
        "routed/outputs.txt",
        ("H-A-OUTJOB-RUN", "H-A-OUTJOB-RUN-2"),
        document="routed/routed.OutJob",
        checks=("listing",),
    ),
    _file(
        "K8.1",
        KIT_SAMPLE,
        "Open `templates/iso5457_generic.SchDot` with File » Open. Save it with File » Save As as "
        "`results/templates/iso5457_generic.SchDot`.",
        "templates/iso5457_generic.SchDot",
        ("H-A-SCHDOT-OPEN",),
        document="templates/iso5457_generic.SchDot",
        checks=("present",),
    ),
    _form(
        "K8.2",
        "flat",
        "Open `flat.SchDoc` and read the title block. Type the title it shows.",
        "text",
        "Flat",
        ("H-A-SCHDOT-STRINGS",),
    ),
    _form(
        "K8.3",
        "flat",
        "Type the revision that the same title block shows.",
        "text",
        "B",
        ("H-A-SCHDOT-STRINGS",),
    ),
    _file(
        "K9.1",
        "libs",
        "Open `libs.SchDoc` and run Tools » Update From Libraries with full replacement for every part. "
        "Save the document with File » Save As as `results/libs/libs.SchDoc`.",
        "libs/libs.SchDoc",
        ("H-A-SCHLIB-UPDATE", "H-A-SCH-UPDATE"),
        document="libs/libs.SchDoc",
        checks=("netlist", "parity"),
    ),
    _form(
        "K9.2",
        "libs",
        "Type the number of parts that the update of step K9.1 reported as not found.",
        "int",
        0,
        ("H-A-SCHLIB-UPDATE",),
    ),
)
"""The closed list of the kit's steps, in the order a run performs them."""

TABLES = """\
## Values the steps read

Rules of `routed` (step K4.1). The values are shown in the unit Altium is set to.

| kind | scope | second scope | value |
|---|---|---|---|
| Clearance | net `VIN` | net `LED_A` | 1.5 mm |
| Clearance | all | all | 0.15 mm |
| Clearance | net class `PWR` | all | 0.2 mm |
| Width | net class `PWR` | | minimum and preferred 0.6 mm, maximum 2 mm |
| Width | all | | minimum 0.15 mm, preferred 0.25 mm, maximum 2 mm |

Planted violations of `routed` (steps K4.3 and K4.4): one `VIN` track that is 0.5 mm wide, and one `VIN`
via and one `LED_A` via whose edges are 0.6 mm apart.

Vias of `board6` (step K5.3), in millimetres from the upper-left corner of the outline:

| via | position | net | span |
|---|---|---|---|
| 1 | (10, 18.81) | `VIN` | top layer to bottom layer (through) |
| 2 | (38, 9) | `LED_A` | top layer to the first inner layer (blind) |
| 3 | (20, 24) | `GND` | first inner layer to the plane below it (buried) |

Texts of `board6` (step K5.5):

| string | layer | rotation |
|---|---|---|
| `Tensão 5 V` | Top Overlay | 0 |
| `BOARD6 REV A` | Bottom Overlay | 0, mirrored |
| `ASSEMBLY TOP` | Mechanical 13 | 0 |
| `BOTTOM` | Mechanical 14 | 90, mirrored |

Outputs of `routed.OutJob` (step K7.1):

| output | source | container |
|---|---|---|
| Gerber Files | `routed.PcbDoc` | `fab` |
| NC Drill Files | `routed.PcbDoc` | `fab` |
| Pick and Place | `routed.PcbDoc` | `fab` |
| Bill of Materials | the project | `fab` |
| Schematic Prints | the project | `doc` |
| PCB Prints | `routed.PcbDoc` | `doc` |
"""
"""The values that the typed steps are read against, as the samples' scripts state them."""


def step(ident: str, steps: Sequence[Step] = STEPS) -> Step:
    """The step ``ident``; ``KeyError`` when the list holds none."""
    for found in steps:
        if found.id == ident:
            return found
    raise KeyError(ident)


def _expected(found: Step) -> str:
    if found.kind == "file":
        text = f"file `{RESULTS}/{found.result}`"
        checks = "; ".join(CHECKS[name] for name in found.checks)
        pending = "".join(
            f"; pending ({change}): `{name}`, because {PENDING_REASONS[change]}"
            for name, change in sorted(found.pending.items())
        )
        return f"{text}. Checked: {checks}{pending}."
    shown = {True: "true", False: "false"}.get(found.expected, found.expected)  # type: ignore[arg-type]
    return f"form field `{found.result}` ({found.value_type}), expected `{shown}`."


def steps_markdown(steps: Sequence[Step] = STEPS) -> str:
    """``STEPS.md`` of a kit: the checklist, generated from ``steps`` (LF line ends, one final newline)."""
    lines = [
        "# Altium verification kit: steps",
        "",
        "Work on this folder only, and change no file outside `results/`. Do the steps in order. A step ends "
        "in a file that Altium writes under `results/`, or in a value that you type into "
        "`results/form.json` under `values`. First fill `altium_version` (as `AD <major>.<minor>`), "
        "`os_family` and `date` of that form.",
        "",
        "A step marked *scripted* may be done by the kit script instead: open `kit_script.pas` in Altium, "
        "focus the sample's project, run File » Run Script and choose `FenoliteKitRun`. The manual "
        "instruction of such a step is complete without the script. Before you use the script for the "
        "first time, open it in Altium's script editor and compile it: its calls were written from a "
        "rendering of Altium's documentation and it has not run in Altium. If a line is refused, report "
        "that line and do the scripted steps by hand.",
        "",
        "A saved file may hold your user name or the path of a folder. `fenolite kit verify` lists what it "
        "finds; read that list before you publish anything.",
    ]
    for group in GROUPS:
        members = [found for found in steps if found.group == group.number]
        if not members:
            continue
        lines += [
            "",
            f"## K{group.number}: {group.title}",
            "",
            f"{group.about} About {group.minutes} minutes.",
        ]
        for found in members:
            mark = " *(scripted)*" if found.scripted else ""
            lines += [
                "",
                f"- [ ] **{found.id}**{mark} (`{found.sample}`): {found.instruction}",
                f"  Result: {_expected(found)}",
                f"  Settles: {', '.join(f'`{ident}`' for ident in found.hypotheses)}.",
            ]
    return "\n".join([*lines, "", TABLES.rstrip("\n"), ""])


def problems(steps: Sequence[Step] = STEPS) -> list[str]:
    """What is wrong with the form of ``steps``: one message per broken rule of the requirement."""
    found: list[str] = []
    seen: set[str] = set()
    results: set[str] = set()
    for item in steps:
        where = item.id
        if STEP_ID.fullmatch(item.id) is None:
            found.append(f"{where}: the id is not K<group>.<n>")
        if item.id in seen:
            found.append(f"{where}: the id is used twice")
        seen.add(item.id)
        if item.sample not in (*SAMPLES, KIT_SAMPLE):
            found.append(f"{where}: unknown sample {item.sample!r}")
        if len(re.findall(r"[.!?](?:\s|$)", item.instruction)) > 2:
            found.append(f"{where}: the instruction has more than two sentences")
        if not item.hypotheses:
            found.append(f"{where}: the step settles no hypothesis")
        if item.result in results:
            found.append(f"{where}: the result {item.result!r} is used twice")
        results.add(item.result)
        if item.kind == "file":
            if not item.checks or item.expected is not None or item.value_type is not None:
                found.append(f"{where}: a file step has checks and no expected value")
            if item.result.startswith("/") or ".." in item.result.split("/") or "\\" in item.result:
                found.append(f"{where}: the result is not a path under {RESULTS}/")
        else:
            if item.value_type is None or item.expected is None or item.checks or item.scripted:
                found.append(f"{where}: a form step has a type and an expected value, and is never scripted")
        for name, change in item.pending.items():
            if change not in PENDING_REASONS:
                found.append(f"{where}: the pending check {name} names the unknown change {change}")
    return found


__all__ = [
    "CHECKS",
    "GROUPS",
    "KIT_SAMPLE",
    "PENDING_REASONS",
    "RESULTS",
    "SAMPLES",
    "STEPS",
    "STEP_ID",
    "TABLES",
    "Group",
    "Step",
    "problems",
    "step",
    "steps_markdown",
]
