## MODIFIED Requirements

### Requirement: Per-component pin-to-pad mapping
`fenolite.dsl.Part(..., pad_map=...)` SHALL take, for each symbol pin it lists, one pad number (a non-empty string, the spelling before this requirement allowed several) or a tuple or list of pad numbers for a pin that is bonded to several pads. The DSL build SHALL assign each symbol pin's net to every physical footprint pad that `Component.pin_pad_map` names for it, using identity mapping for pins not listed. Circuit net members and no-connects SHALL remain keyed by symbol pin number. A mapping with a missing source pin, missing pad target, or duplicate physical target MUST report `build.pin-pad-map-invalid` as an error and write no output. This issue SHALL join the closed build issue set of `design-dsl`, "Build issue codes".
- **Spelling.** `pad_map={"3": "5"}` MUST mean what it meant. `pad_map={"3": ("3", "EP")}` MUST give pin `3` the pads `3` and `EP`, in that order. A sequence of one pad MUST equal that pad written as a string. An empty sequence, an empty pad number, a pad listed twice for one pin and a pad listed for two pins MUST raise `DslError` naming the part.
- **`Part.pad_map`** MUST hold the mapping sorted by pin, each value a string for one pad and a tuple for several, so a script of one pad per pin reads back what it wrote.
- **Model.** `to_model` MUST give `pin_pad_map` the pairs of the pins in sorted pin order, the pads of one pin in the order written. For a part whose pins have one pad each these MUST be the pairs, in the order, that `to_model` gave before.
- **Pads.** Every pad of a pin on a net MUST carry that net, and every pad of a pin on no net or under a no-connect mark MUST carry none. `build.pad-without-pin` MUST count a pad as mapped when a pin names it, and `build.pin-pad-map-invalid` MUST name each pad of a pin that the footprint lacks.
- The build MUST read the map through `Component.pads_of` and `Component.pin_pads` only.

#### Scenario: Remap a connected symbol pin
- **GIVEN** component `U1` maps symbol pin `1` to physical pad `2` and pin `1` is connected to net `N`
- **WHEN** the build resolves its footprint pads
- **THEN** pad `2` carries net `N`, while `Net.members` keeps pin number `1`

#### Scenario: Refuse an invalid pin-to-pad map
- **GIVEN** a map names a missing source pin or target pad
- **WHEN** the component is built
- **THEN** `build.pin-pad-map-invalid` is an error and the build writes no files

#### Scenario: Two pads for one pin
- **GIVEN** a part `U1` with `pad_map={"3": ("3", "EP")}` whose footprint holds the pads `1`, `2`, `3` and `EP`, and pin `3` on the net `GND`
- **WHEN** `uv run pytest tests/unit/lens/test_build_pins.py -k several` builds it
- **THEN** the pads `3` and `EP` carry `GND`, `Net.members` holds pin `3` once, `component.pin_pad_map == (("3", "3"), ("3", "EP"))`, and the build reports no `build.pad-without-pin` for `EP`

#### Scenario: Spelling refused
- **WHEN** `uv run pytest tests/unit/dsl/test_footprint.py -k pad_map` creates parts with `pad_map={"3": ()}`, `{"3": ("4", "4")}`, `{"3": ("4", "")}` and `{"1": "4", "3": ("3", "4")}`
- **THEN** each raises `DslError` naming the part, and `Part("R1", ..., pad_map={"2": "1", "1": ("2",)}).pad_map` equals `{"1": "2", "2": "1"}`

#### Scenario: One pad per pin gives the pairs it gave
- **GIVEN** the units design of `tests/_schbuild.py`, whose `D1` has `pad_map={"1": "2", "2": "1"}`
- **WHEN** `to_model` runs
- **THEN** `pin_pad_map` of `D1` is `(("1", "2"), ("2", "1"))`

#### Scenario: Missing pad among several
- **GIVEN** a part whose `pad_map` gives pin `3` the pads `3` and `TAB`, and whose footprint has no pad `TAB`
- **WHEN** it is built
- **THEN** `build.pin-pad-map-invalid` is an error that names `TAB`, and the build writes no files
