## ADDED Requirements

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

## MODIFIED Requirements

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
