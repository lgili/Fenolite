# Altium v0.3 acceptance

The authored acceptance tree is prepared and its local readback proofs passed on
2026-10-14. The complete KiCad-import acceptance test passed in CI 38504478797.
Aggregate verification of its newly registered probe and native acceptance of
this new project remain pending. No write kind graduates from these results. The register retains `INFERRED` until the new probe criterion is verified. Local
readback uses Fenolite's own writers and readers; the separate CI import result is
recorded below.

## Project and scope

`examples/acceptance_v03/design.py` declares six copper layers, a two-level module
tree, three via kinds, board text, a keep-out, a polygon and all eight exact rule
kinds. All dimensions are Fenolite choices. The CC0 drawing sheet is an unchanged
copy of the shipped generic template, retaining its public provenance S-0077 and
S-0078.

The runner adds an authored ranged bus, a free non-plated hole and explicit
extruded bodies through the neutral model and existing writers. These are model
preparation steps, not additional DSL features. KiCad stores its free hole in an
anonymous footprint; Altium stores it as a free pad. Both written holes must be
one non-plated 2 mm drill within the committed triangle tolerance before the triangle's existing unnamed-reference policy
can exclude unpairable references. The Altium scope inventory reads the generated
project and typed keep-out records; it does not rely solely on its model cache.

## Local result, 2026-10-14

| step | result |
|---|---|
| Build KiCad target 10 with reviewed plan | passed |
| Build Altium binary module sheets with reviewed plan | passed |
| Required written scope | passed, all twelve criteria |
| KiCad model validation and same-version roundtrip | passed |
| Altium model validation and RT-A1 | passed |
| Altium project RT-A3 | passed |
| KiCad board versus Altium PCB document, level 5 | passed |
| KiCad importer versus the KiCad board, level 5 | passed in CI 38504478797, KiCad 10.0.6 |
| Probe `acceptance-v03` and frozen outcome | registered as equal from the full CI acceptance; aggregate probe verification pending next batch |
| Native kit correspondence and publication | task 3.1 complete; supplemental v0.4.0 asset, see provenance below |

The focused acceptance tests passed (5 tests); fixture-manifest and hypothesis/provenance
checks passed (91 tests). The comparison uses the committed
`kicad-import` triangle profile; it adds no new tolerance or exclusion. The checks
above validate model and readback only: this intentionally sparse exercise board
is not a fully routed or DRC-clean production board. Copper short and clearance
acceptance are covered separately by the kit and the roadmap's planted controls.

Fenolite version: `0.5.0.dev0`. KiCad output target: `10`; no `kicad-cli` was
launched for the local proofs. Altium version and kit run id for this new project:
not measured. Existing native kit records are retained separately and are not
reported as a native run of this project.

## Reproduce and finish

Local preparation, into a new output folder:

```console
uv run python tools/acceptance_v03.py --out build/acceptance-v03-prepared --prepare-only
uv run pytest tests/unit/test_acceptance_v03.py -q
```

Full oracle acceptance runs in GitHub CI:

```console
uv run pytest tests/kicad/acceptance/test_v03_acceptance.py -q
```

`summary.json` records each stage, tool versions and an optional reported kit run
id. `acceptance_complete` remains false for preparation, a failed stage or an
exception. Raw command replies stay beside the generated files for diagnosis;
they are not committed, because receipts may contain local paths. An existing
output folder is refused so an earlier result cannot be overwritten. Task 2.1
remains open until the complete oracle proof, probe outcome and evidence update
pass. Archive still requires actual successful CI and the dependency order.

## Complete oracle result and native-kit reconciliation

The KiCad-10 job of [run 38504478797](https://github.com/lgili/Fenolite/actions/runs/38504478797)
passed on pinned KiCad 10.0.6 (3274 passed, 116 skipped, 3 expected failures).
It includes the complete acceptance test, including the import comparison. Its
result justifies adding the new `acceptance-v03: equal` probe criterion for
10.0.6; all 992 pre-existing outcomes remain unchanged. The test and probe now
share the same cached full acceptance. Registration tests passed 19 cases without
launching an external tool. Task 2.1 still waits for the new aggregate probe proof.

A fresh `kit status` on this tree confirms four records, no stale rows and no
problems. Completed run `2026-10-13-462b38ba` uses AD 26.5 and the current kit
digest `af3c911e0fc76db4bac6dabeb48c401f1ca12ac216b3951f9c99cace2ae15483`.
Its 32 passed steps remain valid; no failure is recorded. Its archive publication
and privacy review remain pending task 3.1. All 27 hypotheses settled by that run
currently retain their existing inferred/author-report levels; this reconciliation
changes no evidence label and does not claim native acceptance of the newly
authored acceptance project. Task 3.2 will apply eligible promotions after the
publication requirement is met.

## Archive publication review

CI completion on 2026-10-14: [run 38520443552](https://github.com/lgili/Fenolite/actions/runs/38520443552)
passed all 11 jobs on exact commit `d9d980d7046cb2254ca9bcb94f0ccdcd96555626`.
The pinned 10.0.6 job ran the full KiCad/corpus selection with heavy inputs:
3274 passed, 116 skipped, 3 expected failures. Neither the complete acceptance
nor the aggregate probe test appears in the reported skips. The new
`acceptance-v03: equal` outcome is confirmed, closing c0092 task 2.1 and making
`H-A-ACC-V03` `KICAD-VERIFIED (10.0.x)` within its established triangle profile.
This is not a native Altium run of the new acceptance project. The later
Clearance/archive batch has its own CI run and is outside this verdict.

The full-run ZIP matches its committed SHA-256 and its size of 1236513 bytes;
it contains 27 members. A fresh privacy scan reproduces the record's 43
home-folder findings across eight files: five native binary documents/libraries
and three reports. No personal value is reproduced here. A value-free local
review is saved under `build/c0092-publication-review.md`.

The original ZIP and immutable run record remain unchanged and unpublished.
Changing result bytes changes the archive digest, so a cleaned version cannot
be published as the original run. A new native save in a neutral folder, followed
by verification and a new record, is the proposed publication path. This review
changes no native verdict or evidence level.

### Publication edition prepared on 2026-10-14

New record `2026-10-13-87c930fa` passes 32 steps with no failure or skip.
Its 1199847-byte archive has SHA-256
`87c930fa06446319df87edd49a010f80a9448cf350effb452c500b293eda232a`.
The [publication provenance](altium-kit/2026-10-13-87c930fa-publication.md)
records five new native saves, the one display-only ECO metadata derivative,
the actual new DRC and the retained historical form/script observations.
The date in the record remains the historical form's date; this is not a
complete fresh replay. The original archive and record are preserved.

Privacy review has zero home-folder/login findings and seven absolute references
in the neutral Fenolite namespace. The native TXT is used unchanged for K4.2
under its legacy `drc.html` filename; the HTML with a personal logo reference
remains outside the publication results. On 2026-10-14 the maintainer selected
v0.4.0 for supplemental publication. The uploaded asset was downloaded again:
its SHA-256 and size match the immutable record and GitHub's asset digest.
Task 3.1 is complete; no hypothesis is promoted here. This record was generated
by `0.5.0.dev0` and does not revalidate the released v0.4.0 package binaries.

Task 3.2 reconciliation on 2026-10-14 labels the 27 passing kit candidates,
with the committed run and archive digest and explicit typed-form qualifiers.
Their prior observations are retained in the register. The
[remaining hypothesis inventory](altium-kit/2026-10-14-graduation-inventory.md)
states the independent criterion or missing kit proof for the other 115 rows
used by write cells and acceptance/kit families. This changes no capability;
all nine write kinds still fail the complete graduation rule.

## Fresh native handoff preparation, 2026-11-03

Source `b5f6c84a`, Fenolite `0.7.0.dev0`, prepared a new immutable acceptance-v03-v2 packet with the existing prepare-only runner. Both reviewed build plans confirmed successfully; all twelve written-scope checks passed. Preparation/probe focus:10passed. The packet binds47 prepared files plus a separate handoff/expectation/manifest layer: four components,8pins, exact3net membership, six copper layers and all8 exact rule kinds. Embedded drawing frames are included; no standalone SchDot artifact is claimed.

All43 non-reply prepared files equal the historical v1 packet. Four command replies differ only in elapsed time, locations, plan and receipt identifiers. The new source binding does not reuse the old packet's version or execution claims. Actual native version and run ID remain null; `acceptance_complete` is false. Native compilation/ERC/DRC, save/reopen, current register/graduation conditions and exact-source CI remain gates. No result or evidence promotion follows from this preparation.

## Native OutJob and drawing-frame inspection, 2026-11-04

Source S-1573. A Claude agent ran this inspection at the maintainer's request of 2026-11-04. It operated
the Altium Designer installed in the maintainer's Parallels Windows VM. This is not the maintainer's own
review. The tool reports `Client.GetProductVersion` 24.5.2.23 (Trial).

The eight top-level Altium files of the prepared-v2 packet (source `b5f6c84a`) were copied unchanged,
and their digests equal the packet manifest before and after the run:

| file | SHA-256 |
|---|---|
| `acceptance_v03.PrjPcb` | `e2ee4c5c1958b52d6fe8e4d5e8f82ea99aceb5d073913e3a7c01970268e36aa2` |
| `acceptance_v03.OutJob` | `f2e42097a2728a316a8fa4afd0d4774547ef4656c2e45ca072d096db3a304f3f` |
| `acceptance_v03.SchDoc` | `53682f6f0314343747b7049acb41ffa49655c9c23b9c5f6169dcf0c5070a0f63` |
| `acceptance_v03_front.SchDoc` | `bc7b275e8921bc2270ce5dccfddbbe5b3eba8f8c4531b93768afb9a6aa2fd5bb` |
| `acceptance_v03_front.stage.SchDoc` | `c28bd9df71ddb30ab64697b207e41a5a26304557e7922cfa34657628c2071886` |
| `acceptance_v03.PcbDoc` | `2a78551faf793ea1c95843b1fac518c175caba105c03fc722566412c9ebd212e` |
| `acceptance_v03.PcbLib` | `79a54d5b9ba0203fe61c6290a9bd0e467cdecb601c92e52c7ff1fe4c3c4de3ae` |
| `acceptance_v03.SchLib` | `1e3c3436c173d2c26c0d373018a3833d007bd225bdebab5499fc1072ab760387` |

**Project.** All seven logical documents open with no new message: three sheets, the PCB, the OutJob,
the PcbLib and the SchLib. The compile gives the single message `Compile successful, no errors found.`
(Info). It flattens 4 components and 4 nets. This repeats S-1303's result; the net count includes the
compiler's own entries.

**OutJob.** The OutJob opens in its editor and lists six outputs:

| output | data source |
|---|---|
| Schematic Prints | All SCH Documents |
| PCB Prints | `acceptance_v03.PcbDoc` |
| Pick and Place | `acceptance_v03.PcbDoc` |
| Gerber Files | `acceptance_v03.PcbDoc` |
| NC Drill Files | `acceptance_v03.PcbDoc` |
| Bill of Materials | `[Project]` |

It lists two output containers:

- `fab` (Generated Files): with `fab` selected, the editor links Gerber Files (1), NC Drill Files (2),
  Pick and Place (3) and Bill of Materials (4) to it.
- `doc` (PDF): its local path ends in `acceptance_v03.PDF`.

No output was generated, and the doc container's links were not displayed.

**Embedded drawing frame.** For each of the three sheets, a read-only DelphiScript procedure read the
document's sheet properties and every label and polyline. The procedure has SHA-256
`05830cce083177f3b720afc60ad04904988470fb30f66e1daaa14e591b66e592`. All three sheets read the same:

- `UseCustomSheet` true;
- `CustomX` 116929134 and `CustomY` 82677165 (1169.29134 × 826.77165 in units of 10 mil, that is
  297 × 210 mm);
- `BorderOn` false, `TitleBlockOn` false and `SheetStyle` 0;
- 36 labels and 27 polylines.

Every label's text and location, and every polyline's vertices, equal the label (record 4) and polyline
(record 6) records that Fenolite's reader decodes from the same file. The match holds on every sheet with
no missing or extra object. This shows that Altium reads the embedded frame as written. It is not a
review of the frame's appearance, and no standalone SchDot is part of the packet.

Nothing was saved and no input changed. This closes the OutJob and frame inspection items of the handoff.
It does not close task 5.3. Three things remain:

- a recorded run of the whole acceptance tree;
- per-kind graduation, which needs a current `ALTIUM-VERIFIED` kit support that the approved 24.5 scope
  cannot give;
- exact-source CI.

## Native run of the handoff steps 2 to 6, 2026-11-04 evening (source S-1586)

A Claude agent ran steps 2 to 6 of the handoff at the maintainer's request of 2026-11-04/05. It operated
the Altium Designer installed in the maintainer's Parallels Windows VM, which reports
`Client.GetProductVersion` 24.5.2.23 (Trial). This is not the maintainer's own review. The same eight
top-level files of prepared-v2 were copied unchanged into a new VM folder. Their digests before the run
equal the table above.

| step | observed |
|---|---|
| 2. open | all seven logical documents open with no new message. The compile leaves one message and flattens 4 components (R1 to R4) and 4 nets. The nets are `D0` = R1.1, R3.1; `D1` = R2.1, R4.1; `GND` = R1.2, R2.2, R3.2, R4.2; plus the bus entry `D[0..1]` with no pin. This is the expected partition: no pin is missing or merged, and there is no singleton net |
| 3. PCB scope | four components `TwoPin` on Top. Three GND vias of 0.3 / 0.6 mm: through (Top–Bottom), blind (Top–Mid 1) and buried (Mid 1–Mid 2). One polygon, one keepout region, 9 texts, 4 bodies, one free non-plated 2 mm hole. `LayerIsUsed` reports Top, Mid 1, Mid 2 and Bottom, so the six-layer stack is not confirmed by this listing. The rule iterator lists 37 rules under the default names, so the 8 written rule kinds are not singled out |
| 4. ERC and DRC | the compile is the ERC and leaves one message. DRC gives 14 violations: 9 UnRoutedNet and 5 NetAntennae (three vias and the free track). This is the expected outcome for the sparse, partly routed exercise board; nothing was suppressed |
| 5. save, close, reopen | each logical document was saved in place by `DoFileSave` and closed. The PcbDoc, the three SchDocs and the PrjPcb keep their bytes. The OutJob (`f7c759cb…`), the PcbLib (`476b6c86…`) and the SchLib (`2c6ae35b…`) are rewritten. After reopening, the compile, the nets and the PCB scope are the same as in steps 2 and 3, and there are still 37 rules |
| 6. Fenolite read-back of the saved copy | `fenolite inspect` exits 0 on the saved PcbLib, SchLib and PrjPcb. Counts are unchanged: PcbLib 1 footprint, 2 pads, 4 graphics, with 26 opaque records against 20 before; SchLib 1 symbol, 1 unit, 2 pins, with a new `cfb.note.entry-fields` note. The prepared originals were not rewritten |

The saved files and logs stay in `claude-2026-11-04/c0092-saved/` and `c0092-out/`, outside the
repository. This is an agent run on the acceptance tree. It records the steps and does not graduate any
kind. Task 5.3 stays open: per-kind graduation needs a current `ALTIUM-VERIFIED` kit support, which the
approved 24.5 scope cannot give, and exact-source CI is still pending.

## Altium kit run of the converted sheets, 2026-11-08 (source S-2287)

A Claude agent ran the schematic kit at the maintainer's request on the maintainer's Parallels Windows
VM, with the Altium Designer that reports `Client.GetProductVersion` 24.5.2.23 (Trial). This is not the
maintainer's own review. The artifacts were written by the c0470 code state (branch `claude/c0470-impl`,
one commit behind `dev` `faacd6382`) with Fenolite's `convert` in both directions; `hier`, which has no
PCB document, went through `convert/schematic.py` in both directions. The job opened each project in a
new Altium session, compiled it, and printed every flattened component, every net with its pins, and
every compiler message; it saved nothing.

| project | source | components | nets | compiler messages |
|---|---|---|---|---|
| `blink` | S-0188 family, `tests/data/altium/blink` | 3 / 3 | 32 / 32 | 3 Error + 2 Warning, identical |
| `altium_hier_board` | authored example | 3 / 3 | 32 / 32 | source 3 Error + 2 Warning; converted 3 Error + 3 Warning |
| `hier` | `tests/data/altium/hier` | 6 / 6 | 9 / 9 | source 1 Info; converted 1 Info + 6 Warning |
| `Battman` (`altium-set:02`, supplementary) | S-0188 | 248 / 248 | 183 / 188 | source 86 Warning + 1 Info; converted 3 Error + 58 Warning |

The pair in each cell is the source drawing and the drawing read back after Altium → KiCad → Altium, or
KiCad → Altium for the demos.

**`blink`, `altium_hier_board`, `hier`.** The components and the net partition are equal on all three:
no pin is missing, no two nets are merged, and no net is split. The three Errors on `blink` and
`altium_hier_board` are the source's own (`NetU1_11` and `NetU1_12` contain floating input pins, `VIN`
has only one pin), and they are reproduced word for word. The converted `altium_hier_board` adds one
warning, a duplicate port `LED_A` at two positions. The converted `hier` adds six: four "net has multiple
names" warnings (`SPI_CS`, `SPI_MISO`, `SPI_MOSI` and `SPI_SCK` carry both a net label and the two
`flash-SPI.*` / `mcu-SPI.*` sheet entries) and two duplicate ports (`FLASH_WP`, `RESET_N`). Each is a
message about the same connectivity; the net partition does not change.

**Six public KiCad 10.0.6 demos.** Each Altium project opened, compiled and produced no script `ERROR`
row:

| project (corpus row) | components | nets | compared with `kicad-cli` 10.0.6 |
|---|---|---|---|
| `complex_hierarchy` (`kicad-demo-10-0-6-sch-01`) | 68 | 52 | 52 nets, same partition and same pins |
| `ecc83-pp` (`-011`) | 15 | 13 | 13 nets, same partition and same pins |
| `ecc83-pp_v2` (`-012`) | 15 | 13 | 13 nets, same partition and same pins |
| `interf_u` (`-013`) | 24 | 175 | 173 nets; equal after the 16 implicit power pins and 2 empty bus nets below |
| `laser_driver` (`-053`) | 13 | 9 | 9 nets, same partition and same pins |
| `royer1` (`-058`) | 17 | 10 | 10 nets, same partition and same pins |

The reference is the `kicadxml` netlist of the source project from `kicad-cli` 10.0.6, compared as a
partition of `(reference, pin)` pairs. `interf_u` has 16 pins of `U5` and `U9` that `kicad-cli` puts on
`GND` or `VCC` as `power_in` pins; Altium connects them implicitly and does not list them, so the two
`GND` and `VCC` groups differ only by those 16 pins. Altium also lists the two empty bus nets
`PC-DB[0..7]` and `PC-A[0..11]`, which have no pin. Removing the 16 implicit power pins and the two empty
nets makes every group equal.

**`Battman` (supplementary, not acceptance).** All 248 components and their references are equal and no
script `ERROR` row appears. The source gives 183 nets and the converted drawing 188. Every difference is
accounted for:

- **`JP6` pin designators.** The source lists the connector's pins by number (`JP6.1`, `JP6.2`, `JP6.3`,
  `JP6.5`, `JP6.6`, `JP6.ID`); the converted symbol takes the names of its pin-to-pad map
  (`JP6.VBUS`, `JP6.D+`, `JP6.D-`, `JP6.GND`, `JP6.MT1`, `JP6.ID`). Each pair is on the same net, so the
  connectivity is unchanged; only the pin spelling differs.
- **Five nets split by a local label promoted to a port at a sheet crossing.** `POWER_BTN` becomes the
  identical net `NetQ1_3` (`Q1.3`, `R62.1`, `U2.20`), and four nets lose one branch each, which becomes a
  net of its own: `NetQ1_1` → `NetQ12_1` (`Q12.1`, `R46.1`, `R47.2`); `NetR39_1` → `NetU2_18` (`U2.18`);
  `NetQ9_1` → `NetU2_43` (`U10.7`, `U2.43`); `NetQ11_1` → `NetU2_19` (`U2.19`); and `NetJP4_1` →
  `NetR46_2` (`R46.2`). Every pin is present exactly once; the split follows the label that the source
  keeps on one sheet and the conversion promotes across the sheet boundary.

Within this scope the run supports `ALTIUM-VERIFIED(kit)` for the converted sheets of `blink`,
`altium_hier_board`, `hier` and the six demos. It covers netlist and compiler-message equivalence on the
24.5 trial, not the drawing's appearance and not per-kind graduation; it also does not cover the
`Battman` net split, which is supplementary evidence only. The artifacts, the scripts and the results
stay in the harness folder outside the repository, and no input file changed.

## Native allowance observations (c0465, S-2245)

Altium Designer 24.5.2.23 batch DRC, 2026-11-10. Four authored documents were written from
`feb039bb5`; none was saved by Altium. Each report names its input and lists zero waived findings;
the input SHA-256 was checked again after DRC. The `allow`, `zero` and `deny` documents have identical
compound streams except `Rules6/Data`. The independent `threshold` board tests track width at fixed
50 mil tolerance. None of these reports is a complete Fenolite kit graduation.

| Probe | Total | Short-Circuit | Net Antennae | DRC SHA-256 |
|---|---:|---:|---:|---|
| allow | 4 | 1 | 1 | `9faba14767f74db6ede937a26fafa26f9df47c32a8a3a52af823656f57019f19` |
| zero | 7 | 1 | 4 | `d11c223a39c7d2e9ec45f4e3ce3513461105261d3019f3d48a4bd978e15cb7f7` |
| deny | 6 | 2 | 1 | `78d9dd011d7f21a295524aecc2ec23253c736f13d236777b940527a4c2eb50ac` |
| threshold | 8 | 0 | 8 | `f154b974a6424ecf31938cf473ca494984316cda363560c852714848ae13ea92` |

- At 50 mil with the allowing rule, Altium reports only the control short (`VIN`–`DGND`), not the
  `AGND`–`DGND` short. With the one allowance bit changed, Altium reports both pairs. This supports
  the priority/scope hypothesis for these two authored pairs.
- At 0 mil it reports each 40, 50 and 60 mil bare track stub and the via-ended branch. At 50 mil it
  reports only the via-ended branch, despite that branch's 40 mil track centre-line length.
- For 10 mil wide branches at 50 mil tolerance, the largest tested length that passes is 60 mil and
  the shortest flagged length is 61 mil. At 20 mil wide the corresponding lengths are 70 and 80 mil.
  These finite probes establish a width-dependent difference; they do not establish a general formula,
  behaviour for arcs or bends, or the boundary at 71 mil for the 20 mil track.
- The prior native construction script still stops at `Priority := 1` when it is moved before
  `AddPCBObject`; its partial test document was not saved or used for these DRC reports. The writer
  produced the fresh authored inputs with their rule priorities already encoded.

The centre-line hypothesis did not predict these results. The follow-up below records the
additional controls and the resulting portability decision.


## Native antenna matrix (c0465, S-2298)

Altium Designer 24.5.2.23 batch DRC ran three authored boards containing the same 56 cases:
32 straight tees, 12 via-ended branches, four vias with connected continuations, four bent stubs
and four arcs. The inputs' compound streams differ only in `Rules6/Data`. The source file hashes
were verified before and after DRC. The three reports each ended normally with zero waivers.

| Tolerance (mil) | Straight tee findings | Via findings | Bent stub findings | Arc findings | DRC SHA-256 |
|---:|---:|---:|---:|---:|---|
| 0 | 32 | 11 | 4 | 4 | `cc51544785dd7bd9bc39c22f49fb5722ce7ecd60fd3d7789c9591372cf65874e` |
| 50 | 14 | 11 | 0 | 1 | `ab392584c1d513161563dda6bb1d5f1fc3e39d6d957bbb4f1b8a832a25653e0f` |
| 1000 | 0 | 11 | 0 | 0 | `fb842e2d160088417842368917ed078e131491f882dbcbeda7ecdb7453cf7107` |

At 50 mil the equal-width 10 mil tee passes at 60 and is reported at 61; the equal-width 20 mil tee
passes at 70 and is reported at 71. Changing either trunk or stub width changes some outcomes.
The same 11 via endpoints are reported at all three tolerances, including a 20 mil branch ending in
a 24 mil via. A 20 mil branch ending in a 60 mil via and all four vias with a connected continuation
pass at all three tolerances. These observations establish differences from neutral centre-line
measurement on the authored inputs. They leave the general Altium algorithm unverified. The
coordinate-matched comparison receipt has SHA-256
`34096fbe523f3829e492374310c8cc704ddd5934daac70216363a780b7656ff0`.

A native NetAntennae record travels through the KiCad board carrier, including its original scope,
priority, enabled state and tolerance. The CLI identifies the coverage limit. Legacy typed rules with
Altium identity cannot reduce KiCad dangling findings. An authored portable rule still uses its
centre-line length, and Altium export writes its declared tolerance without promising matching DRC
outcomes.
