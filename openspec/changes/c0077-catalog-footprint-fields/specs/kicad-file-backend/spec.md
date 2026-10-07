## ADDED Requirements

### Requirement: Mandatory fields of a placed footprint
Every `FootprintInstance` that `fenolite.backends.kicad.embed.place_footprint` returns SHALL hold one `Reference` field whose value is `component.ref` and one `Value` field whose value is `component.value`, whatever the origin of the definition.
- `embed.default_fields(defn) -> tuple[FieldDefault, FieldDefault]` MUST return the placement of a field that a definition lacks, `Reference` first. With `box = embed.footprint_extent(defn)` and `cx` the centre of its X range: `Reference` has the text `REF**`, the layer `F.SilkS` and the position `(cx, box.y1 − FIELD_GAP)`; `Value` has the text `defn.name`, the layer `F.Fab` and the position `(cx, box.y2 + FIELD_GAP)`. `FIELD_GAP` MUST be 1 mm, `FIELD_SIZE` 1 mm by 1 mm and `FIELD_THICKNESS` 0.15 mm; both fields are visible, centred and at angle 0.
- A definition that has a `property` child of a name MUST keep that child: only its value atom is set, as before this requirement.
- A definition that lacks one MUST get it from `default_fields`, placed before the footprint's first `property` child, `Reference` before `Value`. Its uuid MUST be `embed.placement_uuid(key, "/footprint/property:<name>")`.
- An added field MUST be flipped with the footprint's other children on the bottom side: its layer becomes `B.SilkS` or `B.Fab` and its text is mirrored.
- `read_board` of the written board MUST map both properties to `FootprintField`s ("Footprint fields on boards"), and the component's `ref` MUST be `component.ref`.
- `lens.build` MUST report one `build.field-added` issue of severity `info` for each definition read from a library file that lacks `Reference` or `Value`, naming the lib id and the fields added. A definition prepared by `mod.prepare_authored_definition` MUST NOT give it. `docs/cli-contract.md` MUST document the code, and `src/fenolite/cli/data/explain.toml` MUST hold its table (`cli-contract`, "Explain command").

#### Scenario: Catalog footprint placed on top
- **GIVEN** `catalog.get_footprint("Fenolite:Chip_0603")` prepared with `mod.prepare_authored_definition`, and a component `R1` with value `330`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k top` places it with `place_footprint(..., key="R1")` and writes the instance
- **THEN** the footprint holds `(property "Reference" "R1"` on `F.SilkS` above the courtyard box and `(property "Value" "330"` on `F.Fab` below it, each with a font of 1 mm by 1 mm, and reading the board back gives a component whose `ref` is `R1`

#### Scenario: Bottom side
- **WHEN** the same definition is placed with `side="bottom"`
- **THEN** the `Reference` field is on `B.SilkS`, the `Value` field on `B.Fab`, and both are mirrored

#### Scenario: Library footprint keeps its own fields
- **GIVEN** `Mini_R_0603` read from `tests/data/libs/Mini.pretty`
- **WHEN** it is placed
- **THEN** the instance equals the one placed before this requirement, and the build reports no `build.field-added`

#### Scenario: Library footprint without a reference
- **GIVEN** a copy of `Mini_R_0603`, made in the test, without its `Reference` property
- **WHEN** a design that uses it is built
- **THEN** the board footprint holds a `Reference` field with the part's reference at the default placement, and the build reports one `build.field-added` info naming the lib id and `Reference`

#### Scenario: Deterministic uuids
- **WHEN** the catalog footprint is placed twice with the key `R1`, and once with the key `R2`
- **THEN** the two `R1` instances have equal field uuids, and the `R2` instance shares none of them
