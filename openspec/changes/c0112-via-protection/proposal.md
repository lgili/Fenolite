## Why

Vias are tented, filled and capped in a pad, or left open for a probe. The review of 2026-10-05 found, among the gaps to a complex board (milestone v0.4; `docs/roadmap.md`, "v0.4: proposals on other branches"), that a script can make blind, buried and micro vias (c0068) but cannot protect any: `Via` has no field for it, the reader keeps KiCad's protection children opaque, and a created board leaves the default to KiCad. On `origin/dev` at `9aba2dff` this is still so for the model, KiCad and the DSL. On the Altium side half of it moved: the PCB reader reads the two tenting flags of a via (`ViaRecord.tented_top`, `tented_bottom`) and drops them for want of a model field, and the writer writes every via with the flags `0C 00`, not tented.

Measured on `kicad-cli` 10.0.6 and 9.0.9 (design, Context):

- 10.0.6 stores five features per via (tenting, covering and plugging per side, capping, filling), each `yes`, `no` or `none` (the board's value), and five defaults in `setup`. 9.0.9 stores tenting only and refuses the others.
- The mask plot follows tenting alone. The other four reach only 10.0.6's drill side files and IPC-2581, for vias that carry them; a board default adds none.
- 10.0.6 reads a 9.0 via child naming one side, or none, unlike 9.0.9: the unnamed side follows the board default instead of staying open.

## What Changes

- **Model.** `ViaProtection`, eight optional booleans; `Via.protection` (`None` follows the board) and `Board.via_protection`, the default (`None`: KiCad's, tented and nothing else).
- **KiCad files.** Via children and `setup` defaults read and written in each major's form, meaning taken from the file's major. Target 9 refuses a true covering, plugging, capping or filling (exit 7).
- **Script.** `protect(tenting=…, covering=…, plugging=…, capping=…, filling=…)` with `True`, `False`, `"front"`, `"back"` or `None`; `protection=` on `Design.via`, `via_step`, `Design.stitch`; `Design.via_protection(…, locked=False)`.
- **Rebuilds.** Script vias take their intent's protection every build; the default follows the zones' rule (KiCad's edit wins unless locked).
- **Reports.** `inspect` counts, for KiCad boards and Altium PCB documents; the build notes a default that no fabrication file carries.
- **Altium** (decision of the maintainer, 2026-10-07: tenting is written and imported for the Altium target). The Altium build writes each via's tenting into the two flags of its record, where the via or the board default states it; the import maps the flags to `Via.protection`. Covering, plugging, capping and filling have no recorded Altium fact: they stay in the model and are named in one `altium.not-lowered` info. A design without protection builds the same Altium bytes as before.

Size: 4.75 design-days; cut order in the design.

## Prerequisites

What must be on `dev` before this change starts:

- Release `0.3.0` is cut, with c0085 archived (the via record for blind and buried vias and `result.pcb`), and c0128, c0124 and c0132, which hold deltas of "Via records" and "Tracks, arcs and vias"; this change refines both by ADDED requirements and modifies neither.
- Of the v0.4 proposals: c0100, c0101 and c0103 land first, in this order, and this change regenerates its three MODIFIED requirements of `kicad-file-backend` ("Created board header", "Modelled board content", "Projected fields on write") from the text they leave.
- The board model and `schemas/fenolite.model.v0/board.json` are also touched by c0096 and c0099 (their branches), c0121 and c0126 (open on `dev`) and c0108, c0114 and c0118 (v0.4): all additive; whichever lands later regenerates the schema.
- c0068 and c0069 are archived on `dev`: satisfied.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Via protection in the board model".
- `kicad-file-backend`: ADDED "Via protection on boards", "Via protection defaults on boards"; MODIFIED "Modelled board content", "Created board header", "Projected fields on write".
- `manual-copper`: ADDED "Via protection of script copper".
- `design-dsl`: ADDED "Via protection in the DSL", "Via protection defaults in the DSL".
- `layout-lens`: ADDED "Via protection defaults across rebuilds".
- `kicad-oracle`: ADDED "Via protection passes the oracle".
- `cli-contract`: ADDED "Via protection in inspect".
- `altium-build`: ADDED "Via protection in an Altium build".
- `altium-pcb-writer`: ADDED "Via tenting flags".
- `altium-import`: ADDED "Via tenting of imported vias".

## Non-goals

- Back-drill: nowhere for now; no change and no line of `docs/roadmap.md` owns it. Pad tenting and pad mask margins: nowhere for now, for the same reason; a pad's `tenting` child stays opaque.
- Export kinds for the drill side files and IPC-2581: c0116. Fabrication notes: c0117.
- Protection of fan-out and escape vias: c0107, c0110, which create them.
- IPC-4761 type names: nowhere, because the standard is not a public source and KiCad stores features.
- A check that a via in a pad is filled: nowhere, because Fenolite ships no fabricator rule (plan D6).
- Covering, plugging, capping and filling in Altium documents, written or read: nowhere for now, because `docs/formats/altium/` records no fact about them. A board default in an Altium document: nowhere, because every Altium via carries its own flags.
- Tenting in Altium footprints (`PcbLib`) and of pads: nowhere for now.

Limits: target 9 holds tenting only; on 10.0.6 a default of the four other features reaches no fabrication file, and no feature reaches the Excellon drill file; KiCad 10's own upgrade of a 9.0 board changes the mask of vias naming one side or none; KiCad 9's written form for "neither side" is inferred; the Altium tenting flags are `INFERRED`, and a side that neither the via nor the default states is tented by KiCad and left clear in the Altium document.

## Evidence level required

- `H-K-VIAPROT-FORMS`, `-UPGRADE`, `-OUTPUTS`: `KICAD-VERIFIED (10.0.x)`; `-MASK`: `KICAD-VERIFIED (9.0.x, 10.0.x)`; `-NINE`: `KICAD-VERIFIED (9.0.x)`, its written form `INFERRED`. Corpus forms: `CORPUS-VERIFIED` (RT1).
- Model, script, merge, `inspect`, Altium info: mechanical.
- Altium tenting flags, written and imported: `INFERRED` (`H-A-PCB-CU-VIATENT`, beside the existing fact rows of the two flags), until an author report in Altium Designer settles it; then `ALTIUM-VERIFIED(author-report)`.

## Impact

- New: `backends/kicad/via_protection.py`, `tests/kicad/vias/`.
- Changed: the model, `pcb.py`, `copper.py`, the DSL, the build, the Altium build, writer and import adapter (`backends/altium/pcbrecords.py`, `pcbdoc.py`, `lower.py`, `adapter/copper.py`), `inspect`, `cli/data/explain.toml` (four new codes), the board schema, four token rows, docs.
- Model documents: `board.json` gains the keys `protection` (vias) and `via_protection` (board); 0.2.x and 0.3.0 cannot read a document that carries them. The model of an imported Altium board gains `protection` on every via.
- No source id is added; the block S-0640 to S-0659 of this group is not used here.
- A KiCad 9 board with via tenting, rebuilt for target 10, keeps 9.0.9's mask.
