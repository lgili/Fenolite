## Context

The review of 2026-10-05 of the gaps to a complex board gives this change three gaps of milestone v0.4 (`docs/roadmap.md`, "The complex board, c0100–c0120"; the branch the proposal was written on called the group v0.2c), owned by no change and no roadmap line until then: net-tie pad groups reported as shorts, no way to accept a finding, and DRC severities and exclusions that the model cannot set.

**What exists** (read at `origin/dev` `9aba2dff` on 2026-10-07; no source file there mentions `net_tie`):
- `pcb.py` and `mod.py` keep `net_tie_pad_groups` as an opaque footprint child. `FootprintInstance` and `FootprintDef` have no field for it.
- `checks/copper.py` judges every pair of items of different nets (`_judged`). The living "Supported cases are documented against KiCad's DRC" still says "net-tie pad groups reported as shorts" and "KiCad project severity overrides and exclusions not applied", both documented differences; since c0068 it also holds the zone's own clearance (`H-K-COPPER-ZONECLR`) and the scenario "Zone rows of the table".
- `drc_json.issue_severity` gives `info` to an excluded entry. `DrcViolation.comment` is read (`backends/kicad/drc.py`) and never shown.
- `pro.py` neither reads nor writes `rule_severities` or `drc_exclusions`; `update_project` keeps both verbatim. `canary.py` reads `rule_severities/clearance` and is inconclusive, reason `clearance-ignored`, when it is `ignore`.
- `Design.findings` holds `issues` only; the build writes `findings.json` without any. `model/canonical.py` omits a field at its default, so a new field with a default changes no byte of a document that does not use it.
- `check` has two pipelines. `run_checks` (`checks/stages.py`) takes a KiCad project through `STAGE_ORDER`: `model.validate`, `erc.kicad`, `copper.clearance`, `zone.fill`, `drc.kicad`, `parity`, `netlist.assignment_compare`, `roundtrip`, `roundtrip.rt2`, `render`. `run_document_checks` (`checks/documents.py`, c0088) takes Altium documents through `DOCUMENT_STAGES`, which holds `copper.clearance` and `parity` and no DRC stage. `drc_json.RESERVED_SUFFIXES` is `rules-not-loaded`, `rules-unchecked`, `parity-unchecked`.
- `build --target altium` has a copper guard of its own (`cmd_build.altium_copper_guard`; c0088's "Copper guard in an Altium build"): it refuses shorts and reports other copper errors as warnings. What the Altium build does not write is counted per kind in `backends/altium/lower.py` and reported once per kind with `altium.not-lowered`: a warning for a kind of the closed set `LOSS_KINDS`, whose loss changes the board that is made, an info otherwise.
- Finding families that came after the proposal: `kicad.erc.*` (stage `erc.kicad`, c0062) and `parity.*` (c0072). `explain` (c0066) needs a table in `cli/data/explain.toml` for every issue code.
- Items in `where`: `REF-PIN` for a pad, `REF` for a footprint, otherwise the entity's locator, such as `/kicad_pcb/segment[12]`, which shifts when items are added or removed.
- An authored footprint can already draw a copper bridge (`Footprint.line(…, layer="F.Cu", width=…)`), and its pads may overlap.
- c0029, Decision 10, rejected honouring project severities and exclusions in the copper check, because a GUI preference would then silence the guard. c0069 leaves the exclusions of a renamed footprint as an Open Question, their stored form unmeasured.

**Public data** (S-0018, S-0042, S-0058; read for facts, nothing copied):
- KiCad's `NetTie.pretty` holds 12 footprints at 9.0.9 and 10.0.6. Each writes `(net_tie_pad_groups "1, 2")` (or `"1, 2, 3"`, `"1, 2, 3, 4"`) after `attr`, keeps its pads 0.5 mm to 2 mm apart edge to edge, and joins them with a filled `fp_poly` on each copper layer. The bridged solder jumpers of `Jumper.pretty` use the same token.
- The demo boards of tag 10.0.6 hold 12 net-tie footprints on 3 boards (`kicad-demo-10-0-6-pcb-11`, `-13`, `-16`): one `NetTie-2_SMD_Pad0.5mm` and eleven bridged jumpers, with both spellings `"1, 2"` and `"1,2"`; on 8 of them each pad number names two pads. Their grouped pads are 250 µm to 2.1 mm apart, at least the class clearance in force (100 µm to 200 µm). Today's copper check, run with each board's own project file, gives no finding that names one of their pads. The defect therefore needs grouped pads that touch, or a clearance above their gap: custom Kelvin and star-ground footprints, or a high-voltage class.
- `kicad-demo-10-0-6-pro-01` stores five exclusions as `["<type>|<x>|<y>|<uuid>|<uuid>", "<comment>"]`, `x` and `y` in nm, the nil uuid when the entry has one item.
- A demo project holds the `rule_severities` keys of the KiCad that last saved it: four different sets of 36 to 58 keys at tag 9.0.9.1, eight sets of 36 to 63 at 10.0.6. Six keys of the packaged templates appear in no 9.0.9.1 project (`footprint_symbol_field_mismatch`, `missing_tuning_profile`, `text_on_edge_cuts`, `track_not_centered_on_via`, `track_on_post_machined_layer`, `tuning_profile_track_geometries`), and two keys absent from the templates appear in most (`hole_near_hole`, `overlapping_pads`). The packaged 9 template holds the 62 keys of the 10 template, from which it was derived. So the demo files cannot say which keys 9.0.9 applies.

**Measured on 2026-10-05** with `kicad-cli` 10.0.6 (macOS) and 9.0.9 (the pinned image), `pcb drc --format json --severity-all -o drc.json <board>`, on benches written in the 9.0 format so that both majors read the same bytes:

1. *Net-tie bench.* A `{}` project (KiCad's Default class, 0.2 mm), every case on `F.Cu` on nets of its own, and each of the first five also without the token. A control pair of tracks 0.1 mm apart gave `clearance` in every run.

   | case | footprint | with the token | without it |
   |---|---|---|---|
   | official | two 0.5 mm round pads 0.5 mm apart, a filled `fp_poly` joining them | nothing | `shorting_items` and `solder_mask_bridge`, graphic against each pad |
   | touching | two 1 mm square pads overlapping by 0.2 mm | nothing | `shorting_items`, `solder_mask_bridge` |
   | close | the same pads 0.1 mm apart | nothing | `clearance` |
   | track near | `official`, and a track of pad 1's net ending 0.1 mm from pad 2 | `clearance` (track, pad 2) | the same, and the graphic's shorts |
   | track on | `official`, and a track of pad 1's net ending at the centre of pad 2 | nothing | the graphic's shorts only |
   | two groups | four overlapping pads in a row, groups `"1, 2"` and `"3, 4"` | `solder_mask_bridge` (pads 2, 3) only | — |
   | ungrouped touching | three overlapping pads, group `"1, 2"` | `solder_mask_bridge` (pads 2, 3) only | — |
   | ungrouped close | group `"1, 2"`, pad 3 0.15 mm from pad 2 | nothing | — |
   | groups close | groups `"1, 2"` and `"3, 4"`, pads 2 and 3 0.15 mm apart | nothing | — |
   | spelling | `touching` written `"1,2"` | nothing | — |
   | three | three overlapping pads, group `"1, 2, 3"` | nothing | — |

   Both majors gave the same entries, counting `shorting_items`, `clearance`, `solder_mask_bridge` and `unconnected_items`; `track near` also gave `unconnected_items` between pad 1 and the track in both runs. So with the token KiCad judges no copper pair inside the footprint, whatever the groups, and still judges a track against its pads. In `track on` KiCad reports no short between the track and pad 2 even without the token, and no missing connection: it takes the track as joined to pad 2, as it does for the via of `H-K-VIA-RENET`.
2. *Exclusions on a public demo, 10.0.6.* `kicad-demo-10-0-6-pcb-01` with its own project: 288 entries, the 5 stored exclusions applied (`excluded: true`), each with its stored text as `comment` and its severity kept; the project file was not written. A via's exclusion holds the via's position; an overlap's holds a position that neither item's reported `pos` gives. Rewriting the keys: `x` + 1 nm, `x` + 0.1 mm, position 0, or the two uuids swapped excluded nothing, without a message; the plain-string form excluded all 5, with an empty `comment`; a sixth key naming no item was ignored silently.
3. *Exclusion bench, both majors, equal results.* A clearance pair, a lone via at (30.123456, 20.654321) mm and partial project files:
   - `[["via_dangling|30123456|20654321|<via uuid>|<nil uuid>", "test point"]]` excluded the via's entry, severity `warning`, `comment` "test point"; the plain string did the same with `comment` "".
   - `x` + 1 nm, or another uuid: nothing excluded, no message.
   - `clearance|10000000|10000000|<first uuid>|<second uuid>`, the first item's reported `pos` and the uuids in report order: excluded; the uuids reversed: not.
   - `rule_severities.clearance` `warning` turned both clearance entries into warnings; `ignore` removed them, and 10.0.6 listed `clearance` in `ignored_checks` (`H-K-PRO-SEV` holds for a partial project).
   - No project file was written, and an entry not excluded carries no `excluded` key.
4. *Severity keys.* On 10.0.6 the 62 template keys, `overlapping_pads` and an invented key, all `ignore`: `ignored_checks` listed exactly the 62 template keys, the other two were ignored silently, and no entry remained; the text report (`--format report`) lists the same 62 checks by description. On 9.0.9 the 62 template keys at `ignore` left no entry on the bench, so 9.0.9 applies the keys of its three checks; neither its JSON nor its text report lists ignored checks, and `hole_near_hole`, `overlapping_pads` or `zone_has_empty_net` alone at `ignore` changed nothing on that bench. Which other keys 9.0.9 applies cannot be read from a run.
5. *Options.* `pcb drc --help` is the same on both majors, except `--refill-zones` and `--save-board` (10.0.6 only).

None of these runs is committed; each becomes a probe of this change.

## Goals / Non-Goals

**Goals**
- A footprint's net-tie groups are model data, read, written and authored, and the copper check honours them as KiCad does for the pads it ties.
- One finding can be accepted, with a reason, by name, in the script; the acceptance shows in every reply, and a waiver that no longer matches is reported.
- A script sets the severity of a KiCad DRC check; `check` explains and audits the exclusions a project stores.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- Copper graphics in the copper check: nowhere, because KiCad's DRC judges them and c0029 documents the difference (`copper-check`, "Copper items and their shapes").

## Decisions

1. **Net-tie groups are footprint data, projected on read.** `FootprintInstance.net_ties` and `FootprintDef.net_ties` hold the groups as tuples of pad numbers, in file order. The readers project `net_tie_pad_groups` and keep the child as a projected slot, as they do for `zone_connect` on library pads; a changed field on a read footprint gives `kicad.board.projection-read-only`. Only authored definitions are written from the field. Rejected: a lookup of the opaque child inside the copper check, because `checks` imports no backend. Rejected: a component-level kind, because KiCad stores the groups per footprint.

2. **Only pads of one group are skipped.** The copper check does not judge two pads of one footprint whose numbers share a group (measurement 1: `touching`, `close`, `spelling`, `three`). KiCad also skips pads outside a common group (`two groups`, `ungrouped touching`, `ungrouped close`, `groups close`) and reports only a mask bridge there. A touch between a tied pad and a pad the designer did not tie is a defect, so Fenolite keeps judging it: a documented difference, Fenolite may report more. Rejected: mirroring KiCad and skipping every pad pair of a net-tie footprint.

3. **Everything else is judged as before.** A track, arc, via or fill of a tied net against the other pads of the tie is judged (measurement 1, `track near`). Where KiCad re-nets a track that ends inside the other pad (`track on`), the copper check keeps reporting `copper.short`, the blind spot it was written for. Graphics stay out of the check, so the official bridge never shows. Rejected: exempting every item of the two tied nets near the footprint, which KiCad does not do and which would hide a track routed across the tie.

4. **Authoring.** `Footprint.net_tie(*numbers)` declares one group of at least two numbers. `definition` checks that every number names a pad and that no number is in two groups. The emitter writes `(net_tie_pad_groups "1, 2")` right after `attr`, with `", "` between numbers, as KiCad's library does; the readers also accept `"1,2"`. Rejected: a `net_ties=` argument of the constructor, because pads are declared after it.

5. **Waivers are design data in the findings layer.** `design.waive(…)` records a `Waiver(name, code, items, reason, min_gap=None)` in `Design.findings.waivers`. The build writes it to `.fenolite/findings.json`; `check` reads the waivers of a built project from there, and the copper guard from the model it builds. Rejected: a `waivers.toml` beside the script, a second source file whose copy the build would have to carry into the output folder for `check`. Rejected: the rules layer, because a rule is lowered to KiCad files and judged by both checks, while a waiver is applied by Fenolite only.

6. **What a waiver says.** A code, the names of the finding's items, a reason, and an optional bound.
   - Codes: `copper.short`, `copper.clearance`, `copper.zone-overlap`, or `kicad.drc.<suffix>`; the verdicts `rules-not-loaded`, `rules-unchecked` and `parity-unchecked` are not findings and are refused (Decision 17).
   - Items: one name per item, as `where` prints it (`REF-PIN`, `REF`, a locator, `@x,y`), with `*`, `?` and `[…]` globs. A finding matches when each of its items matches one name, one to one, in any order. A `Part` stands for its reference. Items without a stable name take `*`.
   - Reason: one non-empty line, printed with every match.
   - Shorts (`copper.short`, `kicad.drc.shorting-items`) take exact names only: an intended short is a net tie, and a waiver must not cover a second one.
   - `min_gap` belongs to `copper.clearance` only: a finding matches when its gap is at least `min_gap`, so a closer gap stays an error. A glob in a `copper.clearance` waiver requires it. A DRC finding has no distance in the report (`H-K-DRC-JSON`), so `min_gap` is refused there; the copper check still judges the copper twin of a KiCad clearance entry.
   - `name` defaults to `<code>:<items joined by ",">`; two waivers of one name are refused, which also refuses a repeated waiver.
   - Rejected: matching by position, KiCad's own key, which a move breaks (measurement 3). Rejected: matching by net, which covers every item of the net.

7. **A waived finding stays listed.** Its issue keeps its code, takes severity `info` and ends with ` (waived by <name>: <reason>)`, so the exit code no longer counts it and nothing is hidden. KiCad's excluded entries already map to `info` the same way. Rejected: a separate code `check.waived`, which loses the finding's kind for an agent that filters by code. Rejected: dropping waived findings.

8. **KiCad exclusions are read, never written.** A stored key holds the marker position to the nanometre (measurement 2), and the report gives item positions only; for a footprint overlap the marker is elsewhere. Fenolite cannot write a key that applies. Rejected: lowering `kicad.drc.*` waivers to `drc_exclusions`.

9. **Stale waivers and exclusions.** A waiver is judged when the stage of its code ran with a verdict: the copper stage for `copper.*`, the DRC stage with a report for `kicad.drc.*`. A judged waiver that matched nothing gives `check.waiver-unmatched` (warning). A stored exclusion is live when an excluded entry has its type and its uuids in order; otherwise it gives `check.exclusion-stale` (warning), `moved` when an entry with those items is reported again, `gone` when none is.
   - KiCad does not repeat entries of `clearance`, `hole_clearance` and `unconnected_items` on large boards (`H-K-DRC-REPEAT`), nor every short on touching copper (`H-K-VIA-RENET`). A waiver or exclusion of one of these four types is applied but never judged stale, so two `check` runs stay equal outside what "Check output is deterministic" already allows.
   - Rejected: judging them and widening "Check output is deterministic"; a warning that comes and goes teaches an agent to ignore it. Rejected: refusing waivers of these types, which would leave the KiCad twin of a waived copper finding an error.

10. **Severities are script data, keyed by code.** `design.rules.severity(code, level)` records `RuleSet.severities[code] = level` for a `kicad.drc.<suffix>` code. The lowering writes `/board/design_settings/rule_severities/<key>`, the suffix with `-` turned into `_`, on synthesis and on update; keys the script does not set keep their value. `pro.SEVERITY_KEYS[target]` is the key set of the target's packaged template: exact for 10 (measurement 4), `INFERRED` for 9, whose template was derived from 10's. A key outside it gives `kicad.project.unknown-check` (error, droppable), and `--allow-lossy` drops it with `kicad.project.dropped-check`.
    - `copper.*` codes are refused: a copper finding is accepted one by one. `ignore` for `kicad.drc.clearance` is refused: the check canary needs clearance entries (`clearance-ignored`).
    - Rejected: KiCad's raw key, which an agent never sees in a reply. Rejected: writing any key, because 10.0.6 ignores an unknown key silently (measurement 4), so a typo would do nothing. Rejected: a 9 list read from the demo projects, whose key sets follow the KiCad that last saved them.

11. **Exclusions reach `checks` through a new protocol.** `StoredExclusion(type, position, uuids, comment)` and `ExclusionSource.stored_exclusions(project)` in `backends.base`; `KicadBackend` reads the project file of the copy set. `run_checks` passes them to `drc_stage`, which also appends ` (excluded in the project: <comment>)` to an excluded entry's issue. Rejected: a new field of `DrcOutcome`, which would modify the living "Oracle protocol" for data that only one stage reads. Rejected: reading project JSON inside `checks`.

12. **The guard applies copper waivers before its mode** (both guards: Decision 15 for the Altium target). A waived finding is `info` in both modes, so it neither refuses the build nor turns into a warning. `result.copper_check.waivers` lists matched and unmatched names; the guard emits no new code, and `check` reports stale waivers. Rejected: `check.waiver-unmatched` from the guard too, which would report one stale waiver twice in a build-and-check loop and put a `check.*` code into the `build` envelope.

13. **Changes in flight** (checked on 2026-10-05, and again at `origin/dev` `9aba2dff` on 2026-10-07).
    - c0068 and c0062 are archived. The delta of "Supported cases are documented against KiCad's DRC" is regenerated from the living text: c0068's clause on the zone's own clearance, its clause on pairs of two fills and its scenario "Zone rows of the table" are kept, and this change replaces the net-tie clause, extends the graphics clause and the severities clause, and adds one scenario.
    - "Pairs that are judged" and "Copper stage issue codes": the living texts are the ones the deltas were made from, no open change on `dev` holds a delta of either, and no other proposal of v0.4 modifies them.
    - Open on `dev`, closed by `0.3.0`: c0088 holds MODIFIED "Copper guard before writing" and ADDED "Copper guard in an Altium build" and "Document check pipeline" (c0090 modifies the last). This change modifies none of them; "Waivers in the copper guard" and "Waivers in the check" extend them by name, so this change lands after they are living (Prerequisites).
    - c0113 adds placement findings to `check`, and c0120 marks KiCad's report limits per type. Both add; a waiver takes any `kicad.drc.*` type, and c0113's codes join the waivable set only by a change of "Waivers in the DSL".
    - Schemas: `board.json` and `library.json` are also regenerated by c0126 (on `dev`), c0096 and c0099; `rules.json` by c0113, c0104 and c0105. All additions; the later change regenerates.
    - Rejected: showing the exclusion comment by modifying "DRC findings as issues", and passing exclusions in `DrcOutcome`: two long living requirements copied for one sentence each.

14. **Beside c0097, c0096 and c0126.**
    - c0097 (on its branch) gives `CopperRef` a `footprint_id` and a finding a `relation`, `intrinsic` for two pads of one footprint. A net-tie pair is a subset of `intrinsic`. On `dev` the skip reads `BoardPad.footprint_id`, which exists; if c0097 is there first it reads `CopperRef.footprint_id`, the same value. c0097 requires that its metadata change no message: the suffix ` (waived by …)` is added by the stages and the guards, never inside `check_copper`, so both hold.
    - c0096's placement search reads copper findings straight from `check_copper`. A waiver is applied after that, by a stage or a guard, so a waived finding still counts there as a finding. Changing that is c0096's.
    - c0126 lets `FootprintInstance.graphics` hold copper graphics and asks a consumer that cannot use them to count them. The copper check does not judge graphics, so the bridge of a net tie stays unseen (Decision 3) and is counted where c0126 says. A later change that judges copper graphics must skip a pad against a copper graphic of its own net-tie footprint: KiCad judges neither (measurement 1, `official`).

15. **Waivers on the second backend.** A waiver is Fenolite's, not KiCad's, so it follows the copper check wherever that runs.
    - `run_document_checks(…, waivers=())` passes the waivers to its `copper.clearance` stage. `fenolite check` on a built Altium project passes the waivers of its `.fenolite/` model, as it does for a built KiCad project. That pipeline has no DRC stage, so a `kicad.drc.*` waiver is listed under `unjudged` as `stage-not-run`, and no exclusion is read.
    - The copper guard of `build --target altium` applies the design's `copper.*` waivers before its mode. A waived short is `info`, so it does not refuse the build; `result.copper_check.waivers` has the same keys as on KiCad.
    - An Altium project that Fenolite did not build has no `.fenolite/`, so it has no waiver, like a native KiCad project (Open Questions).
    - Rejected: waivers on KiCad only. A script built for both targets would pass `check` on one and fail it on the other for the same accepted finding.

16. **Net ties and severities on the second backend: reported, not written.**
    - `Footprint.net_tie` on an Altium build: the pads are written, and the footprints that have groups are counted under the kind `net-tie` in `backends/altium/lower.py`, which gives one `altium.not-lowered` per kind. The kind is not in `LOSS_KINDS`: nothing of the board that is made is lost, so the severity is `info` and a write is not refused.
    - `design.rules.severity` on an Altium build: no severity is written; the codes are counted under the kind `severity`, also outside `LOSS_KINDS`. A severity is no `RuleKind`, so c0084's rule table, in which every kind has exactly one row, is not touched.
    - Import: `AltiumBackend` reads no net-tie group, so `FootprintInstance.net_ties` is `()` on an imported board and the copper check judges every pad pair. `docs/altium.md` says so.
    - Rejected: writing a net tie into a `.PcbDoc` now. How Altium marks one is a format fact that needs a public source and a row in `docs/formats/altium/` first; none is registered.
    - Rejected: the info in `lens/altium.py`, where the proposal first put it. On `dev` the count per kind lives in the lowering, and c0126 sends the build through it.

17. **Verdicts and families outside a waiver.** The refused suffixes are the members of `drc_json.RESERVED_SUFFIXES` (`rules-not-loaded`, `rules-unchecked`, `parity-unchecked`): verdicts of a stage, not findings. `kicad.erc.*` and `parity.*` are not waivable and take no severity from the script (proposal, Non-goals).

18. **Explain entries come with the codes.** Tasks 3.3, 4.2 and 5.2 add the tables of their codes to `src/fenolite/cli/data/explain.toml`, because `tests/unit/cli/test_explain_cmd.py` fails for a code without one.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/board.py`, `library.py` | `FootprintInstance.net_ties`, `FootprintDef.net_ties: tuple[tuple[str, ...], ...] = ()` |
| `src/fenolite/model/findings.py` | `Waiver(name, code, items, reason, min_gap=None)`; `Findings.waivers: tuple[Waiver, ...] = ()` |
| `src/fenolite/model/rules.py` | `RuleSet.severities: dict[str, RuleSeverity]`, default empty |
| `src/fenolite/backends/base.py` | `StoredExclusion`; `ExclusionSource` protocol |
| `src/fenolite/backends/kicad/pcb.py`, `mod.py`, `_fpmap.py` | projection of `net_tie_pad_groups`; the authored emitter writes it |
| `src/fenolite/backends/kicad/pro.py`, `proerrors.py` | `SEVERITY_KEYS`, severity lowering, `ProjectInfo.exclusions`, two codes |
| `src/fenolite/backends/kicad/backend.py` | `stored_exclusions(project)` |
| `src/fenolite/checks/waivers.py` (new) | `UNREPEATABLE_TYPES`, `waiver_matches(waiver, code, names, gap=None)`, `apply_waivers(…)`, `WaiverOutcome` |
| `src/fenolite/checks/copper.py`, `drc.py`, `stages.py`, `documents.py`, `codes.py` | net-tie skip and `summary.net_tie_pairs`; `waivers=` and `exclusions=`; `run_document_checks(…, waivers=())`; `CheckReport.waivers`; two codes, `info` for three |
| `src/fenolite/dsl/footprint.py`, `design.py`, `convert.py` | `Footprint.net_tie`, `Design.waive`, `Rules.severity` |
| `src/fenolite/cli/cmd_check.py`, `cmd_build.py` | `result.waivers` on both pipelines; the waivers of both copper guards |
| `src/fenolite/backends/altium/lower.py` | the kinds `net-tie` and `severity` of `altium.not-lowered`, neither in `LOSS_KINDS` |
| `src/fenolite/cli/data/explain.toml` | tables for `check.waiver-unmatched`, `check.exclusion-stale`, `kicad.project.unknown-check`, `kicad.project.dropped-check` |
| `schemas/fenolite.model.v0/{board,library,findings,rules}.json` | regenerated |
| `tests/kicad/check/_tiebench.py`, `test_net_ties.py`, `test_drc_exclusions.py`, `test_severity_keys.py`, `test_waivers_oracle.py` (new) | probes `nettie-*`, `drc-excl-*`, `pro-sev-keys-*`; the end-to-end check |
| `docs/formats/kicad/copper.md`, `drc.md`, `project.md`, `libraries.md`, `docs/dsl.md`, `docs/cli-contract.md`, `docs/design-model.md` | facts with sources, the table rows, the DSL calls, the codes |

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-NETTIE-DRC | A footprint with `net_tie_pad_groups` gets no `shorting_items` and no `clearance` between any two of its pads, nor between a pad and its copper graphic, on 9.0.9 and 10.0.6; `solder_mask_bridge` is still reported between pads outside a common group; a track is judged against its pads; `"1,2"` reads as `"1, 2"` (S-0020, S-0029) | `tests/kicad/check/test_net_ties.py` | the probes `nettie-<case>` and `nettie-<case>-plain` of `kicad-oracle`, "Net-tie facts are probed", record `equal` on both majors, with the control pair firing |
| H-K-DRC-EXCL | `pcb drc` applies a stored exclusion only when its type, marker position in nm and ordered uuid pair equal a violation's; the pair and plain forms both apply; the entry keeps its severity and gains `excluded: true` and `comment`; a key that matches nothing is ignored without a message; the project file is not written (S-0020, S-0029, S-0055, S-0056) | `tests/kicad/check/test_drc_exclusions.py` | probes `drc-excl-<case>` (pair, plain, moved, stale, reversed, first-position clearance) as measured, on both majors |
| H-K-PRO-SEV-KEYS | 10.0.6 applies exactly the 62 `rule_severities` keys of `project_template_10.json` and ignores any other key without a message; 9.0.9 applies the key of each check that the bench fires, and every key of `project_template_9.json` is one it accepts without an error (S-0020, S-0029) | `tests/kicad/check/test_severity_keys.py` | probe `pro-sev-keys-10` `equal` (`ignored_checks` equals `SEVERITY_KEYS[10]`) on 10.0.6; probe `pro-sev-keys-9-bench` `absent` (no entry of `clearance`, `shorting_items`, `solder_mask_bridge`, `track_dangling`, `via_dangling` or `lib_footprint_issues` under `ignore` of every template key) on 9.0.9 |

The three ids are free in `docs/hypotheses.md` at `9aba2dff`. All three start `INFERRED`, with the measurements of Context as their first record. No source row is registered: S-0018 and S-0042 (the footprint libraries), S-0058 (the demo files), S-0020 and S-0029 (the two `kicad-cli` oracles) and S-0055 and S-0056 (the report keys) cover what was read and run. Ids used without changing their level: `H-K-PRO-SEV`, `H-K-DRC-JSON`, `H-K-DRC-TYPES`, `H-K-DRC-UUID`, `H-K-DRC-REPEAT`, `H-K-VIA-RENET`, `H-K-CHECK-CANARY-3`, `H-K-COPPER-SHAPES`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| KiCad's net-tie verdicts | KICAD-VERIFIED (9.0.x, 10.0.x) | `nettie-*` probes |
| net-tie groups read, written, authored | KICAD-VERIFIED (9.0.x, 10.0.x) for the written token | the authored net tie in `test_net_ties.py` |
| the copper check's net-tie skip | INFERRED; parity recorded per case | "Net-tie parity canaries" |
| exclusion facts | KICAD-VERIFIED (9.0.x, 10.0.x) | `drc-excl-*` probes |
| severity lowering | KICAD-VERIFIED (10.0.x); 9.0.x for the bench checks | `pro-sev-keys-*`, a built project's DRC |
| waivers, stale waivers, stale exclusions | mechanical | unit tests of `checks/waivers.py`, the stages, the guard |

## Risks / Trade-offs

- **A waiver used to reach exit 0.** An agent may waive a real defect. Mitigation: a mandatory reason printed on every match; exact names for shorts; `min_gap` with globs; the finding stays listed; a stale waiver is reported.
- **Unstable names.** A waiver naming a track by its locator breaks when the board changes. Mitigation: names of pads and footprints, `*` with `min_gap` for the rest; `check.waiver-unmatched` shows the break.
- **Fenolite reports more than KiCad on ungrouped pads of a tie.** Documented, and the finding names both pads.
- **A severity that 9.0.9 ignores.** For target 9 the key set is the derived template's; a key of a check that 9.0.9 lacks is written and has no effect, which KiCad itself would not report. `docs/formats/kicad/project.md` names the six template keys that no 9.0.9.1 demo project holds.
- **Waivers of the four unrepeatable types never go stale.** Documented; their matches still show on every run that reports the entry.

## Migration Plan

- Additive, and no byte moves for a design that uses none of it. A design without the new calls builds the same KiCad files, and its `.fenolite/` documents keep their bytes too: canonical JSON omits a field at its default, so `net_ties`, `waivers` and `severities` appear only where they hold something. So every output of 0.2.0 keeps its bytes, the rule of `docs/roadmap.md`, decision 32; the pinned build digests that c0123 and c0126 bring stay equal, and `SCHEMA_VERSION` stays `"0"`.
- The other direction does not hold: 0.2.x and 0.3.0 cannot read a document that carries `net_ties`, `waivers` or `severities`. `docs/design-model.md` says so beside each field, as it does for c0126's keys.
- A board read from KiCad that holds a net-tie footprint gains `net_ties` in its model; its file is written back byte for byte.
- Boards with net-tie footprints whose grouped pads touch, or sit closer than the clearance, lose those `copper.*` findings. `CHANGELOG.md` says so.
- Read boards keep the `net_tie_pad_groups` child byte for byte.
- Rollback: remove the skip and the waiver pass; the fields stay, with their defaults.

## Budget (5.5 days)

| part | days |
|---|---|
| registers; the three probes recorded as tests on both majors | 1.0 |
| net-tie groups: model, readers, writer, `Footprint.net_tie`, the two kinds of `altium.not-lowered` | 0.75 |
| net-tie skip in the copper check, parity canaries, table rows | 0.5 |
| waivers: model, `design.waive`, matching | 0.75 |
| waivers in the copper and DRC stages, `run_checks`, `run_document_checks`, `check` result, both guards | 0.75 |
| severities: model, `Rules.severity`, lowering per target, codes, oracle | 0.75 |
| exclusions: read, `ExclusionSource`, comment, stale detection | 0.5 |
| documentation, explain entries and closing | 0.5 |

Cut order: (1) stale exclusions and `ExclusionSource`, keeping the comment from the report; (2) severities whole. Never cut: the net-tie groups and their skip, waivers with reasons, and stale waivers.

## Open Questions

- **Waivers for a project Fenolite did not build.** `check --waivers FILE` with the same fields, in TOML. Default: no, in this change; a native project accepts KiCad's findings with its own exclusions, which `check` now audits.
- **Zones named in `where`.** A fill is located by its zone's locator. Should a zone with a name be located as `zone:<name>`, which a waiver could name? Default: no; `*` with `min_gap`.
- **The packaged 9 template's severity keys.** It holds six keys that no 9.0.9.1 demo project holds and lacks two that most hold. Default: unchanged here, because no run of 9.0.9 can list the keys it applies; a later save of a new project by the 9.0.9 GUI, which the maintainer can make, would settle it.
- **A short waiver at all.** Default: allowed by exact names, for false shorts that Fenolite's approximated pad shapes can give (`copper-check`, "Copper items and their shapes").
