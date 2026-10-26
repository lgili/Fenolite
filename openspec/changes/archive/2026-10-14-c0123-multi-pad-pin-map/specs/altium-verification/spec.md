## ADDED Requirements

### Requirement: Pin maps in the Altium round trips
The scope of RT-A2 (`backends/altium/roundtrip.RT_A2_SCOPE`, judged by `checks.rta2.rta2_stage`) SHALL compare the pin map of a component: the field `pin_pad_map` of both sides in the form of `model.circuit.normal_pin_pad_map` (the pairs sorted by pin, the pads of one pin in map order, without a pin whose one pad is the pad of its own number). Two maps that give every pin the same pads are equal, whatever the order of their pairs across pins and whether a pin of one pad of its own number is listed or not. RT-A3 compares under the same scope and the same form.
- The table of fields that the scope leaves out (`docs/altium.md`, "Round trips") MUST lose its row for `component.pin_pad_map`, and the written scope MUST list the map as written.
- What the model cannot hold of a map is not written: `roundtrip.unwritten_pin_maps(design) -> int` MUST give the number of `pin_pads` records in the `altium` bags of the components of `design`, and the written scope of `docs/altium.md` MUST name the bag key as not written.
- The write of a model (`lower.from_design`, change c0090) MUST account for a component whose bag holds such a record under the kind `pin-pads`, and under the kind `pin-pad-map` only for a component with a map that has no footprint model in the generated schematic; neither is a kind that refuses a write. RT-A3 reports both among what its write left out, and compares no map of a component counted under `pin-pad-map`.
- `docs/evidence/altium-roundtrip.md` MUST give the row of `altium-set:02` of its table "Project sets" as measured after this change, with the date and the row before it, and MUST NOT list the further pads of a pin as a cause of what remains unless the measure still shows them.

#### Scenario: Map inside RT-A2
- **GIVEN** the built Altium project of the blink whose `R1` has `pad_map={"1": ("1", "5"), "2": ("7", "6")}`
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pin_map.py -k rta2` runs `fenolite check --stages roundtrip.rta2` on it, and again after `DESIMP1` of one record of the written sheet is removed and its count lowered
- **THEN** the first run reports no difference, and the second reports one `check.rta2-failed` whose `where` ends in `pin_pad_map`

#### Scenario: Records the model cannot hold are counted
- **GIVEN** an imported design one of whose components holds a map, a footprint link and the bag record `pin_pads` `3=`, and another a map and no footprint link
- **WHEN** `uv run pytest tests/unit/backends/altium/test_lower.py -k counted` lowers it
- **THEN** `unwritten_pin_maps` returns 1, the first component is counted under `pin-pads` and not under `pin-pad-map`, and the second under `pin-pad-map`

#### Scenario: Page follows the measure
- **WHEN** `uv run pytest tests/unit/test_altium_roundtrip_page.py tests/unit/test_altium_verification_docs.py` runs after the page is updated
- **THEN** it passes, and the row of `altium-set:02` holds the counts that `tests/corpus/test_altium_channels.py -k pin_map` asserts for that set (698 common, 7, 27 and 2)
