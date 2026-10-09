## Outcome in one paragraph

**Resolve an opaque numbered reference to the stored name.** `_Writer.source_table`, which `write_board` hands to `NetForms` as the map from a source number to a net name, gives `stored_net_name(net)`, the spelling that the target-9 table numbers (`NetForms.numbers`) and that every modelled reference writes. One line of `pcb.py` changes; `_pcbwrite` does not.

## Context

- **The refusal (reproduced 2026-10-09 on `origin/dev` 833eefa).** `read_board` on the cached `kicad-demo-10-0-6-pcb-13` (`RoyalBlue54L-Feather.kicad_pcb`, header `20241229`, 3 549 654 bytes) and `write_board(design, target=9)` raise `LossyWriteError` with `droppable = False` and four `kicad.board.opaque-net-ref` errors: `/kicad_pcb/zone[179]/net[0]` and `zone[181]` "`(net 41)` names 'Net-(U1-P1.00/XL1)', which is not a net of the design", `zone[180]` and `zone[192]` the same for `(net 39)` and `Net-(U1-P1.01/XL2)`. `write_board(design, target=10)` succeeds.
- **The construct.** The four zones are teardrops (`(name "$teardrop_padvia$")`, `(attr (teardrop (type padvia)))`), which the reader keeps as opaque root slots. Each holds `(net 41)` (or 39) and `(net_name "Net-(U1-P1.00{slash}XL1)")`; the table row is `(net 41 "Net-(U1-P1.00{slash}XL1)")`, and the pads of `U1` hold `(net 41 "Net-(U1-P1.00{slash}XL1)")` with `(pinfunction "P1.00/XL1")`. KiCad stores the slash of the pin name `P1.00/XL1` as `{slash}` in the net name (`H-K-SCH-UNCONNECTED`, `docs/formats/kicad/schematic.md`).
- **Not a KiCad 10 construct.** Nothing here is classed as too new: the gate (`check_emittable`) reports nothing for target 9, and the errors come from `convert_nets`, before the gate.
- **The root cause.** `read_board` names such a net `Net-(U1-P1.00/XL1)` and keeps the stored spelling in the net's `kicad` bag (`stored`, c0061). `write_board` builds `NetForms.of(target, writer.source_table(), stored)`, where `stored` is the list of `stored_net_name(net)` (so `numbers` is keyed by `Net-(U1-P1.00{slash}XL1)`), but `source_table()` maps 41 to `net.name`, the model name. `NetForms.write` looks the model name up in `numbers`, finds nothing, and `convert_nets` reports the reference as naming no net of the design. Modelled references are not affected: they go through `_Nets.names`, which is built from `stored_net_name`.
- **Target 10 is wrong too, silently.** The same lookup writes `(net "Net-(U1-P1.00/XL1)")` in the four teardrops, while the pads they belong to write `(net "Net-(U1-P1.00{slash}XL1)")`. `test_demos_converted_to_10` did not see it: it compares the re-read model with opaque fragment texts left out, and skips the digest of a fragment that holds a `net` node.

## Decisions

1. **Fix the map, not the lookup.** `source_table` gives `stored_net_name(net)`. `NetForms.resolve` then returns the stored spelling, which `numbers` holds for target 9 and which is the right text for target 10; `_set_net_name` writes the stored spelling as the teardrop's `net_name`, as the source had it. Normalising names inside `NetForms` instead would put a second spelling rule next to `stored_net_name`.
2. **A named opaque reference stays as written.** `(net "<name>")` in opaque content is a target-10 form whose name is already the stored spelling; it is unchanged by this change.
3. **The refusal of an unknown number stays.** A number absent from the source table, or a stored name that is not a net of the design (a net removed from the circuit), is still `opaque-net-ref`.

## Census of the corpus (2026-10-09)

`write_board` for the board's own major and for 10 over every `.kicad_pcb` row of `tests/corpus/manifest.toml` (27 rows), before the fix (`source_table` as on 833eefa) and after it:
- 23 boards are read: 21 of major 9 (written for 9 and 10) and 2 of major 10 (written for 10). The three third-party rows are below the read floor, and `kicad-demo-9-0-9-1-pcb-04` (the 9.0.9.1 copy of RoyalBlue54L-Feather) is refused by the parser as its manifest row says ("content after the root list"), a known defect of the published file that this change does not touch.
- Before the fix one write is refused: `kicad-demo-10-0-6-pcb-13` for target 9 (the four errors above). After it, none.
- The SHA-256 of every other written text (42 of the 44 writes) is the same before and after the fix; the two texts of `kicad-demo-10-0-6-pcb-13` change (target 10: the four teardrops now name their nets with `{slash}`). No other cached board holds the defect.

## Tests

- `tests/unit/backends/kicad/test_pcb_write_nets.py`: the skeleton board with net 2 stored as `Net-(U1-P1{slash}XL1)` and a teardrop on it, written for both targets (the new scenario of "Net form per target").
- `tests/corpus/test_board_write_own.py` (`needs_corpus`, no `kicad-cli`): every readable non-heavy demo board of major 9 is written for target 9 without an error, and the re-read model equals the source's apart from net numbers and opaque fragment texts.
- `tests/kicad/board/test_written_own_target.py` (`needs_kicad`, `needs_corpus`): the RoyalBlue board written for target 9 loads on the running `kicad-cli` (9.0.9 is the proof; 10.0.6 reads it too), and its DRC report equals the source's as RT2 judges a re-dump (`checks.rt2.compare_runs`, three runs per side): KiCad does not repeat its own report on this board (54 to 84 of about 1 100 keys differ between runs of one file, all clearances), so a key whose count differs between the runs of one side is left out, and every other key must be equal.

## Released output

`write_board` writes the boards it refused; no other written file changes.

## Size (design-days)

| group | dd |
|---|---|
| fix, tests, pages | 0.25 |

Total: 0.25. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `kicad-file-backend`: MODIFIED "Net form per target", added by c0017 and changed by later archived changes; c0158–c0162 do not modify it, so this change can be archived at any time.
