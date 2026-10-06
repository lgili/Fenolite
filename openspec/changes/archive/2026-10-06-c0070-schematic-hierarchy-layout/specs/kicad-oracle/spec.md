## ADDED Requirements

### Requirement: Hierarchy and wire facts are probed
`tests/kicad/schematic/test_hierarchy_probes.py` (marker `needs_kicad`, major-aware) SHALL settle `H-K-SCH-HIER-FILE` and `H-K-SCH-WIRE-END` on the running `kicad-cli`, with sheets written by the test for Fenolite, before the generator writes a child sheet or a wire. Each probe MUST run `sch erc --format json --severity-all` and `sch export netlist` on a copy with an empty `KICAD_CONFIG_HOME`, through c0009's `KicadCli`. A hand-written sheet comes without a symbol table, so ERC always reports `lib_symbol_issues` for it (`H-K-SCH-LIBTABLE`); the probes MUST NOT count that type, and "no violation" below means none of another type.
- `sch-hier-file-parent`: a root naming `sheets/a.kicad_sch`, which names `b.kicad_sch` in the same folder, each sheet with one `Mini_R` whose pins carry the global labels `VCC` and `SIG`. `present` when the netlist lists the symbol of `b` with the sheet path names `/a/b/`.
- `sch-hier-file-project`: the same with `a` naming `sheets/b.kicad_sch`. `absent` when the netlist lists no symbol of `b`, ERC reports no violation and both commands exit 0.
- `sch-hier-global`: in the `parent` tree, `equal` when the nets `VCC` and `SIG` each hold the three symbols' pins, ERC reports no violation, and the `tstamps` of each child symbol's `sheetpath` are `/<uuid of a>/` and `/<uuid of a>/<uuid of b>/`.
- `sch-wire-ends`: a flat sheet with two `Mini_R` whose pins 1 are joined by one wire and carry one global label `MID` at one end. `equal` when the net `MID` holds both pins and ERC reports no violation.
- `sch-wire-middle`: a third `Mini_R` whose pin 1 ends in the middle of that wire, without a junction. `absent` when that pin is not in `MID`.
- Outcomes MUST be recorded in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`, and the facts MUST be written to `docs/formats/kicad/schematic.md` with their source and label.
- **Stop rules.** `sch-hier-file-parent` other than `present` stops the hierarchy until the file names are revised; `sch-hier-global` other than `equal` stops it until a pinless design is shown to name nets; `sch-wire-ends` other than `equal` stops the satellites.

#### Scenario: Probes on 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_hierarchy_probes.py -rA` runs on the local KiCad 10.0.6
- **THEN** the five probes give `present`, `absent`, `equal`, `equal` and `absent`

#### Scenario: Probes on 9.0.9
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and `FENOLITE_REQUIRE=kicad`
- **WHEN** the same tests run in the `kicad-9` job
- **THEN** they give the same outcomes, and the 9.0.9 probe file holds them

### Requirement: Hierarchical schematics pass the oracles
`tests/kicad/schematic/test_hierarchy_oracle.py` (marker `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that projects built with module sheets and satellites are accepted as c0061's flat ones are, for the lens acceptance design of c0069, for the nested design of `kicad-schematic`, "Two modules, one nested", and for the designs of `tests/_gendesigns.py::designs(seed=20261005, count=25, modules=True)`, each built for the running major and judged on copies.
- **ERC.** For the nested design, which marks every pin it leaves open, `sch erc --format json --severity-all` MUST report no violation in any sheet. The acceptance design and the generated designs leave pins open and labels alone, which ERC reports whatever the sheets look like; for them no violation type MUST be counted more often than for the same design built with `--schematic-layout grid`, the form `Generated schematics pass ERC and parity` proved: the sheets and the wires add no finding. (Equal counts are not asked: 9.0.9 reports one open pin of one generated design on the flat sheet and not on the readable sheets, while both exports give that pin the same `unconnected-(…)` net.) Only counts per type are compared, never the items, which KiCad names differently from run to run.
- **Parity.** `pcb drc --schematic-parity --format json --severity-all` MUST give an empty `schematic_parity` list.
- **Netlist.** `netlist.differences(sch_netlist.own_netlist(<root>, project=<name>, children=<children>), netlist.read_netlist(<kicad-cli's export>))` MUST be empty, so every child sheet was reached.
- **Paths** (`H-K-SCH-HIER-PATH`). For every component of the export, the `path` of its footprint on the built board MUST be its `sheetpath` `tstamps` joined with one of its own `tstamps`: a part of several units lists the uuid of each unit's symbol, and Fenolite writes that of the lowest unit.
- **Controls.** The `Sheetfile` of one child edited to a missing file MUST make `netlist.differences` non-empty, while ERC reports nothing about the sheet: at most `isolated_pin_label`, `global_label_dangling` or `pin_not_connected` for the pins that lost their net's other pins. One snap wire removed MUST give `pin_not_connected` or a changed net.
- Probes `sch-hier-oracle-acceptance` and `sch-hier-oracle-generated` MUST record `equal` on both majors, and the built folders MUST be unchanged by every tool run.

#### Scenario: Acceptance design on both majors
- **WHEN** `uv run pytest tests/kicad/schematic/test_hierarchy_oracle.py -k acceptance -rA` runs on 9.0.9 and on 10.0.6
- **THEN** ERC reports no violation type more often than for the flat form, parity is empty, the netlists are equal, every footprint path is a joined `tstamps`, and both controls give their finding

#### Scenario: Generated designs
- **WHEN** `uv run pytest tests/kicad/schematic/test_hierarchy_oracle.py -k generated -rA` runs on each major
- **THEN** all 25 designs build, with at least ten child sheets and five satellites among them, and every check holds
