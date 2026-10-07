## ADDED Requirements

### Requirement: Authored footprints carry Reference and Value
`fenolite.backends.kicad.mod.prepare_authored_definition` SHALL give a definition without a KiCad slot list, whether authored with `fenolite.dsl.Footprint` or taken from the built-in catalog, the two properties `Reference` and `Value`, so that the footprint written to the project library and the footprint placed on the board are conventional KiCad footprints.
- The two `property` children MUST come after the `kind` slot and before the pads, `Reference` first, with the texts, layers, positions, size and stroke of `embed.default_fields(defn)` (`kicad-file-backend`, "Mandatory fields of a placed footprint").
- `FootprintDef.properties` of the prepared definition MUST hold `Reference` with the text `REF**` and `Value` with the footprint's name; a `properties` entry the definition already has under either name MUST win over the default text. A footprint definition of the built-in catalog holds no such entry, so the library text of a catalog footprint's `Reference` is `REF**`.
- A definition that already has a slot list MUST be returned unchanged.
- `mod.write_footprint` of a prepared definition MUST write both properties, with uuids that derive from the lib id and the property name. Two builds from equal inputs MUST still give byte-identical footprint files ("Serialize deterministic backend footprints").
- `Part.field("Reference", …)` and `Part.field("Value", …)` MUST apply to a part whose footprint is authored or from the catalog, as they do for a library footprint.
- A definition that is not prepared MUST NOT gain the properties: the Altium build, which reads definitions as the script or the catalog gives them, sees none (`fenolite-component-catalog`, "Catalog-only design passes check").
- `docs/dsl.md` MUST say, under "Authored footprints", that the two fields are generated and where they are placed.

#### Scenario: Authored two-pad footprint
- **GIVEN** the footprint `Local:TwoPad` of `docs/dsl.md`, "Authored footprints", registered in a design whose part `R1` uses it
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k authored` builds the design for targets 9 and 10
- **THEN** `lib/Local.pretty/TwoPad.kicad_mod` holds `(property "Reference" "REF**"` and `(property "Value" "TwoPad"`, the board footprint holds `Reference` `R1`, and a second build writes the same bytes

#### Scenario: Field request on a catalog part
- **GIVEN** a design whose part `R1` uses `Fenolite:Chip_0603` and calls `r1.field("Reference", outside="top")` and `r1.field("Value", visible=False)`
- **WHEN** the design is built
- **THEN** the exit code is 0, the `Reference` field of `R1` lies beside the top of its courtyard box, and its `Value` field is hidden

#### Scenario: Every catalog footprint
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_embed_fields.py -k every_catalog` prepares and places each footprint that `catalog.list_entries(kind="footprint")` names
- **THEN** each instance holds both fields, and neither field's position lies inside the footprint's extent box
