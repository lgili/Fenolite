# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad schematic circuits, embedded symbols and sheet paths for conversion (c0160 task 4.1).

Pure conversion uses the existing own-netlist grammar. The API can prepare a circuit with its existing
KiCad exporter when the source exceeds that grammar; this module never runs a tool.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, cast

from fenolite.backends.altium import drawn_carrier, drawn_read, project
from fenolite.backends.altium.adapter.netlist import SheetInput
from fenolite.backends.altium.altsym import AltiumSymbol, from_symbol_def
from fenolite.backends.kicad import parity_inputs
from fenolite.backends.kicad.netlist import NO_CONNECT_SUFFIX
from fenolite.backends.kicad.netnames import model_name
from fenolite.convert import altium_links
from fenolite.convert.direction import TargetLimitError
from fenolite.convert.sources import SourceError, SourceProject
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.circuit import Circuit, Component, Module, Net, Pin, PinRef
from fenolite.model.design import Design
from fenolite.model.drawn import DrawnSchematic, DrawnSheet
from fenolite.model.drawn_connect import PinKey, PinPoint, natural
from fenolite.model.library import SymbolDef
from fenolite.model.schematic import SymbolInstance

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-A-CONV-SCHEMATIC",))


def root_schematic(source: SourceProject) -> Path | None:
    path = source.path.with_suffix(".kicad_sch")
    return path if path.is_file() else None


def _shape(definition: SymbolDef) -> object:
    """What two embedded symbols of one source link must share to be written as one (change c0451): their
    pins by number, name and type, as ``lower.schematic_design`` compares a link's components. The KiCad
    schematic of an Altium conversion is generated, so one source symbol gives each component its own
    symbol whose pins may lie in another order; the schematic is generated again on the way back."""
    return tuple(sorted((p.number, p.name, p.etype) for p in definition.pins if p.body_style in (0, 1)))


_OWN_FIELDS = frozenset({"Reference", "Value", "Footprint"})
"""The symbol fields a component holds as its own attributes, not as properties."""


def inputs(
    source: SourceProject,
    design: Design,
    links: Mapping[str, str] | None = None,
    bodies: dict[str, AltiumSymbol] | None = None,
) -> tuple[Design | None, dict[str, AltiumSymbol], tuple[str, ...]]:
    """The separate schematic design and symbols; board geometry and board nets stay with the board.
    ``links`` (reference → symbol link; change c0451) names the source symbol of a component of an Altium
    conversion: the component takes that link when every component of the link gives the same pins by
    number, name and type, else its own ``PART_<ref>``. The library holds the symbol of the first
    unmirrored component of a link; ``bodies`` receives, by reference, the own symbol of each other
    component whose symbol differs (change c0470: Altium keeps one body per instance, which the drawn
    writer gives it)."""
    root = root_schematic(source)
    if root is None:
        return None, {}, ()
    sheets = parity_inputs.read_sheets(root)
    if source.schematic is not None:
        circuit = source.schematic.circuit
    else:
        if parity_inputs.grammar_issues(sheets):
            raise SourceError(
                "the source schematic needs an exported netlist",
                where=root.name,
                hint="use fenolite.api.convert or fenolite convert; the pure package runs no tool",
            )
        netlist = parity_inputs.own_netlist(sheets, project=root.stem)
        ids = {
            c.ref: derived_id("cmp", "conversion", f"{root.stem}:{c.ref}")
            for c in netlist.components
            if not c.ref.startswith("#")
        }
        circuit = Circuit(
            components=tuple(
                Component(id=ids[c.ref], ref=c.ref, value=c.value, lib_footprint_ref=c.footprint)
                for c in netlist.components
                if c.ref in ids
            ),
            nets=tuple(
                Net(
                    id=derived_id("net", "conversion", n.name),
                    name=n.name,
                    members=tuple(PinRef(ids[p.ref], p.pin) for p in n.nodes if p.ref in ids),
                )
                for n in netlist.nets
                if len(n.nodes) != 1 or not n.nodes[0].pintype.endswith(NO_CONNECT_SUFFIX)
            ),
            no_connects=tuple(
                dict.fromkeys(
                    PinRef(ids[p.ref], p.pin)
                    for n in netlist.nets
                    for p in n.nodes
                    if p.ref in ids and p.pintype.endswith(NO_CONNECT_SUFFIX)
                )
            ),
        )
    # a net takes the board's spelling: KiCad's stored ``{slash}`` is ``/`` (H-K-SCH-SLASH, change c0470)
    circuit = replace(circuit, nets=tuple(replace(n, name=model_name(n.name)) for n in circuit.nets))
    circuit = replace(
        circuit, components=tuple(parity_inputs.sheet_values(circuit.components, sheets.values()))
    )
    board_ids = {c.ref: c.id for c in design.circuit.components}
    ids = {c.id: board_ids.get(c.ref, c.id) for c in circuit.components}
    paths: dict[str, str] = {}
    modules_of: dict[str, str] = {}
    """Per sheet file, the module path of its first instance: the module of a symbol without an instance
    of this project (change c0470), named by the sheet name as the instances are, not by the file."""
    modules_of[root.name] = ""
    tops = flat_tops(root.read_text(encoding="utf-8"))
    root_sheet = next(iter(sheets.values()))
    paths["/" + root_sheet.native_ids.get("kicad", root_sheet.id)] = ""
    queue: list[tuple[str, str, str, tuple[str, ...]]] = [
        (root.name, "", "/" + root_sheet.native_ids.get("kicad", root_sheet.id), ())
    ]
    while queue:
        file, module, native_path, trail = queue.pop(0)
        if file in trail:
            raise SourceError("cyclic schematic hierarchy", where=file)
        for ref in sheets[file].sheets:
            child = (PurePosixPath(file).parent / ref.file).as_posix()
            if child not in sheets:
                raise SourceError("missing schematic sheet", where=child)
            label = ref.name.replace("/", "_") or Path(child).stem
            # the sheets of a root that stands for a flat Altium project's documents are top sheets
            path = "" if file == root.name and tops else f"{module}/{label}".lstrip("/")
            native = native_path + "/" + ref.native_ids.get("kicad", ref.id)
            paths[native] = path
            modules_of.setdefault(child, path)
            queue.append((child, path, native, (*trail, file)))
    symbols_by_ref: dict[str, tuple[SymbolInstance, SymbolDef, str]] = {}
    shared: dict[str, str] = {}
    """Per reference, the name its symbol has in every instance of a sheet used more than once: the
    first of its references in natural order, so that the drawing names the part once (change c0470)."""
    for file, sheet in sheets.items():
        known = {s.lib_id: s for s in sheet.lib_symbols}
        for instance in sheet.symbols:
            symbol = known.get(instance.lib_name or instance.lib_ref)
            if symbol is None:
                continue
            uses = [(u.ref, paths.get(u.path, ""), u.unit) for u in instance.uses if u.project == root.stem]
            if not uses:
                uses = [(instance.ref, modules_of.get(file, Path(file).stem), instance.unit)]
            named = sorted((ref for ref, _, _ in uses if ref and not ref.startswith("#")), key=natural)
            for ref, module, unit in uses:
                if ref.startswith("#") or not ref:
                    continue
                shared.setdefault(ref, named[0])
                held = symbols_by_ref.get(ref)
                if held is None or unit < held[0].unit:
                    symbols_by_ref[ref] = (dataclasses.replace(instance, unit=unit), symbol, module)
    changed: list[str] = []
    parts: list[Component] = []
    symbols: dict[str, AltiumSymbol] = {}
    shapes: dict[str, set[object]] = {}
    for component in circuit.components:
        held = symbols_by_ref.get(component.ref)
        source_link = (links or {}).get(component.ref, "")
        if held is not None and source_link:
            shapes.setdefault(source_link, set()).add(_shape(held[1]))
    clashing = {link for link, found in shapes.items() if len(found) > 1}
    # an unmirrored component of a link gives its library symbol (the reader draws an Altium part that is
    # not mirrored with its library body); another one keeps its own body in the sheet (change c0470)
    firsts: dict[str, AltiumSymbol] = {}
    own: dict[str, AltiumSymbol] = {}
    in_order = sorted(
        circuit.components,
        key=lambda c: bool((held := symbols_by_ref.get(c.ref)) is not None and held[0].mirror),
    )
    for component in in_order:
        held = symbols_by_ref.get(component.ref)
        source_link = (links or {}).get(component.ref, "")
        if held is None or not source_link or source_link in clashing:
            continue
        name = source_link.rpartition(":")[2]
        try:
            body = from_symbol_def(held[1], lib_ref=name, footprint=None, bodies="graphics", fine=True)
        except ValueError:
            continue  # refused below, with its reason
        if firsts.setdefault(source_link, body) != body:
            own[component.ref] = body
    if bodies is not None:
        bodies.update(own)
    by_body: dict[AltiumSymbol, tuple[str, AltiumSymbol]] = {}
    for component in circuit.components:
        held = symbols_by_ref.get(component.ref)
        if held is None:
            raise SourceError("the schematic component has no embedded symbol", where=component.ref)
        instance, definition, module = held
        # Equal embedded bodies share one library symbol; distinct bodies of one lib id stay apart.
        symbol_name = f"PART_{component.ref}"
        link = f"{design.header.name}.SchLib:{symbol_name}"
        source_link = (links or {}).get(component.ref, "")
        if source_link and source_link not in clashing:
            link, symbol_name = source_link, source_link.rpartition(":")[2]
        try:
            body = from_symbol_def(
                definition, lib_ref=symbol_name, footprint=None, bodies="graphics", fine=True
            )
        except ValueError as error:  # an off-grid pin: the SchLib holds pins on whole mils (PinFrac)
            raise TargetLimitError(
                f"the schematic of {root.name} cannot be written: {error}",
                hint="Altium library pins lie on whole mils; move the pin onto a 1-mil grid in KiCad "
                "(KiCad's 50-mil grid is on it); nothing was converted",
            ) from None
        if link == source_link:
            symbols[link] = firsts.get(link, body)
        else:
            link, body = by_body.setdefault(replace(body, lib_ref=""), (link, body))
            symbols[link] = body
        ident = ids[component.id]
        pins = tuple(
            Pin(
                id=derived_id("pin", "conversion", f"{ident}:{p.number}"),
                number=p.number,
                name=p.name,
                etype=p.etype,
            )
            for p in definition.pins
            if p.body_style in (0, 1)
        )
        pins = tuple({p.number: p for p in pins}.values())
        value = component.value
        if value.startswith("="):
            value = " " + value
            changed.append(ident)
        parts.append(
            dataclasses.replace(
                component,
                id=ident,
                value=value,
                pins=pins,
                lib_symbol_ref=link,
                properties={
                    # the symbol's own fields become parameters of the Altium part (change c0470)
                    # the links of an Altium source are restored, never parameters (c0451)
                    **{
                        k: v
                        for k, v in instance.properties.items()
                        if k not in _OWN_FIELDS and k not in altium_links.NAMES
                    },
                    **component.properties,
                    project.PATH_PROPERTY: f"{module}/{shared.get(component.ref, component.ref)}".lstrip("/"),
                },
                dnp=instance.dnp or component.dnp,
            )
        )
    nets = tuple(
        dataclasses.replace(n, members=tuple(PinRef(ids[m.component_id], m.pin) for m in n.members))
        for n in circuit.nets
    )
    modules = tuple(
        Module(
            id=derived_id("mod", "conversion", path),
            path=path,
            component_ids=tuple(c.id for c in parts if project.component_path(c).rpartition("/")[0] == path),
        )
        for path in sorted(set(paths.values()) - {""})
    )
    # KiCad marks the stacked pins of one net not connected when nothing else meets them (an
    # ``unconnected-(…)`` net of several pins); a pin on a net holds no mark in Altium (change c0470)
    joined = {(m.component_id, m.pin) for n in circuit.nets if len(n.members) > 1 for m in n.members}
    return (
        dataclasses.replace(
            design,
            circuit=dataclasses.replace(
                circuit,
                components=tuple(parts),
                nets=nets,
                modules=modules,
                no_connects=tuple(
                    PinRef(ids[m.component_id], m.pin)
                    for m in circuit.no_connects
                    if (m.component_id, m.pin) not in joined
                ),
            ),
            board=None,
        ),
        symbols,
        tuple(changed),
    )


def flat_tops(text: str) -> bool:
    """Whether the KiCad root sheet ``text`` stands for no document of an Altium source: the root that the
    drawing adds over the top sheets of a flat project, which its carrier marks (``drawn_read.TOPS_KEY``,
    change c0470). Those sheets are written as top documents again, their parts outside every module."""
    from fenolite.backends.kicad import sheet_carrier

    carried = sheet_carrier.take(text)
    if carried is None:
        return False
    try:
        fields = sheet_carrier.AltiumSheet.parse(carried).fields
    except ValueError:
        return False
    return fields.get(drawn_read.TOPS_KEY, {}).get(drawn_read.TOPS_FIELD) == "T"


# --- the drawing of a source (change c0470, design D3) ----------------------------------------------------


def altium_sheets(source: SourceProject) -> list[SheetInput]:
    """The read schematic documents of an Altium project, in project order; none for a PCB document."""
    import hashlib

    from fenolite.backends.altium.read import sch as altium_sch
    from fenolite.backends.altium.read.project import read_project

    if source.backend != "altium" or source.path.suffix.lower() != ".prjpcb":
        return []
    listed = read_project(source.path.read_bytes(), file=source.path.name)
    found: list[SheetInput] = []
    for document in listed.documents:
        path = source.path.parent / document.path.replace("\\", "/")
        if path.suffix.lower() == ".schdoc" and path.is_file():
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            found.append(SheetInput(path.name, digest, altium_sch.read_schematic(data, file=path.name)))
    return found


@dataclass(frozen=True)
class SourceDrawing:
    """The drawing of an Altium source (``drawn_read``) and the documents it was read from."""

    extracted: drawn_read.Extracted
    sheets: tuple[SheetInput, ...]
    project: str = ""
    """The settings of the source project (``prjpcb.carried_settings``, change c0479)."""


def drawing_of(source: SourceProject) -> SourceDrawing | None:
    """The drawing of ``source``'s sheets: the Altium extractor of design D1 for an Altium project with
    schematic documents; ``None`` for a source without sheets, whose schematic stays generated."""
    from fenolite.backends.altium.prjpcb import carried_settings

    sheets = altium_sheets(source)
    if not sheets:
        return None
    project = carried_settings(source.path.read_bytes(), file=source.path.name)
    return SourceDrawing(drawn_read.extract_with_pins(sheets), tuple(sheets), project)


@dataclass(frozen=True)
class WrittenDrawing:
    """The KiCad files of a written drawing (text by project-relative path), the issues of the writer, and
    the ``symbol-graphic`` changes of the source symbols (reason → count)."""

    files: Mapping[str, str]
    issues: tuple[Issue, ...]
    symbol_changes: Mapping[str, int]


def refolded(found: drawn_read.Extracted) -> tuple[drawn_read.Extracted, dict[str, str]]:
    """``found`` with the Altium copies of each reused KiCad sheet (their carriers' ``origin``, change c0470)
    folded into that one sheet again: the first copy keeps its items under the KiCad sheet's key, its parts
    named as the KiCad sheet names them, and every sheet reference to a copy names it. The component path of
    each part of a copy, renamed the same way, by its path in ``found``. The records of the other copies stay
    in ``placed``, so that each component still finds its symbol."""
    groups: dict[str, list[str]] = {}
    for sheet in found.drawn.sheets:
        origin = found.origins.get(sheet.key)
        if origin is not None:
            groups.setdefault(str(origin["sheet"]), []).append(sheet.key)
    groups = {key: copies for key, copies in groups.items() if len(copies) > 1}
    if not groups:
        return found, {}
    taken = {sheet.key for sheet in found.drawn.sheets}
    new_key: dict[str, str] = {}
    for origin_key, copies in groups.items():
        key = origin_key if origin_key not in taken - set(copies) else copies[0]
        new_key.update((copy, key) for copy in copies)
    first = {copies[0] for copies in groups.values()}
    files = {key: str(found.origins[key].get("file", "")) for key in new_key}
    names = {key: cast(Mapping[str, str], found.origins[key]["parts"]) for key in new_key}
    renamed: dict[str, str] = {}
    for (key, _), (path, _, _) in found.placed.items():
        if key in names:
            module, _, part = path.rpartition("/")
            shared = names[key].get(part)
            if shared is not None:
                renamed[path] = f"{module}/{shared}" if module else shared
    sheets: list[DrawnSheet] = []
    for sheet in found.drawn.sheets:
        if sheet.key in new_key and sheet.key not in first:
            continue
        refs = tuple(
            dataclasses.replace(r, sheet=new_key[r.sheet], file=files.get(r.sheet) or r.file)
            if r.sheet in new_key
            else r
            for r in sheet.sheet_refs
        )
        symbols = sheet.symbols
        if sheet.key in names:
            symbols = tuple(
                dataclasses.replace(s, part=names[sheet.key].get(s.part, s.part)) for s in symbols
            )
        sheets.append(
            dataclasses.replace(
                sheet, key=new_key.get(sheet.key, sheet.key), sheet_refs=refs, symbols=symbols
            )
        )

    def kept(key: str) -> bool:
        return key not in new_key or key in first

    drawn = dataclasses.replace(
        found.drawn, sheets=tuple(sheets), root=new_key.get(found.drawn.root, found.drawn.root)
    )
    return (
        dataclasses.replace(
            found,
            drawn=drawn,
            pins={(new_key.get(k, k), kind, i): v for (k, kind, i), v in found.pins.items() if kept(k)},
            placed={(new_key.get(k, k) if kept(k) else k, i): v for (k, i), v in found.placed.items()},
            sheet_records={new_key.get(k, k): v for k, v in found.sheet_records.items() if kept(k)},
            classes={new_key.get(k, k): v for k, v in found.classes.items() if kept(k)},
            files={new_key.get(k, k): v for k, v in found.files.items() if kept(k)},
            altium_fields={new_key.get(k, k): v for k, v in found.altium_fields.items() if kept(k)},
            origins={},
        ),
        renamed,
    )


def _channel_parts(
    found: drawn_read.Extracted,
    placed: Sequence[tuple[tuple[str, int], tuple[str, int, Any]]],
    design: Design,
    links: Mapping[str, str],
) -> list[tuple[str, int, Any, Component]]:
    """``(path, document number, record, component)`` of each component of a channel of an Altium
    ``Repeat`` (change c0470): the board names it by the channel's designator (``D8_12``), the drawing by
    the record's own (``D8``) below the channel's module, so the component's path does not name a drawn
    part. The record is the one of the channel's sheet whose unique id ends the component's link (``links``:
    the source's ``altium`` native id by component id)."""
    from fenolite.model.drawn_connect import instances

    found_instances, _ = instances(found.drawn)
    sheet_of = {instance.module: instance.sheet for instance in found_instances}
    by_uid: dict[tuple[str, str], tuple[str, int, Any]] = {}
    for (sheet, _), (path, number, record) in placed:
        uid = getattr(record, "unique_id", "") or ""
        if uid:
            by_uid.setdefault((sheet, uid), (path.rpartition("/")[2], number, record))
    out: list[tuple[str, int, Any, Component]] = []
    for component in design.circuit.components:
        link = links.get(component.id, "")
        if not component.ref or not component.path or not link.startswith("cmp:"):
            continue
        module = component.path.rpartition("/")[0]
        held = by_uid.get((sheet_of.get(module, ""), link.rpartition("\\")[2]))
        if held is not None:
            part, number, record = held
            out.append((f"{module}/{part}" if module else part, number, record, component))
    return out


def channel_paths(found: drawn_read.Extracted, design: Design, links: Mapping[str, str]) -> dict[str, str]:
    """Reference → drawn path of each component of a channel of an Altium ``Repeat`` in ``design``
    (``_channel_parts``; ``found`` as ``refolded`` gives it, ``links`` as ``links_of`` does)."""
    placed = sorted(found.placed.items(), key=lambda item: (item[1][0], item[1][2].current_part))
    return {component.ref: path for path, _, _, component in _channel_parts(found, placed, design, links)}


def links_of(design: Design) -> dict[str, str]:
    """The ``altium`` native id of each component of ``design`` that holds one, by component id."""
    return {c.id: c.native_ids["altium"] for c in design.circuit.components if "altium" in c.native_ids}


def write_kicad_drawing(
    drawing: SourceDrawing,
    design: Design,
    name: str,
    target: int,
    links: Mapping[str, str] | None = None,
) -> WrittenDrawing:
    """The KiCad sheets of ``drawing`` for ``design`` (``backends/kicad/drawn.lower_drawn``): each component
    gets the symbol its source sheet embeds (``drawn_symbols.component_symbol``), each power port a power
    symbol of its style, and each sheet the carrier ``Fenolite.Altium.Sheet`` in its title block's
    comment 9 (design D4). An ``error`` of the writer is in ``issues`` and no file is written. ``links`` holds
    the source's ``altium`` native ids by component id when ``design`` no longer does (``_channel_parts``)."""
    from collections import Counter

    from fenolite.backends.altium import drawn_symbols
    from fenolite.backends.kicad import drawn as kicad_drawn
    from fenolite.backends.kicad import sch, sheet_carrier, symembed
    from fenolite.backends.kicad import sym as sym_lib
    from fenolite.backends.kicad.libs import LibTable, write_lib_table
    from fenolite.convert.altium_to_kicad import Part
    from fenolite.core.libnames import library_name
    from fenolite.model.library import FootprintDef

    found, renamed = refolded(drawing.extracted)  # a reused KiCad sheet is one sheet again (c0470)
    by_path = {(c.path or c.ref): c for c in design.circuit.components if c.ref}
    placed = sorted(found.placed.items(), key=lambda item: (item[1][0], item[1][2].current_part))
    parts: list[Part] = []
    changes: Counter[str] = Counter()
    seen: set[str] = set()
    for path, number, record, component in [
        *((path, number, record, by_path.get(path)) for (_, _), (path, number, record) in placed),
        *_channel_parts(found, placed, design, links if links is not None else links_of(design)),
    ]:
        if component is None or path in seen:
            continue
        seen.add(path)
        symbol, changed = drawn_symbols.component_symbol(
            drawing.sheets[number].document, record, name=f"SYM_{library_name(component.ref)}", library=name
        )
        changes.update(changed)
        footprint = FootprintDef(
            id=derived_id("fpd", "conversion", component.id),
            name=component.lib_footprint_ref.rsplit(":", 1)[-1],
            library=name,
        )
        parts.append(Part(component, renamed.get(path, path), symbol, footprint))
    powers: dict[str, kicad_drawn.PowerSymbol] = {}
    for sheet in found.drawn.sheets:
        for power in sheet.powers:
            library, _, style = power.symbol.partition(":")
            # a KiCad power flag carried through Altium names no net: never a global power symbol (c0470)
            flag = style == drawn_carrier.POWER_FLAG
            symbol = (
                drawn_symbols.power_flag(library, style)
                if flag
                else drawn_symbols.power_symbol(style, library)
            )
            powers.setdefault(power.symbol, kicad_drawn.PowerSymbol(symbol))
    aliases: dict[str, kicad_drawn.PowerSymbol] = {}
    for sheet in found.drawn.sheets:
        for index, pose in enumerate(sheet.symbols):
            held = found.placed.get((sheet.key, index))
            if not pose.symbol or held is None or pose.symbol in aliases:
                continue
            # a unit drawn with another symbol than its component's keeps that lib id (c0470)
            library, _, alias = pose.symbol.rpartition(":")
            symbol, changed = drawn_symbols.component_symbol(
                drawing.sheets[held[1]].document, held[2], name=alias, library=library or name
            )
            changes.update(changed)
            aliases[pose.symbol] = kicad_drawn.PowerSymbol(symbol)
    # the definitions of the opaque symbols, which the carrier keeps (change c0470)
    opaques: dict[str, kicad_drawn.PowerSymbol] = {}
    for lib_id, text in sorted(found.definitions.items()):
        read = sym_lib.read_symbol_library(text, library=lib_id.rpartition(":")[0])
        if len(read) == 1:
            opaques[lib_id] = kicad_drawn.PowerSymbol(read[0])
    generated = kicad_drawn.lower_drawn(
        found.drawn,
        design,
        parts,
        name=name,
        target=target,
        allow_lossy=True,
        power_symbols=powers,
        opaque_symbols=opaques,
        symbol_overrides=aliases,
    )
    if any(issue.severity == "error" for issue in generated.issues):
        return WrittenDrawing({}, generated.issues, dict(changes))
    carriers = {
        sheet.key: sheet_carrier.altium_sheet(
            sheet.opaques,
            found.sheet_records.get(sheet.key, ""),
            _with_project(found.altium_fields.get(sheet.key, {}), drawing.project)
            if sheet.key == found.drawn.root
            else found.altium_fields.get(sheet.key, {}),
        )
        for sheet in found.drawn.sheets
    }
    root = f"{name}.kicad_sch"
    texts = {root: sch.write_schematic(generated.sheet, target=target, allow_lossy=True).text}
    for file, sheet in generated.children.items():
        texts[file] = sch.write_schematic(sheet, target=target, allow_lossy=True).text
    files = sheet_carrier.put_drawing(texts, found.drawn, root, carriers)
    for nickname, definitions in generated.libraries.items():
        files[f"lib/{nickname}.kicad_sym"] = symembed.write_symbol_library(definitions, target=target)
    files["sym-lib-table"] = write_lib_table(LibTable("symbol", generated.rows), target=target)
    return WrittenDrawing(files, generated.issues, dict(changes))


def _with_project(fields: Mapping[str, Mapping[str, str]], project: str) -> Mapping[str, Mapping[str, str]]:
    """The root sheet's carrier ``fields`` with the source project's settings (change c0479)."""
    if not project:
        return fields
    key = drawn_read.TOPS_KEY
    return {**fields, key: {**fields.get(key, {}), drawn_read.PROJECT_FIELD: project}}


def kicad_drawing(source: SourceProject, design: Design) -> tuple[DrawnSchematic | None, tuple[Issue, ...]]:
    """The drawing of a KiCad source's sheets (change c0470, design D3), its symbols named by the component
    paths of ``design``, the schematic design of ``inputs``; ``None`` for a source without sheets."""
    from fenolite.backends.kicad import drawn as kicad_drawn

    root = root_schematic(source)
    if root is None:
        return None, ()
    sheets = parity_inputs.read_sheets(root)
    root_file = next(iter(sheets))
    children = {name: value for name, value in sheets.items() if name != root_file}
    value, issues = kicad_drawn.extract(
        sheets[root_file], children, components=kicad_drawn.refs_to_paths(design.circuit), root_file=root_file
    )
    from fenolite.backends.kicad import sheet_carrier

    # the Altium records of a sheet that came from Altium are written again (design D4)
    texts = {name: (root.parent / name).read_text(encoding="utf-8") for name in sheets}
    return sheet_carrier.take_drawing(texts, value, root_file), tuple(issues)


def drawing_aliases(
    source: SourceProject, drawing: DrawnSchematic, name: str
) -> dict[str, tuple[str, AltiumSymbol]]:
    """The Altium symbols of the units that ``drawing`` draws with another library symbol than their
    component's (``DrawnSymbol.symbol``, change c0470), by that lib id: each in ``<name>.SchLib`` as
    ``ALIAS_<lib id>``. A lib id that no sheet embeds, or whose pins are off whole mils, has none: the
    drawn writer then refuses the drawing, and the report says so."""
    from fenolite.core.libnames import library_name

    root = root_schematic(source)
    wanted = {pose.symbol for sheet in drawing.sheets for pose in sheet.symbols if pose.symbol}
    if root is None or not wanted:
        return {}
    known = {s.lib_id: s for sheet in parity_inputs.read_sheets(root).values() for s in sheet.lib_symbols}
    found: dict[str, tuple[str, AltiumSymbol]] = {}
    for lib_id in sorted(wanted):
        # a sheet embeds a renamed unit by its own name, without the library (``lib_name``)
        definition = known.get(lib_id) or known.get(lib_id.partition(":")[2])
        if definition is None:
            continue
        alias = f"ALIAS_{library_name(lib_id)}"
        try:
            body = from_symbol_def(definition, lib_ref=alias, footprint=None, bodies="graphics", fine=True)
        except ValueError:
            continue
        found[lib_id] = (f"{name}.SchLib", body)
    return found


def drawing_definitions(source: SourceProject, drawing: DrawnSchematic) -> dict[str, dict[str, str]]:
    """Per drawn sheet key, the KiCad library text (``.kicad_sym``) of each opaque symbol's definition by its
    lib id, as its source sheet embeds it (change c0470): the carrier keeps it, since no Altium record
    holds a symbol that Altium does not draw, and the way back embeds it again. A lib id no sheet embeds
    has none."""
    from fenolite.backends.kicad import drawn as kicad_drawn
    from fenolite.backends.kicad import sym

    root = root_schematic(source)
    if root is None or not any(
        kicad_drawn.opaque_symbol(o) is not None for s in drawing.sheets for o in s.opaques
    ):
        return {}
    known = {s.lib_id: s for sheet in parity_inputs.read_sheets(root).values() for s in sheet.lib_symbols}
    found: dict[str, dict[str, str]] = {}
    for sheet in drawing.sheets:
        for opaque in sheet.opaques:
            native = kicad_drawn.opaque_symbol(opaque)
            if native is None:
                continue
            lib_id = native.lib_name or native.lib_ref
            definition = known.get(lib_id) or known.get(lib_id.partition(":")[2])
            if definition is None:
                continue
            library, _, name = lib_id.rpartition(":")
            named = replace(definition, library=library, name=name)
            found.setdefault(sheet.key, {})[lib_id] = sym.write_symbol_library([named])
    return found


def drawing_fields(source: SourceProject, drawing: DrawnSchematic) -> dict[str, dict[str, dict[str, str]]]:
    """Per drawn sheet key, the Altium fields that the carrier of a source sheet keeps
    (``sheet_carrier.carried_fields``, change c0470)."""
    from fenolite.backends.kicad import sheet_carrier

    root = root_schematic(source)
    if root is None or sheet_carrier.take(root.read_text(encoding="utf-8")) is None:
        return {}
    sheets = parity_inputs.read_sheets(root)
    texts = {name: (root.parent / name).read_text(encoding="utf-8") for name in sheets}
    return sheet_carrier.carried_fields(texts, drawing, next(iter(sheets)))


def write_altium_drawing(
    drawing: DrawnSchematic, design: Design, symbols: Mapping[str, AltiumSymbol], name: str
) -> tuple[dict[str, bytes], tuple[Issue, ...]]:
    """The Altium sheets, libraries and project file of ``drawing`` (design D3): the drawn writer
    (``backends.altium.drawn.lower_drawn``) with the KiCad items it cannot draw in each sheet's carrier.
    ``design`` holds the components the drawing names by path, ``symbols`` their library symbols by lib id.
    ``lower.write_design`` takes the same path for a converted project with a board."""
    from fenolite.backends.altium.drawn import lower_drawn
    from fenolite.backends.altium.hierarchy import plan_sheets

    issues: list[Issue] = []
    planned = plan_sheets(
        design, name=name, sheets="modules", form="binary", symbols=symbols, read_circuit=True
    )
    planned = lower_drawn(drawing, design, planned, name=name, issues=issues, allow_lossy=True, carry=True)
    if any(issue.severity == "error" for issue in issues):
        return {}, tuple(issues)
    files = project.write_project(
        design, name=name, issues=issues, symbols=symbols, sheets="modules", read_circuit=True,
        planned_sheets=planned,
    )  # fmt: skip
    return files, tuple(issues)


_KICAD_OPAQUE_KINDS = {
    "text": "schematic-text", "text_box": "schematic-text", "image": "image", "symbol": "schematic-symbol",
    "bus_alias": "bus", "netclass_flag": "directive", "directive_label": "directive",
    "rule_area": "directive",
}  # fmt: skip
"""The report kind of a KiCad opaque item by its head; every other head is a ``schematic-graphic``."""


def kicad_drawing_rows(drawing: DrawnSchematic) -> tuple[dict[str, int], list[tuple[str, str, str]]]:
    """The report of a KiCad drawing written to Altium (design D5): the count per kind and each change as
    ``(kind, item, reason)``. Every item is written or carried (``backends.altium.drawn_carrier``): a global
    label and a power symbol become power ports, a power flag and an item Altium cannot draw travel in the
    carrier."""
    from fenolite.convert import codes

    counts: dict[str, int] = {}
    changes: list[tuple[str, str, str]] = []

    def add(kind: str, count: int) -> None:
        if count:
            counts[kind] = counts.get(kind, 0) + count

    for sheet in drawing.sheets:
        add("sheet", 1)
        add("schematic-symbol", len(sheet.symbols))
        add("wire", len(sheet.wires))
        add("bus", len(sheet.buses) + len(sheet.bus_aliases))
        add("bus-entry", len(sheet.bus_entries))
        add("junction", len(sheet.junctions))
        add("no-connect", len(sheet.no_connects))
        add("sheet-symbol", len(sheet.sheet_refs))
        add("title-block", 1 if sheet.title_block else 0)
        for index, _ in enumerate(sheet.bus_aliases):
            changes.append(("bus", f"{sheet.key}:bus_alias:{index}", codes.KICAD_CARRIED))
        for index, label in enumerate(sheet.labels):
            kind = "port" if label.kind == "hierarchical" else "label"
            add(kind, 1)
            if label.kind == "global":
                changes.append((kind, f"{sheet.key}:label:{index}", codes.KICAD_LABEL_STAND_IN))
        for index, power in enumerate(sheet.powers):
            add("power", 1)
            library, _, style = power.symbol.partition(":")
            if style == drawn_carrier.POWER_FLAG:
                changes.append(("power", f"{sheet.key}:power:{index}", codes.KICAD_FLAG_CARRIED))
            elif library != "AltiumPower":
                changes.append(("power", f"{sheet.key}:power:{index}", codes.KICAD_POWER_STAND_IN))
        for index, opaque in enumerate(sheet.opaques):
            head = opaque.kicad.lstrip("(").split(None, 1)[0].rstrip(")") if opaque.kicad else ""
            kind = (
                drawn_read.opaque_kind(opaque.altium)
                if opaque.altium
                else _KICAD_OPAQUE_KINDS.get(head, "schematic-graphic")
            )
            add(kind, 1)
            if not opaque.altium:
                changes.append((kind, f"{sheet.key}:opaque:{index}", codes.KICAD_CARRIED))
    return counts, changes


def drawing_rows(
    drawing: SourceDrawing, written: WrittenDrawing
) -> tuple[dict[str, int], list[tuple[str, str, str]]]:
    """The report of a written drawing (design D5): the source count per kind (``drawn_read.KINDS``) and
    each change as ``(kind, item, reason)``, the reasons of ``convert.codes.DRAWING_REASONS`` and of
    ``drawn_symbols.CHANGED``."""
    from fenolite.convert import codes

    found = drawing.extracted
    counts = dict(found.counts)
    changes: list[tuple[str, str, str]] = []
    for sheet in found.drawn.sheets:
        for index, opaque in enumerate(sheet.opaques):
            kind = drawn_read.opaque_kind(opaque.altium)
            if kind == "harness":
                reason = codes.DRAWING_HARNESS
            else:
                reason = codes.DRAWING_STAND_IN if opaque.kicad else codes.DRAWING_CARRIED
            changes.append((kind, f"{sheet.key}:opaque:{index}", reason))
        for index, _ in enumerate(sheet.powers):
            changes.append(("power", f"{sheet.key}:power:{index}", codes.DRAWING_POWER))
    for reason, count in sorted(written.symbol_changes.items()):
        changes += [("symbol-graphic", f"{reason[:24]}#{n}", reason) for n in range(count)]
    return counts, changes


def undrawn(drawn: DrawnSchematic, circuit: Circuit) -> list[Component]:
    """The components of ``circuit`` that no instance of ``drawn`` draws (an Altium component of the PCB
    document only, change c0470), bill-of-materials-only components aside."""
    paths = {
        instance.component(symbol.part)
        for instance in drawn.walk()[0]
        if (sheet := drawn.sheet(instance.sheet)) is not None
        for symbol in sheet.symbols
    }
    return [c for c in circuit.components if c.path not in paths and not c.bom_only]


def read_kicad_drawing(
    files: Mapping[str, str | bytes], components: Mapping[str, str], top: str | None = None
) -> tuple[DrawnSchematic, Mapping[PinKey, tuple[PinPoint, ...]], tuple[Issue, ...]]:
    """The drawing of written KiCad sheets (``files`` by project-relative path), read back with the KiCad
    extractor and completed by the Altium records of their carriers (``sheet_carrier.restore``).
    ``components`` maps a reference to its component path; ``top`` names the root sheet (by default the
    first sheet at the top of the project)."""
    import tempfile

    from fenolite.backends.kicad import drawn as kicad_drawn
    from fenolite.backends.kicad import sheet_carrier

    with tempfile.TemporaryDirectory(prefix="fenolite-drawing-") as folder:
        root = Path(folder)
        for name, data in files.items():
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data.encode("utf-8") if isinstance(data, str) else data)
        # the root sheet is the project's ``<stem>.kicad_sch`` when present, else the first top sheet
        stems = [
            f"{name.removesuffix('.kicad_pro')}.kicad_sch" for name in files if name.endswith(".kicad_pro")
        ]
        first = (
            top
            or next((name for name in stems if name in files), None)
            or next(name for name in sorted(files) if name.endswith(".kicad_sch") and "/" not in name)
        )
        sheets = parity_inputs.read_sheets(root / first)
        texts = {name: (root / name).read_text(encoding="utf-8") for name in sheets}
    root_file = next(iter(sheets))
    children = {name: value for name, value in sheets.items() if name != root_file}
    found = kicad_drawn.extract_with_pins(
        sheets[root_file], children, components=components, root_file=root_file
    )
    restored = sheet_carrier.take_drawing(texts, found.drawn, root_file)
    return restored, found.pins, tuple(found.issues)


__all__ = [
    "channel_paths",
    "links_of",
    "flat_tops",
    "EVIDENCE",
    "SourceDrawing",
    "WrittenDrawing",
    "altium_sheets",
    "drawing_aliases",
    "drawing_fields",
    "drawing_rows",
    "kicad_drawing",
    "kicad_drawing_rows",
    "drawing_of",
    "inputs",
    "read_kicad_drawing",
    "refolded",
    "undrawn",
    "root_schematic",
    "write_altium_drawing",
    "write_kicad_drawing",
]
