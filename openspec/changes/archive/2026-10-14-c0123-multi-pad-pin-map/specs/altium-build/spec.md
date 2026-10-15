## MODIFIED Requirements

### Requirement: Pin maps in an Altium build
An Altium build SHALL apply `Component.pin_pad_map` to the PCB document and write it to the schematic: a pad of a placed component MUST carry the net of the pin that names it (`Component.pads_of`: each pad of a pin that is bonded to several pads, change c0123), a pin outside the map naming the pad of its own number, and the schematic MUST hold the map ("Pin map records of a footprint model" of `altium-schematic-writer`). Before this requirement a pad carried the net of the pin of its own number, whatever the map said, which the requirement "Per-component pin-to-pad mapping" of `design-dsl` did not allow.
- **Copper.** The check of a copper source (script copper and `--copper-from`) MUST read the wanted net of each pad through the same map (`altium_copper.pad_net_names`, which the PCB document reads too), every pad of a pin carrying the pin's net: a design with a map and tracks on its mapped part builds; the KiCad board of the same script is accepted as copper source; a board that was routed for another assignment of the pads is refused with `altium.copper-board-mismatch`, whose message names the net the design puts on the pad.
- **Issue code.** `altium.pin-pad-map-invalid` (error) joins the closed table `lens.altium.ALTIUM_ISSUE_CODES`: one issue for each pair of a map that names a pin the component does not hold, for each pair that names a pad the resolved footprint does not hold, and for each pad of two pins (below), with `where` set to the component's path. A build with this issue MUST exit 5 and write nothing.
- **A pad of two pins.** A pad that two pins of the component stand for, one by the map and one by its own number (`pad_map={"1": "2"}` on a part that has a pin `2`, and its mirror `{"2": "1"}`), MUST give one `altium.pin-pad-map-invalid` that names the pad and both pins, also when both pins are on one net. This keeps the two targets alike: "Per-component pin-to-pad mapping" of `design-dsl` refuses a "duplicate physical target", and the KiCad build refuses such a map with `build.pin-pad-map-invalid` in both cases (measured at the tag `v0.2.0`). The release 0.2.0 built such a script for Altium, ignoring the map. Since change c0123 the model itself says `model.pin-pad-map` of such a pad ("Persist per-component pin-to-pad maps" of `design-model`), which is what model validation and `fenolite check` report of a model that holds it. The build MUST still report its own code: it MUST reach `pin_map_issues` before the model's finding ends the build, and its issue list then holds `altium.pin-pad-map-invalid` and, beside it, `model.pin-pad-map` once for each of the two pins; the KiCad build holds `build.pin-pad-map-invalid` and the same findings of the model. The form in which the map itself lists one pad for two pins never reaches a build: `Part` raises `DslError` for it. A pin number that a component lists twice is one pin.
- For a part of an Altium link the pins are the designators its nets and marks use, so the symbol is not known: a pair whose pin no net uses MUST NOT be reported as a pin the symbol lacks, and gets no record.
- A footprint that is not resolved gives `altium.footprint-unresolved` as before; its pads are not checked.
- A design in which no component holds a map MUST build the files it built before, byte for byte.
- `docs/altium.md` and `src/fenolite/cli/data/explain.toml` MUST list the code.
- **What `check` says.** `fenolite check` on a project built from a script with a map, renaming or of several pads per pin, compares the schematic and the board through the map (the import reads the map records into `pin_pad_map`, change c0083, and `netlist.assignment_compare` names every pad): it MUST NOT report `netlist.assignment-differs` for the mapped pins, and exits 0 as for the project without a map. The release 0.2.1, whose import leaves the map records out of the model, compares the schematic by pin number and the board by pad number and reports it; `docs/altium.md` and the changelog MUST say which release does which.

#### Scenario: Net on the mapped pads
- **GIVEN** the blink with `pad_map={"1": "2", "2": "1"}` on its `D1`, whose pin `1` is on `GND`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k "renaming_map or both_targets"` builds it with `--target altium`, reads the written PCB document, and builds the same script for KiCad
- **THEN** the pad `2` of `D1` is on `GND` and its pad `1` is not (the releases 0.1.0 and 0.2.0 wrote the opposite), and the KiCad board has the same nets on the two pads

#### Scenario: Net on every pad of a pin
- **GIVEN** the blink with its `R1` on a 32-pad footprint and `pad_map={"1": ("1", "5"), "2": ("7", "6")}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pin_map.py -k pad_nets` builds it with `--target altium` and reads the written PCB document
- **THEN** the pads `1` and `5` of `R1` are on the net of its pin `1`, the pads `7` and `6` on the net of its pin `2`, and its pads `2` and `8` on none

#### Scenario: Copper on a mapped part
- **GIVEN** the routed blink with the same map on `D1` and its two tracks ending on the mapped pads, with and without a zone, and the KiCad boards built from the routed blink with and without the map
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map_copper.py` builds each script for Altium, alone and with `--copper-from` each board
- **THEN** the script with the map builds with its tracks and with its zone, with the nets of `D1` equal to those of its KiCad board; `--copper-from` its own board is accepted; and `--copper-from` the board of the other script is refused with `altium.copper-board-mismatch` saying "pad 1 of D1 is on GND there, the design puts it on LED_A", nothing written

#### Scenario: Copper of pins with several pads
- **GIVEN** the blink with a pour whose `D1` is on a 32-pad footprint, on the top side, with `pad_map={"1": ("1", "5"), "2": ("2", "6")}`, and the KiCad boards of that script and of the same script without the map
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pin_map_copper.py` builds the script for Altium with `--copper-from` each board
- **THEN** its own board is accepted, with `GND` on the pads `1` and `5` and `LED_A` on the pads `2` and `6` of both; the board without the map is refused with `altium.copper-board-mismatch` for the pads `5` and `6`, which it leaves on no net

#### Scenario: Map that names a missing pad
- **GIVEN** the blink whose `D1` has `pad_map={"1": "TAB"}`, a pad its footprint lacks, and the blink whose `D1` has `pad_map={"9": "1"}`, a pin its symbol lacks
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k missing` builds each with `--target altium --confirm --json`
- **THEN** the exit code is 5, `issues` holds `altium.pin-pad-map-invalid` naming `TAB` or the pin `9` with `where` `D1`, and the output folder is not created

#### Scenario: Pad that two pins stand for
- **GIVEN** the blink whose two-pin `D1` has `pad_map={"1": "2"}`, and the one with `pad_map={"2": "1"}`, each once with its pins on two nets and once with both pins on `GND`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py -k "two_pins or repeated_pin"` builds each for the Altium target and for KiCad
- **THEN** the Altium build exits 5 with one `altium.pin-pad-map-invalid` that names the pad and the pins `1` and `2`, and `model.pin-pad-map` beside it, and creates no output folder; the KiCad build exits 5 with one `build.pin-pad-map-invalid` and `model.pin-pad-map` beside it; `Part(..., pad_map={"1": "3", "2": "3"})` raises `DslError`; a component that lists a pin number twice gives no issue; and a part of an Altium link with a mapped pin that no net uses gives none

#### Scenario: Check of a built project with a map
- **GIVEN** the Altium builds of the blink with `pad_map={"1": "2", "2": "1"}` on `D1`, of the blink with its `R1` on a 32-pad footprint and `pad_map={"1": ("1", "5"), "2": ("7", "6")}`, and of the blink without a map
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pad_map.py tests/unit/lens/test_altium_pin_map.py -k "check_compares or check_knows"` runs `fenolite check` on each
- **THEN** each exits 0 and none reports `netlist.assignment-differs`

#### Scenario: Closed set still closed
- **WHEN** `uv run pytest tests/unit/lens/test_altium_issues.py -k closed_set` collects the codes the Altium build tests produce
- **THEN** `altium.pin-pad-map-invalid` is a key of `ALTIUM_ISSUE_CODES` with the severity `error` and is produced by a test
