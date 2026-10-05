## Why

Fenolite's rule model has six kinds: clearance, track width, via diameter, via drill, hole size and edge clearance. A design that needs a hole-to-hole distance, an annular ring, a courtyard gap or a creepage distance has to hand-write a `.kicad_dru` rule, which `read_rules` keeps opaque and no check of Fenolite understands. The script can declare net classes and minimums (c0054), but no rule with a selector.

The plan gives v0.2b "full rules → `.kicad_dru` (courtyard/silk/hole-to-hole/annular/creepage)". c0026 left `annular_width`, `hole_to_hole` and `hole_clearance` open as kinds. Probes on 9.0.9 and 10.0.6 (2026-10-05) show how KiCad treats each:

- `hole_to_hole`, `hole_clearance` and `annular_width` are enforced on both majors, with a net condition, under DRC types of the same names.
- `courtyard_clearance` is enforced on both majors as `courtyards_overlap`. It selects a footprint by `A.Reference`, never by `A.memberOfFootprint`.
- `silk_clearance` fires as `silk_overlap` and `silk_over_copper`, also between a footprint's own silkscreen and its other items.
- `creepage` is enforced on 10.0.6 (c0047's bracket). 9.0.9 reports nothing on the same bench, below or above the value.

## What Changes

- **Six new kinds** in the model and the lowering: `hole_to_hole`, `hole_clearance`, `annular_width`, `courtyard_clearance`, `silk_clearance` and `creepage`, each with its written constraint, limits and selector rules.
- **Kind support by major.** `rulemap.KIND_SUPPORT` holds the majors whose `dru-kind-*` probe passed. A rule of a kind outside its entry gives `rules.kind-unchecked` (error); `--allow-lossy` drops it with `rules.dropped-for-target`. Creepage is therefore written for KiCad 10 only.
- **Selectors per kind.** `courtyard_clearance` takes `all` and references, written as `A.Reference == '…'`. `silk_clearance` is board-wide only. `selector_b` serves `clearance` and `creepage`.
- **Reading.** `read_rules` lifts the new kinds, so hand-written rules of these kinds become model rules.
- **A rule constructor in the DSL.** `design.rules.rule(name, kind, where=…, between=…, layers=…, min=…, opt=…, max=…, severity=…, priority=…)`, with selectors from `fenolite.dsl.select` (`net`, `netclass`, `ref`, `item`, combined with `&`, `|` and `~`).
- **Probes and acceptance.** One bench per kind on both majors; the plan's overlapping-rule fixture repeated for `hole_to_hole`. A probe checks that a board-wide rule of a new kind governs below the template's board-setup minimum.
- **Stale text.** The living rules text still states the pre-probe claims for `FLOOR_OVER_RULES`; it is replaced by the measured table.

Size: 10 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `rules-model`: MODIFIED "Rule kinds and limits", "Closed selector grammar", "Lowering refuses what it cannot represent", "Rule issue codes", "Conflicts with board-setup minimums are reported"; ADDED "Kind support by major".
- `kicad-file-backend`: MODIFIED "Custom rules files are read and written".
- `design-dsl`: MODIFIED "Rule minimums in the DSL"; ADDED "Rule constructor in the DSL", "Selectors in the DSL".
- `kicad-oracle`: ADDED "New rule kinds are enforced by kicad-cli".

## Non-goals

- No requirement values: Fenolite ships no clearance, creepage or ring table (plan D6). Every value comes from the user.
- No zone connection or thermal kinds (c0031 rejected them as kinds), no `disallow`, no text, length or differential-pair kinds (v0.6).
- No check of the new kinds by Fenolite's own copper check: KiCad's DRC judges them.
- No board-setup minimum keys for the new kinds, unless the floor probe shows that they are needed (design, Decision 7).

## Evidence level required

- New rows `H-K-DRU-KIND-2` (the new kinds, per major) and `H-K-DRU-COURTYARD` (selection by reference), and `H-K-PRO-MIN-RULE-3` (floors of the new kinds), settled on 9.0.9 and 10.0.6. `KIND_SUPPORT` holds only probed majors.
- `dru.EVIDENCE` and the lowering keep their levels.

## Impact

- Changed: `model/rules.py`, `backends/kicad/{rulemap,lowering,dru}.py`, `dsl/design.py`, new `dsl/select.py`, `schemas/fenolite.model.v0/rules.json`, `docs/formats/kicad/rules.md`, `docs/formats/kicad/drc.md`, `docs/dsl.md`.
- No dependency on v0.2a.
