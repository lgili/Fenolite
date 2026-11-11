# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite.api.convert``: a conversion, verified (capability design-conversion, "Conversion verified by
equivalence", "Differences matched to the report" and "Conversion without verification"; change c0159).

``convert`` calls ``fenolite.convert.convert_project``, writes the files into a private temporary folder,
reads the direction's read-back file with the target backend and compares it with the design that was
written through ``fenolite.api.equivalent``, at the highest level both hold, under the direction's profile
(``fenolite/convert/data/profiles.toml``). Each difference is then matched against the report: one that a
lost item explains (``convert.report.EXPLAINS``) is listed under ``explained`` with the lost kind, any other
gives one ``convert.unexplained`` error. Nothing outside the temporary folder is written.
"""

from __future__ import annotations

import dataclasses
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass, replace
from functools import cache
from pathlib import Path, PurePosixPath
from typing import Any

import fenolite.convert as convert_package
import fenolite.convert.schematic as drawing_lib
from fenolite.api.equivalence import EquivalenceResult, equivalent
from fenolite.api.sides import _with_source_bom, read_schematic  # pyright: ignore[reportPrivateUsage]
from fenolite.backends import registry
from fenolite.backends.altium import drawn_read
from fenolite.backends.base import BoardFrame
from fenolite.backends.kicad import parity_inputs
from fenolite.checks.equivalence import Profile, load_profiles
from fenolite.checks.equivalence.model import Difference
from fenolite.convert import PROFILES_FILE, Conversion, convert_project, profiles_text
from fenolite.convert.codes import issue
from fenolite.convert.direction import Pour, Target
from fenolite.convert.report import ConversionReport, Explainer
from fenolite.convert.rings import RING_KIND, RingDifference, compare_rings
from fenolite.convert.schematic import root_schematic
from fenolite.core.errors import FenoliteError, Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.model.circuit import Circuit
from fenolite.model.design import Design
from fenolite.model.drawn import DrawnSchematic
from fenolite.model.drawn_connect import PinKey, PinPoint


@cache
def profiles() -> dict[str, Profile]:
    """The verification profiles by name."""
    return {profile.name: profile for profile in load_profiles(profiles_text(), file=PROFILES_FILE)}


@dataclass(frozen=True, slots=True)
class Explained:
    """A difference of the read-back that a lost item of the report explains, with the lost kind."""

    difference: Difference
    kind: str


@dataclass(frozen=True, slots=True)
class ConversionResult:
    """A conversion with its verification: the comparison (``None`` without one), the differences it
    explained and those it did not, the issues in order and the evidence."""

    conversion: Conversion
    equivalence: EquivalenceResult | None
    explained: tuple[Explained, ...]
    unexplained: tuple[Difference, ...]
    issues: tuple[Issue, ...]
    evidence: Evidence

    def equivalence_json(self) -> dict[str, Any] | None:
        """``result.equivalence`` of ``fenolite convert``: the reply of ``fenolite equivalent`` with the
        explained differences and the count of the unexplained ones; ``None`` without verification."""
        if self.equivalence is None:
            return None
        reply = self.equivalence.to_json()
        reply["explained"] = [
            {
                "level": found.difference.level,
                "kind": found.difference.kind,
                "where": found.difference.where,
                "field": found.difference.field,
                "a": found.difference.a,
                "b": found.difference.b,
                "by": found.kind,
            }
            for found in self.explained
        ]
        reply["unexplained"] = len(self.unexplained)
        return reply


def _unexplained(difference: Difference) -> Issue:
    message = (
        f"{difference.where}: {difference.field} is {difference.a or 'nothing'!r} in the source and "
        f"{difference.b or 'nothing'!r} in the converted project (level {difference.level}, "
        f"{difference.kind}), and no loss of the report explains it"
    )
    hint = "a writer changed the design without saying so: report it with the source"
    return issue("convert.unexplained", message, where=difference.where, hint=hint)


SCHEMATIC_LEVEL = 2
"""The level at which a downgrade's root schematic is compared with the source's (change c0162)."""


def _schematic(
    conversion: Conversion, folder: Path, profile: Profile | None
) -> tuple[Difference, ...] | Issue:
    """The differences between the source's root schematic and the written one at level 2, or the
    ``convert.schematic-unverified`` warning when they cannot be compared (change c0162)."""
    assert conversion.schematic is not None
    if conversion.source.backend == "altium":
        try:
            found = equivalent(
                replace(conversion.design, board=None),
                folder / conversion.schematic,
                level=SCHEMATIC_LEVEL,
                profile=profile,
                ignore_refs=("",),
            )
        except FenoliteError as error:
            # a drawn sheet is outside Fenolite's own netlist grammar: reading it back needs kicad-cli
            return issue(
                "convert.schematic-unverified",
                f"the schematic was not compared with the source's: {error}",
                where=conversion.schematic,
                hint=getattr(error, "hint", "") or "install kicad-cli to compare the schematic too",
            )
        return found.report.differences if found.report is not None else ()
    suffix = ".kicad_sch" if conversion.target == "altium" else PurePosixPath(conversion.schematic).suffix
    source = conversion.source.root / f"{conversion.source.name}{suffix}"
    target = folder / conversion.schematic
    if conversion.target == "altium":
        from fenolite.backends.altium.prjpcb import relisted
        from fenolite.backends.altium.project import write_prjpcb

        stem = PurePosixPath(conversion.read_back).stem
        # the first sheet of the written project: ``<name>.SchDoc``, or a flat project's first document
        listed = [
            line.partition("=")[2].strip().replace("\\", "/")
            for line in conversion.files.get(f"{stem}.PrjPcb", b"")
            .decode("utf-8-sig", "replace")
            .splitlines()
            if line.startswith("DocumentPath=") and line.strip().endswith(".SchDoc")
        ]
        main = f"{stem}.SchDoc" if f"{stem}.SchDoc" in conversion.files or not listed else listed[0]
        sheets = [f for f in conversion.files if f.endswith(".SchDoc") and f != main]
        libraries = [f for f in conversion.files if f.endswith(".SchLib")]
        # Physical pads can include unused pins absent from the schematic circuit.
        target = folder / "schematic-verification.PrjPcb"
        data = write_prjpcb(
            schematic=PurePosixPath(main).name,
            sheets=tuple(PurePosixPath(f).name for f in sheets),
            libraries=tuple(PurePosixPath(f).name for f in libraries),
            # the names of the channels of a sheet written once for several symbols (c0470)
            channels=b"ChannelDesignatorFormatString=" in conversion.files.get(f"{stem}.PrjPcb", b""),
        )
        # the documents in the folders of a source's layout (change c0483)
        if any("/" in f for f in (main, *sheets, *libraries)):
            data = relisted(data, [(f, PurePosixPath(f).name) for f in (main, *sheets, *libraries)])
        target.write_bytes(data)
    try:
        found = equivalent(source, target, level=SCHEMATIC_LEVEL, profile=profile)
    except FenoliteError as error:
        return issue(
            "convert.schematic-unverified",
            f"the schematic was not compared with the source's: {error}",
            where=conversion.schematic,
            hint=getattr(error, "hint", "") or "install kicad-cli to compare the schematic too",
        )
    return found.report.differences if found.report is not None else ()


def _placed(design: Design) -> Design:
    """``design`` with only the components that a footprint of its board places or that are BOM-only
    (c0334, read back with the board), and their net members: what a written board can hold. The written
    schematic is compared with the others (change c0371)."""
    if design.board is None:
        return design
    placed = {fp.component_id for fp in design.board.footprints}
    placed |= {c.id for c in design.circuit.components if c.bom_only}
    circuit = design.circuit
    nets = tuple(
        replace(net, members=tuple(m for m in net.members if m.component_id in placed))
        for net in circuit.nets
    )
    components = tuple(c for c in circuit.components if c.id in placed)
    return replace(design, circuit=replace(circuit, components=components, nets=nets))


def _rings(conversion: Conversion, written: Path) -> tuple[RingDifference, ...]:
    """The edge rings of the source against those of the written board read back (change c0170;
    ``convert.rings``): each backend's ``BoardFrame.board_edges``. Nothing when a backend gives none."""
    source_backend = registry.get(conversion.source.backend)
    target_backend = registry.for_path(written)
    if not isinstance(source_backend, BoardFrame) or not isinstance(target_backend, BoardFrame):
        return ()
    source = source_backend.board_edges(conversion.source.design)
    if not source:
        return ()
    read = target_backend.read(written).design
    return compare_rings(source, target_backend.board_edges(read), conversion.report)


_DRAWN_KINDS = {
    "wire": "wire", "bus": "bus", "bus_alias": "bus", "bus_entry": "bus-entry", "junction": "junction",
    "no_connect": "no-connect", "power": "power", "sheet_ref": "sheet-symbol", "label": "label",
    "sheet": "sheet",
}  # fmt: skip
"""The report kind of a level S item by the head of its field."""


def _drawn_kinds(difference: Difference) -> tuple[str, ...]:
    """The report kinds whose changes or losses explain a level S ``difference``."""
    if difference.kind.startswith("symbol-"):
        return ("schematic-symbol", "symbol-graphic")
    if difference.kind == "sheet-missing":
        return ("sheet", "sheet-symbol")
    if difference.kind == "drawn-net":
        return ("label", "port", "power", "wire", "bus", "sheet-symbol", "harness")
    head = difference.field.split(".", 1)[0]
    if head == "opaque":
        return tuple(sorted(drawn_read.KINDS))
    if head == "label":
        return ("label", "port")
    if difference.field.startswith("sheet.title_block"):
        return ("title-block",)
    return (_DRAWN_KINDS.get(head, head),)


def explain_drawn(difference: Difference, report: ConversionReport) -> str | None:
    """The report kind that explains a level S ``difference`` of a converted drawing (design D5): a kind
    whose row has changed or lost items, else ``None``. A net of the drawing that differs from the circuit's
    is explained by a lost item only: a changed item is written in another form that keeps its connection."""
    for kind in _drawn_kinds(difference):
        row = report.row(kind)
        if row is not None and (row.lost or (row.changed and difference.kind != "drawn-net")):
            return kind
    return None


def _net_issues(
    drawn: DrawnSchematic,
    pins: Mapping[PinKey, tuple[PinPoint, ...]],
    circuit: Circuit,
    paths: Mapping[str, str],
) -> tuple[list[Issue], list[Issue]]:
    """The pins whose drawn net differs from ``circuit``'s (``drawn_connect.pin_differences``) and the other
    errors of ``drawn_connect.compare``, for the resolved netlist of ``drawn``. ``paths`` maps a reference
    to the component path the drawing names it by. Members of a bus group join by their names, across the
    group names on one bus: KiCad joins them so, and Altium joins the entries of a harness by name."""
    from fenolite.backends.kicad.drawn import bus_member_keys
    from fenolite.model.drawn_connect import PATH_PROPERTY, compare, pin_differences, resolve

    by_ref = {c.ref for c in circuit.components if c.ref and c.ref in paths}
    components = tuple(
        dataclasses.replace(c, properties={**c.properties, PATH_PROPERTY: paths[c.ref]})
        if c.ref in by_ref
        else c
        for c in circuit.components
    )
    named = dataclasses.replace(circuit, components=components)
    netlist = resolve(drawn, pins, _bus_member_keys=bus_member_keys)
    per_pin = [i for i in pin_differences(netlist, named) if i.severity == "error"]
    codes = {i.code for i in per_pin}
    others = [
        i
        for i in compare(netlist, named)
        if i.severity == "error" and not (i.code in codes and i.message.startswith(_SUMMARY))
    ]
    return per_pin, others


_SUMMARY = "the drawing does not mean the code: "


def _net_differences(
    source: tuple[list[Issue], list[Issue]], written: tuple[list[Issue], list[Issue]]
) -> list[Difference]:
    """The ``drawn-net`` differences of the written drawing (``_net_issues``) that the source drawing does not
    have itself: its differing pins, summarised in one difference, and its other errors."""
    from fenolite.checks.equivalence import SCHEMATIC_LEVEL

    own_pins = {i.where for i in source[0]}
    own = {(i.code, i.where, i.message) for i in source[1]}
    pins = [i for i in written[0] if i.where not in own_pins]
    found: list[Issue] = []
    if pins:
        more = f" (and {len(pins) - 1} more)" if len(pins) > 1 else ""
        found.append(dataclasses.replace(pins[0], message=f"{_SUMMARY}{pins[0].message}{more}"))
    found += [i for i in written[1] if (i.code, i.where, i.message) not in own]
    return [
        Difference(SCHEMATIC_LEVEL, "drawn-net", i.where or i.code, "circuit", i.message, "") for i in found
    ]


def verify_drawing(conversion: Conversion, folder: Path) -> tuple[Difference, ...] | Issue:
    """The level S differences of the drawing that ``conversion`` wrote (change c0470, design D5): the source
    drawing against the drawing read back from the files in ``folder``, then the resolved netlist of the
    written drawing against the circuit written with it, less the disagreements the source drawing has with
    that circuit itself. Nothing for a conversion that wrote no drawing;
    the ``convert.schematic-unverified`` warning when the written drawing cannot be read back."""
    from fenolite.backends.kicad import drawn as kicad_drawn
    from fenolite.checks.equivalence import compare_drawn
    from fenolite.checks.equivalence.drawn import flattened
    from fenolite.convert.codes import issue
    from fenolite.convert.sources import read_source
    from fenolite.core.errors import FenoliteError

    if conversion.report.row("sheet") is None:
        return ()
    try:
        if conversion.source.backend == "altium":
            source = drawing_lib.drawing_of(conversion.source)
            if source is None:
                return ()
            circuit = conversion.design.circuit
            held = {c.ref: c.path for c in circuit.components if c.ref and c.path}
            files = {k: v for k, v in conversion.files.items() if k.endswith(".kicad_sch")}
            # a reused KiCad sheet was folded from its Altium copies (``refolded``): its parts are read by
            # their KiCad names, then copied once per instance again, as Altium wrote them
            folded, renamed = drawing_lib.refolded(source.extracted)
            # a channel of a Repeat is drawn by its record's designator below its module (change c0470)
            channels = drawing_lib.channel_paths(
                folded, conversion.design, drawing_lib.links_of(conversion.source.design)
            )
            paths = {
                ref: renamed.get(path, path)
                for ref, path in (kicad_drawn.refs_to_paths(circuit) | held | channels).items()
            }
            back, back_pins, _ = drawing_lib.read_kicad_drawing(files, paths, conversion.schematic)
            back, back_pins = flattened(back, back_pins, {path: ref for ref, path in paths.items()})
            # KiCad names a channel's part by its board designator below its module
            back_paths = paths | {
                ref: f"{head}/{ref}" if (head := paths[ref].rpartition("/")[0]) else ref
                for ref in channels
                if ref in paths
            }
            drawn, pins = source.extracted.drawn, source.extracted.pins
        else:
            root = root_schematic(conversion.source)
            design, _, _ = drawing_lib.inputs(conversion.source, conversion.source.design)
            if root is None or design is None:
                return ()
            circuit = design.circuit
            paths = kicad_drawn.refs_to_paths(circuit)
            sheets = parity_inputs.read_sheets(root)
            root_file = next(iter(sheets))
            children = {name: value for name, value in sheets.items() if name != root_file}
            found = kicad_drawn.extract_with_pins(
                sheets[root_file],
                children,
                components=paths,
                root_file=root_file,
            )
            from fenolite.backends.kicad import sheet_carrier

            texts = {name: (root.parent / name).read_text(encoding="utf-8") for name in sheets}
            drawn, pins = sheet_carrier.take_drawing(texts, found.drawn, root_file), found.pins
            # Altium writes a reused sheet once per instance, its parts named by their own references
            drawn, pins = flattened(drawn, pins, {path: ref for ref, path in paths.items()})
            paths = {ref: f"{path.rpartition('/')[0]}/{ref}".lstrip("/") for ref, path in paths.items()}
            written = next(name for name in conversion.files if name.endswith(".PrjPcb"))
            target = folder / "schematic-verification.PrjPcb"
            written_source = read_source(target if target.is_file() else folder / written)
            read = drawn_read.extract_with_pins(drawing_lib.altium_sheets(written_source))
            # a sheet written once for several channels names their parts by its records (c0470): each
            # channel is copied, its parts named by their references, as the source's copies are
            channels = drawing_lib.channel_paths(
                drawing_lib.refolded(read)[0],
                written_source.design,
                drawing_lib.links_of(written_source.design),
            )
            back, back_pins = flattened(read.drawn, read.pins, {path: ref for ref, path in channels.items()})
            back_paths = paths
    except (FenoliteError, ValueError, StopIteration) as error:
        return issue(
            "convert.schematic-unverified",
            f"the written drawing was not compared with the source's: {error}",
            where=conversion.schematic or "",
            hint="convert with --no-verify to skip the check, and report it with the source",
        )
    found_s = compare_drawn(drawn, back, pins_a=pins, pins_b=back_pins)
    # a disagreement of the source drawing with the code is the source's own, not one the conversion made
    nets = _net_differences(
        _net_issues(drawn, pins, circuit, paths), _net_issues(back, back_pins, circuit, back_paths)
    )
    return (*found_s.differences, *nets)


def verify_conversion(conversion: Conversion, *, profile: Profile | None = None) -> ConversionResult:
    """The verification of ``conversion``: its files read back from a private temporary folder and
    compared with the design that was written, a downgrade's root schematic with the source's at level
    2, and the edge rings of the written board with the source's (change c0170, ``convert.rings``: a ring
    is a difference of the kind ``edge-ring`` at level 0, explained by the ``cutout`` or ``outline`` rows of
    the report). ``profile`` overrides the conversion's."""
    chosen = (
        profile if profile is not None else profiles().get(conversion.profile or conversion.direction.profile)
    )
    schematic: tuple[Difference, ...] | Issue = ()
    drawing: tuple[Difference, ...] | Issue = ()
    with tempfile.TemporaryDirectory(prefix="fenolite-convert-") as name:
        folder = Path(name)
        for key, data in conversion.files.items():
            target = folder.joinpath(*PurePosixPath(key).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
        model = _placed(conversion.design) if conversion.schematic is not None else conversion.design
        if conversion.read_back.endswith(".PrjPcb") and conversion.source.schematic is not None:
            # no PCB document was written (an empty board): the project reads back its sheets' circuit,
            # which is compared with the source schematic's (change c0470)
            model = replace(model, circuit=conversion.source.schematic.circuit, board=None)
        compared = equivalent(
            model,
            folder / conversion.read_back,
            profile=chosen,
            # A free pad reads back as a component with no designator (a board-only footprint): it is a
            # pad, not a component, so level 1 ignores the empty reference (change c0160).
            ignore_refs=("",),
        )
        if conversion.schematic is not None:
            schematic = _schematic(conversion, folder, chosen)
        drawing = verify_drawing(conversion, folder)
        rings = _rings(conversion, folder / conversion.read_back)
    explanation_model = (
        conversion.source.design if conversion.source.backend == "altium" else conversion.design
    )
    explainer = Explainer(explanation_model, conversion.report)
    explained: list[Explained] = []
    unexplained: list[Difference] = []
    report = compared.report
    for difference in report.differences if report is not None else ():
        kind = explainer.explain(difference.kind, difference.where, difference.a, difference.b)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append(Explained(difference, kind))
    for difference in schematic if not isinstance(schematic, Issue) else ():
        kind = explainer.explain(difference.kind, difference.where, difference.a, difference.b)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append(Explained(difference, kind))
    for difference in drawing if not isinstance(drawing, Issue) else ():
        # level S of a written drawing (change c0470, design D5): a report row of its kind explains it
        kind = explain_drawn(difference, conversion.report)
        if kind is None:
            unexplained.append(difference)
        else:
            explained.append(Explained(difference, kind))
    for found in rings:
        difference = Difference(
            0,
            RING_KIND,
            found.name,
            "ring",
            found.text if found.side == "source" else "",
            found.text if found.side == "written" else "",
        )
        if found.explained_by is None:
            unexplained.append(difference)
        else:
            explained.append(Explained(difference, found.explained_by))
    notes = tuple(found for found in (schematic, drawing) if isinstance(found, Issue))
    # the comparison's own errors are its differences: each is explained, or one convert.unexplained; its
    # notices are kept, and the read-back's own reader notes are not the conversion's
    kept = tuple(
        found for found in compared.issues if found.severity != "error" and found.code.startswith("equiv.")
    )
    issues = (*conversion.issues, *(_unexplained(d) for d in unexplained), *notes, *kept)
    evidence = Evidence.combine(conversion.evidence, compared.evidence)
    return ConversionResult(conversion, compared, tuple(explained), tuple(unexplained), issues, evidence)


def convert(
    source: str | Path,
    *,
    to: Target,
    kicad_version: int = 10,
    allow_lossy: bool = False,
    bodies: str = "extruded",
    name: str | None = None,
    verify: bool = True,
    pour: Pour | None = None,
) -> ConversionResult:
    """Convert ``source`` to ``to`` and, with ``verify``, check the written project against the source
    (capability design-conversion, "Conversion verified by equivalence"). The arguments are those of
    ``fenolite.convert.convert_project``; its errors are raised unchanged. Without ``verify`` the result
    holds no comparison, one ``convert.no-verify`` warning, and the evidence ``UNVERIFIED``."""
    prepared = convert_package.read_source(Path(source))
    # Reuse private API source preparation before the writer; retain the original rule/input context.
    if prepared.backend == "kicad" and (root := root_schematic(prepared)) is not None:
        prepared = replace(prepared, design=_with_source_bom(prepared.design, root))
    if to == "altium" and prepared.backend == "kicad" and (root := root_schematic(prepared)) is not None:
        prepared = replace(prepared, schematic=read_schematic(root).design)
    conversion = convert_project(
        prepared,
        to=to,
        kicad_version=kicad_version,
        allow_lossy=allow_lossy,
        bodies=bodies,
        name=name,
        pour=pour,
    )
    if verify:
        return verify_conversion(conversion)
    warning = issue(
        "convert.no-verify",
        "the converted project was not read back and compared with the source",
        hint="run without --no-verify to check the conversion",
    )
    evidence = Evidence(Level.UNVERIFIED, None, conversion.evidence.hypotheses)
    return ConversionResult(conversion, None, (), (), (*conversion.issues, warning), evidence)


__all__ = ["ConversionResult", "Explained", "convert", "profiles", "verify_conversion"]
