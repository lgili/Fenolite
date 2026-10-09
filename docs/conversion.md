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
majors it writes, whether it is experimental, and its evidence.

| from | to | writer | experimental | evidence |
|---|---|---|---|---|
| kicad | altium | the footprint items projected (`fpitems.with_footprint_items`), then `lower.write_design`: the PCB document, and the schematic, its libraries and the project file when the schematic writer takes the circuit | yes | `INFERRED` (the Altium writers), with the triangle `H-K-CONV-TRIANGLE` |
| kicad | kicad | `write_triad` for the target major with the source's project file updated, the source's rules file written again for the target, and the schematic files copied when the majors are equal | no | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-CONV-RETARGET`) |

- A KiCad target older than the source's major exits 7 (`FEN-7002`): the downgrade is change c0162.
- A schematic of another major is not converted: the report counts it as a lost `schematic` (a `report`
  kind, which needs no consent).
- An Altium document larger than a compound file without DIFAT sectors is not written (`FEN-7001`, with
  or without consent); two KiCad demo boards are (`docs/evidence/conversion.md`).

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
| `schematic` | project | report |
<!-- kinds:end -->

- The Altium write's kinds are those of `lower.KINDS` and `lower.MORE_KINDS` (`docs/altium.md`, "Written
  scope"); `refuse` is exactly `lower.LOSS_KINDS` and `dnp`.
- **`dnp`.** The Altium documents hold no fitted flag outside variants, which are after 1.0: a component
  marked do-not-populate is written as fitted, so a bill of materials of the converted project would
  list it. The maintainer decided on 2026-10-09 that this loss is a refusal.
- **Changes of KiCad to Altium.** `zone-fill`: a polygon is written unpoured, and Altium fills it on a
  repour (decision of 2026-10-06). `schematic`: the schematic is generated from the circuit on one sheet
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
| `pad` | its `REF-PIN` | `pad-missing`, `pin-missing` |
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

`src/fenolite/convert/data/profiles.toml` holds one profile per direction, in the exclusion format of
`docs/equivalence.md`; neither holds a rule today.

| profile | frame | tolerances | why |
|---|---|---|---|
| `kicad-to-altium` | relative | 3 nm, 20 ppm | the writer moves the board's corner to the document's origin; a length is written in 1/10 000 mil (2.54 nm), and the 16 demo boards read back within 2 nm per coordinate; a routed length as in the triangle |
| `kicad-to-kicad` | absolute | none | the board is written with its own coordinates |

## Evidence

The level of a reply is the lowest of the source's read, the direction's writer and the read-back; the
Altium direction stays experimental until change c0092's rule lets its write kinds leave that state.

| claim | level | proof |
|---|---|---|
| the report: kinds, reasons, counts | mechanical | `tests/unit/convert` |
| every difference of the 16 written KiCad 10.0.6 demo boards is explained (`H-G-CONV-LEDGER`) | `CORPUS-VERIFIED` | `tests/corpus/test_convert_census.py`, `docs/evidence/conversion.md` |
| `kicad-cli pcb import` of a converted board equals the source (`H-K-CONV-TRIANGLE`) | see `docs/hypotheses.md` | `tests/kicad/convert/test_triangle.py` |
| a KiCad 9 project converted to 10 gives the DRC of the source (`H-K-CONV-RETARGET`) | `KICAD-VERIFIED (9.0.x, 10.0.x)` | `tests/kicad/convert/test_retarget.py` |

A conversion's report is Fenolite's view: what Altium Designer does with the documents is the question of
the verification kit and the author reports (`docs/altium-kit.md`).
