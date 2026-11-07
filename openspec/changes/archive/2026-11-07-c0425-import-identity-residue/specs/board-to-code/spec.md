## ADDED Requirements

### Requirement: A pad on no net beside a pad of its number on a net
The DSL joins a pin to every pad of its number, so the emitted code would put on the net a pad that the source leaves on no net beside a pad of its number on a net. The import SHALL count each such pad number as the unexpressed kind `pad-net-conflict` (example `<ref>.<number>`), as it counts a pad number on two nets; that kind explains the self-check's level 2 difference at the pad. An `unconnected-(…)` net beside the open pad counts as no net.
- The vendored library MUST hold one footprint and one symbol per name: a footprint variant takes a name no footprint of the board holds (design-conversion, "Library made from a board").

#### Scenario: Open pad beside a netted pad
- **GIVEN** the authored two-sheet board with a second pad `1` on no net added to `J1`, whose pad `1` is on `VIN`
- **WHEN** `uv run pytest tests/unit/importer/test_open_pad_beside_netted.py` imports it
- **THEN** without `--allow-lossy` the exit code is 7 naming `pad-net-conflict`; with it the plan is made, `import.item-unexpressed` names `pad-net-conflict` and `J1.1`, and no `import.unequal` is reported; and the board compares equal to itself at level 2

#### Scenario: Variant name the board already holds
- **GIVEN** the authored two-sheet board with `D201`'s pad 2 moved and `J1` on a footprint named `Mini_LED_THT_3mm_2`
- **WHEN** `uv run pytest tests/unit/importer/test_variant_name_collision.py` imports it with `--confirm`
- **THEN** the exit code is 0, the vendored footprints are `Mini_LED_THT_3mm`, `Mini_LED_THT_3mm_2`, `Mini_LED_THT_3mm_3` and `Mini_R_0603`, and no symbol name repeats
