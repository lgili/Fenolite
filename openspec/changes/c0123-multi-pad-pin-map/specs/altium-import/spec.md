## MODIFIED Requirements

### Requirement: Pin-to-pad map of a footprint model
When the current footprint model of a schematic component carries a pin map, the imported component SHALL carry it in `Component.pin_pad_map`, so that the elements of each mapped pin in the assignment comparison and in level 2 of `equivalent` are `REF-<pad>` for every pad the map gives the pin; without a map the pin number is the pad name. The members of the circuit's nets stay keyed by pin number.
- A map record that lists several pads MUST give one pair per pad, in the order of the record ("Persist per-component pin-to-pad maps" of `design-model`): a pad listed twice gives one pair, and a record that lists the pin's own designator among several pads gives a pair of the pin with itself (`H-A-IMP-PINMAP-MULTI`).
- `pin_pad_map` gives a pad one pin. The pins are taken in the order of the pin table; a pin without a record, a pin whose record lists its own designator, and a pin whose record lists no pad stand for the pad of their own designator before any other pin is taken. A pad that another pin already stands for MUST give no pair, and a pin none of whose pads gives a pair keeps its own designator. Each record of which a pad gave no pair, and each record that lists no pad, MUST be kept whole in the component's extension bag (`pin_pads`, `<pin>=<pad>,<pad>…`), and one `altium.import.pin-map` (info) per import MUST give their count. A record that the pairs say in full MUST NOT be in the bag and MUST NOT be counted, and an import without such a record MUST NOT report the code.
- A record that names no pin of the component MUST be left out.
- A net of the PCB document that the sheets lack MUST list the pin of each pad, through the map.

#### Scenario: Mapped pins
- **GIVEN** an authored sheet whose component `Q1` maps the pins `1, 2, 3` to the pads `G, D, S`
- **WHEN** the schematic netlist of the import is built
- **THEN** its elements for `Q1` are `Q1-G`, `Q1-D` and `Q1-S`

#### Scenario: Several pads of one pin
- **GIVEN** an authored sheet whose component maps pin `1` to the pads `1, 4`, pin `2` to `5, 6` and pin `3` to no pad
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_repeat.py -k pin_map` imports it
- **THEN** `pin_pad_map` is `(("1", "1"), ("1", "4"), ("2", "5"), ("2", "6"))`, the bag holds the one record `3=`, `altium.import.pin-map` counts one, and the schematic netlist holds the elements `-1`, `-4`, `-5`, `-6` and `-3` of the component

#### Scenario: Pad that another pin holds
- **GIVEN** an authored sheet whose component has the pins `1` and `2` and maps pin `1` to the pads `2, 7`
- **WHEN** the import runs
- **THEN** `pin_pad_map` is `(("1", "7"),)`, the bag holds `1=2,7`, and `altium.import.pin-map` counts one

#### Scenario: Board net through a pin of two pads
- **GIVEN** an authored project whose sheet maps pin `3` of `U1` to the pads `3, EP`, and whose PCB document holds a net that the sheets lack on the pads `3` and `EP` of `U1`
- **WHEN** `uv run pytest tests/unit/backends/altium/adapter/test_project.py -k several_pads` imports the project
- **THEN** that net lists the pin `3` of `U1` once

#### Scenario: The public set with such records
- **WHEN** `uv run pytest tests/corpus/test_altium_channels.py -k pin_map` imports `altium-set:02` and compares its schematic with its PCB document
- **THEN** no component holds a `pin_pads` record that lists several pads, and the comparison gives 698 common elements, 7 that only the schematic covers, 27 that only the PCB document covers and 2 differences (694, 7, 31 and 2 before this change); the other sets give the counts they gave
