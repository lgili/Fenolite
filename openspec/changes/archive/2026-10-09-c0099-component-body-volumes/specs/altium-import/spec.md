## MODIFIED Requirements

### Requirement: Component body records
`fenolite.backends.altium.read.bodies` SHALL decode the component-body storages that c0041 keeps as bytes (the `Data` streams of `ComponentBodies6` and `ShapeBasedComponentBodies6` in `PcbDocument.storages`, and the `raw` of the type 12 `RawPrimitive` values of a library footprint; c0041 types no body field), and the adapter SHALL map each component-associated body to a `ComponentBody` ("Component bodies" of `design-model`).
- `read_bodies(data: bytes, *, shape_based: bool = False, storage: str = "", issues=None) -> tuple[BodyRecord, ...]` MUST read the `Data` stream of `ComponentBodies6` or `ShapeBasedComponentBodies6`, and the body primitives (type 12) of a library footprint. `BodyRecord` MUST be a frozen dataclass with `index`, `raw`, `layer`, `component` (`None` for `0xFFFF`), `properties` (the record's property text as the reader's `PropertyRecord`), `outline` (as a region's) and typed views of the keys that `docs/formats/altium/pcb-bodies.md` lists: the standoff height, the overall height, the body projection, the identifier, the model name, the model id and the embed flag.
- `encode(records) == data` MUST hold: the decoder keeps every byte. A record it cannot frame MUST be returned raw with one `altium.pcb-read.short-record` warning, as c0041's primitives are.
- The module MUST obey the import rules of c0041's reader modules. A key MUST be typed only when its row of the fact page has a source; the page MUST say which rows are `INFERRED` (`H-A-IMP-BODY`).
- The adapter MUST give each body with a component index to that component's `FootprintInstance.bodies`, in stream order, and each body of a library footprint to `FootprintDef.bodies`. `kind` MUST be `model` when the record names a model and `extruded` otherwise; `outline` the converted vertices in the footprint frame, without the repeated last vertex; `height` the overall height; `standoff` the standoff height; `layer` the neutral name of the body's layer; `model` the model name; `name` the identifier. The adapter MUST derive authoritative signed z bounds and mounted-face orientation only from publicly evidenced body/projection semantics. Original native properties/raw bytes and model references MUST remain available independently of the projection. An unknown transform or model extent MUST retain those records and report unknown geometry with locators; it MUST NOT emit an invalid legacy body, discard native content or silently clamp its height.
- A body without a component index, and model data of the `Models` storage, are unmapped.

#### Scenario: Bytes kept
- **WHEN** `uv run pytest tests/corpus/test_altium_import.py -k bodies_identity` decodes the body storages of every fetched PCB document and library and encodes them again
- **THEN** each stream is rebuilt byte for byte, and the test reports the number of bodies per file

#### Scenario: Extruded body of a footprint
- **GIVEN** an authored body record with four vertices, an overall height of 40 mil and a standoff of 0, with component index 0
- **WHEN** the document is imported
- **THEN** footprint 0 holds one `ComponentBody` with `kind == "extruded"`, `height == 1_016_000`, `standoff == 0` and four outline points in the footprint frame

#### Scenario: Unproved signed projection
- **GIVEN** an authored body record has a projection whose signed-height meaning is not registered
- **WHEN** the adapter imports it
- **THEN** raw native content and resources remain preserved and its neutral volume is explicitly unknown rather than dropped or clamped

### Requirement: Import issue codes
Every issue of the adapter SHALL carry a code of the closed table `adapter.IMPORT_ISSUE_CODES`, which maps each code to its one severity, and `docs/cli-contract.md` SHALL list the table.
- Errors: `altium.import.bad-stack`, `altium.import.sheet-loop`.
- Warnings: `altium.import.bad-length`, `altium.import.body-unknown`, `altium.import.bad-geometry`, `altium.import.layer-outside-stack`, `altium.import.duplicate-net`, `altium.import.unknown-member`, `altium.import.padstack-unknown`, `altium.import.via-span`, `altium.import.no-designator`, `altium.import.sheet-missing`, `altium.import.repeated-sheet`, `altium.import.channel-naming`, `altium.import.scope-unknown`, `altium.import.duplicate-net-name`, `altium.import.duplicate-sheet-name`, `altium.import.bus-width`, `altium.import.harness-nested`, `altium.import.pcb-only-component`, `altium.import.document-skipped`, `altium.import.zone-hole-outside`.
- Infos: `altium.import.inexact`, `altium.import.multi-class`, `altium.import.zone-arc`, `altium.import.copper-shape`, `altium.import.scope`, `altium.import.option-ignored`, `altium.import.pin-map`, `altium.import.channels`, `altium.import.bus-member`, `altium.import.harness-entry`, `altium.import.extra-board`, `altium.import.linked-by-designator`, `altium.import.pcb-only-net`, `altium.import.rule-unmapped`, `altium.import.unmapped`.
- An issue's `where` MUST be a locator of "Identifiers and provenance", a reference, a `REF-PIN` or a net name; a counting issue's message MUST hold its counts.
- An error issue never stops the import: the adapter raises only for a programming error and for a project with nothing to read.
- No code of this table MUST equal a code of `fenolite.lens.altium.ALTIUM_ISSUE_CODES` or of the readers' tables.

#### Scenario: Closed table
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_codes.py` collects the codes that the adapter's source can give and those the tests have seen
- **THEN** both sets are within `IMPORT_ISSUE_CODES`, every code of the table has one severity, every code is a row of `docs/cli-contract.md`, and none is a code of the build or of a reader
