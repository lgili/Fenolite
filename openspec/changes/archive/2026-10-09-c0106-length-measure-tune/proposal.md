## Why

Pairs and buses of a complex board must match in length. Fenolite cannot say how long a net is: `fenolite net` (c0066) sums track and arc centre lines only. c0104 writes length and skew rules for KiCad, but an agent learns KiCad's numbers only from DRC violations, and no script can lengthen a track. The review of 2026-10-05 found both among the gaps to a complex board (milestone v0.4; `docs/roadmap.md`, "v0.4: proposals on other branches"). On `origin/dev` at `9aba2dff` both are still open: `fenolite analyze` has the kinds `current`, `clearance` and `creepage`, `backends/base.py` has no length protocol, and no meander exists. The nearest neighbour is the equivalence level 5 of c0089 (archived 2026-10-07), which compares the routed length per copper span of two designs with a length function of its own and counts no via height and no die length.

Measured on 2026-10-05 with `kicad-cli` 9.0.9 and 10.0.6, from DRC violations:

- KiCad's length of a net sums all its tracks and arcs, stubs included, plus a height per via and the die length of each pad. No other headless command prints it.
- Via heights differ per major: 10.0.6 counts the depth between the outermost layers the net joins at the via; 9.0.9 counts the via's own span when the net reaches both its ends, else nothing.
- A board file without a stack-up is measured with a default stack-up.

## What Changes

- **KiCad net lengths** (`backends/kicad/lengths.py`): each net's length as the target major counts it, read through a `LengthSource` protocol.
- **Pin-to-pin lengths and pair skew** (`analysis/length.py`): shortest paths along copper from a start pad, stubs, skew per pair; `fenolite analyze --kinds length --net GLOB [--from REF]`.
- **Check stage `length.rules`**: judges c0104's `length` and `skew` rules on these lengths, without `kicad-cli`.
- **Kernel**: `segment_length`, `arc_length`, `arc_length_to`. The two length implementations that `dev` holds (`analysis/views.py` and, since c0089, `checks/equivalence/routing.py`) call the kernel, so one function measures an arc everywhere.
- **Meanders** (`Design.meander`): a square-wave meander on one straight segment of a script track, up to a target length or another script track's length, inside a band the script gives. Can be cut.

Size: 9.5 design-days; cut order in the design.

## Prerequisites

What must be on `dev` before this change starts:

- Release `0.3.0` is cut (c0088's document pipeline and c0089 are part of it).
- c0104 (the kinds `length`, `skew`, `diff_pair_skew`, `RuleSubject.diff_pair`, `model.pairs`).
- c0101 (`Board.stackup` read and written for KiCad, `Stackup.depth`); c0100 for the six- and eight-layer rows of task 1.3 only.
- c0066 and c0068 are archived on `dev`: satisfied.

Every requirement of this change is ADDED and each name is free in the living specs of `9aba2dff`, so no delta is regenerated. c0123 (several pads per pin, on its own branch) changes which pad `--from REF` names; whichever of the two lands second checks the start-pad rule.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `board-analyses`: ADDED "Net length report", "Pin-to-pin length", "Pair skew in the length report", "Length kind in the analyze command", "Length analysis issue codes".
- `backend-protocol`: ADDED "Length facts source".
- `board-frame`: ADDED "KiCad net lengths".
- `geometry-kernel`: ADDED "Path lengths".
- `verification-loop`: ADDED "Length rules stage", "Length stage issue codes".
- `design-dsl`: ADDED "Meanders in the DSL", "Meanders in a build".
- `manual-copper`: ADDED "Meanders from intents".
- `kicad-oracle`: ADDED "Net length parity canaries", "Meanders pass the oracle".

## Non-goals

- Length, skew, pair gap and uncoupled length rule kinds: c0104.
- Delay tuning and KiCad 10 tuning profiles: profiles are c0105's; a delay measure goes nowhere, because the yardstick asks for matched length.
- Routing pairs: c0110; meanders on router copper: a follow-up of c0110.
- Rounded meander corners: nowhere, because square corners meet the length and copper checks.
- Die lengths set from a script: nowhere for now, because no yardstick part needs one.
- Lengths as Altium counts them, and length or skew rules judged on Altium documents: nowhere for now. The Altium backend is no `LengthSource` (no public source recorded here says how Altium counts a via or a pad in a net length), the Altium rule table gives c0104's `length` and skew kinds the reason `no-counterpart`, and the stage `length.rules` is not in the document pipeline of c0088 (`checks.documents.DOCUMENT_STAGES`). `fenolite analyze --kinds length` on an Altium PCB document gives the routed lengths and paths with one `analysis.input-missing` warning and the level `UNVERIFIED`.
- A meander in an Altium build: the meander is resolved as script copper through the KiCad build in memory ("Script copper in an Altium build") and written as plain tracks; nothing else is added for that target.

Limits: zones add no length and a layer change inside a through-hole pad adds none, as in KiCad; crossing items without an end inside each other are not joined in a path; on KiCad 9 a path can exceed the total; a meander does not avoid other copper (the copper guard reports a clash); the default stack-up is measured for 2 and 4 layers only.

## Evidence level required

- KiCad's counting per major (totals, via heights, default stack-up, rule semantics): `KICAD-VERIFIED (9.0.x, 10.0.x)` by parity canaries (`H-K-NETLEN-TOTAL`, `-VIA10`, `-VIA9`, `-STACKUP`, `-RULES`).
- Pin-to-pin paths: `INFERRED` (`H-G-NETLEN-PATH`).
- Meanders: `KICAD-VERIFIED (9.0.x, 10.0.x)` on benches (`H-K-NETLEN-MEANDER`).

## Impact

- New modules: `geometry/lengths.py`, `backends/kicad/lengths.py`, `backends/kicad/meander.py`, `analysis/length.py`, `checks/length.py`.
- Changed: `backends/base.py`, the KiCad backend, `analysis/views.py`, `checks/equivalence/routing.py`, `checks/stages.py`, three commands, the DSL intents, `lens/build.py`, `cli/data/explain.toml` (fifteen new codes).
- Depends on c0104 and c0101.
- No model field, schema or source id is added; the block S-0640 to S-0659 of this group is not used here.
- `check` gains a default stage, empty without length or skew rules.
