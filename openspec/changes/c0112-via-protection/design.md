## Context

The review of 2026-10-05 named the gaps to a complex board; since 2026-10-07 the group is milestone v0.4 (`docs/roadmap.md`, "Milestone names" and "v0.4: proposals on other branches", where the row of c0112 holds its id and slug only). It found that via protection is in no change and on no roadmap line: blind, buried and micro vias come from the script since c0068, but tenting, covering, plugging, capping and filling exist only in the token inventory and in the opaque columns of the board reader.

**What exists** on `origin/dev` at `9aba2dff` (2026-10-07; `model/board.py`'s `Via` and the KiCad code named below did not change since the measurements of 2026-10-05):

- `model/board.py`: `Via(position, diameter, drill, layers, net_id, via_type)`; `ViaType` holds the four kinds. No field says how a via is protected, and `Board` holds no default.
- `backends/kicad/pcb.py`: `VIA_FIELDS` maps `at`, `size`, `drill`, `layers`, `net`, `uuid` and the leading type atom; every other child of a via is an opaque slot (`docs/formats/kicad/board.md` lists `locked`, `free`, `remove_unused_layers`, `tenting`, `padstack`, `teardrops`). A created board writes `(setup (pad_to_mask_clearance 0))`; the `setup` of a read board is an opaque root slot.
- Token inventory: `tenting` since 9 (20240609, the note "9.0 writes (tenting front back) in setup, on vias and on pads"); `tenting/front`, `tenting/back`, `covering`, `plugging`, `capping`, `filling` since 10 (20250228). No row for the `front` and `back` children of `covering` and `plugging`.
- c0068 (archived 2026-10-05): `via_step(…, kind=)`, `Design.via(…, kind=, layers=)`, through stitch vias. `resolve_copper` creates script vias, and `merge_copper` regenerates them at every build, comparing points, width, diameter, drill, layers, via type and net (`copper._fields`). Children of an existing script via are opaque slots of the item it drops, so a protection set in KiCad on a script via is lost at the next build without an issue.
- `exports.plan.KINDS`: `drill` runs `pcb export drill --format excellon`; `gerbers` plots `F.Mask` and `B.Mask`. `exports.preset.FORBIDDEN` keeps `--generate-tenting` out of user presets. `fenolite inspect` reports counts per board, and also reads Altium documents (kind `altium_pcbdoc` among them); c0101 adds `result.stackup`.
- The Altium side (c0038, c0085 and the readers of v0.3, on `dev`):
  - `backends/altium/read/pcbprims.py` reads `ViaRecord.tented_top` and `tented_bottom` from bits 5 and 6 of the first flags byte of the via's prefix (`flags1 & 0x20`, `flags1 & 0x40`), both labelled `INFERRED` (`docs/formats/altium/pcb-read.md`, rows of `ViaRecord`; `H-A-RD-PCB-LENGTHS`). The import adapter (`adapter/copper.py`) builds `Via(position, diameter, drill, layers, net_id, via_type)` and drops the two values.
  - `pcbrecords.via_record` writes the prefix with the flags `0C 00`. `docs/formats/altium/pcb-copper.md` holds the fact row "Flags of a via: `0x0C` unlocked and untented; bit 5 tents the top, bit 6 the bottom" (S-0160, S-0172, S-0174, S-0175, S-0176; `INFERRED`; `H-A-PCB-CU-VIA`), lists "tented vias" among what is not written, and says "flags `0C 00` (not tented)" under "Vias". `H-A-PCB-CU-VIA` is `INFERRED` with its author report pending.
  - The solder-mask expansion of a via is written as 4 mil at offsets 54 and 242; no recorded fact ties it to the flags.
  - c0085 (implemented, not archived): `result.pcb` of an Altium build counts every model item as written or not lowered. RT-A2 compares a via by `position`, `diameter`, `drill` and `net_id` (`backends/altium/roundtrip.py`).
  - Open changes on `dev` that hold deltas near this one: c0085 and c0128 MODIFY "Via records" (`altium-pcb-writer`); c0124 and c0132 MODIFY "Tracks, arcs and vias" (`altium-import`). None adds a model field to `Via`.

**Measured on 2026-10-05.** Bench: a created two-layer board written by `write_board` for target 9 or 10, a row of vias (0.8 mm, drill 0.4 mm) on one net joined by an `F.Cu` track, one via per protection form; protection children inserted after `layers` and `setup` children after `pad_to_mask_clearance` by tree edit. Sets: 6 setups × 19 vias in the 10.0 form on target-10 boards; 5 setups × 6 vias in the 9.0 form on target-9 boards; the 10.0 forms on one target-9 board; 4 setups × 6 vias in the 9.0 form on target-10 boards. Per board, on copies:

```
kicad-cli pcb drc --format json --severity-all -o drc.json B.kicad_pcb
kicad-cli pcb export gerbers -l F.Mask,B.Mask,F.Cu -o g/ B.kicad_pcb
kicad-cli pcb export drill --format excellon -o dx/ B.kicad_pcb
kicad-cli pcb export drill --format gerber -o dg/ B.kicad_pcb
kicad-cli pcb export drill --format gerber --generate-tenting -o dt/ B.kicad_pcb
kicad-cli pcb export ipc2581 -o B.xml B.kicad_pcb
kicad-cli pcb upgrade --force U.kicad_pcb          # U: a copy of B
```

10.0.6 is the macOS application. 9.0.9 ran the target-9 boards in one container: `docker run --rm --platform linux/amd64 -v <bench>:/p -w /p -e HOME=/tmp kicad/kicad:9.0.9@sha256:e638b79b… sh run.sh kicad-cli work9 boards/t9 boards/t9x`. A mask opening is a flash (`D03`) within 0.45 mm of the via centre on the mask plot. The corpus census read the cached boards with Fenolite's parser. Nothing is committed; each fact becomes a recorded probe or test of this change. The measurements were made on the branch `review-roadmap-complex-board` and were not repeated on `dev`. The bench sizes (0.8 mm vias, 0.4 mm drill) are authored round values.

1. *Corpus* (S-0058, counts only). 24 readable boards. `setup` holds `(tenting front back)` on 19 (9.0 format), the five 10.0 children on 2 (tented on both sides, the others `no`), nothing on 3 (third-party boards of older formats). Of 3 498 vias, 452 hold protection children: 444 vias of one board in the 10.0 development format 20250513 hold all five children with `none` only; 6 vias of one 20260206 board hold an explicit `no` for covering, plugging, capping and filling and no `tenting`; 2 vias of one 9.0 board hold `(tenting front back)`. No cached library footprint holds a `tenting` child.
2. *10.0.6 forms* (re-saves). A via holds `(tenting (front V) (back V))`, `(capping V)`, `(covering (front V) (back V))`, `(plugging (front V) (back V))` and `(filling V)`, in that order after `layers` (and after an opaque `free`), V being `yes`, `no` or `none`. A re-save writes a child only when one of its values is not `none`, a two-sided child always with both sides (`(tenting (front no))` comes back as `(tenting (front no) (back none))`), and drops all-`none` children. `setup` always gets all five, `(tenting (front yes|no) (back yes|no))`, `(covering …)`, `(plugging …)`, `(capping yes|no)`, `(filling yes|no)`, in that order after `allow_soldermask_bridges_in_footprints`: absent children come back as tented on both sides and `no` for the rest, and a lone `(tenting (front no) (back no))` keeps the rest `no`. A 9.0 board re-saved by 10.0.6 gets `(capping no) (covering (front no) (back no)) (plugging (front no) (back no)) (filling no)` on every via.
3. *Mask plots.* With the 10.0 forms on 10.0.6 (F/B: `F.Mask`/`B.Mask`):

   | via children | default tented (no `setup` child, or `yes`/`yes`) | default open (`no`/`no`) |
   |---|---|---|
   | no child | tented/tented | open/open |
   | `(tenting (front no) (back no))` | open/open | open/open |
   | `(tenting (front yes) (back yes))` | tented/tented | tented/tented |
   | `(tenting (front no) (back yes))` | open/tented | open/tented |
   | `(tenting (front no))` | open/tented | open/open |
   | covering, plugging (both sides), capping or filling `yes`, alone | tented/tented | open/open |
   | `(tenting (front no) (back no))` with covering, plugging or filling `yes` | open/open | open/open |

   A default `(tenting (front yes) (back no))` gives a via without children tented/open. With the 9.0 via forms, under a `setup` of `(tenting front back)` or none:

   | via `tenting` child | 9.0.9 | 10.0.6, 9.0 file | 10.0.6, 10.0 file |
   |---|---|---|---|
   | no child | tented/tented | tented/tented | tented/tented |
   | `front back` | tented/tented | tented/tented | tented/tented |
   | `front` | tented/open | tented/tented | tented/tented |
   | `back` | open/tented | tented/tented | tented/tented |
   | `none`, or no atom | open/open | tented/tented | tented/tented |

   Under a `setup` of `(tenting none)` or `(tenting)`, a via without a child is open on both sides and the other rows are those of the 9.0.9 column, on both majors. The `setup` forms mean the same on both majors and in both file formats: no child and `front back` tent both sides, `front` the front only, `none` and no atom neither. 10.0.6 re-saves the 9.0 via `front` as `(tenting (front yes) (back none))`, `back` as `(front none) (back yes)`, and drops `none` and the empty child.
4. *9.0.9.* Every 9.0 form loads: `pcb drc`, `export gerbers`, `drill` and `ipc2581` exit 0. A 9.0 board holding the 10.0 forms gives exit 3, "Failed to load board", for every command. `pcb upgrade` does not exist ("Failed to parse 'upgrade'"), nor `--generate-tenting` ("Unknown argument"), so what KiCad 9 writes cannot be observed headless (S-0037).
5. *Outputs on 10.0.6.* `--format gerber` writes, beside the PTH drill file, one file per feature and side that some via holds, and `--generate-tenting` adds tenting:

   | feature | drill side file | file function | IPC-2581 layer function |
   |---|---|---|---|
   | tenting | `-tenting-front.gbr`, `-tenting-back.gbr` (with `--generate-tenting`) | `Other,Tenting-Front`, `-Back` | `COATINGNONCOND`, one per side |
   | covering | `-covering-front.gbr`, `-covering-back.gbr` | `Other,Covering-Front`, `-Back` | `COATINGNONCOND`, one per side |
   | plugging | `-plugging-front.gbr`, `-plugging-back.gbr` | `Other,Plugging-Front`, `-Back` | `HOLEFILL`, one per side |
   | filling | `-filling-front-back.gbr` | `Other,Filling` | `HOLEFILL`, from `F.Cu` to `B.Cu` |
   | capping | `-capping-front-back.gbr` | `Other,Capping` | `COATINGCOND`, from `F.Cu` to `B.Cu` |

   Each file and layer holds exactly the vias whose own value is `yes`; a `setup` of `yes` for all five adds none, and a via tented by the default alone is in neither tenting file. The Excellon file marks vias `ViaDrill` only. On 9.0.9, `--format gerber` writes the PTH and NPTH files only, and IPC-2581 has no coating or hole-fill layer.
6. *DRC on 10.0.6* reports `via_dangling` and nothing else on every bench board, whatever the protection.
7. *Today's code on these files.* A read board keeps every protection child as an opaque via slot (minimum version 20250228 or 20240609) and RT1 holds. A 10.0 board is refused for target 9 (FEN-7002) before any via is looked at. A 9.0 board written for target 10 keeps `(tenting front)` verbatim, which 10.0.6 then reads with the back side following the board default (measurement 3).

## Goals / Non-Goals

**Goals:**
- A script says how each via is protected and what the board default is, and the files say the same on both majors where the major can hold it.
- Read boards keep their protection across reads, edits and rebuilds, with the meaning of the KiCad that wrote them.
- What 10.0.6 does not carry to a fabrication file is reported, not hidden.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Choosing a protection for the user: nowhere, because Fenolite ships no fabricator value (plan D6); without a script value KiCad's default applies.

## Decisions

1. **One value object of eight optional booleans.** `ViaProtection(tenting_front, tenting_back, covering_front, covering_back, plugging_front, plugging_back, capping, filling)`, each `bool | None`. It is KiCad 10's own set (measurement 2), and the 9.0 form is its tenting half. One type serves a via and the board default. Rejected: an IPC-4761 type (`Ia` … `VII`): the standard is not a public source, KiCad stores features, and a type cannot say "plugged on the front, tented on the back". Rejected: a second, all-boolean type for the default: two types of one shape, and `None` in a default has a meaning.
2. **`None` keeps KiCad's meaning; effective values are computed, never stored.** On a via, `None` is KiCad's `none`, the board's value. A `Board.via_protection` of `None`, or a `None` field of it, is the loader default of both majors: tented on both sides, nothing else (measurements 2 and 3). `via_protection.effective(protection, default)` gives the eight booleans that the mask follows and that the reports count. Rejected: writing the default into every via: the file would no longer say what KiCad shows, and an edit of the default in KiCad would not reach those vias. Rejected: `Via.protection: ViaProtection | None`, a second spelling of "follows the board".
3. **The meaning is the file's major.** A 9.0 file is read as 9.0.9 reads it: a `tenting` child lists the tented sides and the others are `False`; no child is `None`. A 10.0 file is read as 10.0.6 reads it, a 9.0 child in it included (named sides `True`, the others `None`). A read 9.0 board written for target 10 then gets the 10.0 form of 9.0.9's meaning, and keeps the mask that 9.0.9 plots. Rejected: one meaning for both majors, wrong for one of them on `front`, `back`, `none` and the empty child (measurement 3). Rejected: keeping 9.0 children opaque, as today: the mask changes on a target-10 write (measurement 7).
4. **Target 10 writes the re-save form; the bag keeps all-`none` children.** A child is written when one of its values is set, with both sides, in KiCad's order, so a re-save by 10.0.6 changes nothing (probe `via-prot-resave`). The 444 vias of the development-format board hold all-`none` children that this form drops: the reader records their heads as the pair `protection_none` of the via's `kicad` bag, and the emitter writes them again while their values stay `None`, so RT1 holds with no opaque child and no info. Rejected: every child always: each via grows by five children and differs from 10.0.6's own re-save. Rejected: the kept-opaque path of "Modelled children are reproducible" for them: 2 220 `kicad.board.kept-opaque` infos when one demo board is read.
5. **Target 9: tenting only, in 9.0's override form.** 9.0's child names every tented side, so a via whose tenting sets one side and leaves the other `None` takes that side from the effective default; 9.0.9 then plots what the model means. `False` and `None` of the four 10.0 features write nothing: no 9.0 via has them, and 10.0.6 turns every 9.0 via into an explicit `no` (measurement 2). A `True` raises `LossyWriteError` with `kicad.board.via-protection-too-new` and `droppable = False`, as a buried via is refused, because the model holds it. Rejected: leaving it to the emit check's `kicad.token.too-new`: inside `setup`, an opaque root slot, that error is droppable, and `--allow-lossy` would drop the whole `setup`. Rejected: refusing one-sided tenting for target 9: the resolved form plots the same.
6. **The default is a projection of the opaque `setup` slot,** as c0101 projects the stack-up. Each projection rewrites only its own children, in place, and keeps the others tree-equal. The comparison uses `effective_default`, so a 10.0.6 re-save, which writes all five children with the same values, is no change. A created board writes the children only when `Board.via_protection` is set, so a board without one keeps today's header. Rejected: modelling `setup` whole (c0101, Decision 1). Rejected: writing the default on created boards only: an edit on a read board would not reach the file.
7. **The script names features and sides.** `protect()` takes, for tenting, covering and plugging, `True` (both sides), `False` (neither), `"front"` or `"back"` (that side, the other `False`), or `None` (both follow the board); `capping` and `filling` take `True`, `False` or `None`. A one-sided `None` is left to the model API. `protection=` takes the value on `Design.via`, `via_step` and `Design.stitch`, the three calls that make vias. Rejected: five keywords on each call (fifteen names). Rejected: the words `"none"` and `"both"`: `"none"` reads as KiCad's `none`, which means the board's value.
8. **Script vias carry their intent's protection and are regenerated.** `resolve_copper` gives every via it creates, each via of a stitch included, the protection of its intent, and `merge_copper` compares `protection` with the other modelled fields: a protection set in KiCad on a script via is replaced with `kicad.copper.regenerated`, where today it is lost without an issue (Context). Rejected: the board winning on script vias: script copper is derived output (c0028, Decision 20). Rejected: script vias inheriting the script's default as their own values (Decision 2).
9. **The default across rebuilds follows the zones' rule.** No script default, or an equal one: the board's stays. A board without one takes the script's. Different and unlocked: the board's stays, with `kicad.via.protection-overridden` (info); locked: the script's replaces it, with `kicad.via.protection-forced` (warning). It is the rule of zones (c0031), pad zone connections (c0068) and stack-ups (c0101); KiCad has no lock token in `setup`, so the lock lives in the script, as for the stack-up. Rejected: the script always wins (an edit in KiCad's Board Setup undone at every build). Rejected: the board always wins (a script could change it only with `--discard-layout`).
10. **The export gap is reported, not repaired.** A default of `True` for covering, plugging, capping or filling reaches no file that 10.0.6 writes (measurement 5). The build gives `kicad.via.protection-not-exported` (info) naming the features and the number of vias that take them from the default only, and `inspect` counts them; the user sets them per via, or states them in the notes (c0117). Rejected: refusing such a default: KiCad's Board Setup holds it, and a later KiCad may export it, which `via-prot-default-outputs` will show. Rejected: an export kind for the side files here: c0116 owns new kinds.
11. **`inspect` reports the default and counts per side.** `result.via_protection` holds the effective default and its source, and per field the number of vias whose effective value is `True` and how many of those take it from the default. It is the count per protection kind that the review asked for; c0117 reads the same function. Rejected: a new command (c0066 owns the inspection commands). Rejected: the export manifest (c0065 owns it, and the counts describe the board, not a file).
12. **Altium: tenting is written and imported; the four other features are named** (decision of the maintainer, 2026-10-07).
    - *Written.* `pcbrecords.via_record` gains `tented_top` and `tented_bottom` and sets bits 5 and 6 of the first flags byte: `0C`, `2C`, `4C`, `6C`. The Altium lowering resolves each side: the via's own value; else the board default's, when the board holds one; else a clear flag. No other byte of the record moves, the mask expansions included.
    - *The side nobody states.* The model says that `None` in `Board.via_protection` is the backend's own default. KiCad's is "tented"; the Altium backend's is a clear flag, which is what it writes at `9aba2dff`. So a design that states nothing builds the Altium bytes it built before, and the samples, their goldens and the author reports that name them stay valid. The price is a known difference: the same script gives tented vias in KiCad and clear flags in Altium. It is not new (`pcb-copper.md` lists tented vias as not written today), it is said in `docs/altium.md`, and as soon as a design states any protection the `via-protection` info counts the vias with a side stated nowhere and names the call that states it.
    - *Imported.* `Via.protection = ViaProtection(tenting_front=tented_top, tenting_back=tented_bottom)`, both explicit. An Altium via follows no board default, so `False` is the honest reading of a clear flag; `None` would turn into "tented" the moment the board is written for KiCad. `Board.via_protection` stays `None`.
    - *Named.* Covering, plugging, capping and filling: one `altium.not-lowered` info at `via-protection` with the count of vias and the features. A via stays "written" in `result.pcb`: a field is not lowered, not an item.
    - *Evidence.* The two bits are `INFERRED` on both sides (the fact rows of `pcb-read.md` and `pcb-copper.md`). A new row `H-A-PCB-CU-VIATENT` states what Altium Designer shows for the four flag values; an author report settles it, and until then every reply that rests on a written or imported flag is `INFERRED`.
    - *Compared.* RT-A2 and the equivalence levels do not gain the field: a `None` has no Altium form, so a written and re-read model differs where a side is stated nowhere. A test of this change proves the round trip of stated values.
    - *`inspect`.* An Altium PCB document gets `result.via_protection` with `default.source` `altium`: counts of set flags, nothing by default.
    - Rejected: writing the effective tenting with KiCad's default (both flags set where nothing is stated). It would change the flags byte of every via of every Altium build, so every golden file and every sample an author report names, on an `INFERRED` fact; and a model written and read again would still differ (`None` against `True`).
    - Rejected: importing a clear flag as `None`. Written for KiCad, such a via would be tented by KiCad's default, the opposite of what the Altium document says.
    - Rejected: a MODIFIED "Via records" and "Tracks, arcs and vias". Four open changes of `dev` hold deltas of those two requirements; the two ADDED requirements name them and change one byte and one field, so no text is regenerated.
    - Rejected: setting the mask expansion of a tented via to another value. No recorded fact says that Altium does.
    - Rejected: the info alone (the first draft of this change), written when the Altium writer was experimental and its lowering was planned for a later phase.
13. **Nothing is checked.** KiCad's DRC reports nothing about protection (measurement 6), and which via a fabricator wants filled is the user's rule (plan D6). A blind or buried via may hold a value for a side it does not reach; it is written as given (not measured).
14. **Changes in flight** (checked on `origin/dev` at `9aba2dff`, 2026-10-07).
    - c0068 and c0069 are archived. "Copper intents in the DSL" and "Script copper is regenerated" are not modified here: "Via protection in the DSL" adds a last field to three intents and "Via protection of script copper" adds a compared field.
    - The three MODIFIED requirements of `kicad-file-backend` are the living text of `9aba2dff` with one sentence, one bullet and their scenarios added (compared word by word on that commit); no open change on `dev` holds a delta of them, c0126 included. Inside v0.4, by the order the review of 2026-10-07 fixed: "Created board header" is modified by c0100 and c0101, "Modelled board content" by c0101 and c0103, "Projected fields on write" by c0101. The order is c0100, c0101, c0103, c0112: this change lands last and regenerates the three copies from the text they leave (task 0.1). Their designs say the same.
    - "Via records" (c0085, c0128) and "Tracks, arcs and vias" (c0124, c0132) are refined by ADDED requirements, not modified; the four changes land with `0.3.0`, before this one, and task 0.1 reads their text for a sentence that the two ADDED requirements would contradict.
    - The board model and `board.json`: c0096 and c0099 (branches), c0121 and c0126 (open on `dev`), c0108, c0114 and c0118 (v0.4) add fields too. All additive; whichever lands later runs `tools/gen_schemas.py` on the merged model.
    - c0101 projects `stackup` from the same `setup` slot; each projection rewrites only its own children (c0101 Decision 13 says the same).
    - c0108 (proposal) adds `Via.locked`, `(locked yes)` and `locked=` on `Design.via` and `Design.stitch`. The fields and keywords are independent and both come last with defaults; the second change to land regenerates the board schema and re-bases `VIA_FIELDS` and `CANONICAL_ORDER["via"]`.
    - c0107 (fan-out) and c0110 (escape) create vias with `ViaProtection()`, so they follow the default; a protection argument there takes this change's type. c0111's thermal arrays pass `protection=` through, so an array in a pad can be filled and capped.
    - c0116 owns the side files and IPC-2581 as export kinds; c0117 the notes.
    - c0069 (archived) modified "Board content outside the design is kept"; "Via protection defaults across rebuilds" states its precedence for the protection children of `setup` without modifying it, as c0101 does.
    - `kicad-slots` "Slot source for model entities" is not modified: its first sentence admits every rewrite that a `kicad-file-backend` requirement names, which c0101 relies on too.

## Found on 2026-10-07

Implemented on the local branch `v04-impl-c0112`, based on `0ea988da` (`v04` at `991b3f57` plus change
c0101), where the prerequisites of the proposal do not all hold. What the code and the measurements of the
day showed, and what was corrected in the same commit:

1. **Prerequisites.** Release 0.3.0 is not out; c0085, c0124, c0128 and c0132 are implemented on the branch
   and not archived. Their deltas of "Via records" and "Tracks, arcs and vias" were read: none contradicts
   the two ADDED requirements ("Via tenting flags" adds two keywords to `via_record` after `start` and
   `end` of c0085; "Via tenting of imported vias" adds one field beside the pair `pad_removed` of c0132).
   c0100 and c0103 are not on the branch. The three MODIFIED deltas of `kicad-file-backend` were
   regenerated from the delta text of c0101, which modifies all three, with this change's sentence, bullet
   and scenarios re-applied; they must be regenerated again when c0100 and c0103 land (task 0.1). Six and
   eight copper layers do not exist on the branch: the benches are two-layer boards, as designed.
2. **Decision 12 is the Altium decision.** The brief of the night calls it "decision 7"; the numbering of
   this file was kept.
3. **The token rows `covering-front`, `covering-back`, `plugging-front` and `plugging-back` are not
   added.** The inventory rule "each row above KiCad 9 is the only row above 9 in at least one example"
   (`tests/unit/backends/kicad/test_token_examples.py::test_coverage_isolates_rows_above_9`) cannot hold for
   them: their parent `covering` or `plugging` is itself a row of KiCad 10, so no example exercises the
   child alone (`tenting/front` passes because `tenting` is a row of KiCad 9). The rows would add nothing
   to the write gate either: the parent row already refuses the child for target 9, and the model refuses
   the value before the gate sees it. The children are recorded as fact rows of
   `docs/formats/kicad/board.md`, "Via protection", which says why the inventory holds no row.
4. **Each protection child is a slot field of its own name** (`VIA_FIELDS` maps `tenting` to `tenting`,
   and so on), as the zone settings are, not one field `protection`: a file that holds the children in
   another order than KiCad's is then still reproduced without an opaque slot.
5. **A kept 9.0 child is rewritten for target 10 even when the model did not change.** A 9.0 board whose
   via holds `(tenting)` keeps the child as an opaque projected slot (the 9.0 emitter writes
   `(tenting none)`); copied into a 10.0 file it would be read by KiCad 10 with both sides `none`, so the
   mask would change, against Decision 3. The writer therefore writes such a child from the model whenever
   the target is not the major of the board that was read ("Projected fields on write", the regenerated
   bullet and its new scenario).
6. **`merge_default` on its own result.** The requirement said "the same value and no issue". An unlocked
   default that differs from the kept board default differs again at the next build, so the info is given
   again, as `kicad.zone.overridden` and `kicad.stackup.overridden` are. The sentence now says so; a
   locked default reports nothing the second time.
7. **`via-prot-resave` matches vias by position and leaves the bench without a default out.** A re-save
   by 10.0.6 orders the vias its own way, and gives a `setup` without protection children the five
   children of KiCad's default (measurement 2), which is not what Fenolite wrote and is no error.
8. **The Altium build test uses the routed blink.** `examples/altium_sample/design.py` declares no board,
   so it cannot carry via intents. The scenarios of "Via protection in an Altium build" now name a copy of
   `examples/blink_routed` with two vias added: nine vias are written, and eight are counted when no
   default states their tenting.
9. **The board default reaches the document writer as `PcbDocSpec.via_protection`.** Resolving the tenting
   into the vias of the spec changed `.fenolite/board.json` of an Altium build with script copper (every
   via gained `protection`), against "a design without protection keeps its bytes". The vias of the spec
   now keep the model's protection, and `pcbdoc.via_tenting(via, default)` gives the two flags at the
   write.
10. **`H-A-PCB-CU-VIATENT` is a row of the writer's evidence and one more id of the import's.**
    `tests/unit/lens/test_altium_build.py::test_evidence` asks that the build's evidence names every
    registered `H-A-PCB-*` row, so the row is in `pcbdoc.EVIDENCE` and every Altium build names it, not only
    one that sets a flag. `import_evidence.EVIDENCE` names it beside the `H-A-IMP-*` rows
    (`MAPPING_HYPOTHESES`); `adapter/test_package.py` was extended to allow exactly this one row.
11. **The write of a model (`backends.altium.lower`) follows the same rule** as the build: the tenting of
    each via from the via, else from `Board.via_protection`, and a count under the kind `via-protection`
    for covering, plugging, capping and filling. The rewrite of a document that was read therefore keeps
    its tenting flags, where it wrote `0C` before: every imported via states both sides.
12. **Measured on the eight public PCB documents** (2 933 via records; `docs/formats/altium/pcb-copper.md`,
    "Via"): bit 5 and bit 6 both clear in 734 records, bit 5 alone in 1, bit 6 alone in 0, both in 2 198.
    The solder-mask expansion does not follow the bits (two documents hold a negative expansion on every
    via, with both bits set). `kicad-cli pcb import --format altium` 10.0.6, run as a subprocess on a
    written document with the four flag values, gives the four vias the tenting that Fenolite's import
    gives them (`tests/kicad/altium/test_via_tenting_oracle.py`). Neither settles what Altium Designer
    shows: `H-A-PCB-CU-VIATENT` stays `INFERRED`, and step C8 of `docs/evidence/altium-pcb.md` asks.
13. **Sources.** One id was added after all: S-0630, the re-reading of the eight public documents for the
    two bits. Three addresses of Altium's documentation were tried and gave HTTP 404, so no Altium fact
    rests on a documentation page; S-0631 to S-0634 are not used. The "used for" cells of S-0020, S-0029,
    S-0037, S-0058, S-0125 and S-0160 were not extended: shared files are append-only tonight (task 1.1).
14. **The old-document fixture holds no via.** `tests/data/model/v0.2.1/blink_2layer.board.json` (the
    fixture of c0101) is loaded and dumped byte-equal by `tests/unit/model/test_via_protection.py`; a
    second test builds a board with vias, checks that its text holds neither key, and loads it again.
15. **Hard condition, measured.** `examples/blink_2layer` and `examples/blink_routed` built for KiCad 9 and
    10 and for Altium, and `examples/altium_sample` for Altium, with the code of `0ea988da` and with this
    change (`--seed 7 --timestamp 2026-10-07T00:00:00Z`): 108 files, 108 byte-equal. No committed sample
    and no pin moved.

## Found on 2026-10-08 (rebase onto `be2c01ec`)

The commit was rebased onto the wave-1 tip (`v04` with c0138, c0123, c0141, c0077, c0078, c0100, c0108,
c0116, then c0101). What changed in this change because of it:

1. **`locked` (c0108) and `protection` share the via.** c0108's requirements make `locked` the last
   field of `Via`, `ViaIntent` and `StitchIntent`; this change lands second, so `protection` is the field
   right before it, and the keyword `protection=` follows `locked=` on `Design.via` and `Design.stitch`
   ("Via protection in the board model" and "Via protection in the DSL" say so now). `merge_copper`
   compares geometry, net, lock and protection, and judges a duplicate without the lock and without the
   protection.
2. **Order of the via children.** A re-save by 10.0.6 writes `layers`, `remove_unused_layers`,
   `keep_end_layers`, `locked`, `free`, `zone_layer_connections`, then the five protection children, then
   `net` and `uuid` (measured on 2026-10-08). `CANONICAL_ORDER["via"]` holds the protection children after
   `locked`. `free` and `zone_layer_connections` stay opaque, so `slots.rebuild` gained the argument
   `after` (field → heads of opaque children that precede it) and `pcb.OPAQUE_BEFORE` names the two heads
   for the five protection fields: a child added to a read via that holds `(free yes)` lands after it. The
   probe `via-prot-order` proves on 10.0.6 that a re-save keeps the written order.
3. **Altium flags beside the lock bit.** c0108 writes a locked via with bit 2 of the first flags byte
   clear (`08`). The tenting bits are added to whatever byte the lock gives: `28`, `48`, `68` for a locked
   via. The 36 records with `68` in one public document fit this reading (locked, tented on both sides).
4. **The three MODIFIED deltas** were regenerated from the text the tip leaves: "Created board header"
   from c0100's delta as c0101's rebased delta carries it on (six and eight layers), "Modelled board
   content" and "Projected fields on write" from c0101's delta. c0103 is still not on the branch.
5. **Unexplained flag values, neither read nor written.** On the public document of corpus row
   `altium-third-party-pcbdoc-02`, 11 via records hold the first flags bytes `88` (5) and `E8` (6) with a
   second flags byte `01`; every other record of the eight documents has bit 7 clear and a second byte
   `00`. Bit 7 of the first byte and the second byte are unexplained: no fact row and no hypothesis is
   recorded for them, the reader reads neither, and the writer writes bit 7 clear and the second byte `00`.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py` | `ViaProtection` (frozen dataclass, eight `bool \| None` fields defaulting to `None`); `Via.protection: ViaProtection = ViaProtection()`; `Board.via_protection: ViaProtection \| None = None` |
| `schemas/fenolite.model.v0/board.json` | regenerated |
| `src/fenolite/backends/kicad/via_protection.py` (new) | `FEATURES`; `SUPPORT` (`tenting` {9, 10}, the others {10}); `KICAD_DEFAULT`; `effective_default(default) -> ViaProtection`; `effective(protection, default) -> ViaProtection`; `project_via(children, *, major) -> ViaRead` (value, `none_written`); `emit_via(protection, *, major, default, none_written=frozenset()) -> dict[str, Node]`; `project_setup(setup, *, major) -> ViaProtection \| None`; `setup_children(default, *, major) -> tuple[Node, ...]`; `rewrite_setup(setup, default, *, major) -> Node`; `too_new(protection) -> tuple[str, ...]`; `merge_default(script, board, *, locked) -> DefaultMerge`; `not_exported(design) -> Issue \| None`; `summary(design) -> dict[str, object]`; `ISSUE_CODES`; `EVIDENCE` |
| `src/fenolite/backends/kicad/pcb.py` | `VIA_FIELDS` gains `tenting`, `capping`, `covering`, `plugging`, `filling`; `CANONICAL_ORDER["via"]`; the `setup` projection, created children and rewrite; `kicad.board.via-protection-too-new` in `WRITE_ISSUE_CODES` |
| `src/fenolite/backends/kicad/data/tokens.toml` | no row is added ("Found on 2026-10-07", item 3) |
| `src/fenolite/backends/kicad/copper.py` | `protection` read by attribute from via steps and intents; stitch vias; `_fields` compares it |
| `src/fenolite/dsl/intents.py` | `protect`; `ViaStep`, `ViaIntent` and `StitchIntent` gain `protection` |
| `src/fenolite/dsl/design.py`, `convert.py`, `__init__.py` | `protection=` on `via` and `stitch`; `Design.via_protection`; `to_model` sets `Board.via_protection`; `via_protection_locked`; `protect` re-exported |
| `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py` | `lock_via_protection=`; the merge step; the not-exported info |
| `src/fenolite/lens/altium.py` | the info at `via-protection`; the evidence id when a flag is set |
| `src/fenolite/backends/altium/pcbrecords.py`, `pcbdoc.py`, `lower.py` | `via_record(…, tented_top=False, tented_bottom=False)`; the tenting of each via resolved from the via and the board default; `H-A-PCB-CU-VIATENT` in the writer's evidence |
| `src/fenolite/backends/altium/adapter/copper.py` | `Via.protection` from `ViaRecord.tented_top` and `tented_bottom` |
| `src/fenolite/cli/data/explain.toml` | tables for `kicad.board.via-protection-too-new`, `kicad.via.protection-overridden`, `kicad.via.protection-forced`, `kicad.via.protection-not-exported`; the `where` value `via-protection` in the text of `altium.not-lowered` |
| `src/fenolite/cli/cmd_inspect.py` | `result.via_protection`, for KiCad boards and for Altium PCB documents |
| `tests/kicad/vias/_viabench.py`, `test_via_protection_oracle.py`; `tests/kicad/zones/_gerber.py` (`flashes`); `tests/kicad/_probes.py`; `tests/kicad/conftest.py` | the bench, its probes, the flash reader |
| `tests/unit/model/test_via_protection.py`, `tests/unit/backends/kicad/test_via_protection_read.py`, `test_via_protection_write.py`, `test_via_protection_merge.py`, `tests/unit/dsl/test_via_protection_dsl.py`, `tests/unit/lens/test_build_via_protection.py`, `tests/unit/lens/test_altium_via_protection.py`, `tests/unit/backends/altium/test_pcb_vias.py`, `tests/unit/backends/altium/adapter/test_copper.py`, `tests/unit/cli/test_inspect_cmd.py`, `tests/corpus/test_board_census.py` | hermetic and corpus tests |
| `docs/formats/kicad/board.md` (section "Via protection"), `docs/formats/kicad/gerber.md`, `docs/dsl.md`, `docs/copper.md`, `docs/lens.md`, `docs/cli-contract.md`, `docs/altium.md`, `docs/design-model.md`, `docs/formats/altium/pcb-copper.md`, `docs/formats/altium/pcb-document.md` if it lists what an import maps, `docs/evidence/altium-pcb.md` (the author-report step) | fact rows with sources and labels; the user's pages |

No new source: the KiCad facts rest on S-0020 and S-0029 (the two oracles), S-0037 (the 9.0 command set), S-0058 (the corpus census), S-0030 and S-0033 (the inventory rows) and S-0125 (flashes and file functions of the plots); the Altium tenting flags rest on the sources of their existing fact rows (S-0160, S-0172, S-0174, S-0175, S-0176). All are rows of `docs/evidence/sources.md` at `9aba2dff`. Task 1.1 extends their "used for" cells. No file is added under `tests/data/`: the benches and the Altium documents of the tests are generated.

New names of this change, for the cross-check among the v0.4 proposals:

- Hypothesis ids: `H-K-VIAPROT-FORMS`, `H-K-VIAPROT-MASK`, `H-K-VIAPROT-NINE`, `H-K-VIAPROT-UPGRADE`, `H-K-VIAPROT-OUTPUTS`, `H-A-PCB-CU-VIATENT`.
- Issue codes: `kicad.board.via-protection-too-new`, `kicad.via.protection-overridden`, `kicad.via.protection-forced`, `kicad.via.protection-not-exported`. The `where` value `via-protection` of `altium.not-lowered`.
- Model: `ViaProtection`, `Via.protection`, `Board.via_protection`; the bag pair `protection_none` of a via's `kicad` bag.
- DSL: `protect`, `protection=` on `Design.via`, `via_step` and `Design.stitch`, `Design.via_protection(…, locked=False)`; `build_design(lock_via_protection=)`.
- Result keys: `result.via_protection.{default,effective,by_default}` and `default.source` with the values `board`, `kicad` and `altium` (inspect). No CLI flag is added.
- Altium writer: `via_record(…, tented_top=, tented_bottom=)`.
- Token rows: none ("Found on 2026-10-07", item 3). Probe ids: `via-prot-*`. Source id: S-0630.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-VIAPROT-FORMS | On 10.0.6 a via's protection is the children `tenting`, `capping`, `covering`, `plugging`, `filling` (sides `front` and `back` for the first three), each value `yes`, `no` or `none`; a re-save writes a child only when a value is not `none`, both sides always, in that order after `layers`; `setup` holds the five with `yes` or `no`, all written by a re-save, absent ones as tented both sides and `no` (S-0020, S-0058) | `tests/kicad/vias/test_via_protection_oracle.py -k resave` | probe `via-prot-resave` `equal` on 10.0.6 |
| H-K-VIAPROT-MASK | The mask plot of a via is open on a side exactly when its effective tenting there is false: the via's own value, else the board default, else tented; covering, plugging, capping and filling open nothing (S-0020, S-0029; plots read as S-0125 describes) | `-k mask` | probe `via-prot-mask` `equal` on 9.0.9 (9.0 forms) and 10.0.6 (10.0 forms) |
| H-K-VIAPROT-NINE | 9.0.9 reads a via's `tenting` child as the list of its tented sides (`none` or no atom: neither), a via without one takes the board default, and `setup` the same way (no child: both tented); it refuses to load a board holding a 10.0 protection form. The form KiCad 9 writes for neither side is not observed (S-0029, S-0037) | `-k "mask or nine"` on 9.0.9 | probes `via-prot-mask` `equal` and `via-prot-load-nine` `reject` on 9.0.9 |
| H-K-VIAPROT-UPGRADE | 10.0.6 reads a 9.0 via child naming one side, or none, in a 9.0 or a 10.0 file, with the unnamed sides `none`, so the default decides where 9.0.9 leaves them open; it reads the 9.0 `setup` forms as 9.0.9 does, and re-saves every via of a 9.0 board with an explicit `no` for the four 10.0 features (S-0020) | `-k upgrade` | probe `via-prot-upgrade` `different` on 10.0.6, the rows `front`, `back` and `none` differing and the others equal |
| H-K-VIAPROT-OUTPUTS | On 10.0.6 the drill side files of `pcb export drill --format gerber [--generate-tenting]` and the coating and hole-fill layers of `pcb export ipc2581` hold exactly the vias whose own value is `yes`; a board default adds none; 9.0.9 writes none of them (S-0020, S-0029) | `-k outputs` | probes `via-prot-outputs` `equal` and `via-prot-default-outputs` `absent` on 10.0.6 |

| H-A-PCB-CU-VIATENT | Altium Designer shows a via whose record has bit 5 of its first flags byte set as tented on the top, one with bit 6 set as tented on the bottom, and one with the flags `0C` as tented on neither side; it opens a document with the four flag values without a message (S-0160, S-0172, S-0174, S-0175, S-0176) | an author report: step C8 of `docs/evidence/altium-pcb.md` on a sample with four vias, one per flag value (task 8.4); `tests/unit/backends/altium/test_pcb_vias.py -k tenting` for the bytes and the read-back | the report names the four vias with the expected tenting; the unit test proves only that Fenolite reads back what it wrote |

The five `H-K-` rows start `INFERRED`, with the measurements of "Context" as their first record. `H-A-PCB-CU-VIATENT` starts `INFERRED` with result `pending (author report)`; it stands beside `H-A-PCB-CU-VIA` and `H-A-RD-PCB-LENGTHS`, whose levels do not move. None of the six ids is in `docs/hypotheses.md` at `9aba2dff`. Cited without a change of level: `H-K-COPPER-VIAKINDS` (c0068), `H-K-UUID-KEEP-2`, `H-K-PCB-READ`, `H-K-PCB-WRITE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| reading every corpus form, RT1 | `CORPUS-VERIFIED` | `tests/corpus/test_board_census.py -k via_protection`, `tests/corpus/test_board_rt1.py` |
| the target-10 written forms | `KICAD-VERIFIED (10.0.x)` | `via-prot-resave` |
| the mask of the written forms | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `via-prot-mask`, and the written bench of task 9.1 |
| the 9.0 meaning, the refusal of the 10.0 forms by 9.0.9 | `KICAD-VERIFIED (9.0.x)`; KiCad 9's own written form `INFERRED` | `via-prot-mask`, `via-prot-load-nine` |
| KiCad 10's reading of 9.0 children | `KICAD-VERIFIED (10.0.x)`, recorded | `via-prot-upgrade` |
| what the outputs carry | `KICAD-VERIFIED (10.0.x)` | `via-prot-outputs`, `via-prot-default-outputs` |
| model, DSL, script copper, default merge, `inspect`, Altium info | mechanical | the unit tests of "Files and public API" |
| Altium tenting flags written and read back by Fenolite | mechanical | `test_pcb_vias.py -k tenting`, `adapter/test_copper.py -k tenting` |
| what Altium Designer shows for the written flags; the meaning of the imported flags | `INFERRED`; `ALTIUM-VERIFIED(author-report)` once the report of task 8.4 is in | `H-A-PCB-CU-VIATENT` |

`via_protection.EVIDENCE` is `INFERRED` with the five ids until they are settled; `pcb.EVIDENCE` keeps its level.

## Risks / Trade-offs

- **A later 10.0.x exports the defaults, or changes a form.** The probes are pinned per version: `via-prot-default-outputs` flips to `present` and its test fails before the info misleads; `via-prot-resave` guards the forms.
- **A target-9 board opened in KiCad 10.** KiCad's own conversion changes the mask of vias whose 9.0 child names one side or none (measurement 3). `docs/formats/kicad/board.md` and `docs/dsl.md` say so; `fenolite build --target 10` keeps 9.0.9's mask.
- **KiCad 9's written form is inferred.** `(tenting none)` loads and plots as meant on 9.0.9 (measured); only the spelling KiCad 9 would choose is unknown. A child of another spelling in a 9.0 file stays opaque and projected, so RT1 holds.
- **Three MODIFIED requirements shared with c0100, c0101 and c0103.** One sentence or bullet each; task 0.1 re-bases.
- **Fields and keywords beside c0108.** Both additive, with defaults; the schema is regenerated after the re-base.
- **Two projections of one `setup`.** A test edits the stack-up and the default of one board together (task 4.1).
- **An agent sets a default of plugging and expects it in the files.** The info of Decision 10, the counts of `inspect`, and the DSL page.
- **The Altium tenting bits are inferred.** They come from one public description and a census of files, not from Altium's own word. Mitigation: nothing is set unless the design states a tenting, so no existing output moves; the author-report step of task 8.4; the label `INFERRED` on every reply that rests on a flag.
- **A clear Altium flag is read as "not tented".** Altium may also close a via's mask through its mask expansion, which is not read. Mitigation: said in `docs/altium.md` and in the fact row; the imported value is `False`, never a claim about the plotted mask.
- **KiCad tents what Altium leaves clear.** A side nobody states (Decision 12). Mitigation: the `via-protection` info counts those vias once a design states any protection, and `docs/altium.md` says it for designs that state none.
- **Imported Altium boards gain a field on every via.** Their model JSON grows, and `fenolite diff` between an Altium import and a KiCad reading of the same board may list `protection`. Mitigation: task 8.3 runs the diff and equivalence tests and records what moved; the equivalence levels do not compare the field.

## Migration Plan

- Additive model: documents without the fields load; a via whose protection is `ViaProtection()` writes no new JSON key (default values are omitted). The other direction does not work: **0.2.x and 0.3.0 cannot read a `board.json` that carries `protection` or `via_protection`**, because the reader of the canonical form is strict, as after every earlier additive change of the model; `SCHEMA_VERSION` stays `"0"`, and the changelog line and `docs/design-model.md` say so (tasks 11.4 and 2.1).
- Altium builds: a design without protection writes the bytes it wrote before. A design that states tenting gets the flags `2C`, `4C` or `6C` on the vias concerned, and nothing else moves.
- Altium imports: every imported via gains explicit tenting, so `.fenolite/board.json` and the canonical JSON of an imported board gain `protection` on each via. `CHANGELOG.md` says so.
- Created boards without protection write the bytes they wrote before: no `setup` child, no via child.
- Read boards: protection children become modelled and are written tree-equal (RT1). `.fenolite/board.json` of a board with protected vias gains `protection` once.
- A KiCad 9 board with via-level tenting, rebuilt for target 10, gets the 10.0 form of 9.0.9's meaning instead of the copied 9.0 text. `CHANGELOG.md` says so.
- A protection set in KiCad on a script via is now replaced with `kicad.copper.regenerated`, where it was dropped silently.
- Rollback: remove the projection and the emitters; the fields stay, defaulted, and the children become opaque again.

## Budget (4.75 days)

| part | days |
|---|---|
| 1. registers; token-edit bench, flash reader, probes on 10.0.6; the 9.0.9 run | 0.75 |
| 2. model and schema | 0.25 |
| 3. via children: forms per major, the bag pair, target-9 resolution and refusal, token rows, corpus census and RT1 | 0.75 |
| 4. board default: `setup` projection, created children, editable projections | 0.5 |
| 5. script: `protect`, `protection=`, resolve and merge, `Design.via_protection`, build step and info | 0.5 |
| 6. lens: `merge_default` and its codes | 0.25 |
| 7. `inspect` and `summary` | 0.25 |
| 8. Altium: the two flags in the via record, the lowering rule, the import mapping, the info, `inspect` on a PCB document, the fact rows and the author-report step | 1.0 |
| 9. written bench on both majors, documentation, closing | 0.5 |
| **total** | **4.75** |

Cut order: (1) `inspect` on Altium PCB documents (the key is then absent there, which `docs/cli-contract.md` states); (2) the lock: the board's default then always wins once it has one, and a script change needs KiCad's Board Setup or `--discard-layout`; (3) `inspect`: c0117 calls `summary`, and the info of Decision 10 stays. Never cut: the model, the forms of both majors with the target-9 refusal, the default, `protection=`, the script-copper rule, the probes, and the Altium tenting written and imported with its info (decision of the maintainer).

## Open Questions

- **Should the build write the four 10.0 features of the script's default onto every script via, so they reach the side files?** Default: no (Decisions 2 and 10); revisit if `via-prot-default-outputs` stays `absent` on later 10.0.x.
- **Should a target-9 build warn when a via's child names one side or none?** Default: no; it is KiCad 10's conversion, not the written file, that changes the mask, and the documentation says so.
- **Should `protect()` accept a one-sided `None`?** Default: no; the model API does.
- **Blind, buried and micro vias.** Should a value on a side the via does not reach be refused? Default: no, written as given; not measured.
- **Pad tenting.** 633 pads of one development-format board hold `(tenting (front none) (back none))`. Default: stays opaque; no change owns pad mask options yet.
- **Should an Altium build tent the sides nobody states, as KiCad does?** Default: no (Decision 12): no existing output moves on an `INFERRED` fact. Revisit when `H-A-PCB-CU-VIATENT` is `ALTIUM-VERIFIED`; it would then be a change of its own, with the goldens and the samples rebuilt once.
- **Should RT-A2 compare the tenting of vias whose two sides are stated?** Default: no; the test of this change covers stated values.
- **A per-via list in `inspect`.** Default: counts only; c0066's views can list vias.
