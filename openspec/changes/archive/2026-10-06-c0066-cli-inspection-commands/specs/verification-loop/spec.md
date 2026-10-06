## ADDED Requirements

### Requirement: Model difference report
`fenolite.checks.diff` SHALL define `Change(path: str, change: Literal["added", "removed", "changed"], a: str, b: str)`, `DiffReport(equal: bool, changes: tuple[Change, ...], summary: Mapping[str, Mapping[str, int]])`, `diff_designs(a: Design, b: Design, *, ext: bool = False) -> DiffReport`, `diff_libraries(a: Library, b: Library, *, ext: bool = False) -> DiffReport` and `diff_sheets(a: SchematicSheet, b: SchematicSheet, *, ext: bool = False) -> DiffReport`. The report lists every difference between two models exactly; it gives no verdict by level and removes no frame.
- **Never compared.** `id`, `native_ids` and `provenance` MUST be left out. `ext` MUST be left out unless `ext=True`, and is then compared as the SHA-256 of its canonical JSON. A reference by id (`net_id`, `component_id`, `netclass_id`, a member's component) MUST be replaced by the key of the entity it names before values are compared.
- **Keyed kinds.** `component` is matched by `ref`; `net` by `name`, and a net with an empty name by its sorted members as `REF-PIN`; `netclass` and `layer` by `name`; `no_connect` by `REF-PIN`; `footprint` by the `ref` of its component; `pad` by `<ref>-<number>`, with `#<k>` for the k-th further pad of one number or of no number; `interface` by `name` and `module` by `path`; in a library, `footprint_def` and `symbol_def` by `<library>:<name>` (the bare name for a definition without a library); in a sheet, `symbol` by `<ref>#<unit>`, `sheet_ref` by `name` and `lib_symbol` by its embedded name. An entity on one side only is `removed` (only in `a`) or `added` (only in `b`), with path `/<kind>/<key>`. A field that differs is `changed`, with path `/<kind>/<key>/<field>` and `a` and `b` holding the compact canonical JSON of each value. A key is one path segment: `~` is written `~0` and `/` is written `~1`, as in a JSON pointer, so a net called `/SDA` has the path `/net/~1SDA`. A key used twice in one kind takes `#<k>` as pads do. The values a design holds once (the board `outline`, the stack-up `finish`, `sheet` and `title_block`, and the board's `ext` with `ext=True`) are the fields of the kind `design`, which has no key: their paths are `/design/<field>`. In a sheet, `paper`, `title_block` and `pages` (and the sheet's `ext` with `ext=True`) are the fields of the keyless kind `sheet`, and the sheet's `name` MUST NOT be compared. The design's `name`, its manufacturing manifest and its findings MUST NOT be compared: the name identifies the design as an id does, and the other two describe outputs.
- **Content kinds.** `track`, `arc`, `via`, `zone`, `keepout`, `text`, `graphic`, `hole`, `rule` and `stack_layer`, and in a sheet `label` and `no_connect_flag`, have no key: two entities match when every compared field is equal, and each entity matches at most one. Unmatched entities are `removed` or `added`, with path `/<kind>/<n>`, `n` being the index among the unmatched entities of that side in canonical order (the order of the entities' compact canonical JSON, which no id takes part in), and the entity's compact canonical JSON as `a` or `b`.
- **Order.** `changes` MUST be sorted by path, then by change. `summary` MUST map each kind that has a change to its counts `added`, `removed` and `changed`. `equal` MUST be true exactly when `changes` is empty.
- `DiffReport.to_json(limit: int | None)` MUST return `equal`, `summary`, `differences` (the first `limit` changes, or all), `total` and `truncated`.
- The module MUST import only `core`, `model`, `geometry` and `backends.base`.
- A later change MAY add keyword-only arguments with defaults to the three functions (a comparison scope, a length tolerance); each such requirement names this one.

#### Scenario: Equal designs with different ids
- **GIVEN** two designs built from the same data with different seeds, so every `id` differs
- **WHEN** `uv run pytest tests/unit/checks/test_diff.py -k ids` runs `diff_designs`
- **THEN** `equal` is true and `changes` is empty

#### Scenario: One change per kind
- **GIVEN** design `b` equal to `a` except: `R1` has another value, net `VIN` has one member more, one track is removed and one via is added
- **WHEN** `diff_designs(a, b)` runs
- **THEN** `changes` holds exactly `/component/R1/value` (`changed`), `/net/VIN/members` (`changed`), `/track/0` (`removed`) and `/via/0` (`added`), sorted by path

#### Scenario: Moved footprint is one change
- **GIVEN** design `b` equal to `a` except that the footprint of `R1` is moved by 1 mm in X
- **WHEN** `diff_designs(a, b)` runs
- **THEN** `changes` holds exactly one entry, `/footprint/R1/position` (`changed`), and no entry for the pads of `R1`, whose positions are stored relative to their footprint

#### Scenario: Renamed net
- **GIVEN** design `b` equal to `a` except that the net `VIN` is called `VBUS`
- **WHEN** `diff_designs(a, b)` runs
- **THEN** it reports `/net/VBUS` as `added` and `/net/VIN` as `removed`, and each pad of that net as `changed` in its `net_id` field

#### Scenario: Libraries
- **GIVEN** two libraries that hold the same footprint, the second with one pad 0.1 mm wider
- **WHEN** `diff_libraries(a, b)` runs
- **THEN** the only change is `changed` at `/pad/<library>:<name>-<number>/size`

#### Scenario: Sheets
- **GIVEN** two sheets read from `tests/data/kicad/schematic/flat.kicad_sch`, the second with `R1` moved and one global label removed
- **WHEN** `diff_sheets(a, b)` runs
- **THEN** `changes` holds `/symbol/R1#1/position` (`changed`) and one `/label/0` (`removed`)

#### Scenario: Opaque content only with ext
- **GIVEN** two sheets that differ in one opaque `wire`
- **WHEN** `diff_sheets(a, b)` runs, and again with `ext=True`
- **THEN** the first reports `equal` true, and the second one change whose path ends in `/ext`

#### Scenario: Diff stays backend-free
- **GIVEN** a version of `src/fenolite/checks/diff.py` that imports `fenolite.backends.kicad`
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it fails naming `checks → backends.kicad`
