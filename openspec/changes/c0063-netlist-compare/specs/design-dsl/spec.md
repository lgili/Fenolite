## ADDED Requirements

### Requirement: Schematic netlist guard in a build
A build that writes a schematic SHALL prove, before it returns any file and without any tool, that the sheet it generated means the circuit, as a step that "Built project files" allows after `schgen.generate_schematic`.
- The guard MUST compute `sch_netlist.own_netlist(generated.sheet, project=name)` and compare it with the expected netlist of the design: each net of the circuit under `netnames.stored_name` of its name, with each member named by its component's reference and its pad number (the pin number mapped through `pin_pad_map`), and each entry of `generated.pad_nets` as a net of one node under its name. A pin on no net whose name is not in `pad_nets` MUST only be required to be a net of one node.
- A net or a node on one side only, or a grammar issue, MUST give one `build.schematic-netlist-differs` issue of severity `error`, naming the first net and `REF-PIN` in sorted order, and the build MUST return no file (exit 5).
- The code SHALL join the closed build issue set of "Build issue codes".
- With `schematic="skip"` the guard MUST NOT run.
- The guard MUST NOT compare `pintype`, net classes or component values: it is about connectivity.

#### Scenario: Examples pass the guard
- **WHEN** `uv run pytest tests/unit/lens/test_build_netlist_guard.py -k examples` builds the blink and the units design for targets 9 and 10
- **THEN** no `build.schematic-netlist-differs` is reported, and `files` holds the schematic

#### Scenario: Generator defect caught
- **GIVEN** a `generate_schematic` patched in the test to put the label of `R1` pin `2` on pin `1`
- **WHEN** `build_design` runs for the blink
- **THEN** `files` is empty, and `issues` holds one `build.schematic-netlist-differs` error naming `LED_A` or `LED_DRV` and `R1-1` or `R1-2`

#### Scenario: Skipped schematic, no guard
- **WHEN** the blink is built with `schematic="skip"` and the same patch
- **THEN** the build returns its files and no `build.schematic-netlist-differs`

#### Scenario: Hermetic
- **GIVEN** `subprocess.run` and `subprocess.Popen` patched to raise
- **WHEN** the blink is built with a schematic
- **THEN** the build succeeds
