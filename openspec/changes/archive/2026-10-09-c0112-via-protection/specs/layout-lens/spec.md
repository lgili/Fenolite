## ADDED Requirements

### Requirement: Via protection defaults across rebuilds
`fenolite.backends.kicad.via_protection.merge_default(script, board, *, locked) -> DefaultMerge` SHALL decide the board's via protection default when a build merges an existing board, and `build_design` SHALL apply it to the `Merged` result of `merge_layout` before the layout is validated and written. For the protection children of `setup` it replaces the rule of "Board content outside the design is kept"; every other child of `setup` stays under that rule.
- `script` is `Board.via_protection` of the built design and `board` the projection of the existing board ("Via protection defaults on boards"); they MUST be compared by `effective_default`.
- Without a script default, or with equal effective values, the board's MUST be kept with its fragment, and no code is given.
- When the board has no default (`None`), the script's MUST be written.
- When they differ and the script's is not locked, the board's MUST be kept, and `kicad.via.protection-overridden` (info) MUST name the first field that differs with both values, with the hint "lock the default in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout".
- When they differ and the script's is locked, the script's MUST replace the board's, and `kicad.via.protection-forced` (warning) MUST name the first field that differs.
- `DefaultMerge` MUST hold `default`, the decided value, `source` (`script`, `board`, or `None` when neither holds one) and `issues`. `merge_default` MUST be pure, and run again on its own result with the same arguments it MUST return the same value; a locked default then reports nothing, and an unlocked one that still differs from the kept board default reports `kicad.via.protection-overridden` again, as an overridden zone does at every build.
- The vias are not decided here: script vias follow `manual-copper` "Via protection of script copper", and every other via of the board keeps its protection with the rest of its fields ("Copper items follow their nets").
- `via_protection` SHALL report only the codes of the closed table `via_protection.ISSUE_CODES`. They are `kicad.*` codes, so they pass through `lens.preserve.PRESERVE_ISSUE_CODES` and `lens.build.BUILD_ISSUE_CODES` unchanged, as "Layout issue codes" and `design-dsl` "Build issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.via.protection-forced` | warning | a locked `via_protection()` replaced a board default that differed from it |
| `kicad.via.protection-overridden` | info | an unlocked `via_protection()` differs from the kept board default |
| `kicad.via.protection-not-exported` | info | vias take a covering, plugging, capping or filling of `True` from the board default only (`design-dsl`, "Via protection defaults in the DSL") |

- The normal-form pass of "Preservation is the build's normal form" MUST NOT call `merge_default`: the written board already holds the decided default, so a rebuild over the build's own output writes the same bytes.

#### Scenario: An edit in KiCad wins
- **GIVEN** a confirmed target-10 build of a blink variant with `design.via_protection(protect(tenting=True))`, whose `setup` tenting is then changed to `(tenting (front no) (back no))` by token edit
- **WHEN** the build runs again with `--confirm`
- **THEN** the written `setup` holds `(tenting (front no) (back no))`, and `issues` hold one `kicad.via.protection-overridden` naming `tenting_front`

#### Scenario: A locked default wins
- **GIVEN** the same edited build, and the script's default declared with `locked=True`
- **WHEN** the build runs again with `--confirm`, and then once more
- **THEN** the first writes `(tenting (front yes) (back yes))` and its `issues` hold `kicad.via.protection-forced`; the second writes every file with the same bytes and gives no `kicad.via.*` code

#### Scenario: A default added to a built board
- **GIVEN** a confirmed blink build without a default, after which `design.py` declares `design.via_protection(protect(tenting="front"))`
- **WHEN** the build runs again
- **THEN** the written `setup` holds the five children with `(tenting (front yes) (back no))`, every other child of `setup` is tree-equal to the board's, and no `kicad.via.*` code is given

#### Scenario: Equal in effect
- **GIVEN** a confirmed target-10 blink build without a default, whose `setup` is then given, by token edit, the five children that a 10.0.6 re-save writes: `(tenting (front yes) (back yes))`, `(covering (front no) (back no))`, `(plugging (front no) (back no))`, `(capping no)` and `(filling no)`; and `design.py` then declares `design.via_protection(protect(tenting=True))`
- **WHEN** `uv run pytest tests/unit/lens/test_build_via_protection.py -k effect` builds again
- **THEN** no `kicad.via.*` code is given, and the `setup` fragment is written as the board holds it
