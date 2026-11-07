# c0401 design: attributions of the 2026-11-04 census rows

Base `origin/dev` `1169f10d`, re-run 2026-11-05 with KiCad 10.0.6 (macOS `kicad-cli`) through the strict
`tests/_fidelity.roundtrip` pipeline, with no acceptance, tolerance or level subset. The counts are the
same as the 2026-11-04 census. Each attribution below rests on the named files of the public demo row;
nothing is normalized to reach equality.

## Differing rows

| row | counts | attribution | evidence | owner |
|---|---|---|---|---|
| 10.0.6 pcb-14 | 5:track-width=4 | Fenolite (comparator) | Both boards hold the same three F.Cu tracks of net 1 from (160.3, 123.399735) to (160.3, 123.399995), widths {0.3, 0.29997, 0.29997}, and two such tracks on B.Cu. `strict.match` pairs equal geometry keys in file order, so the 0.3 track of one side meets a 0.29997 track of the other. The spec says "each kind matched as a multiset". | c0401 task 1.3 |
| 9.0.9.1 pcb-05 | 7:graphic-missing=5 | Fenolite (import/build) | The original outline is one `gr_rect` on Edge.Cuts. Import turns it into `design.board(outline=…)` and the build writes the outline as four `gr_line`s. c0349 keeps explicit physical root edges, but only lines and arcs. | c0401 task 1.4 |
| 9.0.9.1 pcb-02 | 7:opaque-count=1, 7:zone-field=1 | Fenolite (derived teardrop caches), same mechanism as c0384 | The import leaves out the 176 `$teardrop_padvia$` caches (opaque). The c0340 same-tool proof qualifies both sides, removes the caches and refills with KiCad 10.0.6: 178 caches on each side, with different exact geometry (sha256 `6c67e319…` vs `37277939…`), so the teardrop count stays a difference. This is c0384's first finding (RoyalBlue, 289 vs 293) on another board. | c0384 (0.4, 2.3, 4.4) |
| 9.0.9.1 pcb-01 | 7:opaque-count=1 | Fenolite (proof scope) | 6 teardrop caches are left out by import. The c0340 proof refuses this board before native execution: `_parents` raises "unqualified non-quarter parent pose" (custom and rotated pads), so the proof is deliberately narrower than KiCad's teardrop feature. | c0413 |
| 9.0.9.1 pcb-01 | 8:render-pixels=1 | input inconsistency, carried by a Fenolite model limit | The original schematic's R2 has an empty, visible `Footprint` field while its board footprint is `custom_pads_test:DO-214AB`. A `Part` holds one footprint, so the build writes it into the schematic field: the 0.762 mm vertical text at x = 132.842 mm is the differing strip (872/37894 pixels). The `#PWR0001`→`#PWR01` renumbering of the change list draws nothing (hidden references). | c0414 |

`kicad-demo-10-0-6-pcb-13` stays with c0384.

## Refused rows (task 2.1)

| row | refusal | attribution | evidence |
|---|---|---|---|
| 10.0.6 pcb-01 (cm5_minima) | import `FEN-5001`, `build.schematic-netlist-differs` | input | KiCad 10.0.6 `sch export netlist` puts J701 pin M1 (`GND2230_M1`) on GND, but the board footprint of J701 has no pad M1 (only two unnamed NPTH pads). The drawing means a pin the board cannot carry; the self-check refuses it as intended. |
| 10.0.6 pcb-11 (openair-max) | import `FEN-5001`, `build.schematic-netlist-differs` | input | KiCad 10.0.6's netlist puts I2C3 pin 6 on GND (a wire at (137.16, 170.18)), while the board pad is `unconnected-(I2C3-Pad6)`: the board was not updated from the schematic. Intended refusal. |
| 10.0.6 pcb-07, pcb-17 | import `FEN-5001`, `kicad.project.too-new-key` | input (mixed versions) | Board 20241229 and schematics 20250114 are KiCad 9 files, but the `.kicad_pro` holds `component_class_settings`, `tuning_profile` and `net_settings/meta/version`, written only by 10.0. The import targets the board's major (9) and refuses keys 9 cannot read. Intended refusal; `pcb upgrade` of the board is the user's fix. |
| 10.0.6 pcb-05 (interf_u) | import `FEN-3004` | corpus | The project names `pagelayout_logo.kicad_wks`, which the corpus manifest does not fetch. Intended refusal (kicad-file-backend, "Checked native project worksheet resources": a missing declared worksheet refuses). Adding the worksheet as a manifest row would make the row comparable; that is a corpus change, not code. |
| 10.0.6 pcb-09 (multichannel unrouted) | verify-source `FEN-3004` | input | `multichannel_mixer-unrouted.kicad_pcb` has no project of its own stem, so the source side has no native project context and the generated side has one; complete native rules are unjudged. Intended refusal. |

## Decisions

- The comparator change pairs, inside one equal geometry key, the items whose strict-rule fields are all
  equal first, then the rest in their previous order. This is the multiset the spec names, not a
  tolerance: a pair is only formed between items of equal key, and every field is still compared.
- A root `gr_rect` on Edge.Cuts becomes an explicit physical edge (`design.rect(..., layer="Edge.Cuts")`)
  when it is the outline's owner. The writer's c0349 reconstruction accepts unfilled rects beside lines and
  arcs; everything else on Edge.Cuts still refuses.
