## Why

While c0162 was written (2026-10-09, its design, "Found on the way") the public demo board `RoyalBlue54L-Feather` (corpus row `kicad-demo-10-0-6-pcb-13`, format `20241229`, a KiCad 9 board) was refused by `write_board` even for its own target 9: four `kicad.board.opaque-net-ref` errors, at `/kicad_pcb/zone[179]/net[0]`, `zone[180]`, `zone[181]` and `zone[192]`, each "`(net 41)` names 'Net-(U1-P1.00/XL1)', which is not a net of the design" (or `(net 39)` and `Net-(U1-P1.01/XL2)`). The four zones are teardrops, kept opaque by the reader. Their nets are stored in the file's table with `{slash}` (`(net 41 "Net-(U1-P1.00{slash}XL1)")`), as KiCad stores the slash of a pin name.

The cause is in the writer: `_Writer.source_table` maps each number of the source table to the net's **model** name, in which `read_board` has turned `{slash}` into `/` (c0061, "Net names in KiCad's stored form"), while the target-9 numbering and every modelled reference use the **stored** name (`pcb.stored_net_name`). A numbered reference inside opaque content to a net stored with `{slash}` therefore resolves to a name that target 9 cannot number, and the write is refused. For target 10 the same lookup is not refused but wrong: the teardrop is written `(net "Net-(U1-P1.00/XL1)")`, a name no pad of the board holds, so the zone leaves the net of its pad.

The maintainer decided on 2026-10-09 that this gets a correction change of its own (c0162, design, open question 4).

## Outcome in one paragraph

**An opaque net reference keeps the stored spelling of its net.** `write_board` resolves a numbered reference inside opaque content to the stored name of that net (`pcb.stored_net_name`), the name the target-9 table numbers and the target-10 references write, so `RoyalBlue54L-Feather` is written for target 9 and loads on KiCad 9.0.9 with the same DRC report as its source, and its target-10 text references the teardrops' nets by the spelling the pads use.

## What Changes

- **`backends/kicad/pcb.py`**: `_Writer.source_table` maps a number to `stored_net_name(net)` instead of `net.name`.
- **Tests**: a unit test on a board authored in the test (a teardrop zone on a net stored with `{slash}`), for both targets; a corpus test that writes every readable non-heavy major-9 demo board for target 9 (no `kicad-cli`); a KiCad 9 oracle test on the RoyalBlue board (the target-9 text loads and its DRC report equals the source's on the keys KiCad repeats).
- **Pages**: `docs/formats/kicad/board.md` (a fact row on the teardrops of the demo board and the oracle result; the writer's "Net forms" bullet).

Size: 0.25 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `kicad-file-backend`: MODIFIED "Net form per target": a numbered reference inside opaque content resolves to the stored name of its net, and a new scenario for a net stored with `{slash}`.

## Non-goals

- No change to the reader, to `netnames`, or to the refusal of a reference whose number is absent from the source table.
- No change to `rebuild_board` (same-version rebuild), which writes opaque fragments as read.
- No downgrade work: that is c0162.

## Evidence level required

- The board's form (teardrop zones reference nets stored with `{slash}` by number, with `net_name` in the stored spelling): `CORPUS-VERIFIED` (S-0058).
- The written target-9 board loads with the source's DRC report (on the keys KiCad repeats): `KICAD-VERIFIED (9.0.x, 10.0.x)`, 9.0.9 and 10.0.6 in the pinned images.

## Impact

- Changed: `src/fenolite/backends/kicad/pcb.py`, the tests above, `docs/formats/kicad/board.md`, `CHANGELOG.md`, `openspec/README.md`.
- Behaviour: a board whose opaque content references a net stored with `{slash}` is written instead of refused (target 9), and with the right net name (target 10). No other output changes.
