## Context

- **Scope.** The review of 2026-10-05 named the gaps to a complex board; since 2026-10-07 the group is milestone v0.4 (`docs/roadmap.md`, "Milestone names" and "v0.4: proposals on other branches", where the row of c0105 holds its id and slug only). The gap this change closes, in the review's words: "an impedance target per class or pair; width and gap from the stack-up, or KiCad 10 tuning profiles; the impedance table for the fabricator". It depends on c0101 (the stack-up in the model and in the board file) and c0104 (pairs lowered to KiCad, and the rule kind for the pair gap).
- **What exists** on `origin/dev` at `9aba2dff` (2026-10-07).
  - No model, DSL, file or command names an impedance. `NetClass` holds `clearance`, `track_width`, `via_diameter`, `via_drill` and `description`. `RuleSet` holds `rules` only. `StackLayer(name, kind, thickness, material, epsilon_r, loss_tangent)` keeps dielectric constants as decimal text, and `Stackup` holds `layers` and `finish`; no KiCad reader, writer or DSL call fills `Board.stackup` until c0101 (the Altium import and the Altium PCB writer of c0085 use it).
  - The packaged 10 template (`backends/kicad/data/project_template_10.json`) holds `tuning_profiles = {"meta": {"version": 0}, "tuning_profiles_impedance_geometric": []}`, the class key `tuning_profile: ""`, and the severities `missing_tuning_profile: warning` and `tuning_profile_track_geometries: ignore`. `pro.TEN_ONLY_PATHS` holds `/tuning_profiles`, its two children and `/net_settings/classes/*/tuning_profile`, so a target-9 project never carries them. `H-K-PRO-TUNING` (`KICAD-VERIFIED (10.0.x; GUI save)`) records where profiles live. `update_project` keeps them verbatim; `lower_netclass` copies the class key unchanged.
  - "Project files are synthesised and preserved" lets another requirement of `kicad-file-backend` take named keys out of its template-value, added-path and keep rules, as the board-setup minimums do.
  - The rules lowering writes `track_width` with `min`, `opt` and `max` and a layer clause per layer (`H-K-DRU-KIND`, `H-K-DRU-COND`, both majors); rules are emitted priority 0 first and priority 1 last, ties by name, and the later rule governs (`H-K-DRU-ORDER`). `design.rules.minimum()` makes class minimums named `min_<kind>_<class>` at priority 1.
  - c0073 (archived 2026-10-05) checks pair names (`H-K-DIFFPAIR-NAMES`) and gives `DiffPair` and `USB2` interfaces. c0047 (archived) set the precedent for formulas: one public source per formula, constants in `docs/analyses.md`, `decimal` arithmetic, `INFERRED`, no shipped requirement value. `package-layering` lets `dsl` import `model` only, and `analysis` and `exports` not each other.
  - c0064 (archived 2026-10-05) gives `fenolite bom` and `exports.assembly.render_csv(header, rows, options)`, the precedent for a table as JSON with `--out FILE` as CSV. `bom` takes a `.kicad_pcb`, a `.kicad_pro` or a project folder, and no Altium document. Its `--manifest` adds a manifest entry of the derived kind `bom`; the derived kinds are a closed list in "Artefact states" (c0065, archived).
  - The Altium build (c0084, implemented on `dev`, not archived): every rule of the design is either written as a rule record or reported with one `altium.not-lowered` warning at `design-rules/<kind>` and an entry of `result.rules.not_lowered`. A rule with `layers` is refused with `scope-unsupported`, because the closed scope grammar holds no layer; a kind without an `exact` row is `no-counterpart`. Nothing of an impedance is read or written: `backends/altium/docboard.py` carries the impedance text of an Altium board file as opaque content only.
- **The proposals this change builds on** (v0.4 proposals, not on `dev`; read as proposed on 2026-10-07; task 0.1 re-checks them once they are archived).
  - c0101: `Stackup.impedance_controlled` (written as `(dielectric_constraints yes|no)`, set by `design.stackup(…, impedance_controlled=…)`), `Stackup.between(upper, lower)`, `StackLayer.dielectric_kind`; copper entries take the board's copper names; the board's stack-up wins over an unlocked script stack-up on a rebuild. Its `H-K-STACKUP-JOB` covers `ImpedanceControlled` and the dielectric constants of the job file on both majors.
  - c0104: pairs stay `DiffPair` and `USB2` interfaces; `NetClass.diff_pair_width`, `diff_pair_gap`, `diff_pair_via_gap`; the kind `diff_pair_gap` with `min`, `opt` and `max`, side A only, the only pair kind that takes a layer clause (one rule per layer, measured there on both majors), leaves `diff_pair`, `net` and `netclass`; `opt` is written and never checked by DRC; in the Altium rule table the kind has a row of reason `no-counterpart`; `select.pair()` and `design.rules.pair()`; a class pair gap below the class clearance relaxes the clearance inside a pair where no custom clearance rule governs it, and a `diff_pair_gap` rule does not. It sends tuning profiles and time units in rules to this change.
  - c0106: tuning profiles are this change's; a delay measure goes nowhere, because the yardstick matches length.
- **Measured on 2026-10-05.** Bench: the four-layer board of `write_triad(…, target=10)` with a stack-up typed into `(setup …)` (F.Cu, 0.2 mm prepreg of permittivity 4.3, In1.Cu, 1.065 mm core, In2.Cu, 0.2 mm prepreg, B.Cu; copper 35 µm), classes `SE50` (tracks `CLK` on F.Cu and `CLK2` on B.Cu) and `USB90` (pair `USB_P`/`USB_N` on F.Cu), class clearances 0.2 mm, and the scoped canary. Profiles and class keys were written into the project JSON; `kicad-cli pcb drc --format json --severity-all` judged each case. Profile form written: `profile_name`, `type` (0 single, 1 differential), `target_impedance`, `enable_time_domain_tuning`, `layer_entries` (`signal_layer`, `top_reference_layer`, `bottom_reference_layer`, `width`, `diff_pair_gap`, `delay`), `via_prop_delay`, `via_overrides`; the key names come from S-0640. On 10.0.6:

  | case | result |
  |---|---|
  | single profile, rows F.Cu and B.Cu at 0.35 mm, B.Cu track 0.30 mm, template severity | no finding |
  | the same, `tuning_profile_track_geometries` = `error`, then `warning` | one `track_width` finding on the B.Cu track ("min width 0.3500 mm; actual 0.3000 mm"), at `error`, then at `warning` |
  | F.Cu track 1 µm wider, B.Cu track 100 nm narrower | both reported: the check is `min` = `max` = the row's width |
  | profile listing F.Cu only, B.Cu track 0.30 mm | no finding: a layer without a row is not checked |
  | class key naming an absent profile | `missing_tuning_profile` warning "(Net Class: SE50, Tuning Profile: NOPE)" |
  | differential profile, row F.Cu 0.2 mm / 0.15 mm; pair at 0.2 / 0.15, then 0.2 / 0.2, then 0.25 / 0.15 | nothing; `diff_pair_gap_out_of_range` ("tuning profile 'USB90' maximum gap 0.1500 mm; actual 0.2000 mm"); `track_width` on both tracks |
  | `target_impedance` 0 instead of 50 | the same findings: DRC does not use the target |
  | keys of later schemas (`frequency`, `model_solder_mask`, `net_chain_bridge_prop_delay`) and `meta.version` 2 | loaded, same findings |
  | a differential profile on the single-ended class | no width finding: single tracks are not checked by it |
  | `width` written `350000.0` | loaded |
  | rows without the two reference keys | the profile is not loaded: `missing_tuning_profile` |
  | a custom rule `track_width (min 0.3mm)` on `A.NetClass == 'SE50'` beside the profile, severity `error` | no finding: the custom rule replaces the profile's check |
  | per-layer custom rules `track_width (min 0.35mm) (opt 0.35mm) (max 0.35mm)`, no profile; F.Cu track 0.351 mm, B.Cu 0.30 mm | `track_width` "max width 0.3500 mm; actual 0.3510 mm" and "min width 0.3500 mm; actual 0.3000 mm" |
  | per-layer custom `diff_pair_gap (min 0.15mm) (opt 0.15mm) (max 0.15mm)`, no profile; pair at gap 0.2, then 0.15 | `diff_pair_gap_out_of_range` "maximum gap 0.1500 mm"; at 0.15 the class clearance is still reported between the two nets |
  | the differential profile at template severity, pair at gap 0.15 | no clearance finding between the two nets: the profile's gap relaxes the pair's own clearance |
  | profile plus the per-layer rules, at `ignore` and at `error` | one finding per item, named by the rule; the pair's clearance stays relaxed |

  On 9.0.9 (pinned image, one run, target-9 bench with the per-layer rules): `track_width` reported above `max` (0.351 mm) and below `min` (0.30 mm); the pair at gap 0.15 mm still gets the class clearance finding. Not run on 9.0.9: the gap rule at a wrong gap (c0104 probes its kind) and the job file (c0101 measured it on both majors).
- **Outputs, 10.0.6.** `pcb upgrade --force` leaves a project with profiles byte for byte unchanged (kicad-cli never saves a project, so the key set a GUI save writes is not observable headless). `pcb export gerbers` with `(dielectric_constraints yes)` writes `"ImpedanceControlled": true` under `GeneralSpecs` and `DielectricConstant` and `LossTangent` on each dielectric of `MaterialStackup`; with `no`, neither. `pcb export ipc2581` writes the dielectric constants and no impedance element; `pcb export stats --format json` has no stack-up, impedance or profile key.
- **Formulas, checked in floats for orientation.** The one-formula microstrip form of 1977 that S-0641 states gives 50.763 Ω for 0.35 mm over 0.2 mm, 35 µm copper, permittivity 4.3; at zero thickness it differs from the 1975 form of the same page by at most 1.21 % for w/h from 0.1 to 10 and permittivity from 2.2 to 10. The thick-strip stripline form of S-0642 at thickness → 0 differs from the exact zero-thickness value (conformal mapping, complete elliptic integrals) by at most 0.48 % for w/b from 0.1 to 2. Scripts and outputs: the probe folder of this change (not committed); every case becomes a recorded probe or a test here. The measurements were made on the branch `review-roadmap-complex-board` and were not repeated on `dev`; task group 1 repeats them before any table is filled. The bench numbers (a 0.2 mm prepreg of permittivity 4.3, a 1.065 mm core, 35 µm copper, 0.35 mm and 0.2 mm tracks) are authored round values of a generic 1.6 mm four-layer board, taken from no board of anyone.
- **Constraints.** Stdlib only, integers in nm, no float in the model or in an analysis module, no shipped value, nothing written for a major that did not prove it.

## Goals / Non-Goals

**Goals:**
- A script states an impedance target once, per class or per pair, with the geometry for each layer.
- KiCad's DRC checks that geometry on both majors; KiCad 10 also gets a tuning profile, so its interactive router and length tuner see the same numbers.
- The fabricator gets a table of targets, layers, references and geometry, and the job file says the board is impedance-controlled.
- An agent without KiCad's GUI calculator can get a sourced estimate of single-ended lines, labelled `INFERRED`.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Judging the impedance of a routed board in `check`: nowhere, because the DRC rules judge the geometry and impedance itself has no oracle here.

## Decisions

1. **A target belongs to net classes, in the rules layer.** `ImpedanceTarget` lives in `RuleSet.impedance` and names its classes by id; a pair is given in the DSL and resolved to the class of its two nets. KiCad attaches a profile to classes, and the per-layer rules select classes, so one carrier serves both majors.
   - Rejected: fields on `NetClass`. Per-layer rows and a tolerance do not fit four class values, and c0104 adds pair values to classes.
   - Rejected: the pair interface (c0073, c0104) as the carrier. Single-ended targets need one too, and KiCad attaches profiles to classes, not to pairs.

2. **Numbers.** Widths and gaps are `Nm`. `ohms` and `tolerance_percent` are decimal text such as `"90"` or `"7.5"`, the convention of `StackLayer.epsilon_r`. A target read from KiCad may have `ohms == ""` (KiCad's target is optional).
   - Rejected: integer milliohms. The model's numbers that are not lengths or angles are decimal text.
   - Rejected: a `Quantity` in the model. c0073 keeps quantities out of the model; the DSL takes `ohm(90)` and stores its value as text.

3. **The geometry is the user's; the estimate is advice.** Every width and gap in the model comes from the script or from a KiCad profile. The estimate of Decision 11 is computed by `fenolite impedance --estimate` and returned in its reply, never written into the model or a file.
   - Rejected: the build filling missing widths from the formula. An `INFERRED` number would enter the files beside the user's, and `dsl` may not import `analysis`.
   - Rejected: no estimate at all. KiCad's calculators run only in its GUI, so an agent working headless has none.

4. **DRC checks the geometry through derived rules, on both majors.** For each layer row of a target, `to_model` adds a `track_width` rule on the target's classes with that layer and `min` = `opt` = `max` = the width. A differential target also adds, for each layer row, one `diff_pair_gap` rule of c0104 on its classes with that layer and `min` = `opt` = `max` = the row's gap: c0104 gives the kind a layer clause and the three limits, measured on both majors. Rows of different gaps are thus each checked exactly, on their own layer. These are ordinary model rules, written by the existing lowering.
   - On 10.0.6 the profile is written beside them at the template severity `ignore`. The rule governs the width (measurement "a custom rule … replaces"), so each item gets one finding, named by the rule, whatever the user sets the profile severity to. The profile still gives the interactive router and the length tuner their per-layer numbers, and relaxes the pair's own clearance to the gap where no custom clearance rule governs the pair.
   - Rejected: the profile alone, with `tuning_profile_track_geometries` raised. It checks nothing on 9.0, and severities are c0114's.
   - Rejected: rules alone on 10. The router, the tuner and the pair clearance would not see the target.
   - Rejected: one gap rule per target without layers, with `min` the smallest and `max` the largest gap of its rows (the first draft of this change, written when c0104's draft gave the kind no layer clause). It checks a band, not a gap, and needed a warning of its own (`build.impedance-gap-band`, dropped).

5. **The derived rules govern over class minimums.** They are named `track_width_<target>_<layer>` and `diff_pair_gap_<target>_<layer>`, with the target's priority, 1 by default. At priority 1 the names sort after `min_<kind>_<class>`, so they are emitted after the class minimums and govern on their layers. A later rule of the same kind that selects a target class, a pair of it or the whole board, without an area leaf, gives `build.impedance-shadowed` (Decision 9); c0104's `pair()` rules (`pair:<name>:gap`) sort after `diff_pair_gap_<target>_<layer>` and are flagged when they overlap.
   - Rejected: moving class minimums to priority 2. That modifies "Rule minimums in the DSL" for one consumer.

6. **Exact width limits.** The width rules and the gap rules have `min` = `opt` = `max`, as KiCad's own profile check does (measured). A neck-down near a fine-pitch pad needs an area rule of c0103 at a higher priority, which the shadow check does not flag.
   - Rejected: a width band from the tolerance. It needs the estimate, which is `INFERRED`, and there is none for pairs.

7. **KiCad 10 profiles.** `backends/kicad/tuning.py`:
   - `lower_profile(target)` gives one entry of `tuning_profiles_impedance_geometric`: `profile_name` = the target name, `type` 0 or 1, `target_impedance` = the exact text of `ohms` as a `JsonNumber` (`0` when empty), `enable_time_domain_tuning` false, one `layer_entries` item per row (`signal_layer`; with one reference it is `bottom_reference_layer` and `top_reference_layer` is `""`; with two, the upper in stack order is `top_reference_layer`; `width` and `diff_pair_gap` as integers in nm, `0` for a single target; `delay` 0), `via_prop_delay` 0, `via_overrides` empty. This is the key set of `meta.version` 0, which the 10.0.6 template holds.
   - `apply_profile_keys(text, design, *, target, issues=None)` runs in `write_triad` after `apply_sheet_keys`, for target 10 only. A profile whose name is a target's is replaced; a target without a profile is appended, sorted by name; every other profile is kept in place. The class key of each class of a target is set to the target name; when it named another non-empty profile, `kicad.project.profile-reassigned` (warning) names the class and both names. Classes without a target keep their key. No profile is deleted.
   - The script wins, as for class values. A profile edited in KiCad's GUI is replaced at the next build unless its name is not a target's.
   - Rejected: the rule of zones and pads ("the board wins unless locked"). A profile is a project setting like a class value, which the script already governs.

8. **Profiles are read back.** `read_project` also returns the profiles, and `apply_project` turns each profile named by at least one class into a target of those classes: kind from `type`, `ohms` from `target_impedance` (`""` for 0), no tolerance, one row per entry with a copper layer. An entry with a non-integer width, an unknown layer or a missing key gives `kicad.project.unread-entry` and is skipped. Profiles named by no class stay in the file only. Rules of `.kicad_dru` are read as they are today.
   - Rejected: lifting every profile. A target governs classes; a profile no class names governs nothing, and it is kept in the file anyway.
   - Rejected: lifting the derived rules back into targets. A rule holds no ohms, references or kind; the profile does on 10, and on 9 the `.fenolite/` model does.

9. **Build checks.** `lens.build.impedance_checks(design, *, target)` runs after the parts are resolved and joins the closed build set with six codes:

   | code | severity | when |
   |---|---|---|
   | `build.impedance-layer` | error | a row's layer or reference is not a copper layer of the board |
   | `build.impedance-shadowed` | warning | a rule of the same kind, emitted later, selects a target class, a pair of it or the whole board on a row's layer |
   | `build.impedance-class-width` | warning | a class value differs from a row's: `track_width` (single), or c0104's `diff_pair_width` or `diff_pair_gap` (differential); routers and KiCad 9's router use the class values |
   | `build.impedance-gap-clearance` | warning | target 9: a row's gap is below its class clearance and the class has no pair gap at or below it, so KiCad 9 reports the pair's own clearance |
   | `build.impedance-stackup` | warning | no stack-up, or one with `impedance_controlled` false: the job file then states neither the flag nor the dielectric constants |
   | `build.impedance-rules-only` | info | target 9 with targets: rules are written, no profile |

   - Rejected: refusing a shadowed target with an error. A narrower rule outside an area is legal in KiCad and may be meant; the warning names it.
   - Rejected: the gap-clearance warning on target 10. The profile relaxes the pair's own clearance there (measured without a custom clearance rule); the probe `pro-tuning-gap-clearance-rule` decides the case with one, and the warning extends to it if KiCad then reports the pair.

10. **The stack-up flag stays the user's.** c0101's `Stackup.impedance_controlled` writes `(dielectric_constraints yes)`, which makes the job file state `ImpedanceControlled` and the dielectric constants (measured here and by c0101). A design with targets whose board has no stack-up, or whose flag is false, gets `build.impedance-stackup` with the call to make.
    - Rejected: setting the flag from the targets. On a rebuild c0101's merge keeps the board's unlocked stack-up, so the build would either fight that rule or write a flag the script never stated.
    - Rejected: a field of this change on `Stackup`. Stack-up fields are c0101's.

11. **The estimate.** `analysis/impedance.py`, pure, `decimal` at 40 digits, results in integer milliohms rounded half-even:
    - `microstrip_mohm(width, height, thickness, epsilon_r)`: the 1977 one-formula form with its thickness correction, as S-0641 states it, with the vacuum impedance of S-0643.
    - `stripline_mohm(width, spacing, thickness, epsilon_r)`: the thick-strip form for a centred strip, as S-0642 states it; `in_range` is the condition under which S-0642 claims its accuracy.
    - `offset_stripline_mohm(width, below, above, thickness, epsilon_r)`: the two centred lines of spacings `2·below + t` and `2·above + t` in parallel, as S-0642 describes (an estimate for small offsets).
    - Structure from the row: one reference on an outer layer is a microstrip; two references on an inner layer a stripline, centred when the two heights are equal. Anything else, and every differential row, gets an `Estimate` without a value and with its reason (`impedance.estimate-unsupported`).
    - Heights and permittivity come from `Board.stackup` through c0101's `Stackup.between`: the dielectric entries between the row's layer and each reference, height the sum of their thicknesses, permittivity their series combination `h / Σ(hᵢ/εᵢ)`; more than one permittivity gives `impedance.mixed-dielectric`.
    - `solve_width(target_mohm, …)` returns the multiple of 1 µm whose estimate is nearest the target, by bisection; the forms decrease with width.
    - Rejected: the longer microstrip sets with dispersion that S-0271 names. Their public statements are papers or image-typeset pages. The 1975 form serves as the cross-check of the 1977 one, and the exact zero-thickness stripline as the cross-check of the thick-strip form.
    - Rejected: a field solver. Floats or a heavy exact method, and a new oracle question.

12. **The table and its command.** `exports/impedance.py`: `impedance_table(design)` gives one `ImpedanceRow` per target and layer row, sorted by target then stack order: target, kind, structure, layer, references, ohms, tolerance, width, gap, the heights to each reference and the permittivity from the stack-up when present, the classes and their nets. `fenolite impedance PATH [--estimate] [--out FILE]` reads the `.fenolite/` model of a built project, else the KiCad board and project; `--out` plans a CSV of the rows through `assembly.render_csv`, with the mutation protocol of `bom`. `PATH` resolves as for `bom`, so an Altium document is refused as `bom` refuses it: no Altium record is read into a target. The command has no `--manifest`: the kind `impedance` names the planned write only and is no manifest entry, so "Artefact states" is not modified here.
    - Rejected: an export kind. "Export kinds and their arguments" lists `kicad-cli` runs, and c0116 owns new kinds; c0116 can call `impedance_table`. If c0116 lists the table in the manifest, the derived kind joins "Artefact states" in c0116's delta, in the order the review of 2026-10-07 fixed for that requirement (c0116, c0117, c0118), and this change adds nothing to it.
    - Rejected: `analyze --kinds impedance`. Its kinds are a closed tuple that c0115 may modify, and the table is not an analysis.

13. **Altium: targets named once, derived rules reported as c0084 reports any rule.** An Altium build keeps targets in the model and `.fenolite/` and reports them in one `altium.not-lowered` info at `impedance`, which names the targets and says how many derived rules follow.
    - The derived rules are ordinary rules of `RuleSet.rules`, so c0084's "Rules in an Altium build" applies unchanged: a `track_width_<target>_<layer>` rule has a layer and is refused with `scope-unsupported`; a `diff_pair_gap_<target>_<layer>` rule has a kind whose row is `no-counterpart` (c0104). Each gives one warning at `design-rules/<kind>` and one entry of `result.rules.not_lowered`. None is written, so every Altium file equals the file of the same design without the targets.
    - A target with N layers therefore gives N warnings (2 N for a pair). Their names hold the target and the layer, and the `impedance` info says where they come from.
    - Rejected: one warning per target in place of the per-rule warnings (the suggestion of the review of 2026-10-07). c0084 states "each rule that is not written" gets its warning and its entry of `result.rules.not_lowered`; an exception for rules by their origin would need a MODIFIED copy of that requirement, a marker on `Rule` that says "derived", and a second accounting. The model would also stop being what the Altium build reports.
    - Rejected: not deriving the rules for the Altium target. `to_model` does not know the target, and `.fenolite/rules.json` would differ by target.
    - Rejected: writing a Width rule per target without its layer. It would bind every layer to one width, which is not the neutral rule; `lower` "MUST never write a rule whose value or scope differs from the neutral rule's".
    - Rejected: writing the targets as impedance profiles of the PCB document. No fact row records that record.

14. **Changes in flight.** No requirement is modified, so no delta is regenerated and no archive order is imposed beyond the prerequisites: release `0.3.0` with c0084 archived, then c0101 and c0104. The names taken from their proposals (Context) are re-checked by task 0.1; if c0104's `diff_pair_gap` has lost its layer clause or its `opt` by then, Decision 4 falls back to one gap rule per target with `min` and `max` and this design is corrected first. This change does not modify "Net classes lower to the project file", which c0104 modifies: the class key is set by a later step. c0100's inner names (`In3.Cu` …) are plain copper names here.
    - Three living requirements are extended, not modified, each by an ADDED requirement that names it, as their texts allow or as c0073 did for "DSL package": "Generated projects are coherent" (one step after `apply_sheet_keys`), "Project files are read into the model" (one more field) and "Model layers for v0.1" (two more types in the rules layer). No open change on `dev` at `9aba2dff` holds a delta of any of the three (searched in `openspec/changes/`, archive excluded); c0061, archived, modified "Built project files" and kept the clause that lets later requirements add build steps.
    - Schemas: `rules.json` is regenerated by this change and, among the v0.4 proposals, by c0104, c0107, c0113 and c0114; each is additive, and whichever lands later runs `tools/gen_schemas.py` on the merged model.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/model/rules.py` | `ImpedanceKind`, `TraceGeometry(layer, references, width, gap=None)`, `ImpedanceTarget(name, kind, netclass_ids, ohms, tolerance_percent="", layers=())`, `RuleSet.impedance`; `Design.validate()` gains `model.impedance-invalid` |
| `src/fenolite/dsl/impedance.py` (new) | `Trace`, `trace(layer, *, refs, width, gap=None)` |
| `src/fenolite/dsl/design.py`, `dsl/convert.py`, `dsl/__init__.py` | `Rules.impedance(name, *, ohms, netclass=None, pair=None, layers, tolerance=None, priority=1)`, `ImpedanceSpec`; targets and derived rules in `to_model`; `trace` re-exported |
| `src/fenolite/lens/build.py` | `impedance_checks(design, *, target)`; six codes in `BUILD_ISSUE_CODES` |
| `src/fenolite/lens/altium.py` | the info `altium.not-lowered` at `impedance` |
| `src/fenolite/cli/data/explain.toml` | one table per new code (fourteen, listed below) and the `where` value `impedance` in the text of `altium.not-lowered` |
| `src/fenolite/backends/kicad/tuning.py` (new) | `lower_profile`, `apply_profile_keys`, `read_profiles`, `lift_profiles`, `PROFILE_KEY_PATHS` |
| `src/fenolite/backends/kicad/pro.py`, `triad.py`, `proerrors.py` | `ProjectInfo.profiles`; targets in `apply_project`; the call in `write_triad`; `kicad.project.profile-reassigned` |
| `src/fenolite/analysis/impedance.py` (new) | `Z_VACUUM_OHM`, the named constants of the forms, `microstrip_mohm`, `stripline_mohm`, `offset_stripline_mohm`, `stripline_in_range`, `solve_width`, `Dielectric`, `dielectric_between`, `Estimate` (with `mohm`, `form`, `in_range`, `heights`, `epsilon_r`, `mixed`, `reason`), `estimate(stackup, layers, geometry) -> Estimate`, `EVIDENCE` |
| `src/fenolite/analysis/PROVENANCE.md` | rows for S-0641, S-0642, S-0643: facts only, each form re-derived and written in Fenolite's own code, no text copied |
| `src/fenolite/exports/impedance.py` (new) | `ImpedanceRow`, `impedance_table(design)`, `COLUMNS`, `render_csv(rows, estimates=None)`, `ISSUE_CODES`, `issue()`, `EVIDENCE` |
| `src/fenolite/cli/cmd_impedance.py` (new) | `fenolite impedance` |
| `schemas/fenolite.model.v0/rules.json` | regenerated |
| `docs/impedance.md` (new), `docs/dsl.md`, `docs/analyses.md`, `docs/cli-contract.md`, `docs/formats/kicad/{project,rules,drc}.md`, `docs/evidence/impedance.md` (new) | the guide, the table "Impedance formulas", the facts with labels, the probe outcomes |
| tests | `tests/unit/model/test_impedance_model.py`, `tests/unit/dsl/test_impedance_dsl.py`, `tests/unit/lens/test_impedance_checks.py`, `tests/unit/backends/kicad/test_tuning_profiles.py`, `tests/unit/analysis/test_impedance.py`, `tests/unit/exports/test_impedance_table.py`, `tests/unit/cli/test_impedance_cmd.py`, `tests/kicad/impedance/_zbench.py`, `test_tuning_drc.py`, `test_impedance_rules.py` |

## Sources registered by this change

| id | source | licence | used for |
|---|---|---|---|
| S-0640 | https://docs.kicad.org/doxygen/tuning__profiles_8cpp_source.html | GPL-3.0-or-later (facts only; nothing transcribed or followed) | the key names of a tuning profile, the value kinds, `type` 0 and 1, the schema migrations of the development branch |
| S-0641 | https://en.wikipedia.org/wiki/Microstrip | CC-BY-SA-4.0 (facts only: the formula is a fact, re-derived and written in Fenolite's own code and words; no text copied) | the 1977 one-formula microstrip form with its thickness correction and claimed error; the 1975 form, used as a cross-check |
| S-0642 | https://en.wikipedia.org/wiki/Stripline | CC-BY-SA-4.0 (facts only: the formula is a fact, re-derived and written in Fenolite's own code and words; no text copied) | the thick-strip form for a centred stripline and its claimed accuracy; the offset estimate from two centred lines |
| S-0643 | https://physics.nist.gov/cgi-bin/cuu/Value?z0 | public domain (US government) | the characteristic impedance of vacuum, 376.730 313 412 Ω (CODATA 2022) |

The four ids are the first of the block S-0640 to S-0659, which the coordinator of v0.4 reserved for this group on 2026-10-07; the block is free in `docs/evidence/sources.md` at `9aba2dff`, whose highest id is S-0601, and none of the four URLs is registered there under another id. The first draft used S-0380 to S-0383, which `dev` gave to four package datasheets. S-0644 to S-0659 stay unused by this change. Task 1.1 checks the block again on the day. S-0038 (the 10.0 PCB editor manual) gains in its "used for" cell the sections "Tuning profiles" and "Time-domain tuning" and the DRC violation "Tuning profile track geometries", read on 2026-10-05. S-0271 (the calculator page) is cited for the models it names. No standard was read.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PRO-TUNING-DRC | On 10.0.6 a tuning profile named by a class key makes DRC check each listed layer's width, and for a differential profile the pair gap, with `min` = `max`, at the severity of `tuning_profile_track_geometries`; unlisted layers and single tracks under a differential profile are not checked; a custom `track_width` rule replaces the check; the profile's gap relaxes the pair's own clearance at any severity where no custom clearance rule governs the pair; an absent profile gives `missing_tuning_profile` (S-0038, S-0020) | `tests/kicad/impedance/test_tuning_drc.py` | the eight measured `pro-tuning-<case>` probes `present` or `absent` as in Context, and `pro-tuning-gap-clearance-rule` recorded, with the canary, on 10.0.6 |
| H-K-PRO-TUNING-KEYS | The entry `lower_profile` writes has the keys and value kinds that a 10.0.6 GUI save writes for one profile (S-0640, S-0020) | task 1.4, one GUI save compared key by key | equal key paths and value kinds; a difference is recorded and the writer follows the save |
| H-K-DRU-IMPEDANCE | A per-layer `track_width` rule with `min` = `opt` = `max` reports tracks of its class above `max` and below `min` on its layer only, on 9.0.9 and 10.0.6 (S-0010, S-0038, S-0020, S-0029) | `tests/kicad/impedance/test_impedance_rules.py` | probe `dru-impedance-width` `present` on both majors |
| H-G-AN-ZMS | The 1977 microstrip form, as S-0641 states it and Fenolite records it, gives the quasi-static impedance of a surface microstrip within the error its source claims | `tests/unit/analysis/test_impedance.py -k microstrip` | arithmetic within 1 mΩ of an independent `math` computation; within 2 % of the 1975 form at zero thickness on the grid of Context; no oracle, stays `INFERRED` |
| H-G-AN-ZSL | The thick-strip stripline form, as S-0642 states it, gives a centred stripline within its claimed accuracy, and the parallel estimate an offset one for small offsets | `tests/unit/analysis/test_impedance.py -k stripline` | arithmetic within 1 mΩ of `math`; within 1 % of the exact zero-thickness value at thickness 10⁻⁶ of the spacing; the offset form equal to the centred one for equal heights; stays `INFERRED` |

Ids used without changing their level: `H-K-PRO-TUNING`, `H-K-DRU-KIND`, `H-K-DRU-COND`, `H-K-DRU-ORDER`, `H-K-DIFFPAIR-NAMES`, `H-K-PRO-SEV`, and the proposals' `H-K-STACKUP-JOB` (c0101), `H-K-DRU-PAIR` and `H-K-PRO-PAIR` (c0104).

The five new ids are in no file of `dev` at `9aba2dff`; `H-K-PRO-TUNING` is, and is a different row (where profiles are stored).

## New names of this change

For the cross-check among the v0.4 proposals.

- Source ids: S-0640, S-0641, S-0642, S-0643.
- Hypothesis ids: `H-K-PRO-TUNING-DRC`, `H-K-PRO-TUNING-KEYS`, `H-K-DRU-IMPEDANCE`, `H-G-AN-ZMS`, `H-G-AN-ZSL`.
- Issue codes (fourteen, each with a table in `cli/data/explain.toml`): `build.impedance-layer`, `build.impedance-shadowed`, `build.impedance-class-width`, `build.impedance-gap-clearance`, `build.impedance-stackup`, `build.impedance-rules-only`; `impedance.none`, `impedance.no-stackup`, `impedance.estimate-unsupported`, `impedance.mixed-dielectric`, `impedance.out-of-range`, `impedance.off-target`; `kicad.project.profile-reassigned`; `model.impedance-invalid`. `kicad.project.unread-entry` exists on `dev` and gains a case. The `where` value `impedance` of `altium.not-lowered`.
- Command and flags: `fenolite impedance PATH`, `--estimate`, `--out FILE`.
- Result keys: `result.source`, `result.columns`, `result.rows`, `result.counts.{targets,rows,estimated,left_out}`, and per row `estimate.{mohm,suggested_width,in_range,form,reason}`; the planned-write kind `impedance`.
- Model: `RuleSet.impedance`, `ImpedanceTarget`, `TraceGeometry`, `ImpedanceKind`; rule names `track_width_<target>_<layer>` and `diff_pair_gap_<target>_<layer>`.
- DSL: `design.rules.impedance`, `trace` (re-exported by `fenolite.dsl`).
- Probe ids: `pro-tuning-*`, `dru-impedance-width`. Data file: `tests/data/kicad/project/tuning_10.kicad_pro`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| per-layer width rules | KICAD-VERIFIED (9.0.x, 10.0.x) | `dru-impedance-width` |
| the pair gap rule, with its layer clause | the level of c0104's `diff_pair_gap` | c0104's `H-K-DRU-PAIR` |
| the Altium info and the per-rule warnings | mechanical; no Altium fact is claimed | `tests/unit/lens/test_altium_rules.py -k impedance` |
| profiles written and checked | KICAD-VERIFIED (10.0.x) | `pro-tuning-*` |
| profile key set | INFERRED until task 1.4 | `H-K-PRO-TUNING-KEYS` |
| profiles read into targets | mechanical, on the form of `H-K-PRO-TUNING-KEYS` | unit tests |
| model, DSL, build checks, table, command | mechanical | unit tests |
| estimates | INFERRED | `H-G-AN-ZMS`, `H-G-AN-ZSL` |

`exports.impedance.EVIDENCE` is the level of the input read. With `--estimate`, the reply combines it with `analysis.impedance.EVIDENCE` (`INFERRED`), and is `UNVERIFIED` when a row was left out for a missing input.

## Risks / Trade-offs

- [An estimate read as the board's impedance] → `INFERRED` in every reply, the claimed error and the omitted effects (solder mask, etch, frequency) in `docs/impedance.md` and in the command help; the model never holds it.
- [Exact width rules flag a deliberate neck-down] → an area rule of c0103 at a higher priority; the shadow check ignores selectors with an area leaf.
- [A profile tuned in KiCad's GUI is replaced by the next build] → stated in the guide: copy the values into the script, or rename the profile.
- [A removed target leaves its profile and class key behind] → never deleting matches classes; Open Questions.
- [An Altium build of a design with targets gives one warning per derived rule] → the `impedance` info names the targets and the count; `docs/impedance.md` says that the Altium target keeps targets in the model only.
- [A stack-up not marked impedance-controlled] → `build.impedance-stackup`; the table still lists the targets.
- [The 10.0.6 GUI writes another key set] → `H-K-PRO-TUNING-KEYS` and task 1.4; DRC already loads the written form, and later keys are tolerated.
- [Routers use the class width, not per-layer widths] → `build.impedance-class-width`; a note for c0107 and c0110.

## Migration Plan

- Additive. A design without targets writes the same bytes; `rules.json` without `impedance` loads with an empty tuple. The other direction does not work: **0.2.x and 0.3.0 cannot read a `rules.json` that carries the key `impedance`**, because the reader of the canonical form is strict, as after every earlier additive change of the model; `SCHEMA_VERSION` stays `"0"`, and the changelog line and `docs/design-model.md` say so (tasks 9.4 and 2.1).
- A project that already holds profiles keeps them; only profiles named like a target, and the class keys of target classes, change.
- Rollback: remove the targets, the derived rules and the module files; written profiles stay in projects and are kept by the keep rule.

## Budget (8.5 days)

| part | days |
|---|---|
| entry check, registers, probes recorded as tests | 0.75 |
| model, schema, validation | 0.75 |
| DSL: `impedance()`, `trace()`, derived rules | 1.0 |
| build checks | 0.75 |
| KiCad 10 profiles: write, update, gating | 0.75 |
| reading profiles into targets | 0.5 |
| oracle tests on both majors | 0.5 |
| table and `impedance` command | 1.0 |
| estimates, facts table, cross-checks | 1.5 |
| Altium info | 0.25 |
| documentation and closing | 0.75 |

Cut order: (1) the estimate, that is `--estimate`, `analysis/impedance.py` and the `H-G-AN-*` rows (−1.5); (2) reading profiles into targets, after which the command reads built projects only (−0.5); (3) `build.impedance-shadowed` (−0.25). Never cut: the model, the DSL with its derived rules, the profiles, the stack-up check, the table, the command without `--estimate` and the oracle.

## Open Questions

- **Estimates for pairs.** Edge-coupled microstrip (the coupled-line equations that S-0271 names) and edge-coupled stripline (an exact zero-thickness form exists). Default: not in this change; the user gives width and gap.
- **Removing stale profiles.** A profile whose target left the script. Default: kept, as classes are; a later change may track what Fenolite wrote.
- **A width band from the tolerance.** Default: exact limits.
- **Raising `tuning_profile_track_geometries`.** Default: no; the rules carry the check, and c0114 owns severities.
- **One warning per derived rule in an Altium build.** Default: yes, as c0084 states for every rule; a quieter form needs a change to c0084's requirement.
- **Delays and time units.** c0104 sends time units in rules here, c0106 sends delays nowhere. Default: profiles keep `delay` 0 and time-domain tuning off; a later change may add unit delays and time units together.
- **Governing by name order.** Default: the derived names sort after class minimums; the alternative moves class minimums to priority 2.
- **Tolerance as ohms.** Default: percent only.
- **Solder mask in the estimate.** Default: none; documented.
