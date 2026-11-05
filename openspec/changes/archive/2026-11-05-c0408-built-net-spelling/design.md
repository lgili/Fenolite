# c0408 design

## Context

The build writes a board beside a schematic, and KiCad's `pcb drc --schematic-parity` compares the board's
pad nets with the netlist KiCad derives from that schematic by stored name (`H-K-SCH-SLASH`). On the public
flat_hierarchy demo the build disagrees with its own sheets in 67 pads (c0384 finding 1.4). Two rules of
the board side are wrong; the sheets are right.

## (a) A pin name equal to the pin number

KiCad's default net name of a pin carries the pin name only when it is not empty and differs from the pin
number (S-1490, `eeschema/sch_pin.cpp` at 9.0.9.1 and 10.0.6, read for facts only; probe
`sch-unconnected-samename` = `absent` on both majors). `netnames.unconnected_name` now treats
`pin_name == pad_number` as no name, so the name is `unconnected-(<ref>-Pad<number>)` without a unit letter.
The one function serves the generator's `pad_nets`, the drawn lowering, the own netlist and the test
helpers, so they follow together; the generator's files are not edited.

The number compared is the pad number the caller passes, which is the symbol pin number of every sheet
Fenolite writes (one embedded pin per pad). For stacked pins `open_name` passes the lowest pad number
(`H-K-SCH-STACKED-OPEN`), so the name of the pin of that number is compared with it: INFERRED from the two
measured rules, no probe combines them.

## (b) Sheet-path nets of a drawn build

`pcb.stored_net_name` writes a created net with `stored_name(name)`, every `/` as `{slash}`. That is KiCad's
spelling for a slash of a label text, not for the path of a sheet: KiCad names a net named only by local or
hierarchical labels `/` plus the sheet names, each followed by `/`, plus the text (`H-K-DRAWN-NAMES`), and
writes the path's slashes raw (the reader's rule, `/cpu/A{slash}B`). A model name like
`/pic_programmer/VPP_ON` cannot say which slashes are which, so the board side needs the drawing.

The drawn build already resolves the sheets it writes (`drawn_netlist_issues`, through
`drawn.resolve_sheets`). The resolver names a label-named net `<prefix><text>`, the prefix from the sheet
instance names, with model-spelled texts. `sheet_spellings(drawn, netlist, circuit)` takes each drawn net
whose pins are exactly a circuit net's pins and whose name is the circuit net's name, splits the name into
one known sheet prefix and one of its label texts, and gives `prefix + stored_name(text)` when that differs
from `stored_name(name)`. It leaves a net alone when:

- its name is one of its own label texts (a global label or a power symbol names it);
- no split or more than one split exists (a label text holding a `/` that also ends another label);
- a sheet name holds `/` or `{` (its prefix is not offered: KiCad's escaping of sheet names is not measured);
- its `kicad` bag already keeps a `stored` pair (a read spelling wins).

`lower_for_schematic` keeps each spelling as the `stored` pair of the net's `kicad` bag, the pair the board
reader already keeps and `pcb.stored_net_name` already writes first, so the board, the project's net-class
patterns and every other caller of `stored_net_name` agree without a change of the writer's rule. Applying
`lower_for_schematic` twice gives the result of applying it once. The schematic generator path
(`schgen.generate_schematic`) writes global labels only, so `stored_name` stays right there and nothing
changes on it.

Alternatives not taken: a name-shape rule in `pcb.py` (a leading `/` means a sheet path) would respell a
created net whose global label text starts with `/`, which KiCad stores `{slash}...`; asking the generator
to expose the names would edit files that c0406 owns.

## Proof

`tests/kicad/schematic/test_drawn_sheet_net_names.py` builds the authored `hier` fixture with its child-sheet
nets renamed to their sheet-path names (`/child/IN` by a hierarchical label, `/child/FB` by a local one) and a
root part whose pins are named `1` and `2`, left open (the mini library copied into the test's folder with
those names). KiCad's parity test of the board against the written sheets reports nothing, and a control
board with `/child/FB` respelled `{slash}child{slash}FB` gives `net_conflict`, so the run reads names.

## Goldens and snapshots that change

None. No golden, snapshot or recorded digest in the repository holds a name that either fix changes: a
search of `tests/`, `examples/`, `docs/` and `src/` for `-<n>-Pad<n>` names finds only hand-written test
names, no authored symbol library has a pin named like its number, and no fixture's code names a net by its
sheet path. Measured 2026-11-05 on `origin/cac/lote-21` b845eb00 with this change: the unit suite gives
22568 passed and 18 failed. One failure is the DCO check of the temporary unsigned commits, gone with the
signed commit. The other 17 fail identically on b845eb00 without this change (c0406's wired default and the
stale matrix page, being fixed on cac/lote-22); their actual digests are the same with and without c0408.

Builds that will change, none of them recorded in the repository: an imported project whose vendored
symbols (`importer.vendor.symbol_for`, one pin per pad named by its number) leave a pin open, which now gets
KiCad's `unconnected-(<ref>-Pad<n>)`, and a drawn build whose code names a net by its sheet path, which now
gets KiCad's raw-slash spelling.

## Risks

A drawn build whose code names equal the drawn sheet-path names changes its board text: a later same-version
rebuild of a board written before c0408 reads the `{slash}` spelling back as the same model name
(`model_name`), so layout preservation still matches it, and the next write stores KiCad's spelling.
