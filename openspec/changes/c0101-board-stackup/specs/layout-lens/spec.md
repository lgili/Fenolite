## ADDED Requirements

### Requirement: Stack-up across rebuilds
`fenolite.backends.kicad.stackup.merge_stackup(built, board, *, layers, locked) -> StackupMerge` SHALL decide the stack-up of the layout when a build merges an existing board, and `build_design` SHALL apply it to the `Merged` result of `merge_layout` before the layout is validated and written. For the `stackup` child of `setup` and the `thickness` of `general` it replaces the rule of "Board content outside the design is kept"; every other child of `setup` stays under that rule.
- The script's stack-up is `complete(built, layers)`, and the board's is its projection ("Stack-up on boards"); the two MUST be compared by `stackup.values`.
- Without a script stack-up, or with equal ones, the board's MUST be kept with its fragments, and no code is given.
- When the board has no projected stack-up (no node, or a node that "Stack-up on boards" calls incomplete or unmodelled), the script's MUST be written.
- When they differ and the script's is not locked, the board's MUST be kept, and `kicad.stackup.overridden` (info) MUST name the first entry or value that differs, with the hint "lock the stack-up in the script, edit it in KiCad's Board Setup, or re-run with --discard-layout".
- When they differ and the script's is locked, the script's MUST replace the board's, and `kicad.stackup.forced` (warning) MUST name the first entry or value that differs.
- `StackupMerge` MUST hold `stackup`, the decided value, and `source`: `script`, `board`, or `None` when neither holds one. `merge_stackup` MUST be pure, and run again on its own result with the same arguments it MUST return the same value.
- `merge_stackup` SHALL report only the codes of the closed table `stackup.MERGE_ISSUE_CODES`. They are `kicad.*` codes, so they pass through `lens.preserve.PRESERVE_ISSUE_CODES` and `lens.build.BUILD_ISSUE_CODES` unchanged, as "Layout issue codes" and `design-dsl` "Build issue codes" allow.

| code | severity | when |
|---|---|---|
| `kicad.stackup.forced` | warning | a locked `stackup()` replaced a board stack-up that differed from it |
| `kicad.stackup.overridden` | info | an unlocked `stackup()` differs from the kept board stack-up |

- The normal-form pass of "Preservation is the build's normal form" MUST NOT call it: the written board already holds the decided stack-up, so a rebuild over the build's own output writes the same bytes.

#### Scenario: An edit in KiCad wins
- **GIVEN** a confirmed target-10 build of the stack-up blink of `design-dsl` "Stack-up in a build", whose core is changed to 1.4 mm by token edit, with `general` thickness changed to 1.49 to match
- **WHEN** the build runs again with `--confirm`
- **THEN** the written `setup` and `general` nodes are tree-equal to the edited ones, `issues` holds `kicad.stackup.overridden` naming `dielectric 1`, and `result.stackup.source` is `board`

#### Scenario: A locked stack-up wins
- **GIVEN** the same edited build, and the script's stack-up declared with `locked=True`
- **WHEN** the build runs again with `--confirm`, and then once more
- **THEN** the first writes the core of 1.5 mm and `(thickness 1.59)` and its `issues` hold `kicad.stackup.forced`; the second writes every file with the same bytes and gives no `kicad.stackup.*` code

#### Scenario: A stack-up added to a built board
- **GIVEN** a confirmed blink build without a stack-up, after which `design.py` declares the stack-up of the stack-up blink
- **WHEN** the build runs again
- **THEN** the node is the first child of the written `setup`, every other child of `setup` is tree-equal to the board's, and `issues` hold no `kicad.stackup.*` code

#### Scenario: A KiCad stack-up kept without a script one
- **GIVEN** a confirmed blink build whose board gets a complete two-layer node by token edit, and a `design.py` without `stackup()`
- **WHEN** the build runs again
- **THEN** the node is written unchanged, and `result.stackup.source` is `board`
