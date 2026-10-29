# Converting a project

`fenolite convert SRC --to kicad|altium --out DIR` converts a project to another backend, or to another
KiCad major, and says per kind of item and per reason what it kept, changed and lost (change c0159,
capability design-conversion). Every conversion is read back and compared with its source: the written
project differs from the source only where the report says so, or the command writes nothing.

```bash
fenolite convert board/blink.kicad_pro --to altium --out altium --dry-run --json     # plan and report
fenolite --allow-lossy convert board/blink.kicad_pro --to altium --out altium --confirm
fenolite --kicad-version 10 convert old/blink.kicad_pro --to kicad --out v10 --confirm
```

The options, the `result` and the exit codes are in `docs/cli-contract.md`, "convert". The library call
is `fenolite.api.convert(source, *, to, kicad_version=10, allow_lossy=False, bodies="extruded", name=None,
verify=True)`; `fenolite.convert.convert_project` is the same conversion without the read-back, in
memory, which writes no file and runs no tool.

## Sources

- **KiCad.** A `.kicad_pro`, a `.kicad_pcb` or a folder, resolved as `fenolite check` resolves it. The
  design is the board read, completed by the project's files (`KicadBackend.design_rules`): the net
  classes, the class of each net and the custom rules. A board read alone holds none of them.
- **Altium.** A `.PrjPcb`, a `.PcbDoc` or a folder that holds one project file (else one PCB document),
  read by the Altium backend. No direction from Altium is registered yet (change c0161), so such a source
  is refused with exit 2.
- Anything else exits 2 (`FEN-2001`); a path that does not exist exits 3 (`FEN-3001`).

## Directions

`fenolite capabilities` lists the registered directions under `result.conversions`, each with the KiCad
majors it writes, whether it writes a KiCad target older than the source (`downgrade`), whether it is
experimental, and its evidence.

| from | to | writer | experimental | evidence |
|---|---|---|---|---|
| kicad | altium | the footprint items projected (`fpitems.with_footprint_items`), then `lower.write_design`: the PCB document, and the schematic, its libraries and the project file when the schematic writer takes the circuit | yes | `INFERRED` (the Altium writers), with the triangle `H-K-CONV-TRIANGLE` |
| altium | kicad | 9, 10 | `altium-to-kicad`; derived libraries, generated schematic, reported losses |
| kicad | kicad | `write_triad` for the target major with the source's project file updated, the source's rules file written again for the target, and the schematic files copied when the majors are equal; for an older target, every file written through the downgrade resolver (below) | no | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-CONV-RETARGET`; a downgrade: `H-K-DOWN-ROWS`, `H-K-DOWN-DEMOS`) |

- A schematic of an older major than the target is not converted (a schematic is not upgraded): the
  report counts it as a lost `schematic` (a `report` kind, which needs no consent).

### KiCad downgrade

A KiCad target older than the source's major is a downgrade (change c0162): a KiCad 10 project written
for KiCad 9 with `fenolite --kicad-version 9 convert <project> --to kicad --out <dir>`. It is the only
way to write a design of 10 for 9: `build`, `place`, `route` and `fill` keep refusing such a source
(`FEN-7002`, whose hint names `convert`).

- Every file is written with `downgrade=True`: the board and the project and rules files (`write_triad`,
  `dru.write_rules`), each schematic sheet (`sch.retarget_schematic`), the footprints of the project's own
  `.pretty` folders (`mod.write_footprint`) and its own symbol libraries (`sym.retarget_symbol_library`).
  The library tables and drawing sheets, whose formats both majors read, are copied.
- The capability resolver (`docs/formats/kicad/versions.md`, "Downgrade") decides each construct of 10
  where it is: written in 9's form (`rewrite`), dropped because 9 behaves the same (`same`), dropped with
  a reported loss of a drawing or of metadata (`presentation`) or of the design (`design`).
- The report holds one row per resolver id, kind `downgrade:<id>` in the group `downgrade`: `rewrite` and
  `same` are `changed`, `presentation` and `design` are `lost`; a row that can be `design` is a `refuse`
  kind, so a design loss needs `--allow-lossy`. The ids of an item are `<file>:<locator>`. Every KiCad 10
  project holds `component_class_settings` and `tuning_profiles`: they are `same` when they hold what a
  fresh KiCad 10 project writes there, and `design` rows (`--allow-lossy`) when they hold content (the
  maintainer's decision of 2026-10-09; `docs/formats/kicad/project.md`, "Default sections of KiCad 10").
- The verification compares the board at level 5 and the root schematic at level 2 under the profile
  `kicad-downgrade`. A schematic whose netlist needs `kicad-cli` and finds none is not compared: one
  `convert.schematic-unverified` warning says so.
- Altium compound files use DIFAT sectors when more than 109 FAT sectors are needed. The version 3
  sector-address limit remains a refusal (`FEN-7001`), with or without consent.

## The report

`result.report` holds one row per kind that the source holds or the write touches, in the order of the
table below: `source` (what the source holds), `written` (what the target holds as it was; the writer's
own count where it keeps one), `changed` (written in another form that compares equal), `lost` (not
written) and `reasons`, each reason with its `outcome` (`changed` or `lost`) and its `count`, sorted by
count and then by reason. Every item is counted under its own reason. `--report-ids` adds the ids of the
items. `lossy` is true when any row has a loss, and `refused` names the `refuse` kinds with losses.

A loss of a `refuse` kind changes the board that is made or its bill of materials: without
`--allow-lossy` the conversion exits 7 (`FEN-7001`) with one `convert.lossy` issue per such kind; with it
the same issues are warnings. A loss of a `report` kind is in the report only. Each kind with changes
gives one `convert.changed` info.

The vocabulary is closed (`fenolite.convert.report.KINDS`), one table for every direction:

<!-- kinds:begin -->
| kind | group | loss |
|---|---|---|
| `net` | circuit | refuse |
| `netclass` | circuit | refuse |
| `dnp` | circuit | refuse |
| `pin-net` | circuit | refuse |
| `module` | circuit | report |
| `channel` | circuit | report |
| `pin-pad-map` | circuit | report |
| `pin-pads` | circuit | report |
| `footprint` | footprint | refuse |
| `pad` | footprint | refuse |
| `footprint-copper` | footprint | refuse |
| `body` | footprint | report |
| `footprint-graphic` | footprint | report |
| `footprint-text` | footprint | report |
| `net-tie` | footprint | report |
| `pad-margin` | footprint | report |
| `model` | footprint | report |
| `track` | copper | refuse |
| `arc` | copper | refuse |
| `via` | copper | refuse |
| `zone` | copper | refuse |
| `copper-shape` | copper | refuse |
| `plane` | copper | refuse |
| `zone-fill` | copper | report |
| `via-pad-shape` | copper | report |
| `via-protection` | copper | report |
| `outline` | board | report |
| `cutout` | board | report |
| `stackup` | board | report |
| `keep-out` | board | report |
| `hole` | board | report |
| `rule` | board | report |
| `severity` | board | report |
| `placement-rule` | board | report |
| `keepout-footprints` | board | report |
| `text` | presentation | report |
| `graphic` | presentation | report |
| `dimension` | presentation | report |
| `schematic-text` | presentation | report |
| `schematic` | project | report |
<!-- kinds:end -->

- The Altium write's kinds are those of `lower.KINDS` and `lower.MORE_KINDS` (`docs/altium.md`, "Written
  scope"); `refuse` is exactly `lower.LOSS_KINDS` and `dnp`.
- **`dnp`.** The Altium documents hold no fitted flag outside variants, which are after 1.0: a component
  marked do-not-populate is written as fitted, so a bill of materials of the converted project would
  list it. The maintainer decided on 2026-10-09 that this loss is a refusal.
- **`cutout`** (change c0170). Every inner ring of the source's board edge, cut-out or slot, is counted
  once under `cutout` (a group of overlapping rings once, its id the members' `cutout/<k>` joined by `+`):
  `written` as it is, `changed` with the reason `merged` (a group united into one ring) or `arcs
  polygonised` (an Altium region holds straight edges only, so the arcs are written within 1 µm), or
  `lost` with its reason. The kind is `report`, but an overlap that a conversion to KiCad cannot merge (no
  `geo` extra, or a union that is not one ring) is a `refuse` loss (`report.REFUSE_REASONS`): KiCad would
  call the outline malformed, so the rings are not written and the conversion exits 7 without
  `--allow-lossy`. The kind `outline` keeps only the losses of the board ring.
- **Changes of KiCad to Altium.** `zone-fill`: with `--altium-pour computed` (the default since change
  c0215) the polygon is poured by Fenolite from the written document (experimental), and a polygon the engine
  refuses, or every polygon with `--altium-pour outline`, is written unpoured, and Altium fills it on a
  repour. `schematic`: the schematic is generated from the circuit on one sheet
  with generic symbols. A schematic that the writer refuses is a loss, and the writer's message stays an
  `altium.not-lowered` issue.

## Verification

Without `--no-verify`, `fenolite.api.convert` writes the files into a private temporary folder, reads the
direction's file back with the target backend (`<name>.PcbDoc`, `<name>.kicad_pcb`) and compares it with
the design that was written through `fenolite.api.equivalent` (`docs/equivalence.md`), at the highest level
both hold, under the direction's profile. Each difference is then matched with the report:

- a difference that a lost item explains is listed under `result.equivalence.explained`, with `by`, the
  lost kind;
- any other is one `convert.unexplained` error: the command plans nothing and exits 5.

The edge rings are verified too (change c0170; `fenolite.convert.rings`): the rings of the source's board
edge and those of the written board read back (`BoardFrame.board_edges` of each backend) are compared after
one translation, each ring within 1 µm plus the 1 µm chord of a polygonised arc, a merged ring against the
union of its sources. A ring that matches none is a difference of kind `edge-ring` at level 0, located at
the ring's name (`board`, `edge ring <k>`): explained by `cutout` when the report counts that ring lost or
merged, by `outline` for the board ring when the report counts a loss or change of the outline, and
otherwise a `convert.unexplained` error (exit 5). `fenolite equivalent` does not compare outlines (a
follow-up of `design-equivalence`).

`--no-verify` skips the read-back: `result.equivalence` is `null`, one `convert.no-verify` warning says
so, and the evidence is `UNVERIFIED` (the maintainer's decision of 2026-10-09). The read-back costs at most
as much as the conversion on the measured boards.

### What a loss explains

The table is closed (`fenolite.convert.report.EXPLAINS`): a lost item explains only these differences, at
these places. "Level 5" is `route-missing`, `route-connectivity`, `route-vias`, `route-length`,
`route-stub` and `route-unjudged`; "levels 1 to 4" every kind located at a reference or one of its pins.

<!-- explains:begin -->
| lost kind | place | differences |
|---|---|---|
| `footprint` | its reference, or a pin of it | levels 1 to 4 |
| `footprint` | a net of its pads | level 5 |
| `pad` | its `REF-PIN` | `pad-missing`, `pin-missing`, `pad-kind` |
| `pin-net` | its `REF-PIN` | `net` |
| `pad` | its net | level 5 |
| `track`, `arc`, `via`, `zone` | its net | level 5 |
| `net` | a pin on it | `net` |
| `net` | the net | level 5 |
| `dnp` | its reference | `dnp` |
| `footprint-copper`, `net-tie` | a net of the pads of its footprint | level 5 |
| `source` | a reference held as often on both sides | `ref-ambiguous` |
<!-- explains:end -->

`source` is no kind of the report: several components of the source share a reference (an empty one, or a
mounting hole's), which the comparison of the source with itself reports too, and the conversion kept as
it was.

### Profiles

`src/fenolite/convert/data/profiles.toml` holds one profile per direction, `kicad-downgrade` for the
downgrade and `import` for the self-check of `fenolite import` (`docs/import.md`), in the exclusion format of `docs/equivalence.md`; none holds a rule today.

| profile | frame | tolerances | why |
|---|---|---|---|
| `kicad-to-altium` | relative | 3 nm, 20 ppm | the writer moves the board's corner to the document's origin; a length is written in 1/10 000 mil (2.54 nm), and the 16 demo boards read back within 2 nm per coordinate; a routed length as in the triangle |
| `kicad-to-kicad` | absolute | none | the board is written with its own coordinates |
| `kicad-downgrade` | absolute | none | the same model in another header: a construct the resolver drops is no item that levels 1 to 5 compare |
| `import` | absolute | none | `fenolite import` builds the emitted code and compares it with the source board; the build writes the source coordinates exactly (change c0275) |

## Evidence

The level of a reply is the lowest of the source's read, the direction's writer and the read-back; the
Altium direction stays experimental until change c0092's rule lets its write kinds leave that state.

| claim | level | proof |
|---|---|---|
| the report: kinds, reasons, counts | mechanical | `tests/unit/convert` |
| every difference of the 16 written KiCad 10.0.6 demo boards is explained (`H-G-CONV-LEDGER`) | `CORPUS-VERIFIED` | `tests/corpus/test_convert_census.py`, `docs/evidence/conversion.md` |
| `kicad-cli pcb import` of a converted board equals the source (`H-K-CONV-TRIANGLE`) | see `docs/hypotheses.md` | `tests/kicad/convert/test_triangle.py` |
| a KiCad 9 project converted to 10 gives the DRC of the source (`H-K-CONV-RETARGET`) | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `tests/kicad/convert/test_retarget.py` |
| each row of the downgrade resolver, benched on 9.0.9 and 10.0.6 (`H-K-DOWN-ROWS`) | see `docs/hypotheses.md` | `tests/kicad/downgrade/test_rows.py` |
| the demo projects of format 10 converted for 9 load in 9.0.9 with the DRC and ERC of the source (`H-K-DOWN-DEMOS`) | see `docs/hypotheses.md` | `tests/kicad/downgrade/test_demos.py`, `docs/evidence/conversion.md` |

A conversion's report is Fenolite's view: what Altium Designer does with the documents is the question of
the verification kit and the author reports (`docs/altium-kit.md`).

## KiCad to Altium with c0160

The conversion writes a derived `<name>.PcbLib`: one footprint per name after the last `:` of its
reference, chosen from the first instance in reference order in its local frame. Every board component
links this library. Edited pads or graphics remain on the PCB and are counted `changed` under
`footprint`. Long names that share a compound storage key use distinct storage keys in `SectionKeys`;
the full footprint names are preserved. Bodies follow `--altium-bodies extruded|off`.

Plain per-layer pads use Top-Middle-Bottom or Full Stack records. Connector pads use a surface record
with no paste or solder-mask expansion; final appearance needs Part T in Altium. Unnumbered footprint
pads become free pads at their board position and are reported `changed`. Custom pad shapes stay losses.

The drawing-layer map is fixed: `User.1` through `User.8` → Mechanical 1 through 8; `Dwgs.User`,
`Cmts.User`, `Eco1.User`, `Eco2.User` → Mechanical 9 through 12; `F.Fab`, `B.Fab`, `F.CrtYd`,
`B.CrtYd` → Mechanical 13 through 16. The PCB names these layers after the source. Copper texts stay
on their copper layer. Unsupported layers remain losses; there is no user layer-map option.

A source schematic supplies its own circuit and embedded symbol graphics. Each sheet instance gets an
Altium sheet, including each use of a repeated child. The writer lays out symbols and wires anew;
`schematic` is `changed` with reason "positions and wires are not converted". Without a source
schematic, the generic generated sheet remains. The API may use its existing KiCad netlist exporter
for schematics outside Fenolite's own grammar. Pure `fenolite.convert.convert_project` runs no tool:
it accepts a prepared `SourceProject` whose optional `schematic` is the independently read design.

Imported Altium comments beginning with `=` are retained; KiCad literal comments beginning with `=`
receive a leading space and are counted as `schematic-text` changes. Binary properties preserve
printable Unicode in `%UTF8%` twins with `?` fallback outside Windows-1252; ASCII stays restricted.
A pin on conflicting nets uses the largest membership set, then the smallest net name on a tie.
Each discarded membership is a `pin-net` loss requiring consent. A membership naming an absent pin
is also reported, never silently removed. Colliding generated symbol names or differing pin sets
receive distinct library entries. These read-circuit allowances do not relax script validation.

Local proof covers 16 light demo boards with no unexplained differences and four light Altium project
sets. Heavy corpus cases and the full suite remain CI work. Part T is required before c0160 archives;
Fenolite read-back alone does not prove that Altium opens or compiles the generated files.

## Altium to KiCad (c0161)

Verification profile: `altium-to-kicad`, absolute frame, 1 nm tolerance.

`fenolite convert input.PrjPcb --to kicad --kicad-version 10 --out out --dry-run --json`
prepares a reviewed project; commit it with `--confirm --plan <plan_id>`. Targets 9 and 10 are supported.
The result includes PCB/project/rules, a derived `.pretty` library and table, and (when the imported
circuit has unique designators) generated schematic sheets and a symbol library/table.

Mechanical layers map in numerical order to User.1..45, preserving their name as the layer alias.
Unknown/out-of-stack layers and excess mechanical layers are reported as losses. Closed Keep-Out
outlines become all-copper rule areas forbidding tracks, vias and pours; open/branching lines are lost.
Curved boundaries are polygonized with at most 5000 nm chord error, reported as changed.
An odd copper count gains an empty inner layer; its original stack-up is reported changed.
A copper pour whose Altium outline holds an arc vertex has no outline in the imported model
(`altium.import.zone-arc`); the conversion takes its outline from the source document's polygon record,
flattened at 5000 nm chord error, and reports the zone changed. A zone without a usable record is
reported lost. KiCad 9.0.9 cannot write a DRC report for a zone without an outline.
`kicad.board.layer-undeclared` refuses any caller's modelled item on an undeclared layer, even with consent.

Arbitrary slots rotate circular pads without changing copper; incompatible non-circular pads are
reported lost. The import holds a slot's axis in the pad's own frame (change c0170), so a slot along a
turned oval pad is kept as it is.

**Slots, cut-outs and holes** (change c0170). The edges are taken with `edge_outline`. Inner rings that do
not overlap are written as read, each counted `written` under `cutout`. Overlapping ones are united
(`merge_groups`, the `geo` extra) and the board gets the model outline of its rings, its edge graphics
replaced: each group is one ring, counted `changed` with `merged`; a group that cannot be united is a
`refuse` loss (see `cutout` above). Each board `Hole` of the import (a free pad without copper, c0168)
becomes the footprint that `design.hole` generates (`fenolite.model.holes.hole_footprint`,
`Fenolite_Holes:NPTH_<d>mm` or `NPTH_Slot_<d>x<l>mm`), placed at the hole, turned by its rotation, locked,
`board_only` (no schematic symbol) and outside the position file and the bill of materials, its library
written as `lib/Fenolite_Holes.pretty` with its row in `fp-lib-table`, as a build writes it. A length the
document cannot tell from a whole micrometre (one unit is 2.54 nm) is taken to it, so a 2 mm slot is
`NPTH_Slot_2x12mm`, the script's name. A plated hole, whose copper is the hole, is the pad `1` of
`PTH_…_Pad_<d>mm` and is counted `changed` under `hole`. The shared slot fixture converted to Altium and
back loads with no `invalid_outline` and drills what the source drills (`H-K-CONV-SLOTS`). Derived footprints use the first instance in reference order in its top-side local frame;
instances that differ are reported without replacing board geometry. Filename collisions are disambiguated.
Symbols are taken from available SchLib definitions or generated from the circuit pins. Positions and
wires are regenerated. Duplicate designators refuse the schematic alone, with an explicit report.
**Pad openings** (change c0223). An imported pad keeps its copper layers and gains its openings by its
kind: a surface pad on `F.Cu` gets `F.Paste` and `F.Mask` (on `B.Cu` the bottom ones), a plated or unplated
through-hole pad `F.Mask` and `B.Mask` and no paste; a surface pad on an inner layer gets none. Its mask and
paste expansions become `Pad.mask_margin` and `Pad.paste_margin`, written as `solder_mask_margin` and
`solder_paste_margin`: a manual expansion as it is, an expansion "from the rules" as the first enabled
`SolderMaskExpansion` or `PasteMaskExpansion` rule of scope `All`, none without one. A pad that a rule of
another scope may govern takes the `All` rule and is a `pad-margin` loss: the scope is not evaluated, but
a rule whose scope selects no pad (`IsVia`, `IsTrack`, in the closed scope grammar) is left out. The
paste `Enabled` switch and the solder `Tented` option are not read (`docs/formats/altium/pcb-library.md`,
U1 and U2), so a tented pad of the source is open in KiCad (`H-A-CONV-PADMASK`).

**3D models** (change c0223). The model that the PCB document embeds for a body of a top-side part
(`models3d.body_models`) is written beside the derived library as `<name>.3dshapes/<footprint>_<sha12>.step`
(`sha12`, the first 12 hex digits of the SHA-256 of the model's bytes) and named in the library footprint
with its placement: the offset of the model from the footprint origin, its height `MODEL.3D.DZ` and its turn
about Z less the part's (`H-K-MODEL-PLACE`, `H-A-BODY-MODEL-PLACE`); a placed model is a `model` change. A
model of a bottom-side part or turned about X or Y is a `model` loss. The board's own footprints carry no
model: KiCad's "update footprints from library" brings them. The bodies stay `body` losses.

Unsupported imported rules and nonportable component bodies are reported. Libraries and projects use
relative paths. Loading with DRC (9.0.9 and 10.0.6), agreement with KiCad 10.0.6's own importer and
the generated schematics' netlist and ERC are KICAD-VERIFIED on the public corpus (2026-10-15); the
direction stays INFERRED because the Keep-Out mapping rests on Altium's documentation only.

Unmapped source rule diagnostics are included as lost rule groups with the original message;
group counts are not counts of individual rules. A multiply assigned schematic pin retains
the last imported net assignment and produces a consent-requiring `pin-net` loss.

Generated schematics mark unused symbol pins as no-connects. ERC connection errors are
checked independently; inherited power-drive findings may remain, so a conversion is not
a claim that the source circuit is electrically ERC-clean.
