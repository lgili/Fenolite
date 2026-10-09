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
Definitions MUST NOT be copied or vendored from another CAD library or private project. The catalog
MUST NOT claim complete coverage of commercial parts, choose a package for a part, or assert
manufacturing qualification. Non-standard or proprietary geometry remains project-authored unless
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

### Requirement: Discoverable catalog API and CLI
The public `fenolite.catalog` API SHALL list and retrieve symbol/footprint definitions by stable lib id, with optional case-insensitive search over id, category and summary. `fenolite catalog list` and `fenolite catalog show <lib-id>` SHALL expose the same entries through the CLI JSON envelope, including evidence and source ids, without running an external tool.

#### Scenario: Search by category
- **WHEN** the API or CLI searches for a category in the shipped catalog
- **THEN** matching entries are returned in stable lib-id order with their kind and evidence

#### Scenario: Show a definition
- **WHEN** `fenolite catalog show Fenolite:Resistor` names a known entry
- **THEN** it returns its kind, metadata, source ids and package/symbol definition summary

### Requirement: Build resolves built-in definitions
The KiCad `fenolite build` SHALL resolve catalog symbol and footprint lib ids without consulting global/project CAD library tables for those ids. It SHALL write the definitions used by the design into the generated project's local libraries. A project-authored definition whose lib id exactly matches a catalog entry MUST take precedence for that build only; other catalog entries remain available. The build MUST report the origin as `builtin` for an unmodified catalog entry and `authored` for a project override.

#### Scenario: Offline built-in build
- **GIVEN** a design that names a shipped symbol and footprint
- **WHEN** it is built with empty library tables and offline resolver configuration
- **THEN** its definitions resolve, the generated local tables point to the local output libraries, and the result labels their origin `builtin`

#### Scenario: User customizes a standard definition
- **GIVEN** a project-authored symbol or footprint with the same lib id as a catalog entry
- **WHEN** the project is built
- **THEN** the authored definition is used and labelled `authored`, with no mutation of the shipped catalog

### Requirement: Source and evidence labels
Each factual symbol pin map, polarity claim or physical package dimension in the catalog SHALL cite
one or more public sources registered in `docs/evidence/sources.md`. A land pattern not explicitly
specified by those sources MUST be labelled `INFERRED` in catalog metadata and the definition
description. A writer/readback check MUST NOT upgrade an inferred dimension's evidence level.
Public sources MUST be sufficient for each claim; private board data and copied CAD library content
MUST NOT be used as provenance.

#### Scenario: Every family pack has independent provenance
- **WHEN** the catalog source check runs
- **THEN** it fails for an unregistered source id, a factual claim without supporting provenance,
  or an inferred footprint without an inferred-land description
- **AND** it rejects catalog provenance that points to a private board artifact or third-party CAD
  library file

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
