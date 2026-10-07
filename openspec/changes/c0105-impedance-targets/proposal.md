## Why

The review of 2026-10-05 found, among the gaps to a complex board (milestone v0.4; `docs/roadmap.md`, "v0.4: proposals on other branches"), no impedance target on a class or pair, no width or gap from the stack-up, no KiCad 10 tuning profile and nothing for the fabricator. c0047 and c0073, both archived, list impedance as a non-goal. On `origin/dev` at `9aba2dff` the gap is whole: no model field, DSL call, command or export names an impedance; only the packaged KiCad 10 project template holds the empty `tuning_profiles` keys.

Measured 2026-10-05 (4-layer bench, 10.0.6; one run on 9.0.9):

- A tuning profile in `.kicad_pro`, named by the class key `tuning_profile`, makes DRC check width and pair gap exactly on each layer it lists, at the severity of `tuning_profile_track_geometries` (template: `ignore`). A custom `track_width` rule replaces that check. The profile's gap also relaxes the pair's own clearance.
- Per-layer custom `track_width` rules with `min` = `max` report both limits on 9.0.9 and 10.0.6.
- IPC-2581 and the Gerber job file carry no impedance target; the job file only marks a board impedance-controlled, from c0101's stack-up flag.

## What Changes

- **Model.** `ImpedanceTarget` in `RuleSet.impedance`: name, single or differential, net classes, ohms and tolerance as decimal text, and per layer the references, width and gap.
- **DSL.** `design.rules.impedance(name, ohms=…, netclass=… | pair=…, layers=(trace(…), …))` also adds, per layer, one `track_width` rule (`min` = `opt` = `max`) and, for a pair, one `diff_pair_gap` rule of c0104 with that layer and `min` = `opt` = `max`: DRC checks the geometry on both majors.
- **KiCad 10.** A tuning profile per target, named by the class keys; other profiles kept; profiles read back.
- **Build checks.** A layer that is not copper; a later rule replacing a target's rule; differing class values; a stack-up not marked impedance-controlled; on KiCad 9, a gap below the class clearance.
- **Table.** `fenolite impedance PATH [--estimate] [--out FILE]`: a row per target and layer, JSON and CSV.
- **Estimate.** `--estimate` adds, for single-ended surface microstrip and stripline rows only, the impedance from public closed forms and the width meeting the target, `INFERRED`.
- **Altium build.** Targets stay in the model, named by one `altium.not-lowered` info at `impedance`. Their derived rules are ordinary design rules: the rule writer of c0084 refuses a rule with a layer (`scope-unsupported`) and has no `exact` row for `diff_pair_gap` (c0104), so each derived rule gets its own warning at `design-rules/<kind>` and no Altium file changes.

Size: 8.5 design-days; cut order in the design.

## Prerequisites

What must be on `dev` before this change starts:

- Release `0.3.0` is cut, with c0084 archived (the Altium rule lowering this change's Altium requirement stands on).
- c0101 (the stack-up in the model and the board file: `Stackup.impedance_controlled`, `Stackup.between`).
- c0104 (the kind `diff_pair_gap` with its layer clause and `opt`, `NetClass.diff_pair_*`, `select.pair`, the Altium rows of the pair kinds).
- c0100 where a test names a layer beyond the fourth; nothing else of this change needs it.

No requirement is modified, so no delta is regenerated. c0116 and c0117 use this change's table.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-model`: ADDED "Impedance targets in the rules model".
- `design-dsl`: ADDED "Impedance targets in the DSL", "Impedance targets in a build".
- `kicad-file-backend`: ADDED "Tuning profiles for impedance targets", "Tuning profiles are read into impedance targets".
- `board-analyses`: ADDED "Impedance estimates", "Impedance formula sources are recorded".
- `manufacturing-exports`: ADDED "Impedance table for the fabricator".
- `cli-contract`: ADDED "Impedance command".
- `kicad-oracle`: ADDED "Impedance targets pass the oracle".
- `altium-build`: ADDED "Impedance targets in an Altium build".

## Non-goals

- Estimates for pairs: nowhere in v0.4 (open question): public closed forms for coupled lines are long, and the fabricator sets pair geometry.
- Delays, time-domain tuning and time units in rules: nowhere in v0.4, the yardstick matches length (c0106).
- Routing at these widths: c0107, c0110. Stack-up and its flag: c0101. Pair kinds: c0104. Severities: c0114. Export and manifest kinds: c0116 (the table is no manifest entry here). The drawn table: c0117.
- Default ohms, tolerance or permittivity: nowhere, the user gives every number (c0047).
- Solder mask, etch angle, frequency and loss in the estimate: nowhere, the closed forms omit them.
- A KiCad 9 profile: nowhere, 9.0 has none.
- Targets written into or read from Altium documents, and width rules per layer there: nowhere for now. No public source recorded in `docs/formats/altium/` states the record of an impedance profile, and the closed scope grammar of the rule writer (c0084) holds no layer. `fenolite impedance` takes KiCad input and built projects only.

Limits: exact width and gap rules (a neck-down needs an area rule of c0103); profiles never deleted, and read only when a class names them.

## Evidence level required

- Per-layer rules: `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-DRU-IMPEDANCE`). Profiles: `KICAD-VERIFIED (10.0.x)` (`H-K-PRO-TUNING-DRC`); their key set `INFERRED` until a GUI save (`H-K-PRO-TUNING-KEYS`).
- Estimates: `INFERRED` (`H-G-AN-ZMS`, `H-G-AN-ZSL`).

## Impact

- New: `backends/kicad/tuning.py`, `analysis/impedance.py`, `exports/impedance.py`, `dsl/impedance.py`, `cli/cmd_impedance.py`, `docs/impedance.md`, one data file `tests/data/kicad/project/tuning_10.kicad_pro` with its entry in `tests/data/MANIFEST.toml`.
- Changed: `model/rules.py`, `dsl/{design,convert}.py`, `lens/{build,altium}.py`, `backends/kicad/{pro,triad,proerrors}.py`, `cli/data/explain.toml`, the rules schema.
- Model documents: `rules.json` gains the key `impedance`; 0.2.x and 0.3.0 cannot read a document that carries it.
- A new command, so the contract page, the consistency test and `fenolite capabilities` gain it, and so do the command lists of the agent guide (c0079, c0080) when they are on `dev`.
- Source ids S-0640 to S-0643, from the block S-0640 to S-0659 reserved for this group (free in `docs/evidence/sources.md` at `9aba2dff`, whose highest id is S-0601).
