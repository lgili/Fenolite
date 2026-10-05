## Context

Five follow-ups were left for v0.2a by the v0.1 changes, each in writing, and the measurements for the first of them found a defect of v0.1 that is repaired here:

| follow-up | left by | where |
|---|---|---|
| the zone's own clearance in the copper check | c0029, c0031 | `copper-check`, "Supported cases are documented against KiCad's DRC"; `docs/formats/kicad/copper.md` |
| per-pad zone connection in the DSL | c0031 | design, Open Questions; `docs/dsl.md`, "Zones" |
| arcs and blind, buried and micro vias in script copper | c0028 | design, Non-Goals and Open Question 4 |
| a CLI pad query | c0028 | design, Open Question 6 |
| the `macos-app` nightly job | c0025 | proposal, Non-goals; roadmap, Open decisions, row 6 |
| the shape offset of a pad (new) | c0028 | `board-frame`, "Pad holes": the offset moves the hole there, and the copper in KiCad |

**Measured on 2026-10-05**, with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (pinned image), on benches built with `tests/kicad/rules/_rulebench.py` and the scoped canary, identical on both majors unless said:

1. *Fill against a track of another net*, edge gaps from 0.05 mm to 0.65 mm. A violation is reported exactly below these values:

   | zone | class | rule on the pair | board minimum | reported below | KiCad names |
   |---|---|---|---|---|---|
   | 0 | 0.2 | none | none | 0.2 | the net class |
   | 0.1 | 0.2 | none | none | 0.2 | the net class |
   | 0.3 | 0.2 | none | none | 0.3 | "zone clearance" |
   | 0.5 | 0.2 | none | none | 0.5 | "zone clearance" |
   | 0.1 | 0.4 | none | none | 0.4 | the net class |
   | 0.3 | none | 0.2 | none | 0.2 | the rule |
   | 0.3 | 0.4 | 0.2 | none | 0.2 | the rule |
   | 0.1 | none | 0.4 | none | 0.4 | the rule |
   | 0.3 | 0.2 | none | 0.4 | 0.4 | "board minimum" |
   | 0.3 | 0.2 | none | 0.25 | 0.3 | "zone clearance" |
   | 0.3 | none | 0.1 | 0.4 | 0.1 | the rule |

   At fine steps (zone 0.3 mm, class 0.2 mm): reported at 0.280, 0.290 and 0.299 mm, clean at 0.300 and 0.310 mm, on target-9 and target-10 boards as the writer writes them today. So the stored fill is judged as stored on both majors.
2. *Two stored fills of different nets* 0.05 mm to 0.65 mm apart, zone clearances from 0 to 0.4 mm, class clearances from 0.1 to 0.3 mm, and a rule of 0.2 mm: no clearance violation names the two zones. `check_copper` reports those pairs today with the class or rule value.
3. *Fills that KiCad made, under the proposed rule.* On `tests/data/kicad/fill/triad_t9_refilled.kicad_pcb` no pair of a fill and another net's item is closer than the zone's clearance. On the 16 cached demo boards of tag 10.0.6, read with their project files (the corpus holds no rules file for them), 12 have filled zones with a clearance. The rule adds findings on 2 of them and none on the other 10: 3 on one board, all against pads whose drill has an offset (measurement 8), and 6 on another, all against arc tracks, 499.47 µm to 499.50 µm from the fill by the check's lower bound under a zone clearance of 0.5 mm. No straight track, via or pad without an offset is added on any board.
4. *An arc with a copper uuid* that replaces part of a script track of the routed blink: no unconnected item, and no violation names it; with the arc removed, one unconnected item. `read_board` gives the arc the id `derived_id("arc", "kicad", <uuid>)`.
5. *Via kinds* on the four-layer created board, each via with a track on each of its layers: `blind` and `micro` load on both majors and no violation names them; `buried` loads on 10.0.6, and the writer refuses it for target 9 ("'via buried' needs KiCad 10.0").
6. *A pad that differs from its library pad only by `zone_connect`*, each of the four values, on the built blink with its vendored library: no `lib_footprint_mismatch`.
7. *The macOS disk image.* The Homebrew cask `kicad` names the asset `kicad-unified-universal-10.0.6.dmg` of the tag `10.0.6` of the KiCad source mirror, with the SHA-256 `ef4dcd4278c46d3efcd28c8db273d5957d68efda028f6bf79b4811fc5302dc68`; the asset answers with 1 404 303 659 bytes. Task 7.1 downloads it and checks the digest before pinning it.
8. *The offset of a pad's drill.* A through-hole pad row of the rule bench, its drill given `(offset X Y)` by token edit, class clearance 0.2 mm, a track above the pad:

   | offset | gap without the offset | KiCad | `check_copper` today |
   |---|---|---|---|
   | none | 0.5 mm | clean | clean |
   | 0.4 mm towards the track | 0.5 mm | `clearance` | clean |
   | 0.25 mm towards the track | 0.5 mm | clean | clean |
   | 0.5 mm away from the track | 0.1 mm | clean | `copper.clearance` |

   So KiCad keeps the hole at the pad's `at` and moves the copper by the offset. `frame.py` does the opposite: `BoardPad.hole` is `position + offset` and the copper stays at `position`. On the demo board `kicad-demo-10-0-6-pcb-02` (165 pads, 27 with an offset drill) today's check reports 35 clearance findings, 12 of a fill and a pad, 18 of two pads and 5 of a pad and a track, and every one names a pad with an offset drill.

None of these probes is committed. Each becomes a recorded probe or test of this change.

## Goals / Non-Goals

**Goals**
- The board frame puts the copper of a pad with an offset drill where KiCad puts it.
- `check` judges a fill as KiCad's DRC does, where a zone has its own clearance.
- A script can set how a pad joins a pour, bend a track, and use the via kinds the model holds.
- A script author can read pad positions from the command line.
- The macOS oracle of the register runs in CI.

**Non-Goals**
- Zone clearance between two fills; stitching that avoids zones and the board edge; stitch vias of other kinds.
- Pad zone connection for `--target altium`.
- The follow-ups of Decision 13.

## Decisions

1. **The zone's clearance joins the class value.** Measurement 1: without a custom rule the largest of class, zone and board minimum governs; with one, the rule governs and the zone's clearance is replaced, exactly as a class value is on both majors (`rules_over_classes`). So `z` enters "Clearance in force" beside `k`. Rejected: the zone's clearance as a floor above rules, which the rows with a rule refute. Rejected: lowering it into a custom rule in `.kicad_dru`, which c0031 already rejected: KiCad holds the value in the zone, and a rule would say it twice.

2. **Two fills keep today's rule.** KiCad's DRC judges no pair of fills (measurement 2); its filler decides their distance. `check_copper` goes on judging them with the class, rule and board-minimum values, because a stale or hand-made fill that reaches another fill is a real defect, and it does not add the zones' clearances: nothing measured says which of the two the filler keeps between two fills, so adding either could flag a fresh fill. The difference becomes a row of the supported-cases table. Rejected: no longer judging pairs of fills.

3. **`zone_clearance` is an argument of `resolve`, not a field of `RuleSubject`.** `RuleSubject` is the model type that selectors match (`rules-model`); a zone's clearance is not something a selector can name. Rejected: `RuleSubject.zone_clearance`, a model change for a value only the copper check uses.

4. **Fresh fills must stay clean.** The new value is the distance KiCad's filler cuts to, so a fill that KiCad just made sits at that distance, and the check must not report what the filler produces. Two things follow from measurement 3.
   - *Arcs.* The check widens an arc by twice its band so that no violation is missed, which reports every fill that follows an arc at exactly the zone's value. For a value that comes from a zone, the zone's value is judged against the arc narrowed by its band, the shape the check already uses for shorts, so it is a finding only when the true copper is certainly too close; the value without the zone is still judged against the widened arc, so no finding of today is lost. For rule, class and board-minimum values nothing changes.
   - *Proof before merge.* A bench with every kind of copper is refilled by KiCad 10.0.6 and must give no finding of source `zone` (`copper-zoneclr-fresh`). If it gives one, a margin of at most 1 µm is taken from the zone's value, the bound of KiCad's own tolerance at the boundary; a larger shortfall stops the part. The corpus count is recorded, not gated: a demo's stored fill may be stale.
   - Rejected: a fixed margin from the start. Nothing measured asks for one on straight copper, vias or pads, and c0031's `H-K-ZONE-GEOM` puts a refilled fill at the clearance or up to 5 µm beyond it.

5. **Pad requests: a setting made in KiCad wins unless the request is locked.** That is the rule of zones and of fields, so a script author learns it once. A pad without a setting on the board takes the request, so a request added after the first build applies; a pad that carries another setting keeps it, with an info that says how to force the script's value. Rejected: the script always wins: a connection set in the board editor would be undone by every build, silently. Rejected: the board always wins, a pad without a setting included: a request added later would never apply.

6. **The pad functions live in `backends/kicad/zones.py` and take one footprint.** The codes are `kicad.pad.*`, which pass through the closed tables of the build and of the lens unchanged, so no living table is modified. The lens loops over footprints, as it does for fields. Rejected: `layout.*` codes, which need a MODIFIED "Layout issue codes".

7. **An arc step is `(mid, end)`.** It is the three-point form of the model and of KiCad's file, exact in integers, with the start given by the path. Rejected: centre and angle, which need trigonometry and a rounding rule. Rejected: a fillet helper (`radius=`) between two segments: its tangent points are irrational; a later helper can compute them, round, and emit an arc step.

8. **Via kinds: checked spans, target left to the writer.** `resolve_copper` checks that the two layers fit the kind; it knows no target. The board writer already refuses `buried` for target 9 with exit 7 (measurement 5). Rejected: writing a `buried` via as `blind` on target 9: not measured, and it changes what the script said.

9. **New intent fields come last and have defaults.** `ViaStep(…, kind="through")` and `ViaIntent(…, kind="through", layers=None)` compare equal to the values earlier scripts and tests build, and `copper.py` reads intents by attribute with the same defaults.

10. **`pads` lists board-frame records and takes `--origin`.** It prints `BoardPad`, which exists since c0028. The DSL's frame is offset by a DSL constant, so the command takes a generic origin and `docs/dsl.md` names the value. Rejected: `--frame dsl`, which gives the CLI a DSL concept and has no meaning for a board Fenolite did not build. Rejected: folding the query into `net` or `region` of c0066: they answer other questions, and `pads` needs nothing of c0066.

11. **The macOS job pins the disk image and mounts it.** Rejected: `brew install --cask kicad`: the cask follows KiCad's releases, so the job would change its meaning on the day of a release, and a moving version cannot back a `KICAD-VERIFIED (10.0.x)` label. Rejected: a run on every pull request: 1.4 GB and macOS minutes for what `kicad-10` already gates. The fallback when the binary does not run from the mounted volume is in the spec.

12. **Changes in flight.** No open change holds a delta of `copper-check` or `manual-copper`, nor of the requirements this change modifies in `board-frame`, `design-dsl` and `kicad-oracle` (checked on 2026-10-05; c0066 holds an ADDED requirement of `board-frame`, which reads `BoardPad.copper` and follows the repair). c0066: if "Paged results" is archived first, `pads` declares `paged = "pads"` (task 6.1). c0067: if "Backend modules declare their evidence" is archived first, this change adds no backend module, so nothing is to declare. c0025 holds `ci-baseline` deltas of other requirements, and `nightly.yml` is a new file.

13. **Follow-ups not taken.** Each was pointed at v0.2a by an earlier text and is not in this change:

| follow-up | pointed at v0.2a by | goes to | why |
|---|---|---|---|
| rule kinds for annular width, hole-to-hole, hole clearance, zone connection, silk clearance | c0026, c0031 | v0.2b, with the full rules | the roadmap already notes the overlap |
| export presets | c0024, Decision "free options" | v0.2b | no acceptance item of v0.2a needs them; c0064's template covers the assembly tables |
| outline snapping tolerance and edge items of footprints | c0025, Open Questions | v0.2b | 1 of 3 open demo outlines closes with 1 µm; the other 2 need footprint edge items, a reader change |
| per-command result schemas | c0025, Open Questions | with the v1.0 freeze, unless the maintainer wants them earlier | 25 commands after v0.2a; they are frozen at v1.0 anyway |
| `inspect` of `.kicad_pro` and `.kicad_dru`, `inspect --detailed` | c0013, Non-goals | unscheduled | c0039 holds a MODIFIED "Inspect command"; nobody asked |
| stitching that avoids zones and the board edge | c0028, Non-Goals | v0.2b | needs zone fills at build time |

14. **The pad shape offset is repaired first, in the frame.** Measurement 8 refutes the fact that `docs/formats/kicad/frame.md` took from the format page ("the offset is given from the pad centre"): the page names the drill, the program moves the shape. `frame.py` changes in one place: the hole stays at `position`, and every copper entry of the pad is moved by the offset before the placement transform, so the offset turns with the pad. `BoardPad.position` stays the pad's `at`, where tracks end, which is inside the copper of every sane pad. Everything that reads `BoardPad.copper` follows without a change of its own: the copper check, the stitch clearance, `pads`, the views of c0066. This part comes before the zone clearance, because the zone value would otherwise add false findings on the same pads. Rejected: leaving it for a separate change: it is a wrong verdict of `check` in v0.1, and the zone clearance cannot be accepted on the corpus while it stands. Not touched: the Altium writer's reading of a KiCad offset drill, which c0043 leaves in the pad's opaque slots.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/backends/kicad/frame.py` | the hole at `position`; copper entries moved by the drill's offset |
| `tests/data/libs/Frame.pretty/Frame_Offset.kicad_mod` (authored) | a through-hole `rect` pad of 2 mm × 2 mm with `(drill 0.8 (offset 0 -0.4))` |
| `src/fenolite/checks/clearance.py` | `resolve(a, b, *, zone_clearance=None)`; source `zone`; `max_value` over zone clearances |
| `src/fenolite/checks/copper.py` | passes the zone's clearance for pairs of one fill and one other item; the narrowed arc for a zone value |
| `src/fenolite/backends/kicad/zones.py` | `PadZoneRequestLike`, `apply_pad_connections`, `keep_pad_connections`, `PAD_ZONE_ISSUE_CODES` |
| `src/fenolite/backends/kicad/copper.py` | `ArcStepLike`; arcs, via kinds and spans in `resolve_copper`; arcs in `merge_copper` |
| `src/fenolite/dsl/part.py`, `dsl/convert.py` | `Part.zone_connection`, `PadZoneRequest`, `pad_zones(design)` |
| `src/fenolite/dsl/intents.py` | `arc_to`, `ArcStep`, `kind` and `layers` |
| `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py` | `pad_zones=`; `result.preserved.pad_zones`; `result.copper.arcs` |
| `src/fenolite/cli/cmd_pads.py` (new) | `fenolite pads` |
| `.github/workflows/nightly.yml` (new) | job `macos-app` |
| `tests/kicad/rules/_rulebench.py`, `tests/kicad/copper/_copperparity.py` | `fill_via`, `fill_pad`; the zone clearance cases |
| `tests/kicad/_probes.py`, `docs/evidence/kicad/probes/*.json` | `pcb-frame-pad-offset`, `copper-zoneclr-*`, `copper-zoneclr-fresh`, `copper-fill-fill`, `pcb-frame-arc*`, `pcb-frame-via-*`, `pad-zone-lib` |
| `tests/corpus/test_copper_offset_census.py`, `tests/corpus/test_zone_clearance_census.py` (new) | the two recorded counts |
| `docs/dsl.md`, `docs/copper.md`, `docs/formats/kicad/copper.md`, `docs/formats/kicad/frame.md`, `docs/formats/kicad/libraries.md`, `docs/cli-contract.md`, `docs/roadmap.md` | the six parts; the corrected fact about the drill offset |

`result.copper` of `build` gains `arcs` (created), which "Copper intents in a build" allows as an addition.

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0360 | https://github.com/Homebrew/homebrew-cask/blob/main/Casks/k/kicad.rb | BSD-2-Clause | the asset name and the SHA-256 of the 10.0.6 macOS disk image, checked again by download |
| S-0361 | https://github.com/KiCad/kicad-source-mirror/releases/tag/10.0.6 (`kicad-unified-universal-10.0.6.dmg`, run as an oracle) | GPL-3.0-or-later tool, run as a subprocess, nothing copied | the `kicad-cli` of the nightly job |
| S-0362 | https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows | CC-BY-4.0 | `schedule` and `workflow_dispatch` |
| S-0363 | https://docs.github.com/en/actions/reference/runners/github-hosted-runners | CC-BY-4.0 | the macOS runner labels |

S-0364 stays unused. The DRC behaviours measured above rest on S-0020 and S-0029, the two `kicad-cli` oracles already registered.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-FRAME-OFFSET | The `(offset X Y)` of a pad's drill moves the pad's copper and leaves its hole at the pad's position, turned with the pad, on 9.0.9 and 10.0.6 | `tests/kicad/frame/test_pad_offset.py` | probe `pcb-frame-pad-offset` `equal` on both majors: four rows with KiCad's verdict as expected and `check_copper`'s equal to it |
| H-K-COPPER-ZONECLR | KiCad's DRC judges a stored fill against a track, via or pad of another net with the largest of the zone's own clearance, the class clearance and the board minimum when no custom rule governs the pair, and with the rule's value alone when one does; it reports no clearance between two stored fills | `tests/kicad/copper/test_copper_parity.py -k "zone_clearance or fill_fill"`; `tests/kicad/zones/test_zone_oracle.py -k fresh_fill` | every `copper-zoneclr-<case>` probe `equal` on 9.0.9 and 10.0.6; `copper-zoneclr-fresh` `absent` on 10.0.6; `copper-fill-fill` recorded |
| H-G-FRAME-ARC | An arc whose uuid is a copper uuid loads on 9.0.9 and 10.0.6, keeps its uuid after `pcb upgrade --force`, and joins the copper at its two end points | `tests/kicad/frame/test_copper_oracle.py -k arc` | `pcb-frame-arc` `absent`, `pcb-frame-arc-cut` `present`, `pcb-frame-arc-keep` `equal` |
| H-K-COPPER-VIAKINDS | A `blind` and a `micro` via load on 9.0.9 and 10.0.6 and a `buried` via on 10.0.6, join the tracks of their two layers, and get no violation of their own when their sizes meet the project minimums | `tests/kicad/frame/test_copper_oracle.py -k via_kinds` | the three `pcb-frame-via-*` probes `absent` on their majors |
| H-K-PAD-ZONE-LIB | A pad of a board footprint that differs from its library pad only by a `zone_connect` child makes neither 9.0.9 nor 10.0.6 report `lib_footprint_mismatch` | `tests/kicad/zones/test_pad_zone_requests.py` | probe `pad-zone-lib` `absent` on both majors, for the four values |
| H-K-CI-MACOSAPP | `kicad-cli` of the 10.0.6 macOS disk image runs from the mounted, read-only volume on a GitHub-hosted macOS runner without a display, reports `10.0.6`, and passes `tests/kicad` | the `macos-app` job, run by `workflow_dispatch` | the job is green; the row holds the run's URL, or the fallback that was applied |

All six start `INFERRED`, with the measurements of "Context" as their first record. `H-G-FRAME-OFFSET` corrects a fact that `H-G-FRAME-SHAPE` covered without a test of it; that row keeps its level for the shapes it did test, and its text gains a pointer to the new row.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| copper and hole of a pad with an offset drill | KICAD-VERIFIED (9.0.x, 10.0.x) | `pcb-frame-pad-offset` |
| zone clearance for a fill against a track, via or pad | KICAD-VERIFIED (9.0.x, 10.0.x) | `copper-zoneclr-*` probes |
| two fills | documented difference | `copper-fill-fill`, the table row |
| fresh fills clean | KICAD-VERIFIED (10.0.x) | `copper-zoneclr-fresh` |
| pad zone requests written and merged | mechanical | unit tests of `zones.py`, the lens and the DSL |
| no library mismatch from a pad setting | KICAD-VERIFIED (9.0.x, 10.0.x) | `pad-zone-lib` |
| arcs and via kinds | KICAD-VERIFIED on their majors | `pcb-frame-arc*`, `pcb-frame-via-*` |
| `pads` | the board read's level with `frame.EVIDENCE` | unit tests |
| the nightly job | INFERRED until its first green run | `H-K-CI-MACOSAPP` |

`copper.EVIDENCE` and `checks.copper.EVIDENCE` keep their levels; this change adds hypothesis ids to them only where the audit of c0067 asks for it.

## Budget (9.75 days)

| part | days |
|---|---|
| registers, probes recorded | 0.5 |
| pad shape offset: frame, fixture, canaries, census | 1.0 |
| zone clearance: resolver, check, arcs, canaries, fresh-fill bench, census, table | 1.75 |
| pad zone connection: DSL, build, rebuild, oracle, docs | 1.75 |
| arcs: DSL, resolve, merge, oracle | 1.5 |
| via kinds: DSL, resolve, oracle | 1.0 |
| `pads` command | 0.75 |
| `macos-app` job | 0.75 |
| documentation and closing | 0.75 |

Cut order: (1) the `macos-app` job, whose fallback can cost a day; (2) via kinds; (3) arcs; (4) `pads`; (5) pad zone connection. The pad shape offset and the zone clearance are not cut: the first is a wrong verdict of `check`, the second a case where `check` passes what KiCad's DRC rejects.

## Risks / Trade-offs

- **New findings on existing boards.** A board whose fills are closer to other copper than their zone's clearance gets `copper.clearance` errors, and `build` refuses to write it under the copper guard. Mitigation: a rebuild drops the fills of a layout that changed (`layout-lens`, "Zone fills and the staleness digest"), so only fills that KiCad did not make for this layout are judged; `--copper-check warn` writes anyway; KiCad's DRC reports the same pairs.
- **A fresh fill flagged.** Decision 4: proved on a refilled bench before the rule merges, with a bounded margin as the fallback, and counted on the corpus.
- **Boards whose verdict changes because of the offset.** A pad with an offset drill moves in every reader of the frame. That is the repair; the census records, per demo board, how many findings name such pads before and after.
- **A pad request that seems ignored.** An unlocked request does not replace a setting the board carries. Mitigation: the info names both values and the three ways out, and `result.preserved.pad_zones.kept` lists the pads.
- **Arcs in the stitch and copper checks.** Both already treat arcs within a band; a script arc is one more arc.
- **The nightly job is not watched.** A scheduled job fails silently. Mitigation: `workflow_dispatch` for a run before a release, and the release record of v0.2a names the last run.
- **A second KiCad build to maintain.** The macOS job adds a platform to keep green. It is the platform most register rows were confirmed on.

## Migration Plan

- `check` and the copper guard of `build` may report `copper.clearance` with source `zone` where they reported nothing, and stop reporting false findings on pads with an offset drill. `CHANGELOG.md` says both, with `--copper-check warn` as the way to write anyway.
- `BoardPad.hole` of a pad with an offset drill moves back to the pad's position. Callers that drilled at `hole` now drill where KiCad drills.
- Scripts and tests that build intents keep working: new arguments and fields have defaults.
- No file format changes. A board built with a pad request holds `(zone_connect N)`, which the reader has modelled since c0031.
- Reverting a part removes its code and its rows; the parts share no state.

## Open Questions

- **Clearance overrides of pads and footprints.** A pad or a footprint may carry its own `(clearance …)`; 3 of the 16 cached demo boards do, on 11 items, with values from 0.125 mm to 1.7 mm. The copper check does not model them, and how KiCad combines such an override with a zone's clearance is not measured. Default: out of this change; the census of task 3.6 also counts the findings that name such a pad or a pad of such a footprint, and a follow-up decides with that number.
- **Via sizes of micro vias.** KiCad's classes hold `microvia_diameter` and `microvia_drill`, which the model's `NetClass` does not. Default: a `micro` via takes its sizes from the call, else from `via_diameter` and `via_drill` as any via.
- **Should `zone_connection` also be settable per part** (the footprint-level `zone_connect`, which both readers keep opaque)? Default: no; per pad covers the cases named so far.
- **Per-command result schemas.** Default in Decision 13: with the v1.0 freeze. The maintainer may want them in v0.2b for the agent guide.
- **The digest of the disk image.** It comes from a third party's package definition. Default: task 7.1 downloads the asset from KiCad's release page, computes the digest and pins what it computed, and records both values when they differ.
