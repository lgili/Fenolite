## Why

The dogfood buck board passed a fab rule set to `write_triad`. c0018 wrote the rules to `.kicad_dru`, but the project kept the template's board-setup minimums (`board.design_settings.rules`: tracks 0.2 mm, vias 0.5 mm, holes 0.3 mm, copper to edge 0.5 mm). KiCad's manual says that no rule may go below these minimums (S-0038), so `kicad-cli` reports items that the rule set allows. c0010 only warns when a net class is below a minimum.

## What Changes

- `backends/kicad/lowering.py`: `MINIMUM_KEYS` maps the kinds `clearance`, `track_width`, `via_diameter`, `hole_size` (with `via_drill`) and `edge_clearance` to their keys, such as `min_through_hole_diameter`, per target major.
- `lower_minimums` finds, per kind, the board-wide rule that KiCad applies last: selector `all`, no second selector, no layers. When it has severity `error` and a `min`, the minimum becomes the least `min` of that rule and of the later rules of its kind, so no rule's `min` falls below it.
- `backends/kicad/pro.py`: `synthesize_project` and `update_project` write these values before net classes are lowered, so c0010's floor warning compares with them.
  - Equal values keep their spelling; every other key is kept.
  - Without a board-wide rule the text is unchanged.
  - `project_minimums` reads the values. Minimums are never lifted into the model's rules.
- Board-wide rules still go to `.kicad_dru`, unchanged (c0018).
- Five `kicad.project.*` codes: infos `minimum-replaced` and `minimum-kept`; warnings `rule-below-minimum` (a rule below a kept minimum) and, from `class_conflicts`, `class-shadowed` (a board-wide clearance rule overrides a larger class clearance) and `default-over-rule` (the template's `Default` stays above that rule). Warnings are gated per key and major by tables pinned to `kicad-cli` 9.0.9 and 10.0.6 probes.
- A bench built through the model with a scoped canary, probes `pro-min-*`, hypotheses `H-K-PRO-MIN-*`, rows in `project.md` and `rules.md`, census counts.
- No new rule kinds.

Estimated at 6.5 working days (design, "Budget").

## Capabilities

### New Capabilities
- (none)

### Modified Capabilities
- `rules-model`: ADDED "Board-wide rules lower to board-setup minimums", "Conflicts with board-setup minimums are reported" and "Class clearances against board-wide clearance rules are reported".
- `kicad-file-backend`: ADDED "Project files carry the board-setup minimums"; MODIFIED "Project files are synthesised and preserved" and "Project issue codes", one sentence each that lets another requirement take named keys or add codes.
- `kicad-oracle`: ADDED "Board-setup minimums are proved by kicad-cli".

## Non-goals

- Net-class lowering (c0010), custom-rule lowering (c0018), the copper check (c0029), zone settings (c0031) and `rule_severities` (c0020).
- New rule kinds (annular width, hole-to-hole, hole clearance, micro-vias); the other 14 minimum keys are kept verbatim.
- Reading minimums back into the model as rules.
- A rule constructor in the DSL (an open question of c0011); v0.1 DSL builds carry no rules.

## Evidence level required

- The five keys are read and applied, and the written project lets the rule values take effect: `KICAD-VERIFIED (9.0.x, 10.0.x)`, always with a canary (`H-K-PRO-MIN-KEYS`, `H-K-PRO-MIN-WRITE`). The 9.0 key names come from the derived 9 template until the 9.0.9 run reads them.
- A minimum governs a lower custom rule: per kind and major, as measured on board-wide rules (`H-K-PRO-MIN-RULE`). Rules with a condition, or of severity `warning` or `ignore`, stay `INFERRED` (S-0038).
- How a board-wide clearance rule meets class clearances: as measured (`H-K-PRO-MIN-CLASS`).
- Value choice, update rules and issue codes: mechanical.

## Impact

- Extends `lowering.py`, `pro.py` and `proerrors.py`; no new module, and no model, schema, CLI or dependency change.
- Depends on c0010 (archived), whose two requirements above it modifies; c0012 later uses the same exception paths. Also depends on c0018, c0017 and c0009. Implemented right after c0011, which is archived.
