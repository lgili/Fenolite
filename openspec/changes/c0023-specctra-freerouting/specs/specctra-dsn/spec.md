## ADDED Requirements

### Requirement: Specctra codec package
`fenolite.backends.specctra` SHALL be a codec package that writes Specctra design files and reads session files. It MUST NOT be registered in `fenolite.backends.registry`, MUST import only `core`, `model`, `geometry` and `backends.base`, and MUST hold a `PROVENANCE.md` naming each source and how it was used. No text, table, grammar production or example of S-0224 MUST appear in the repository.

#### Scenario: Not a registered backend
- **WHEN** `registry.all_backends()` is called
- **THEN** no backend is named `specctra`

#### Scenario: Layering holds
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes; a module under `backends/specctra/` importing `fenolite.backends.kicad` makes it fail

### Requirement: Specctra syntax
`backends.specctra.lexer.parse(text, *, file="") -> SNode` SHALL read parenthesised lists of words and quoted strings, with the quote character that the file's `parser` section declares, and `dumps(node)` SHALL print them. Malformed input MUST raise `FormatError` with a byte offset. The writer MUST declare `"` as the quote character and MUST quote every name that is not a plain word.

#### Scenario: Round trip of an authored file
- **GIVEN** `tests/data/specctra/two_pads.dsn`, authored for Fenolite
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_lexer.py` parses it and prints it
- **THEN** parsing the printed text gives an equal tree

#### Scenario: Unbalanced input
- **WHEN** `parse("(pcb x (unit um)")` is called
- **THEN** `FormatError` is raised with an offset

### Requirement: Design files are written from the model
`backends.specctra.dsn.write_dsn(design, *, pads, outline, selected, defaults) -> DsnResult` SHALL write a design file for the board, from the model, the board-frame pads of `BoardFrame.board_pads` and the outline rings.
- **Units.** `(resolution um 10)` and `(unit um)`; every coordinate MUST be `round_half_even(nm / 100)`, with Y negated. Coordinates that were not multiples of 100 nm MUST be counted in one `specctra.rounded` (info).
- **Structure.** One signal layer per copper layer in stack order; the boundary from `outline[0]`; a keep-out per cut-out ring; one via padstack per distinct diameter and drill among the selected nets' classes; a default rule with `defaults`' width and clearance.
- **Components.** One image per placed footprint, placed at the footprint's position with rotation 0 on the front and locked; pins at each pad's board-frame position minus the footprint's position; padstack shapes per layer from the pad's `PadCopper` entries (disc, capsule, polygon). A pad with an entry flagged `exact == False` MUST give `specctra.pad-approximated` (warning).
- **Network.** Every net with pads, its pins as `REF-PIN`; one class per net class with its nets, width, clearance and via.
- **Wiring.** Every existing track and via, protected. An arc MUST be written as straight wires within the kernel's arc error bound.
- **Names.** `DsnResult.names` MUST map each emitted net, component, pin, layer and via-padstack name to the model's; a name the syntax cannot carry MUST be replaced and reported with `specctra.renamed` (info).
- The text MUST be deterministic: equal inputs give equal bytes, with nets, classes, images and padstacks in a fixed order.

#### Scenario: Two-pad board
- **GIVEN** the authored two-pad board of c0016 and its board pads
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_dsn.py -k two_pads` calls `write_dsn`
- **THEN** the text equals `tests/data/specctra/two_pads.dsn`, parses with `lexer.parse`, and holds one net with two pins and two images

#### Scenario: Y is negated and rounded
- **GIVEN** a pad at (10.00005 mm, 5 mm)
- **WHEN** `write_dsn` runs
- **THEN** its component is placed at `100000 -50000` (half-even rounding of 100000.5), and the result holds `specctra.rounded`

#### Scenario: Bottom-side pad
- **GIVEN** a footprint on the bottom side with one SMD pad
- **WHEN** `write_dsn` runs
- **THEN** its image is placed on the front with rotation 0, and the pad's padstack names only the bottom copper layer

#### Scenario: Existing copper is protected
- **GIVEN** a board with one track and one via on net `A`
- **WHEN** `write_dsn` runs
- **THEN** the wiring section holds one protected wire and one protected via on `A`

### Requirement: Session files are read into copper
`backends.specctra.ses.read_session(text, *, file="") -> Session` SHALL read the routed wires and vias of a session file in the session's own resolution, and `ses.to_copper(session, names, *, selected)` SHALL turn them into model tracks and vias in nanometres, with Y negated back.
- Each wire of a selected net MUST become one `Track` per segment, with the wire's width and layer; zero-length segments MUST be dropped.
- Each via MUST become a `Via` with the diameter and drill of the padstack that `write_dsn` defined under its name; an unknown padstack name MUST give `specctra.unknown-padstack` (error) and no copper.
- Wires and vias of nets that were not selected MUST be ignored.
- A session with a placement change or a `was_is` entry MUST give `specctra.session-moved` (error) and no copper.
- Lists the reader does not know MUST be ignored, with one `specctra.unknown-list` (info) per head.
- Ids MUST be `core.ids.derived_id` over the net name and the item's geometry.

#### Scenario: Authored session
- **GIVEN** `tests/data/specctra/two_pads.ses`, authored for Fenolite, with one wire of three points and one via
- **WHEN** `uv run pytest tests/unit/backends/specctra/test_ses.py -k authored` reads it and calls `to_copper`
- **THEN** the result holds two tracks and one via on the net, in nanometres, with the via's diameter and drill from the written padstack

#### Scenario: Unselected net ignored
- **GIVEN** a session with wires on nets `A` and `B` and `selected=("A",)`
- **WHEN** `to_copper` runs
- **THEN** only `A`'s wires become tracks

#### Scenario: Session that moves a component
- **GIVEN** a session whose placement section moves `R1`
- **WHEN** `to_copper` runs
- **THEN** it reports `specctra.session-moved` and returns no copper

### Requirement: Specctra issue codes and facts
`backends.specctra.dsn.ISSUE_CODES` SHALL map every `specctra.*` code to one severity: `specctra.unknown-padstack` (error), `specctra.session-moved` (error), `specctra.pad-approximated` (warning), `specctra.rounded` (info), `specctra.renamed` (info), `specctra.unknown-list` (info). `docs/formats/specctra/dsn.md` and `ses.md` SHALL record every fact the code relies on, in Fenolite's own words, each with a source, a label and a hypothesis; a fact confirmed by no probe MUST be labelled `INFERRED`.

#### Scenario: Fact rows checked
- **WHEN** `uv run pytest tests/unit/test_format_facts.py` runs
- **THEN** it passes with the two pages

### Requirement: Specctra and Freerouting decision record
`docs/adr/0006-specctra-and-freerouting.md` SHALL record: facts from S-0224 in Fenolite's own words only, each also checked against a tool; Freerouting used only across a process boundary and never read for format knowledge; no cloud mode; and the black-box fallback. The change MUST write it with `Proposed` under `## Status`; only the maintainer MAY set `Accepted (<date>)`, with a `LEGAL-ANNEX.md` row, and the change MUST NOT be archived before that. `tests/unit/test_adrs.py` MUST list it in `REQUIRED`.

#### Scenario: ADR present
- **WHEN** `uv run pytest tests/unit/test_adrs.py` runs
- **THEN** it passes with `0006-specctra-and-freerouting.md` in `REQUIRED`
