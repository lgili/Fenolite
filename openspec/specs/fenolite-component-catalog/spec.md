# fenolite-component-catalog Specification

## Purpose
Specify the offline, Fenolite-authored catalog of reusable generic schematic symbols and PCB footprints.
## Requirements
### Requirement: Offline Fenolite-authored standard catalog
Fenolite SHALL ship a deterministic, offline catalog of Fenolite-authored generic schematic symbols
and reusable standard-package footprints under the reserved `Fenolite:` namespace. The catalog
MUST incrementally cover the common component families and standard package styles listed in its
coverage matrix, including passives, discrete and optoelectronic semiconductors, protection,
power/control ICs and electromechanical interfaces. Every entry MUST have a stable lib id, kind,
category, summary, evidence level and public source ids for factual electrical or physical claims.
Definitions MUST NOT be copied or vendored from a CC-BY-SA library, from another CAD library under any
licence other than CC0-1.0, or from a private project. Data from a library whose licence is CC0-1.0
MAY be used openly: each such record MUST carry `origin` (library name, release or commit, the original
element's id), `licence = "CC0-1.0"` and evidence `UNVERIFIED` until a review of its current digest
raises it. The catalog MUST NOT claim complete coverage of commercial parts, choose a package for a part,
or assert manufacturing qualification. Non-standard or proprietary geometry remains project-authored unless
it is separately specified as a reusable generic package with public evidence.

#### Scenario: Catalog covers the published family matrix
- **WHEN** the catalog coverage check runs
- **THEN** every family and standard package style marked in the current coverage matrix has at
  least one discoverable, Fenolite-authored entry or an explicit documented reason it is not
  representable by the current model
- **AND** no private project BOM row or third-party CAD definition is required to build those entries

#### Scenario: A custom package stays project-authored
- **GIVEN** a component package with a non-standard mechanical interface or insufficient public
  evidence
- **WHEN** the catalog coverage is extended
- **THEN** the generic catalog does not claim that geometry as a standard package
- **AND** the user can define it through the project-authored symbol and footprint APIs

#### Scenario: Generic symbols do not select a package
- **GIVEN** a part assigned to a generic catalog symbol that supports multiple package styles
- **WHEN** the design is built
- **THEN** package selection remains explicit on the part and no footprint is silently inferred

#### Scenario: A record from a CC0 library is labelled
- **GIVEN** a shipped record converted from a CC0-1.0 library element
- **WHEN** the catalog source check runs
- **THEN** it passes only if the record holds `origin` with library, version and element id, `licence = "CC0-1.0"`, and evidence `UNVERIFIED` or a review of its current digest

#### Scenario: A record from a CC-BY-SA library is refused
- **GIVEN** a shipped record whose `origin.licence` is `CC-BY-SA-4.0`
- **WHEN** the catalog source check runs
- **THEN** it fails naming the record and the licence

### Requirement: Discoverable catalog API and CLI
The public `fenolite.catalog` API SHALL list and retrieve symbol/footprint definitions by stable lib id, with optional case-insensitive search over id, category and summary. `fenolite catalog list` and `fenolite catalog show <lib-id>` SHALL expose the same entries through the CLI JSON envelope, including evidence and source ids, without running an external tool.

#### Scenario: Search by category
- **WHEN** the API or CLI searches for a category in the shipped catalog
- **THEN** matching entries are returned in stable lib-id order with their kind and evidence

#### Scenario: Show a definition
- **WHEN** `fenolite catalog show Fenolite:Resistor` names a known entry
- **THEN** it returns its kind, metadata, source ids and package/symbol definition summary

### Requirement: Build resolves built-in definitions
The KiCad `fenolite build` SHALL resolve catalog symbol and footprint lib ids without consulting global/project CAD library tables for those ids. It SHALL write the definitions used by the design into the generated project's local libraries. A project-authored definition whose lib id exactly matches a catalog entry MUST take precedence for that build only; other catalog entries remain available. Vendored records rank between them. Origins MUST be reported as `builtin`, `library` or `authored`.

#### Scenario: Offline built-in build
- **GIVEN** a design that names a shipped symbol and footprint
- **WHEN** it is built with empty library tables and offline resolver configuration
- **THEN** its definitions resolve, the generated local tables point to the local output libraries, and the result labels their origin `builtin`

#### Scenario: User customizes a standard definition
- **GIVEN** a project-authored symbol or footprint with the same lib id as a catalog entry
- **WHEN** the project is built
- **THEN** the authored definition is used and labelled `authored`, with no mutation of the shipped catalog

#### Scenario: Vendored definition resolved offline
- **GIVEN** a design that names the footprint of a `footprint` item vendored under `fenolite_library/footprints/`, with empty library tables
- **WHEN** it is built
- **THEN** the footprint is written into the local output library and the result labels its origin `library`, with the item id and version

### Requirement: Source and evidence labels
Each factual symbol pin map, polarity claim or physical package dimension in the catalog SHALL cite
one or more public sources registered in `docs/evidence/sources.md`. A land pattern not explicitly
specified by those sources MUST be labelled `INFERRED` in catalog metadata and the definition
description. A writer/readback check MUST NOT upgrade an inferred dimension's evidence level.
Public sources MUST be sufficient for each claim; private board data and copied CAD library content
MUST NOT be used as provenance. A record taken from a CC0-1.0 library MAY name that library, registered
as a source with its licence, as its origin; that origin is not evidence of correctness, so the record
stays `UNVERIFIED` until it is reviewed.

#### Scenario: Every family pack has independent provenance
- **WHEN** the catalog source check runs
- **THEN** it fails for an unregistered source id, a factual claim without supporting provenance,
  or an inferred footprint without an inferred-land description
- **AND** it rejects catalog provenance that points to a private board artifact or third-party CAD
  library file, other than the registered origin of a CC0-1.0 record

#### Scenario: Origin is not evidence
- **GIVEN** a record whose only source is the registered CC0 library of its `origin`, without a review
- **WHEN** the catalog source check runs
- **THEN** it passes only if the record's evidence is `UNVERIFIED`

### Requirement: Reusable symbol body graphics
`SymbolDef` SHALL carry optional ordered symbol-local graphic primitives in integer nanometres. The DSL symbol authoring API SHALL create line, rectangle, circle and polygon primitives, and the KiCad symbol reader/writer SHALL preserve those primitives through a read/write round-trip. Symbols with declared graphics MUST use those graphics for their body and MUST NOT get an additional synthetic pin-bounds rectangle; symbols with no declared graphics retain the existing fallback.

#### Scenario: Resistor body is drawn from catalog graphics
- **GIVEN** the built-in resistor symbol with two pins and a declared rectangular body
- **WHEN** its symbol library is written and read back
- **THEN** the symbol has the same pins and ordered geometry and no extra generated body rectangle

#### Scenario: Existing symbol without graphics stays compatible
- **GIVEN** an authored symbol with pins and no graphic primitives
- **WHEN** its symbol library is written
- **THEN** the current generated pin-bounds rectangle remains present

### Requirement: Physically separated and oriented footprint lands
Every shipped surface-mount footprint SHALL use land shapes, dimensions, pitch, orientation and
numbering traceable to an official package or land-pattern drawing. Pads with different numbers
MUST have positive copper clearance. A footprint courtyard MUST contain its body and all pads, and
silkscreen graphics MUST NOT cross copper. Multiple shapes carrying one pad number MAY form one
documented shared terminal. Disconnected lands MUST document the assumed component-side connection
and its evidence, and MUST NOT imply copper connectivity on the PCB. Where an official example uses a
rounded rectangle but the current model provides only a rectangle, the approximation SHALL remain
labelled `INFERRED`.

#### Scenario: A package is serialized and checked
- **WHEN** any built-in footprint is serialized and read back
- **THEN** its pad shapes, positions, sizes, numbers, kinds, layers, drills and plated-slot dimensions,
  footprint attributes and complete drawing geometry match the source-backed
  definition
- **AND** no two pads with different numbers overlap
- **AND** its courtyard contains every pad and the body outline

#### Scenario: Multi-sided packages follow the manufacturer's top view
- **WHEN** the 32-lead LQFP or a five-lead SOT package is inspected from the top
- **THEN** pad numbers progress around the body in the order shown by its cited official drawing
- **AND** pads on perpendicular sides have perpendicular long axes

### Requirement: Connected, legible schematic symbol drawings
Every built-in schematic symbol SHALL have pin stems oriented from their wire-attachment points
toward and into a visible body or terminal graphic. Generic symbols SHALL use consistent line
weight, aligned pin positions, readable functional labels and recognizable electrical motifs without
copying a third-party CAD definition. Polarity and amplifier input/supply pin names SHALL match the
graphic. Where a symbol hides its pin names ("Legible pin texts") and the drawing alone would not say
which pin is which, strokes of the drawing SHALL say it. Families without a device-specific pinout
SHALL remain explicitly conceptual.

#### Scenario: A user places any catalog symbol
- **WHEN** the symbol is serialized and read back
- **THEN** each pin direction and stem reaches a visible body or terminal graphic
- **AND** pin numbers, names, graphic order and visibility settings survive the round trip
- **AND** diode cathodes, polarized capacitor positives and amplifier input signs agree with
  the drawn marks, and the positive supply stem of an amplifier is the upper one

#### Scenario: Selected resistor and Zener drawings
- **WHEN** the generic resistor and Zener diode are rendered from catalog definitions
- **THEN** the resistor has a continuous zigzag between its pin stems instead of a rectangle
- **AND** the Zener cathode has one continuous bent stroke with no full-height straight stroke
  under the bends

#### Scenario: Optocoupler, header and polarized capacitor drawing review
- **WHEN** these generic symbols are rendered from catalog definitions
- **THEN** the optocoupler contains a recognizable LED, two optical arrows and a separate
  phototransistor, with its A/K/C/E pin stems joined to the appropriate graphic, and an open
  arrowhead of two strokes at the end of the phototransistor's emitter leg and none on its
  collector leg
- **AND** each two-, three- or four-circuit header contact is square and has exactly one external
  pin stem, with no circular contact graphic
- **AND** only the polarized and electrolytic capacitor variants have one heavier plate opposite
  the marked positive plate

#### Scenario: Complete visual family review
- **WHEN** all 49 catalog symbols are rendered on one gallery sheet
- **THEN** passive and protection contours remain readable at normal schematic scale and their
  pin stems meet the intended body graphics
- **AND** multi-circuit connectors show grouped housings, separate square contacts and one
  external stem per circuit; the single terminal has a square socket form
- **AND** the four conceptual IC blocks are plain rectangles that carry readable functional pin
  names and no interior stroke
- **AND** the two amplifier triangles carry a plus stroke at the non-inverting input and a minus
  stroke at the inverting input and no other interior stroke, while their supply stems meet the
  triangular bodies
- **AND** prior explicit preferences for zigzag resistance, Zener cathode, optocoupler internals
  and weighted polarized capacitor plate remain intact

#### Scenario: Bridge rectifier terminals
- **WHEN** the generic bridge rectifier is rendered from its catalog definition
- **THEN** a plus stroke lies inside the diamond below the positive corner, a minus stroke above
  the negative corner, and a wave of three strokes beside each AC corner
- **AND** the pins keep the names `~`, `~`, `+` and `-`, which the symbol hides

#### Scenario: Distinct coupled choke, discharge tube and dual LED symbols
- **WHEN** the three newly covered generic families are discovered and rendered
- **THEN** the common-mode choke has two winding paths that do not electrically join, with four
  conceptual terminals and a separate magnetic-core cue
- **AND** the gas discharge tube has two opposing electrodes with a visible insulating gap and
  two non-polar terminals
- **AND** the dual LED has two anode branches, one shared cathode and a clear common-cathode
  description; it does not imply a physical package pinout or select a footprint

### Requirement: Published 100-variant footprint target
Fenolite SHALL publish and ultimately ship exactly 100 distinct, discoverable footprint variants
from the c0076 target inventory. The inventory SHALL disclose its public-board sampling method,
snapshot, package-family normalization and limits. An entry SHALL NOT be described as a measured
worldwide top-100 package. Existing definitions count toward the total only once. An unresolved
variant slot is a plan, not a usable footprint. Each shipped definition MUST satisfy the source,
evidence, geometry, serialization, clearance and explicit-assignment requirements above.

#### Scenario: The inventory is audited before implementation
- **WHEN** the target inventory is reviewed
- **THEN** it contains exactly 100 unique slots, identifies the 14 existing catalog entries and
  clearly marks every remaining slot as unimplemented
- **AND** the selection method and public sources can be reproduced without private project data

#### Scenario: A provisional slot becomes a catalog entry
- **WHEN** a package variant is implemented
- **THEN** its final ID identifies the sourced body, pitch, pin count and special pad features
  needed to distinguish it from other variants
- **AND** its registered official drawing supports numbering and land geometry, or any authored
  approximation is visibly marked `INFERRED`
- **AND** focused geometry, readback, discovery and offline-build checks pass before the slot is
  marked implemented

#### Scenario: The 100-variant target is complete
- **WHEN** c0076 is proposed for merge
- **THEN** all 100 inventory slots resolve to distinct built-in footprints with the required
  evidence, previews and checks
- **AND** aliases sharing identical lands do not inflate the count

#### Scenario: All final patterns are used offline
- **WHEN** the 100 definitions returned by the catalog API are explicitly assigned in an authored
  terminal-only audit design and supplied to `build_design()` as `authored_footprints`
- **THEN** the build succeeds with no network connection, CAD installation or global library table
- **AND** every footprint ID, pad geometry, drill/slot, explicit pin mapping and assigned pad net
  survives board readback for the supported KiCad 9 and 10 writer targets
- **AND** the CLI discovers the same 100 IDs and the five review sheets reproduce their definitions
- **AND** this audit does not claim a functional device pinout, routing or manufacturing qualification

### Requirement: Additional 20 generic symbol families
Fenolite SHALL add exactly 20 source-backed, independently drawn symbol variants listed in
`docs/catalog/target-20-symbols.md`, bringing its symbol count to 49. Their terminal numbers SHALL
remain conceptual, their functional roles SHALL be explicit, and no default footprint SHALL be
selected. Public-source registration, connected stems, deterministic discovery and writer/readback
checks SHALL apply to every new definition.

#### Scenario: Discrete and power families are drawn
- **WHEN** NPN/PNP, N/P enhancement MOSFET, IGBT, SCR, TRIAC, Schottky and bidirectional TVS are inspected
- **THEN** emitter arrows distinguish NPN from PNP, MOSFET gates are isolated from segmented channels
  and N/P body diodes have opposite polarity
- **AND** the SCR gate joins the cathode side and the TRIAC gate joins the MT1 side
- **AND** Schottky cathode hooks are continuous, TVS terminals are non-polar and IGBT diode integration
  is not inferred

#### Scenario: Passive, mechanical and optical families are drawn
- **WHEN** potentiometer, NTC/PTC, crystal, SPST/SPDT, pushbutton, relay, transformer and photodetectors
  are inspected
- **THEN** the potentiometer wiper meets the resistance path, NTC/PTC marks differ by coefficient
  sign, and crystal electrodes remain separate
- **AND** switch/relay graphics show resting contacts with COM connected to NC and a visible NO gap;
  the pushbutton exposes two internally common terminal pairs with an open contact at rest
- **AND** transformer windings have separate terminals and photodetector arrows point inward

#### Scenario: New symbols remain usable offline
- **WHEN** the catalog API and CLI list symbols and an explicitly mapped new symbol is built
- **THEN** all 49 IDs are discoverable without network access, and the selected symbol's pin roles
  and graphics survive local-library serialization/readback
- **AND** source registration and the native 20-symbol and complete 49-symbol galleries are reproducible
- **AND** a footprint is never selected from a generic symbol name

### Requirement: Legible pin texts
Every symbol that Fenolite authors SHALL show a pin name only where it can be read at the text size of each tool Fenolite writes for. The symbols are the catalog symbols, the symbols of every example library under `examples/`, and the symbols of the mini library `tests/data/libs/` that the other examples place.
- **Shown texts.** Per unit and in body style 1: the name of each pin that is not hidden, unless the symbol hides its pin names or the name is empty; and the number of each such pin, unless the symbol hides its pin numbers.
- **Rule.** A shown text MUST NOT overlap another shown text of the same unit. A shown name that is drawn inside the body MUST lie inside the box of the body. A shown name or number MUST NOT be crossed by a stroke of the body, by the stem of another pin, or by the mark of a pin shape (an inversion bubble, a clock wedge, a low-level mark), of its own pin or of another. A shown name MUST NOT be equal to the shown number of its own pin.
- **Two sizes.** `tests/_pintext.py` MUST estimate the box of each shown text in integer nanometres at two sizes, each following the text one of Fenolite's writers asks for:
  - the KiCad size: text 1.27 mm high, 1.15 heights per character; a name from the symbol's name offset (0.508 mm when it states none) past the body end of its pin, along the pin; a number centred on the middle of its pin, 0.36 mm clear of the pin line;
  - the Altium size: a line 90 mil thick, 100 mil per character; a name from 50 mil inside the body end of its pin, along the pin; a number from 80 mil outside it, 10 mil clear of the pin line.
  The marks of the pin shapes MUST be the strokes KiCad draws for them; the same strokes are assumed at the Altium size. The KiCad size holds for capitals, digits, `+`, `-`, `_` and `~`, the characters it was compared on; a shown text with another character MUST be a finding.
  The Altium size is an assumption that no tool has confirmed; the module MUST say so, and the rule MUST NOT be reported as a statement about what Altium draws.
- **Drawings hide, plain boxes show.** A catalog symbol whose body is one plain rectangle MUST show its pin names and MUST be large enough for them under the rule. Every other catalog symbol MUST hide its pin names, because its drawing tells its pins apart; where a hidden name carried a sign that the drawing did not show, strokes of the drawing MUST carry it ("Connected, legible schematic symbol drawings").
- **Names stay.** Hiding MUST change `pin_names_hidden` only: every pin keeps its name, number, electrical type and unit, so a design that names a pin by its name builds as before.
- **Exceptions.** A symbol that does not pass MUST be listed in `KNOWN` of `tests/unit/catalog/test_pin_text_legibility.py` with the reason it is left as it is, and the test MUST fail for a listed symbol that passes. The test MUST NOT treat any other symbol by its name.
- **Evidence.** The rule is measured on Fenolite's model with Fenolite's estimate. It raises no evidence level and settles no row of `docs/hypotheses.md`.

#### Scenario: Every authored symbol is measured
- **WHEN** `uv run pytest tests/unit/catalog/test_pin_text_legibility.py` runs
- **THEN** each of the 49 catalog symbols and each symbol of `examples/altium_kicad/FenoliteDemo.kicad_sym` has no finding
- **AND** the only symbols with a finding are the two that `KNOWN` lists, `Mini_DualGate` and `Mini_QFP32_IC`, in both files of the mini library

#### Scenario: Names shown only on plain boxes
- **WHEN** the 49 catalog symbols are read
- **THEN** `Linear_Regulator`, `Offline_Power_Controller`, `Microcontroller` and `Power_Module`, each one filled rectangle, show their pin names
- **AND** the other 45 hide theirs, and every pin of every symbol still holds its name and shows its number

#### Scenario: Linear regulator
- **WHEN** `Fenolite:Linear_Regulator` is measured
- **THEN** its body is a square of 15.24 mm around the origin, `IN` and `OUT` lie on one row 5.08 mm above the centre, and `GND` runs up from the bottom edge
- **AND** at the Altium size `IN` and `OUT` do not overlap, and `GND` ends 2.667 mm below their row

#### Scenario: Pin shapes of the example library
- **WHEN** `MCU8` of the example library is measured
- **THEN** the name `CLK` begins past the clock wedge of its pin, and no pin number lies on the inversion bubble of pin 2 or of pin 5
- **AND** with the name offset KiCad takes by default the name `CLK` is a finding, and with pins of 2.54 mm the numbers of pins 2 and 5 are

#### Scenario: A number on a stroke of the body
- **WHEN** a pin of 2.54 mm ends at a stroke that the body draws beside the pin, as the hook of the bar of `Schottky_Diode` did
- **THEN** the number of that pin is a finding: `Schottky_Diode` with pins of 2.54 mm has one for its number `2`, and a polarized capacitor with its plus mark above the positive lead has one for its number `1`
- **AND** `Schottky_Diode`, `R_V` and the two polarized capacitors as they are have none

#### Scenario: A name that repeats its number
- **WHEN** `CONN2` of the example library is read
- **THEN** it hides its pin names, and its two pins still hold the names `1` and `2` and the numbers `1` and `2`

#### Scenario: The estimate follows the writers
- **WHEN** `uv run pytest tests/unit/catalog/test_pin_text_legibility.py -k writers` runs
- **THEN** the KiCad size is the font size and the name offset that `write_symbol_library` writes
- **AND** the Altium size is no thicker than the line of `backends/altium/layout.TEXT_HEIGHT` and no narrower per character than `backends/altium/symbols.CHAR_WIDTH`

### Requirement: Lands numbered against the generic diode symbols are documented
The generic symbols `Diode`, `Zener_Diode` and `LED` SHALL keep pin 1 `A` and pin 2 `K`. A two-pad catalog land that keeps a manufacturer's numbering with pad 1 at the cathode SHALL be documented as needing a pin-to-pad map with these symbols, and SHALL keep its pad numbers.
- The lands of this kind are `LED0603_Kingbright_APT1608SURCK`, `LED0805_Kingbright_APT2012SURCK` and `SOD128_Nexperia_CFP5`. Each MUST have its fabrication-layer cathode mark on the side of pad 1.
- The row of each in `docs/catalog/sources.md` and its entry in `docs/catalog/coverage.md` MUST say that pad 1 is the cathode, that a build applies the pin-to-pad map by default ("Default pin-to-pad map of the cathode-first lands"), and that an explicit `pad_map` wins.
- A sample script that Fenolite ships and that puts one of the three symbols on one of these lands MUST give the part a `pad_map` that puts pin 2 `K` on pad 1 and pin 1 `A` on pad 2, and MUST connect the part by pin name.

#### Scenario: Warning beside each land
- **WHEN** `uv run pytest tests/unit/catalog/test_polarity_notes.py` reads the two pages
- **THEN** the row and the entry of each of the three lands hold the word "cathode" and name the pin-to-pad map

#### Scenario: A new land of this kind
- **WHEN** a two-pad land is added to the catalog whose pad 1 lies on the side of its cathode mark
- **THEN** `test_the_cathode_first_lands_are_the_known_ones` fails until the land is named in the test and in `catalog.CATHODE_FIRST_LANDS`, and documented

#### Scenario: Kit LED
- **WHEN** each of the kit samples `board6`, `flat`, `libs` and `routed` is loaded
- **THEN** `D1` has the map `{"1": "2", "2": "1"}`, its pin `K` is on `GND` and its pin `A` on `LED_A`

### Requirement: Default pin-to-pad map of the cathode-first lands
A build SHALL give a part of an anode-first catalog symbol on a cathode-first catalog land, when the part gives no `pad_map`, the map `{"1": "2", "2": "1"}`: the anode pin on the anode pad and the cathode pin on pad 1, the cathode. The maintainer decided this on 2026-10-08 (change c0147).
- The anode-first symbols are the two-pin catalog symbols with pin 1 `A` and pin 2 `K` (`catalog.ANODE_FIRST_SYMBOLS`: `Diode`, `LED`, `Photodiode`, `Schottky_Diode`, `Zener_Diode`); the cathode-first lands are those of "Lands numbered against the generic diode symbols are documented" (`catalog.CATHODE_FIRST_LANDS`). `catalog.default_pad_map(symbol_id, footprint_id)` MUST return the map for each such pair and `()` for every other pair.
- The map MUST be applied to the model that the KiCad and the Altium targets share, so both targets put the same net on each pad; `fenolite kit build` and `fenolite sync` MUST apply it as `fenolite build` does.
- A part that gives a `pad_map` MUST keep it as written. A part whose symbol or footprint the design authors under the same lib id MUST get no default.
- Every part that gets the default MUST be reported ("Default pin-to-pad map is reported", `design-dsl`).

#### Scenario: Part without a map
- **GIVEN** a script with `Fenolite:LED` on `Fenolite:LED0603_Kingbright_APT1608SURCK` and `Fenolite:Schottky_Diode` on `Fenolite:SOD128_Nexperia_CFP5`, each without a map, their pin `A` on `VA` and their pin `K` on `GND`
- **WHEN** it is built with `--target kicad` and with `--target altium`
- **THEN** in both written boards pad 1 of each part is on `GND` and pad 2 on `VA`

#### Scenario: Explicit map
- **WHEN** the LED of that script gives `pad_map={"1": "1", "2": "2"}`
- **THEN** its pad 1 is on `VA` and its pad 2 on `GND` in both targets, and the build reports no `build.pad-map-default` for it

#### Scenario: Other lands and symbols
- **WHEN** a part of `Fenolite:Diode` on `Fenolite:SOD123_Diodes` or on `Fenolite:DO41_P10.16_Diodes`, of `Fenolite:LED` on `Fenolite:Chip_0603`, or of `Fenolite:Capacitor_Polarized` on `Fenolite:SOD128_Nexperia_CFP5` gives no map
- **THEN** it keeps the identity map and is not reported

#### Scenario: Pairs read from the catalog
- **WHEN** `uv run pytest tests/unit/catalog/test_polarity_notes.py` reads every catalog symbol and land
- **THEN** `ANODE_FIRST_SYMBOLS` is the set of symbols with pin 1 `A` and pin 2 `K`, `CATHODE_FIRST_LANDS` the set of lands with pad 1 at the cathode mark, and `default_pad_map` maps exactly their pairs

### Requirement: Catalog-only design passes check
A design that names only catalog lib ids SHALL build into a project that `fenolite check` accepts, on a machine that has no KiCad library, and the suites SHALL prove it.
- `tests/_catalog_design.py::catalog_blink()` MUST return a `fenolite.dsl.Design` of a two-pin header (`Fenolite:Connector_2`, `Fenolite:Header_1x2_P2.5`), a resistor (`Fenolite:Resistor`, `Fenolite:Chip_0603`) and a LED (`Fenolite:LED`, `Fenolite:Chip_0805`), with three nets, every part placed, board minimums and one scripted track per net. The design is authored for Fenolite.
- **Hermetic.** `tests/unit/cli/test_catalog_only.py` MUST build it for targets 9 and 10 with no library table and with `subprocess.run` and `subprocess.Popen` patched to raise. On each project it MUST run `fenolite check --stages model.validate,copper.clearance` (both stages `ok`), and MUST compare the model with the re-read board through `checks.assignment_compare.compare(model_netlist(model), board_netlist(board)[0])`: no difference, six common elements, and the references of the board are `D1`, `J1` and `R1`.
- **Oracle.** `tests/kicad/build/test_catalog_only.py` MUST run the same projects through the whole `fenolite check` on the running `kicad-cli`: exit 0, no unconnected item, no `netlist.*` issue, and no design-rule item of type `lib_footprint_issues` or `lib_footprint_mismatch`. A target-10 project is skipped on 9.0.x, as in the acceptance suite.
- **Second backend.** `fenolite build --target altium` of the same design MUST plan the same bytes for every Altium file, and report the same issues, with and without the property step of `mod.prepare_authored_definition`: the Altium documents name each component from `Component.ref` and `Component.value` and MUST NOT change with this requirement. The hermetic test MUST prove it.
- **Script copper for the second backend.** The catalog blink declares tracks, and `build --target altium` resolves script copper through a KiCad build of the design. That build MUST take the catalog's footprint and symbol definitions the design names, as the KiCad build does, so that the Altium build of a catalog-only design is not refused for a missing library table row.
- The result of the oracle test settles `H-K-FP-FIELDS` in `docs/hypotheses.md`.

#### Scenario: Nets of the script and of the board agree
- **WHEN** `uv run pytest tests/unit/cli/test_catalog_only.py -k nets` runs
- **THEN** both targets build with exit 0 and every lib id reported as `builtin`, the two check stages are `ok`, and the comparison of the model with the board gives no difference over six common elements

#### Scenario: KiCad accepts the project
- **WHEN** `uv run pytest tests/kicad/build/test_catalog_only.py -rA` runs on `kicad-cli` 10.0.6 and on 9.0.9
- **THEN** `fenolite check` exits 0 on each project the running tool can read, with no unconnected item, no `netlist.assignment-differs`, and no `lib_footprint_issues` or `lib_footprint_mismatch`

#### Scenario: A regression is caught
- **GIVEN** `embed.default_fields` and the property step of `mod.prepare_authored_definition` patched in the test so that prepared definitions get no field
- **WHEN** the hermetic comparison runs on a project built that way
- **THEN** it gives at least one difference, and the board's references are all empty

#### Scenario: Altium documents are unchanged
- **GIVEN** the catalog blink built with `--target altium --dry-run`, once as the code is and once with the property step of `mod.prepare_authored_definition` patched in the test to add nothing
- **WHEN** `uv run pytest tests/unit/cli/test_catalog_only.py -k altium` compares the two plans
- **THEN** every planned file has the same SHA-256 in both, and both runs report the same issue codes

### Requirement: Installed catalog visual browser

`fenolite catalog view --out FILE [--kind symbol|footprint] [--query TEXT]` SHALL plan one standalone HTML page of the matching installed catalog definitions. It SHALL reuse the existing library and geometry viewer, work offline without an external CAD tool or intermediate CAD file, and use the normal dry-run, confirmation, staged replay and receipt protocol. Its viewer imports SHALL be lazy for list/show. Equal catalog definitions and filters SHALL produce equal page bytes.

#### Scenario: Review the installed catalog
- **WHEN** catalog view is confirmed without filters
- **THEN** one standalone page includes every installed symbol and footprint in stable ID order, grouped into two virtual library documents
- **AND** each item displays its exact lib ID, category, summary, evidence, public source IDs and pin or pad information, with existing measurement and selection tools
- **AND** no evidence level or generic-to-device compatibility claim is upgraded

#### Scenario: A filtered review
- **WHEN** view receives a kind or text filter
- **THEN** its entries equal list_entries with those filters, and only nonempty library documents are included

#### Scenario: No matching entry
- **WHEN** view filters match no entry
- **THEN** it returns FEN-3001 with a hint to change the filters, plans no write and preserves an existing target
- **AND** list with the same filters still succeeds with an empty list

#### Scenario: Review and replay
- **WHEN** view runs with --dry-run and is later confirmed with its plan ID
- **THEN** dry-run creates no output HTML and confirmation writes exactly the staged bytes with their receipt hash

#### Scenario: Invalid arguments do not write
- **WHEN** view has no --out or has a positional lib ID, or list/show has --out
- **THEN** it returns a usage error and writes nothing

#### Scenario: Existing inspection stays read-only
- **WHEN** catalog list or catalog show runs as before
- **THEN** it succeeds without confirmation, returns its existing metadata and creates no output

#### Scenario: Viewer consumes resolved model definitions
- **WHEN** the CLI prepares a catalog browser
- **THEN** it resolves entries into metadata and model definitions before calling the viewer
- **AND** the viewer imports no catalog package and performs no catalog lookup, preserving the existing package-layering rules and generated page bytes

#### Scenario: Catalog geometry remains readable
- **WHEN** a catalog symbol is displayed
- **THEN** metadata properties are shown in item details instead of over the body, and metadata text does not expand the drawing's fitted bounds
- **AND** body geometry, pin numbers and visible pin names remain drawn, without modifying the stored definition or ordinary library rendering
- **WHEN** a catalog footprint is displayed
- **THEN** fabrication and courtyard layers are initially visible, and the initial details omit an exhaustive pad-number list while pad selection retains exact pad information

#### Scenario: Details do not obscure the initial drawing
- **WHEN** a catalog item is selected
- **THEN** its metadata panel starts collapsed with evidence in its labelled summary
- **AND** keyboard or pointer activation expands and collapses the metadata without altering geometry or ordinary library panels

### Requirement: Reviewed catalog component selection

The standalone catalog browser SHALL support selection of a symbol and footprint together, geometric filters, simultaneous previews using the existing renderer and an explicit pin-to-pad map. Metadata and evidence SHALL remain tied to the exact definitions. Generic counts or dimensions SHALL NOT establish device compatibility.

#### Scenario: Search by geometry
- **WHEN** a user filters footprint candidates by mounting kind, electrical pad count or pad/centre dimensions
- **THEN** results use the embedded model facts in consistent units
- **AND** invalid numeric filters, unavailable measurements and no matches have explicit states without silently changing the selected component

#### Scenario: Preview a pair offline
- **WHEN** a symbol and footprint are selected
- **THEN** both actual definitions are rendered together by the existing library viewer
- **AND** preview frames open only the same local page, do not recursively create frames or exchange project selections

#### Scenario: Mapping has not been reviewed
- **WHEN** the mapping is missing, names an unknown pad, repeats a pad across pins, leaves an electrical pad unused or lacks user datasheet confirmation
- **THEN** no ready-to-copy Python component snippet is presented
- **AND** the reason is visible without upgrading catalog evidence

#### Scenario: A reviewed map becomes a Part
- **WHEN** every pin and numbered pad is mapped unambiguously and the user explicitly confirms their datasheet review
- **THEN** the generated Python Part snippet contains the selected symbol ID, footprint ID and exact pad_map
- **AND** changing either definition or the mapping clears confirmation before another snippet is available

### Requirement: Device records
`fenolite.catalog.devices.parse_device(text, *, file) -> DeviceDef` SHALL read one TOML record of schema `fenolite.device.v0` with `tomllib` and `parse_float=Decimal`, and SHALL return a `fenolite.model.library.DeviceDef` that joins a symbol, a footprint, a function-to-pin-and-pad map, an identity, a reference prefix, a value, ratings, an evidence label, sources and an optional provenance. No float MUST be created.

#### Scenario: A device record is read
- **GIVEN** the authored file `tests/data/devices/example_buck.toml` with `id = "Example:BUCK_6V_2A"`, `symbol = "Example:Buck_6pin"` and `footprint = "Fenolite:SOT23_6_TI_DBV0006A"`
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k read` parses it
- **THEN** a `DeviceDef` with that id, symbol and footprint is returned, and no field holds a float

### Requirement: Device record keys
A device record SHALL hold `schema`, `id` (`<namespace>:<name>`, each part matching `[A-Za-z0-9_.+-]+`), `summary`, `symbol`, `footprint`, `evidence` and `pins`, and MAY hold `manufacturer`, `mpn`, `datasheet` (an `https://` URL), `ref_prefix` (`[A-Z][A-Z_]*`), `value`, `sources`, `ground`, `unused_pads`, `properties`, `ratings`, `ends` (two function names) and `provenance`. Another key, a missing key or a wrong type MUST raise `FormatError` (`FEN-3004`) naming the file and the key.

#### Scenario: Unknown key
- **WHEN** a record holding the key `colour` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised, naming the file and `colour`

#### Scenario: Shipped namespace needs sources
- **WHEN** a record with `id = "Fenolite:X"` and no `sources` is parsed
- **THEN** `FormatError` with code `FEN-3004` is raised, naming `sources`

### Requirement: Reserved device keys
The keys `interfaces` and `options`, and a schema version higher than `fenolite.device.v0`, SHALL raise `FormatError` mapped to `FEN-3002`, with a message that names the key as reserved for a later format (c0252 and c0257).

#### Scenario: Reserved key
- **WHEN** a record holding an `interfaces` table is parsed
- **THEN** `FormatError` with code `FEN-3002` is raised, naming `interfaces`

### Requirement: Device pin functions
Each key of `pins` SHALL be a function name matching `[A-Za-z_][A-Za-z0-9_+.~-]*`, unique under `str.casefold`. Its value MUST be a string (one symbol pin on the pad of its number), a list of strings (several such pins), or a table with exactly one of `pins` and `map` (symbol pin to pads, spelled as `Part.pad_map` is), plus optional `voltage`, `current` and `must_connect`. Each symbol pin MUST be in one function, and each pad MUST be on at most one pin.

#### Scenario: Three spellings
- **GIVEN** `BST = "1"`, `GND = { map = { "2" = ["2", "EP"] } }` and `VIN = { pins = ["5"] }`
- **WHEN** the record is parsed
- **THEN** `BST` has `pin_pads == (("1", "1"),)`, `GND` has `pin_pads == (("2", "2"), ("2", "EP"))` and `VIN` has `pin_pads == (("5", "5"),)`

#### Scenario: Refused pin tables
- **WHEN** records are parsed that repeat a symbol pin in two functions, name functions `vin` and `VIN`, name a function `1V8`, or give a table with both `pins` and `map`
- **THEN** each raises `FormatError` with code `FEN-3004`, naming the function

### Requirement: Device ratings in integers
Device ratings SHALL use only the keys `voltage`, `current`, `power` and `temperature`, and pin ratings only `voltage` and `current`. Each rating holds `min`, `max` or both, as text with a unit (`V`, `A`, `W`, `degC`, with an SI prefix), parsed by `fenolite.core.quantities` and stored as an exact integer in µV, µA, µW or m°C. A value that is not a whole number of these units, a unit that does not fit the key, or `min > max` MUST raise `FormatError` (`FEN-3004`).

#### Scenario: Ratings read exactly
- **GIVEN** `VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }` and `temperature = { min = "-40degC", max = "125degC" }`
- **WHEN** the record is parsed
- **THEN** the pin `VIN` has `voltage.min == 2_700_000` and `voltage.max == 6_000_000` in µV, and the device rating `temperature` has `min == -40_000` and `max == 125_000` in m°C

#### Scenario: Refused ratings
- **WHEN** records with `voltage = { max = "6.0000005V" }`, `current = { max = "6V" }` and `power = { min = "2W", max = "1W" }` are parsed
- **THEN** each raises `FormatError` with code `FEN-3004`

### Requirement: Canonical device text
`fenolite.catalog.devices.device_text(device) -> str` SHALL give the canonical TOML of a record: a fixed key order, one table per long-form function, LF line ends and one final newline. `parse_device(device_text(d)) == d` MUST hold for every record.

#### Scenario: Canonical text round trip
- **WHEN** every shipped device and every device under `tests/data/devices` is written with `device_text` and parsed again
- **THEN** each record equals the one read, and writing it twice gives identical bytes

### Requirement: Device sources and precedence
The DSL SHALL resolve a device id from, in this order: the records given to `Design.devices(*records)`, the project devices of `devices/*.toml` beside the design script (installed by the script runner in file-name order), and `fenolite.catalog.devices.shipped_devices()`. The first source that holds the id MUST win. The DSL itself MUST read no file.

#### Scenario: Project device beside the script
- **GIVEN** `examples/devices/design.py` with `devices/example_buck.toml` beside it
- **WHEN** `fenolite build examples/devices/design.py --out B --dry-run --json` runs
- **THEN** the exit code is 0 (a dry run) and `result.devices` holds `Example:BUCK_6V_2A` with `origin` `authored`

### Requirement: Project devices override shipped ones
A project device whose id is a shipped id SHALL give `device.overrides-builtin` (info), and its `origin` SHALL be `authored`. An unmodified shipped device MUST be reported as `builtin`. Two project files with one id MUST raise `FormatError` (`FEN-3004`) naming both files.

#### Scenario: Override of a shipped device
- **GIVEN** a project file `devices/r0603.toml` whose id is `Fenolite:R_0603`
- **WHEN** a design that uses `Fenolite:R_0603` is built with `--dry-run`
- **THEN** `issues` holds one `device.overrides-builtin` info, and the device's `origin` is `authored`

#### Scenario: One id in two files
- **GIVEN** `devices/a.toml` and `devices/b.toml`, both with `id = "Proj:X"`
- **WHEN** the design is built with `--dry-run`
- **THEN** the exit code is 3, stderr carries `FEN-3004`, and the message names both files

### Requirement: Device files are build inputs
`cmd_build` SHALL list the name, relative to the script folder, and the SHA-256 of every project device file in `result.device_files`, and SHALL add the files to the inputs that a plan id depends on (`Result.depends`), so that a changed device file changes the plan. The envelope's `input` keeps naming the design script alone (contract v0).

#### Scenario: Device file in the input
- **WHEN** `examples/devices/design.py` is built with `--dry-run --json`
- **THEN** `result.device_files` lists `devices/example_buck.toml` with its SHA-256, and no absolute path

### Requirement: Shipped generic devices
The catalog SHALL ship the Fenolite-authored devices `Fenolite:R_0402`, `R_0603`, `R_0805`, `R_1206`, `C_0402`, `C_0603`, `C_0805`, `C_1206`, `LED_0603` and `Conn_1x2_P2.54`. Each MUST join one catalog symbol and one catalog footprint, have no manufacturer, MPN or ratings, carry `INFERRED` and the sources of its two entries, and pass `check_device`. Two-terminal devices name their functions `P1` and `P2` (the LED `A` and `K`) and list them in `ends`.

#### Scenario: Every shipped device agrees with the catalog
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k shipped` runs `check_device` on every shipped device with its catalog symbol and footprint
- **THEN** no issue is returned, every device has a non-empty `sources`, and none has a manufacturer or an MPN

#### Scenario: The LED keeps the cathode-first map
- **WHEN** `Fenolite:LED_0603` is read
- **THEN** its pin `A` has `pin_pads == (("1", "2"),)` and its pin `K` has `pin_pads == (("2", "1"),)`

### Requirement: Device digest
`fenolite.catalog.devices.device_digest(device) -> str` SHALL be the lowercase hex SHA-256 of the canonical JSON of the record with `provenance` set to `None`, so that a change of formatting or of key order does not change it.

#### Scenario: Reformatting keeps the digest
- **GIVEN** a device file and a copy with its keys reordered and blank lines added
- **WHEN** both are parsed
- **THEN** their digests are equal

### Requirement: Device provenance and edits
A `provenance` table SHALL hold `tool`, `source` (never an absolute path), `date` (an ISO 8601 date) and `sha256`. A record whose `provenance.sha256` differs from its digest SHALL be `edited`: the build reports `device.edited` (info) once per edited device it uses, and `catalog show` gives `"edited": true`. The evidence label written in an edited record MUST be kept. A record without `provenance` is never `edited`.

#### Scenario: A hand edit is detected
- **GIVEN** a device written by `fenolite catalog import --confirm`, whose `mpn` is then changed by hand
- **WHEN** a design that uses it is built with `--dry-run --json`
- **THEN** `issues` holds `device.edited` naming the device, and `result.devices[0].edited` is `true`

#### Scenario: Reformatting is not an edit
- **GIVEN** the same imported device with its keys reordered and no value changed
- **WHEN** it is loaded
- **THEN** it is not `edited`

### Requirement: Devices in the catalog list and show
`fenolite catalog list --kind device` SHALL list the shipped devices in id order, each with `id`, `kind` `device`, `summary`, `evidence` and `sources`; without `--kind` the list holds symbols, footprints and devices. `catalog show <id> --kind device` SHALL show the record, `digest`, `edited`, `shadowed` (functions that are `Part` attribute names) and, for catalog symbol and footprint, the `check_device` issues. Without `--kind`, `show` gives a device only when no symbol or footprint has the id.

#### Scenario: List devices
- **WHEN** `fenolite catalog list --kind device --json` runs
- **THEN** `result` lists the ten shipped devices in id order, each with `kind` `device`

#### Scenario: Show a device
- **WHEN** `fenolite catalog show Fenolite:R_0603 --kind device --json` runs
- **THEN** `result` holds the record, a 64-character `digest`, `edited` `false` and an empty `shadowed`

### Requirement: Device import
`fenolite catalog import --symbol LIB:SYM --footprint LIB:FP --id NS:NAME --out FILE [--pin FUNCTION=PIN[:PAD[+PAD]]]... [--manufacturer T] [--mpn T] [--datasheet URL] [--ref-prefix P]` SHALL plan one write of kind `device` holding `device_text` of a record with `evidence = "UNVERIFIED"` and a provenance whose `tool` is `fenolite catalog import`, `source` the two lib ids, `date` the date of `--timestamp` (else today in UTC) and `sha256` the digest.

#### Scenario: Import a template
- **WHEN** `fenolite catalog import --symbol Fenolite:Resistor --footprint Fenolite:Chip_0603 --id Proj:R_0603 --out devices/r.toml --timestamp 2026-10-29T00:00:00Z --confirm --json` runs
- **THEN** the exit code is 0, `receipt.written` lists `devices/r.toml`, the file parses with `evidence` `UNVERIFIED` and `provenance.date` `2026-10-29`, and a second run with the same flags writes identical bytes

### Requirement: Device import pins and pads
`catalog import` SHALL name functions after the symbol's pin names, grouping pins that share a name and naming an empty or `~` name `P<number>`, and SHALL map pins to the pads of their numbers unless `--pin` maps them. A pin without such a pad MUST give `catalog.pin-without-pad` (error), and no write is planned. A footprint pad that no pin names MUST give `catalog.pad-unmapped` (warning) and is left out.

#### Scenario: A pin without a pad
- **WHEN** `catalog import` pairs a three-pin symbol with a two-pad footprint and passes no `--pin`
- **THEN** the exit code is 5, `issues` holds `catalog.pin-without-pad` naming pin `3`, and nothing is written

#### Scenario: Grouped names
- **GIVEN** an authored symbol whose pins `2` and `9` are both named `GND`
- **WHEN** it is imported with a footprint that has pads `1` to `9`
- **THEN** the record has one function `GND` with `pin_pads == (("2", "2"), ("9", "9"))`

### Requirement: Device import keeps hand edits
`catalog import` onto an existing `FILE` that is `edited` SHALL exit 7 with `FEN-7001` and write nothing unless `--allow-lossy` is given; onto an existing file that is not edited it SHALL plan the replacement. Catalog ids MUST resolve offline, and other lib ids through the build's `LibraryResolver` with the project folder set to the folder of `--out`. `example_args` and `mutation_example_args` MUST use catalog ids and run no subprocess.

#### Scenario: Re-import over a hand edit
- **GIVEN** `devices/r.toml` from "Import a template", with its `summary` changed by hand
- **WHEN** the same import runs with `--confirm`
- **THEN** the exit code is 7, stderr carries `FEN-7001`, and the file is unchanged

#### Scenario: Re-import of an unedited file
- **GIVEN** `devices/r.toml` from "Import a template", unchanged
- **WHEN** the import runs again with `--mpn X-1 --confirm`
- **THEN** the exit code is 0 and the file holds `mpn = "X-1"` with a new `provenance.sha256`

### Requirement: Catalog definitions are data files
Every shipped catalog symbol and footprint SHALL be given by a record file under `src/fenolite/catalog/data/` (`pins/` or `packages/`), read with `fenolite.catalog.records`. The package MUST NOT hold symbol or footprint geometry in Python. `get_symbol`, `get_footprint`, `list_entries`, `ENTRIES`, `default_pad_map`, `ANODE_FIRST_SYMBOLS` and `CATHODE_FIRST_LANDS` SHALL keep their names and results.

#### Scenario: No geometry in code
- **WHEN** `uv run pytest tests/unit/catalog/test_data_only.py` runs
- **THEN** it finds no `_symbol_expansion.py` and no dimension table in `src/fenolite/catalog/*.py`, and every entry of `ENTRIES` has one record file

#### Scenario: Pad map from the records
- **WHEN** `default_pad_map("Fenolite:LED", "Fenolite:LED0603_Kingbright_APT1608SURCK")` is called
- **THEN** it returns `(("1", "2"), ("2", "1"))`, computed from `polarity` and `pad1` in the records

### Requirement: The move to data keeps every byte
`tests/data/catalog/golden.json`, written from the Python catalog before the move, SHALL hold per lib id the `output_digest` of its definition and the SHA-256 of each file built for the catalog examples. After the move every digest MUST be equal. The file SHALL change only together with a version change in `VERSIONS.toml`.

#### Scenario: Definitions equal the golden digests
- **WHEN** `uv run pytest tests/unit/catalog/test_golden.py` runs
- **THEN** every shipped symbol and footprint has the `output_digest` recorded in `golden.json`

#### Scenario: Built files are byte-identical
- **WHEN** the KiCad job builds `examples/catalog*` with `--seed 1` and a fixed `--timestamp`
- **THEN** every written file but `.fenolite/meta.json` (which names the version of Fenolite) has the SHA-256 recorded in `golden.json`

### Requirement: Catalog entries show version and licence
`CatalogEntry` SHALL gain `version`, `licence` and `uid` with defaults. `fenolite catalog list` and `fenolite catalog show` SHALL add the keys `version`, `licence` and `uid` to each entry; every existing key and value MUST stay as before.

#### Scenario: Show a moved entry
- **WHEN** `fenolite catalog show Fenolite:Resistor --json` runs
- **THEN** the entry holds `version` `1.0.1` (written `1.0.0` by the move, raised by the change of licence to `CC0-1.0`), `licence` `CC0-1.0`, its `uid`, and the same kind, category, summary, evidence and sources as on 0.6.0

### Requirement: Interface ports of a device
A c0248 device record SHALL define its reserved key `interfaces` as `[[interfaces]]` tables. Each holds `name`, `kind`, `direction`, `members` (member name to a list of the device's functions), the parameters allowed for its kind and direction (a range in c0248's `{ min, max }` spelling, a threshold as one quantity text), `reference` (another `power` interface of the device), `requires` and `evidence`. A power `voltage` is an operating range, never an absolute rating.

#### Scenario: Valid ports load
- **GIVEN** an illustrative device record authored for Fenolite with the ports `vdd` (`power`, `in`) and `i2c1` (`i2c`, `inout`, `reference = "vdd"`, `requires = ["pullup", "supply"]`, `input_high_min = "1.3V"`, `output_low_max = "0.4V"`)
- **WHEN** `uv run pytest tests/unit/catalog/test_device_ports.py -k valid` loads it
- **THEN** both interfaces load with their members, parameters, thresholds, companions and evidence, and the record no longer gives `FEN-3002`

### Requirement: Refused device interfaces
The device loader SHALL give `FEN-3004`, naming the file, the interface and the rule, for an interface whose kind or member is unknown, that names a function the device lacks or one in two members, whose `reference` is not another `power` interface of the device, that sets a parameter its kind and direction do not allow (`current` on `inout` included), with a `requires` entry its kind does not take, or named like a function of the device or an attribute of `Part`.

#### Scenario: Bad ports refused
- **WHEN** the loader reads, in turn, an interface naming a function the device lacks, an interface named like one of the device's functions, a `reference` to a non-`power` interface, a `current` on a `logic` interface, a `current` on an `inout` `power` interface, and `requires = ["chip_select"]` on an `i2c` interface
- **THEN** each gives `FEN-3004` naming the file, the interface and the rule

### Requirement: Parametric families in the shipped catalog
The shipped catalog SHALL hold family records (`fenolite.family.v0`) for E24 5 % and E96 1 % chip resistors and for C0G and X7R chip capacitors in the cases 0402, 0603, 0805 and 1206, each naming a shipped symbol and footprint. Every numeric attribute MUST cite a registered public source with a label no higher than the source allows; an attribute without a source MUST be absent, and no family MUST name a manufacturer part number.

#### Scenario: Every family number has a source
- **WHEN** `uv run pytest tests/unit/catalog/test_families.py` runs
- **THEN** every numeric attribute of every shipped family names a source id registered in `docs/evidence/sources.md`, no family has an MPN, and every symbol and footprint it names is a shipped entry

### Requirement: Catalog data version
`fenolite.catalog.FAMILIES_VERSION` SHALL name the version of the catalog data and MUST change whenever a family's canonical text changes. `fenolite catalog list --kind family` and `fenolite catalog show <family id>` MUST show the families with their sources.

#### Scenario: The version follows the data
- **GIVEN** a shipped family whose canonical text differs from the one recorded for the current `FAMILIES_VERSION` in `src/fenolite/catalog/families/VERSIONS.toml`
- **WHEN** the catalog test runs
- **THEN** it fails naming the family and asking for a new `FAMILIES_VERSION`

### Requirement: Absolute and operating limits of a device
In a device record, a pin's `voltage` and `current`, each key of `[ratings]` and each `[[limits]]` `voltage` SHALL be a table of `abs_max` and/or `operating`, each a `{ min, max }` table or a string read as the maximum. The single `{ min, max }` form of c0248 MUST raise `FormatError` (`FEN-3004`) naming the file and the key, with a hint to say `abs_max` or `operating`. An `operating` range outside its `abs_max` range MUST raise `FEN-3004`.

#### Scenario: Both kinds on one pin
- **GIVEN** `VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" }, abs_max = "6.5V" } }`
- **WHEN** `uv run pytest tests/unit/catalog/test_devices.py -k limits` parses the record
- **THEN** `VIN` holds the rating (`voltage`, `abs_max`, max 6 500 000 µV) and the rating (`voltage`, `operating`, 2 700 000 to 6 000 000 µV)

#### Scenario: The ambiguous form is refused
- **WHEN** records with `VIN = { pins = ["5"], voltage = { min = "2.7V", max = "6V" } }` and with `voltage = { operating = "7V", abs_max = "6.5V" }` are parsed
- **THEN** each raises `FormatError` with code `FEN-3004` naming `VIN`, the first with the hint naming `abs_max` and `operating`

### Requirement: Limits between two pins
A device record SHALL accept `[[limits]]` tables, each with `between` (two distinct functions of the device) and `voltage` (as "Absolute and operating limits of a device"), meaning the voltage of the first function minus that of the second. An unknown function, a repeated pair or another key MUST raise `FEN-3004`. The canonical text MUST order the rows by `between`.

#### Scenario: Bootstrap to switch node
- **GIVEN** `[[limits]]` with `between = ["BST", "SW"]` and `voltage = { abs_max = "6V" }` in a record whose functions include `BST` and `SW`
- **WHEN** the record is parsed and written with `device_text`
- **THEN** `DeviceDef.limits` holds one `PinPairLimit` for `("BST", "SW")` with `abs_max` 6 000 000 µV, the text round-trips, and `between = ["BST", "XX"]` raises `FEN-3004` naming `XX`

### Requirement: Logic thresholds of device pins
A pin of a device record MAY state `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max` (voltages from `ground`) and `output_current_max` (a current), each one quantity text from the datasheet. A c0252 `logic` or bus port of the device SHALL take a threshold its own table omits from its member pins, the strictest of them (highest `input_high_min`, lowest `input_low_max`, lowest `output_high_min`, highest `output_low_max`, lowest `output_current_max`).

#### Scenario: A port takes its pins' thresholds
- **GIVEN** a record whose pins `PB6` and `PB7` state `input_high_min` 1.3 V and 1.4 V and whose `i2c1` port (`sda` on `PB7`, `scl` on `PB6`) states no `input_high_min`
- **WHEN** `uv run pytest tests/unit/catalog/test_device_ports.py -k thresholds` loads it and builds a part
- **THEN** the model `Port` `i2c1` has the param `input_high_min` of 1.4 V, and with `input_high_min = "1.2V"` in the port's table it has 1.2 V

### Requirement: Device class key
A device record MAY hold `class`, one name of the roles' class vocabulary (`net-roles`, "Part classes"). Another name MUST raise `FEN-3004` listing the vocabulary. The key is evidence for `fenolite.roles.classify`, never a second classifier.

#### Scenario: A ferrite says what it is
- **GIVEN** a record with `ref_prefix = "L"` and `class = "ferrite"`
- **WHEN** a part placed from it is classified by `roles.classify`
- **THEN** its class is `ferrite` with confidence `high` and source `device`, and `class = "bead"` raises `FEN-3004`

### Requirement: Device temperatures in kelvin
Device temperature limits SHALL be stored in integer millikelvin (unit `mK`), read from texts in `degC` or `K` by `fenolite.core.quantities`. A text that is not a whole number of millikelvin MUST raise `FEN-3004`.

#### Scenario: Celsius and kelvin agree
- **WHEN** records with `temperature = { operating = { min = "-40degC", max = "125degC" } }` and `temperature = { operating = { min = "233.15K", max = "398.15K" } }` are parsed
- **THEN** both give the operating range 233 150 to 398 150 mK, and `"-40.0001degC"` raises `FEN-3004`

### Requirement: Catalog footprints come from the generators
The catalog footprints SHALL be drawn only from their c0259 package records, without private land helpers or land tuples in `fenolite.catalog`, and every catalog `.kicad_mod` MUST keep its bytes.

#### Scenario: Catalog bytes unchanged
- **GIVEN** `tests/data/catalog/footprints.sha256`, the SHA-256 of every catalog footprint written for KiCad 9 and 10 before this change
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k golden` writes every footprint that `list_entries(kind="footprint")` names
- **THEN** all 100 digests equal the golden list for both targets

#### Scenario: No private land helper remains
- **WHEN** `uv run pytest tests/unit/catalog/test_catalog_generated.py -k helpers` searches the modules of `src/fenolite/catalog/`
- **THEN** none defines `_chip_footprint`, `_two_terminal_footprint`, `_row_pads`, `_quad_pads`, `_paste_grid`, `_thermal_paste`, `_pin1_index` or `_make_footprint`, and none holds a `_*_LANDS_UM` table

### Requirement: Family entries reproduced under drawing 0
c0259 stores each catalog footprint as an explicit pad list (`generator = "explicit"`); the family-shaped entries (chips, molded two-terminals, small-outline, QFN, DFN, QFP and DIP entries) MUST be reproduced exactly by `fenolite.catalog.footprints.generate` under `drawing = 0` from a record with a `[land]` holding the same numbers, so that a later version of a record can move to its family without changing its bytes.

#### Scenario: Drawing 0 reproduces the catalog
- **GIVEN** family records with `drawing = 0` and a `[land]` holding the numbers of `Chip_0603`, `SOIC14_TI_D0014A`, `LQFP48_TI_PT0048A`, `QFN16_Diodes_W3030_A1`, `DFN6_Diodes_W2020_US` and `DIP8_Microchip_P`
- **WHEN** `generate` draws each
- **THEN** each `FootprintDef` equals `get_footprint` of the catalog entry of the same name

### Requirement: Records move to a family only with cited numbers
A record SHALL be re-expressed in its family only when the family keys the generator requires (span, lead length and width) come from the sources the record cites; numbers the 0.6 tables never held MUST NOT be invented.

#### Scenario: Span not in the sources
- **WHEN** the sources a catalog record cites give no span or lead length for its package
- **THEN** the record stays `generator = "explicit"` and no family key is added to it

### Requirement: Vendored library records
The runner SHALL read `fenolite_library/symbols`, `fenolite_library/footprints` and `fenolite_library/devices` beside the script as project records with c0259's `load_tree`, importing no module. For each id, authored records SHALL win over vendored ones (`library.overrides-item`, info), and vendored over the shipped catalog. One id in two vendored items MUST give `library.item-conflict` (error) naming both folders.

#### Scenario: Authored record wins
- **GIVEN** the vendored device `Demo:EXB` and a project device in `devices/` with the same id
- **WHEN** a design using it is built
- **THEN** the project device is used and `issues` holds `library.overrides-item`

#### Scenario: Two vendored items, one id
- **GIVEN** two vendored device folders that both hold the record `Shop:X`, and a design using `Shop:X`
- **WHEN** it is built
- **THEN** the build reports `library.item-conflict` naming both folders and writes nothing

#### Scenario: Unused vendored item changes nothing
- **GIVEN** a design using only shipped devices, built once without and once with a vendored `Demo:EXB`
- **WHEN** both output trees are compared
- **THEN** they are byte-identical

### Requirement: Vendored records in checks and private tests
Circuit checks and private block tests SHALL use the owning project's authored records before vendored records, with native reference files preserved. Private tests MUST leave source files and locks unchanged. Conflicting vendored identities MUST remain error findings in circuit checks. A golden plan MUST bind the device inputs used by its private build.

#### Scenario: Vendored block uses a vendored device
- **GIVEN** a block and its device items fetched from authored local releases, with an optional authored device override
- **WHEN** its usage example and a plain test calling `instantiate` run
- **THEN** both private builds resolve the device and the original project bytes are unchanged

#### Scenario: Circuit check finds conflicting vendored data
- **GIVEN** a built design whose device id now occurs in two vendored folders, with or without an authored override
- **WHEN** `check --stages circuit.rules` runs
- **THEN** it reports `library.item-conflict` and does not select a conflicting vendored device

#### Scenario: Device edit after golden review
- **GIVEN** a dry-run golden plan for a vendored block using an authored device override
- **WHEN** the device record changes before confirmation
- **THEN** confirmation gives `FEN-4002` and writes no golden

### Requirement: Device builds stay offline
No build, check, `capabilities` or `doctor` run SHALL open a network connection or read device data outside the project, the shipped catalog and, for hints only, the cached library index. An unknown id whose namespace is in the newest cached index SHALL get the hint `fenolite get device <id> --dry-run`.

#### Scenario: Build with vendored records and no network
- **GIVEN** `socket.socket.connect` patched to raise and a vendored `Demo:EXB`
- **WHEN** a design using it is built
- **THEN** it succeeds and no connection was attempted

#### Scenario: Hint for a library id
- **GIVEN** a cached library index holding `device` `Demo:OTHER` and a design naming `Demo:OTHER`, not vendored
- **WHEN** the design is built
- **THEN** it fails as an unknown device and the message names `fenolite get device Demo:OTHER --dry-run`

