# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Test-only numeric role ledger, deliberately incomplete and never a renumbering admission (c0355)."""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction

from fenolite.backends.kicad import _json
from fenolite.backends.kicad.layers import COPPER_ROW_TYPES, is_canonical
from fenolite.backends.kicad.lowering import MINIMUM_KEYS
from fenolite.backends.kicad.sexpr import AtomKind, Node
from fenolite.backends.kicad.zones import ISLAND_CODES, PAD_CONNECT_CODES


@dataclass(frozen=True)
class Role:
    name: str
    arities: tuple[int, ...]
    source: str
    proof: str
    codes: tuple[int, ...] = ()
    wire_integer: bool = False


def roles() -> dict[str, Role]:
    """Only declared physical/identifier facts; no observed-path or template-generated allow-list."""
    result = {}

    def add(
        path, name, arities, source="S-0001; docs/formats/kicad/board.md", proof="existing typed PCB reader"
    ):
        result["kicad_pcb/" + path] = Role(name, arities, source, proof)

    add("version", "format-version", (1,))
    add("general/thickness", "board-thickness", (1,))
    add("footprint/at", "physical-position-angle", (2, 3))
    add("footprint/pad/at", "local-pad-position-angle", (2, 3))
    add("footprint/pad/size", "physical-pad-size", (2,))
    add("footprint/pad/drill/offset", "local-drill-offset", (2,))
    for field in ("roundrect_rratio", "chamfer_ratio", "solder_paste_margin", "thermal_bridge_angle"):
        add("footprint/pad/" + field, "physical-pad-shape-or-margin", (1,))
    for path in ("footprint/pad/zone_connect",):
        result["kicad_pcb/" + path] = Role(
            "zone-connection-enum",
            (1,),
            "S-0001; docs/formats/kicad/board.md",
            "backends.kicad.zones.PAD_CONNECT_CODES",
            tuple(PAD_CONNECT_CODES),
            True,
        )
    for graphic in ("gr_line", "gr_arc", "gr_circle", "gr_rect", "gr_poly"):
        for field in ("start", "mid", "end", "center"):
            # Restrict to actual named graphic geometry; a wrong owner cannot inherit this role.
            if field in {"start", "mid"} and graphic == "gr_circle":
                continue
            if field in {"center", "mid"} and graphic not in {"gr_circle", "gr_arc"}:
                continue
            if field == "center" and graphic != "gr_circle":
                continue
            if field == "mid" and graphic != "gr_arc":
                continue
            if graphic == "gr_poly":
                continue
            add(f"{graphic}/{field}", "board-graphic-coordinate", (2,))
            fp = graphic.replace("gr_", "fp_")
            add(f"footprint/{fp}/{field}", "footprint-graphic-coordinate", (2,))
        add(f"{graphic}/stroke/width", "graphic-stroke-width", (1,))
        add(f"footprint/{graphic.replace('gr_', 'fp_')}/stroke/width", "graphic-stroke-width", (1,))
    for owner in ("gr_text", "footprint/property", "footprint/fp_text"):
        add(owner + "/at", "physical-text-position-angle", (2, 3))
        add(owner + "/effects/font/size", "physical-font-size", (2,))
        add(owner + "/effects/font/thickness", "physical-font-thickness", (1,))
    for owner in ("segment", "arc"):
        for field in ("start", "end", *(("mid",) if owner == "arc" else ())):
            add(owner + "/" + field, "track-coordinate", (2,))
        add(owner + "/width", "track-width", (1,))
    for field in ("size", "drill"):
        add("via/" + field, "physical-via-dimension", (1,))
    add("via/at", "physical-via-position", (2,))
    for owner in ("zone", "footprint/zone"):
        for field in (
            "connect_pads/clearance",
            "min_thickness",
            "fill/thermal_gap",
            "fill/thermal_bridge_width",
        ):
            add(owner + "/" + field, "physical-zone-setting", (1,))
        result["kicad_pcb/" + owner + "/priority"] = Role(
            "zone-priority-ordinal",
            (1,),
            "S-0001; docs/formats/kicad/board.md",
            "existing Zone.priority reader; normal priority remains strict",
            wire_integer=True,
        )
        add(owner + "/fill/island_area_min", "physical-island-area", (1,))
        result["kicad_pcb/" + owner + "/fill/island_removal_mode"] = Role(
            "island-removal-enum",
            (1,),
            "S-0001; docs/formats/kicad/board.md",
            "backends.kicad.zones.ISLAND_CODES",
            tuple(ISLAND_CODES),
            True,
        )
        for container in ("polygon", "filled_polygon"):
            add(owner + "/" + container + "/pts/xy", "exact-zone-vertex", (2,))
            for field in ("start", "mid", "end"):
                add(owner + "/" + container + "/pts/arc/" + field, "exact-zone-arc-vertex", (2,))
    for owner in ("gr_poly", "footprint/fp_poly", "footprint/pad/primitives/gr_poly"):
        add(owner + "/pts/xy", "physical-polygon-coordinate", (2,))
    for field in ("center", "end"):
        add("footprint/pad/primitives/gr_circle/" + field, "physical-custom-circle-coordinate", (2,))
    for primitive in ("gr_poly", "gr_circle"):
        add("footprint/pad/primitives/" + primitive + "/width", "physical-primitive-width", (1,))
    for field in ("offset", "rotate", "scale"):
        add(
            "footprint/model/" + field + "/xyz",
            "model-physical-transform",
            (3,),
            "S-0001; docs/formats/kicad/libraries.md",
            "existing ModelPlacement reader; references only",
        )
    for owner in ("footprint/pad", "via"):
        for field in ("best_length_ratio", "best_width_ratio", "filter_ratio", "max_length", "max_width"):
            add(
                owner + "/teardrops/" + field,
                "physical-teardrop-parameter",
                (1,),
                "docs/formats/kicad/board.md; S-0058",
                "existing typed Teardrop reader",
            )
    for field in ("aux_axis_origin", "grid_origin"):
        add("setup/" + field, "physical-origin", (2,))
    add("setup/pad_to_mask_clearance", "physical-mask-clearance", (1,))
    for field in ("thickness", "epsilon_r", "loss_tangent"):
        add("setup/stackup/layer/" + field, "physical-stackup-property", (1,))
    for field in NONREFERENCE_PLOT_NUMBERS:
        add(
            "setup/pcbplotparams/" + field,
            "plot-setting-not-netcode-reference",
            (1,),
            "docs/formats/kicad/board.md; " + NONREFERENCE_WITNESS,
            "native renumber witness only",
        )
    return result


def _bounded_cache_valid(cache: Node, owner: Node) -> bool:
    """Only the measured silkscreen cache shape; never change, normalize or feed its vertices back."""
    try:
        if len(owner.nodes("render_cache")) != 1 or len(owner.atoms()) != 1:
            return False
        positions, layers, effects = owner.nodes("at"), owner.nodes("layer"), owner.nodes("effects")
        if len(positions) != 1 or len(layers) != 1 or len(effects) != 1:
            return False
        at = positions[0].atoms()
        if len(at) not in (2, 3) or len(at) != len(positions[0].children):
            return False
        if any(a.kind != AtomKind.NUMBER for a in at):
            return False
        layer = layers[0].atoms()
        if len(layer) != 1 or len(layers[0].children) != 1 or layer[0].kind != AtomKind.STRING:
            return False
        if layer[0].value not in {"F.SilkS", "B.SilkS"}:
            return False
        fonts = effects[0].nodes("font")
        if len(fonts) != 1 or len(fonts[0].nodes("face")) != 1:
            return False
        face = fonts[0].nodes("face")[0]
        if len(face.children) != 1 or len(face.atoms()) != 1 or face.atoms()[0].kind != AtomKind.STRING:
            return False
        atoms = cache.atoms()
        if len(atoms) != 2 or atoms[0].kind != AtomKind.STRING or atoms[1].kind != AtomKind.NUMBER:
            return False
        if owner.atoms()[0].kind != AtomKind.STRING or atoms[0].value != owner.atoms()[0].value:
            return False
        if Fraction(atoms[1].text) != (Fraction(at[2].text) if len(at) == 3 else 0):
            return False
        polygons = cache.nodes()
        if not polygons:
            return False
        for polygon in polygons:
            if polygon.name != "polygon" or len(polygon.children) != 1:
                return False
            pts = polygon.nodes()
            if len(pts) != 1 or pts[0].name != "pts" or pts[0].atoms() or len(pts[0].children) < 3:
                return False
            for xy in pts[0].nodes():
                if xy.name != "xy" or len(xy.children) != 2 or len(xy.atoms()) != 2:
                    return False
                if any(a.kind != AtomKind.NUMBER for a in xy.atoms()):
                    return False
                for a in xy.atoms():
                    Fraction(a.text)
            if len(pts[0].nodes()) != len(pts[0].children):
                return False
        return True
    except (ValueError, IndexError):
        return False


def numeric_role_ledger(root: Node) -> dict:
    """Count every numeric atom/head by FULL role path. Unknown or invalid roles remain blockers."""
    if root.name != "kicad_pcb":
        raise ValueError("numeric role ledger requires a board root")
    registry = roles()
    rows = {}
    declared = {}
    declaration_error = False
    for node in root.nodes("net"):
        try:
            atoms = node.atoms()
            if len(atoms) != len(node.children) or len(atoms) != 2 or atoms[1].kind != AtomKind.STRING:
                raise ValueError("malformed declaration")
            code = atoms[0].to_int()
            if code < 0 or code in declared or atoms[1].value in declared.values():
                raise ValueError("ambiguous declaration")
            declared[code] = atoms[1].value
        except ValueError:
            declaration_error = True
    declaration_error |= declared.get(0) != ""

    def record(path, count, role, source, proof, invalid=False):
        key = "/".join(path)
        entry = rows.setdefault(
            key,
            {
                "role": role,
                "source": source,
                "proof": proof,
                "numeric_occurrences": 0,
                "invalid_instances": 0,
            },
        )
        entry["numeric_occurrences"] += count
        entry["invalid_instances"] += int(invalid)

    def walk(node, path=(), parent=None, cache_valid=None):
        if not isinstance(node, Node):
            return
        here = (*path, node.name)
        atoms = node.atoms()
        numbers = [a for a in atoms if a.kind == AtomKind.NUMBER]
        key = "/".join(here)
        descriptor = registry.get(key)
        references = {
            "kicad_pcb/net",
            "kicad_pcb/segment/net",
            "kicad_pcb/arc/net",
            "kicad_pcb/via/net",
            "kicad_pcb/zone/net",
            "kicad_pcb/footprint/pad/net",
            "kicad_pcb/footprint/zone/net",
        }
        cache_path = "kicad_pcb/gr_text/render_cache"
        if key == "kicad_pcb/footprint/zone_connect":
            valid = len(node.children) == 1 and len(atoms) == 1 and len(parent.nodes("zone_connect")) == 1
            try:
                valid &= atoms[0].to_int() in (0, 1, 2, 3)
            except (ValueError, IndexError):
                valid = False
            record(
                here,
                len(numbers),
                "footprint-zone-connection-enum",
                "S-1299",
                "authored native10 connection canary; no THT behavior claim",
                not valid,
            )
        elif key == cache_path or key.startswith(cache_path + "/"):
            if key == cache_path:
                cache_valid = _bounded_cache_valid(node, parent)
            known = key in {
                cache_path,
                cache_path + "/polygon",
                cache_path + "/polygon/pts",
                cache_path + "/polygon/pts/xy",
            }
            record(
                here,
                len(numbers),
                "measured-silkscreen-cache-coordinate-or-angle" if known else "UNKNOWN",
                "S-1299",
                "native10 exact ordered 5mm/7mm translation and owner rotation witness; no geometry rewrite",
                not cache_valid,
            )
        elif key in references:
            valid = not declaration_error
            try:
                if len(atoms) != len(node.children) or len(atoms) not in (1, 2):
                    raise ValueError("malformed code")
                code = atoms[0].to_int()
                if code not in declared or (
                    len(atoms) == 2 and (atoms[1].kind != AtomKind.STRING or atoms[1].value != declared[code])
                ):
                    raise ValueError("unbound or contradictory code/name")
                if key == "kicad_pcb/footprint/zone/net" and (code != 0 or parent.find("keepout") is None):
                    raise ValueError("unproved footprint-zone binding")
                if parent is not None and parent.name == "zone":
                    names = parent.nodes("net_name")
                    if len(names) > 1 or (
                        names
                        and (
                            len(names[0].children) != 1
                            or len(names[0].atoms()) != 1
                            or names[0].atoms()[0].kind != AtomKind.STRING
                            or names[0].atoms()[0].value != declared[code]
                        )
                    ):
                        raise ValueError("contradictory zone name")
            except (ValueError, IndexError):
                valid = False
            record(
                here,
                len(numbers),
                "netcode-reference",
                "S-0001; docs/formats/kicad/board.md",
                "authored two-network numeric-reference controls; full binding still required",
                not valid,
            )
        elif descriptor is not None:
            valid = (
                len(atoms) == len(node.children)
                and len(atoms) in descriptor.arities
                and len(numbers) == len(atoms)
            )
            # Fraction is exact; this classifies units only, never rounds or rewrites any physical value.
            if valid:
                for atom in numbers:
                    Fraction(atom.text)
                try:
                    if descriptor.wire_integer:
                        valid = all(atom.to_int() >= 0 for atom in numbers)
                    if descriptor.codes:
                        valid &= all(atom.to_int() in descriptor.codes for atom in numbers)
                except ValueError:
                    valid = False
            record(here, len(numbers), descriptor.name, descriptor.source, descriptor.proof, not valid)
        elif key == "kicad_pcb/footprint/pad/drill":
            children = node.nodes()
            oval = bool(atoms and atoms[0].kind == AtomKind.SYMBOL and atoms[0].value == "oval")
            expected = 3 if oval else 1
            valid = len(atoms) == expected and len(numbers) == (2 if oval else 1)
            valid &= len(children) <= 1 and all(c.name == "offset" for c in children)
            record(
                here,
                len(numbers),
                "physical-drill-dimensions",
                "S-0001; docs/formats/kicad/board.md",
                "existing pad drill reader; optional exact local offset",
                not valid,
            )
        elif key in {"kicad_pcb/zone/hatch", "kicad_pcb/footprint/zone/hatch"}:
            valid = len(node.children) == 2 and len(atoms) == 2 and len(numbers) == 1
            valid &= bool(
                atoms and atoms[0].kind == AtomKind.SYMBOL and atoms[0].value in {"edge", "full", "none"}
            )
            record(
                here,
                len(numbers),
                "visual-hatch-style-and-pitch",
                "S-0001; docs/formats/kicad/board.md",
                "existing zone hatch fact; not a fill-mode or net reference",
                not valid,
            )
        elif numbers:
            record(here, len(numbers), "UNKNOWN", "not proved", "refuse before any renumbering")
        if node.head.kind == AtomKind.NUMBER:
            if path == ("kicad_pcb", "layers"):
                valid = len(atoms) == len(node.children) and len(atoms) in (2, 3)
                valid &= bool(atoms and atoms[0].kind == AtomKind.STRING and is_canonical(atoms[0].value))
                valid &= bool(
                    len(atoms) >= 2
                    and atoms[1].kind == AtomKind.SYMBOL
                    and atoms[1].value in COPPER_ROW_TYPES | {"user"}
                )
                valid &= len(atoms) != 3 or atoms[2].kind == AtomKind.STRING
                try:
                    ordinal = node.head.to_int()
                    valid &= 0 <= ordinal <= 127
                    peers = [child.head.to_int() for child in parent.nodes()]
                    valid &= peers.count(ordinal) == 1
                except ValueError:
                    valid = False
                record(
                    (*path, "<numeric-head>"),
                    1,
                    "layer-record-ordinal",
                    "S-0021; docs/formats/kicad/board.md; backends.kicad.layers.user_rows",
                    "closed declared row shape/type; layer geometry/mapping still independently checked",
                    not valid,
                )
            else:
                record((*path, "<numeric-head>"), 1, "UNKNOWN", "no declared numeric-head role", "refuse")
        for child in node.nodes():
            walk(child, here, node, cache_valid)

    walk(root)
    unknown = sum(r["numeric_occurrences"] for r in rows.values() if r["role"] == "UNKNOWN")
    invalid = sum(r["invalid_instances"] for r in rows.values()) + int(declaration_error)
    return {
        "paths": rows,
        "remaining_unknown_numeric_occurrences": unknown,
        "invalid_known_role_instances": invalid,
        "renumbering_admitted": False,
        "project_and_reference_closure_still_required": True,
    }


def project_role_ledger(body: bytes) -> dict:
    """Closed subset of documented project roles. Unknown KEYS remain blockers even with zero values.

    No descriptor is inferred from a GUI template or from the values of the observed public source.
    Object keys are literal tuple members; only an ARRAY index can produce the wildcard member.
    """
    schema = {}
    array_item = object()

    def add(pointer, kinds, role, source="S-0020/S-0024; docs/formats/kicad/project.md"):
        schema[
            tuple(array_item if part == "*" else part for part in pointer.split("/")) if pointer else ()
        ] = (frozenset(kinds.split("|")), role, source)

    for pointer in (
        "",
        "meta",
        "net_settings",
        "net_settings/meta",
        "board",
        "board/design_settings",
        "board/design_settings/rules",
    ):
        add(pointer, "object", "closed-known-container")
    add("meta/version", "number", "project-schema-version")
    add("meta/filename", "string", "project-filename-metadata")
    add("net_settings/meta/version", "number", "net-settings-schema-version")
    add("net_settings/classes", "array", "named-netclasses")
    add("net_settings/classes/*", "object", "closed-netclass-entry")
    add("net_settings/classes/*/name", "string", "class-name-not-numeric-code")
    add("net_settings/classes/*/priority", "number", "class-priority")
    for key in (
        "clearance",
        "track_width",
        "via_diameter",
        "via_drill",
        "microvia_diameter",
        "microvia_drill",
        "diff_pair_width",
        "diff_pair_gap",
        "diff_pair_via_gap",
        "wire_width",
        "bus_width",
    ):
        add("net_settings/classes/*/" + key, "number|null", "class-physical-length-or-explicit-unset")
    for key in sorted({key for values in MINIMUM_KEYS.values() for key in values.values()}):
        add("board/design_settings/rules/" + key, "number", "board-physical-floor")
    add(
        "board/design_settings/rules/max_error",
        "number",
        "physical-curve-approximation",
        "S-1207; docs/formats/kicad/project.md",
    )
    for pointer, kinds in (
        ("erc", "object"),
        ("erc/pin_map", "array"),
        ("erc/pin_map/*", "array"),
        ("erc/pin_map/*/*", "number"),
    ):
        add(
            pointer,
            kinds,
            "erc-pin-type-conflict-matrix",
            "S-1299; official Eeschema ERC configuration manual and native9/10 passive-pair witness",
        )
    for pointer in NONREFERENCE_PROJECT_NUMBERS:
        add(pointer, "number", "numeric-setting-not-netcode-reference", NONREFERENCE_WITNESS)
    for pointer in SCHEMA_VERSION_PROJECT_NUMBERS:
        add(pointer, "number", "section-schema-version-not-netcode-reference", NONREFERENCE_WITNESS)
    data = _json.loads(body.decode("utf-8"))
    rows = {}

    def kind(value):
        if isinstance(value, _json.JsonNumber):
            return "number"
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        return "object" if isinstance(value, dict) else "array"

    def pointer(path):
        return "/" + "/".join(
            "*" if part is array_item else part.replace("~", "~0").replace("/", "~1") for part in path
        )

    def walk(value, path=()):
        observed = kind(value)
        descriptor = schema.get(path)
        valid = descriptor is not None and observed in descriptor[0]
        if valid and path[:2] == ("erc", "pin_map"):
            if len(path) in (2, 3):
                valid = isinstance(value, list) and len(value) == 12
            elif len(path) == 4:
                valid = observed == "number" and value.text in {"0", "1", "2"}
        if valid and observed == "number":
            number = Fraction(value.text)
            if path == ("meta", "version"):
                valid = number == 3
            elif path == ("net_settings", "meta", "version"):
                valid = number in (4, 5)
            elif path[-1] == "priority":
                valid = number.denominator == 1 and number >= 0
            else:
                valid = number >= 0 and (path[-1] != "max_error" or number > 0)
        key = pointer(path)
        record = rows.setdefault(
            key,
            {
                "role": descriptor[1] if descriptor else "UNKNOWN",
                "source": descriptor[2] if descriptor else "no declared semantic fact",
                "proof": "existing project reader/format facts; no L6 coverage promotion",
                "occurrences": 0,
                "invalid_instances": 0,
                "numeric_occurrences": 0,
            },
        )
        record["occurrences"] += 1
        record["invalid_instances"] += int(descriptor is not None and not valid)
        record["numeric_occurrences"] += int(observed == "number")
        if isinstance(value, dict):
            for name, child in value.items():
                walk(child, (*path, name))
        elif isinstance(value, list):
            for child in value:
                walk(child, (*path, array_item))

    walk(data)
    return {
        "paths": rows,
        "remaining_unknown_paths": sum(r["role"] == "UNKNOWN" for r in rows.values()),
        "invalid_known_role_instances": sum(r["invalid_instances"] for r in rows.values()),
        "renumbering_admitted": False,
        "full_project_profile_complete": False,
    }


# c0384 task 0.4 (bounded): project numeric leaves and board plot numerics measured as NON-netcode-references
# by the authored native renumber witness in tests/kicad/board/test_native_netcode_order.py. Each listed
# leaf is set to the same integer as a board netcode and the board net is renumbered: native DRC, the
# refilled geometry and the saved plot values stay equal. This classifies numeric LEAVES only; their
# non-numeric containers and every other unknown key remain blockers, and renumbering is still NOT admitted.
NONREFERENCE_PROJECT_NUMBERS = (
    "board/design_settings/defaults/board_outline_line_width",
    "board/design_settings/defaults/copper_line_width",
    "board/design_settings/defaults/copper_text_size_h",
    "board/design_settings/defaults/copper_text_size_v",
    "board/design_settings/defaults/copper_text_thickness",
    "board/design_settings/defaults/courtyard_line_width",
    "board/design_settings/defaults/dimension_precision",
    "board/design_settings/defaults/dimension_units",
    "board/design_settings/defaults/dimensions/arrow_length",
    "board/design_settings/defaults/dimensions/extension_offset",
    "board/design_settings/defaults/dimensions/text_position",
    "board/design_settings/defaults/dimensions/units_format",
    "board/design_settings/defaults/fab_line_width",
    "board/design_settings/defaults/fab_text_size_h",
    "board/design_settings/defaults/fab_text_size_v",
    "board/design_settings/defaults/fab_text_thickness",
    "board/design_settings/defaults/other_line_width",
    "board/design_settings/defaults/other_text_size_h",
    "board/design_settings/defaults/other_text_size_v",
    "board/design_settings/defaults/other_text_thickness",
    "board/design_settings/defaults/pads/drill",
    "board/design_settings/defaults/pads/height",
    "board/design_settings/defaults/pads/width",
    "board/design_settings/defaults/silk_line_width",
    "board/design_settings/defaults/silk_text_size_h",
    "board/design_settings/defaults/silk_text_size_v",
    "board/design_settings/defaults/silk_text_thickness",
    "board/design_settings/defaults/zones/min_clearance",
    "board/design_settings/diff_pair_dimensions/*/gap",
    "board/design_settings/diff_pair_dimensions/*/via_gap",
    "board/design_settings/diff_pair_dimensions/*/width",
    "board/design_settings/rules/min_connection",
    "board/design_settings/rules/min_groove_width",
    "board/design_settings/rules/min_hole_clearance",
    "board/design_settings/rules/min_hole_to_hole",
    "board/design_settings/rules/min_microvia_diameter",
    "board/design_settings/rules/min_microvia_drill",
    "board/design_settings/rules/min_resolved_spokes",
    "board/design_settings/rules/min_silk_clearance",
    "board/design_settings/rules/min_text_height",
    "board/design_settings/rules/min_text_thickness",
    "board/design_settings/rules/min_via_annular_width",
    "board/design_settings/rules/solder_mask_clearance",
    "board/design_settings/rules/solder_mask_min_width",
    "board/design_settings/rules/solder_mask_to_copper_clearance",
    "board/design_settings/teardrop_parameters/*/td_curve_segcount",
    "board/design_settings/teardrop_parameters/*/td_height_ratio",
    "board/design_settings/teardrop_parameters/*/td_length_ratio",
    "board/design_settings/teardrop_parameters/*/td_maxheight",
    "board/design_settings/teardrop_parameters/*/td_maxlen",
    "board/design_settings/teardrop_parameters/*/td_width_to_size_filter_ratio",
    "board/design_settings/track_widths/*",
    "board/design_settings/tuning_pattern_settings/diff_pair_defaults/corner_radius_percentage",
    "board/design_settings/tuning_pattern_settings/diff_pair_defaults/corner_style",
    "board/design_settings/tuning_pattern_settings/diff_pair_defaults/max_amplitude",
    "board/design_settings/tuning_pattern_settings/diff_pair_defaults/min_amplitude",
    "board/design_settings/tuning_pattern_settings/diff_pair_defaults/spacing",
    "board/design_settings/tuning_pattern_settings/diff_pair_skew_defaults/corner_radius_percentage",
    "board/design_settings/tuning_pattern_settings/diff_pair_skew_defaults/corner_style",
    "board/design_settings/tuning_pattern_settings/diff_pair_skew_defaults/max_amplitude",
    "board/design_settings/tuning_pattern_settings/diff_pair_skew_defaults/min_amplitude",
    "board/design_settings/tuning_pattern_settings/diff_pair_skew_defaults/spacing",
    "board/design_settings/tuning_pattern_settings/single_track_defaults/corner_radius_percentage",
    "board/design_settings/tuning_pattern_settings/single_track_defaults/corner_style",
    "board/design_settings/tuning_pattern_settings/single_track_defaults/max_amplitude",
    "board/design_settings/tuning_pattern_settings/single_track_defaults/min_amplitude",
    "board/design_settings/tuning_pattern_settings/single_track_defaults/spacing",
    "board/design_settings/via_dimensions/*/diameter",
    "board/design_settings/via_dimensions/*/drill",
    "net_settings/classes/*/line_style",
    "schematic/annotate_start_num",
    "schematic/connection_grid_size",
    "schematic/drawing/dashed_lines_dash_length_ratio",
    "schematic/drawing/dashed_lines_gap_length_ratio",
    "schematic/drawing/default_line_thickness",
    "schematic/drawing/default_text_size",
    "schematic/drawing/junction_size_choice",
    "schematic/drawing/label_size_ratio",
    "schematic/drawing/operating_point_overlay_i_precision",
    "schematic/drawing/operating_point_overlay_v_precision",
    "schematic/drawing/overbar_offset_ratio",
    "schematic/drawing/pin_symbol_size",
    "schematic/drawing/text_offset_ratio",
    "schematic/subpart_first_id",
    "schematic/subpart_id_separator",
)
SCHEMA_VERSION_PROJECT_NUMBERS = (
    "board/design_settings/meta/version",
    "erc/meta/version",
    "schematic/meta/version",
)
NONREFERENCE_PLOT_NUMBERS = (
    "dashed_line_dash_ratio",
    "dashed_line_gap_ratio",
    "svgprecision",
    "mode",
    "hpglpennumber",
    "hpglpenspeed",
    "hpglpendiameter",
    "outputformat",
    "drillshape",
    "scaleselection",
)
NONREFERENCE_WITNESS = "c0384 0.4 authored native renumber witness; test_native_netcode_order.py"
