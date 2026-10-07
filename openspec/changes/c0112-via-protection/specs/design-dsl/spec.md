## ADDED Requirements

### Requirement: Via protection in the DSL
`fenolite.dsl.protect(*, tenting=None, covering=None, plugging=None, capping=None, filling=None) -> ViaProtection` SHALL build the model value of `design-model` "Via protection in the board model", and `Design.via`, `via_step` and `Design.stitch` SHALL take the keyword `protection=None` and record it on their intents.
- `tenting`, `covering` and `plugging` MUST take `True` (both sides `True`), `False` (both `False`), `"front"` (front `True`, back `False`), `"back"` (front `False`, back `True`) or `None` (both `None`). `capping` and `filling` MUST take `True`, `False` or `None`. Any other value MUST raise `DslError` naming the argument and the value.
- `protection` MUST be `None` or a `ViaProtection`; any other value MUST raise `DslError` at the call, naming the copper key, or `via_step` for a step. `None` records `ViaProtection()`.
- `ViaStep`, `ViaIntent` and `StitchIntent` (`dsl/intents.py`) MUST gain the last field `protection: ViaProtection = ViaProtection()`, and `dsl.copper(design)` MUST return it, so intents built without it compare equal to those of earlier scripts.
- `fenolite.dsl` MUST re-export `protect`, as "DSL package" allows, and the package keeps importing only the standard library, `core` and `model`. `to_model` MUST NOT change for intents: they are not model objects.

#### Scenario: Values of protect
- **WHEN** `protect(tenting="front", plugging=True, filling=True)` and `protect()` are called
- **THEN** the first equals `ViaProtection(tenting_front=True, tenting_back=False, plugging_front=True, plugging_back=True, filling=True)`, and the second equals `ViaProtection()`

#### Scenario: Refused values
- **WHEN** `protect(tenting="both")`, `protect(capping="front")`, `protect(covering=1)` and `design.via("v", mm(1), mm(1), net=gnd, protection="tented")` are called
- **THEN** each raises `DslError`, the first naming `tenting` and `'both'`, the last naming `v`

#### Scenario: Intents carry the protection
- **GIVEN** `design.via("tp1", mm(5), mm(5), net=gnd, protection=protect(tenting="back"))`, a track whose path holds `via_step(mm(8), mm(8), to="B.Cu", protection=protect(filling=True, capping=True))`, and `design.stitch("ep", net=gnd, pitch=mm(1), region=…, protection=protect(plugging=True))`
- **WHEN** `copper(design)` is called
- **THEN** the via intent, the via step and the stitch intent carry those values, and the via step of `led_a` in "A track in board coordinates" still equals `ViaStep(Point(136_000_000, 114_000_000), "B.Cu", None, None)`

#### Scenario: Import edges
- **WHEN** `uv run pytest tests/unit/test_import_graph.py` runs
- **THEN** it passes with no `ALLOWED` change

### Requirement: Via protection defaults in the DSL
`Design.via_protection(protection, *, locked=False)` SHALL declare the board's default protection, and `to_model` SHALL set `Board.via_protection` to it; `via_protection_locked(design) -> bool` (`dsl/convert.py`) SHALL return `locked`, and `False` without a call. This requirement adds a step to "Built project files", and its codes join the `build` envelope as "Build issue codes" allows.
- `protection` MUST be a `ViaProtection` and `locked` a `bool`; a second call MUST raise `DslError`. A design without the call MUST give `Board.via_protection = None`, and its build MUST write every file with the bytes it had before this change, for both targets.
- `lens.build.build_design` MUST take `lock_via_protection: bool = False`, and `cli/cmd_build.py` MUST pass `via_protection_locked(design)`. On a created board the writer follows `kicad-file-backend` "Via protection defaults on boards"; with an existing board, `layout-lens` "Via protection defaults across rebuilds" decides the default first.
- After that decision, `via_protection.not_exported(design)` MUST give one `kicad.via.protection-not-exported` (info) when the board's effective default holds `True` for a covering, plugging, capping or filling field and at least one via of the written board takes that value from the default, its own being `None`. Its message MUST name those fields and the number of such vias, and say that `kicad-cli` 10.0.6 writes them to no fabrication file (`H-K-VIAPROT-OUTPUTS`); its hint MUST name `protection=`. The code belongs to the table of "Via protection defaults across rebuilds".
- `docs/dsl.md` MUST describe `protect`, `protection=`, `Design.via_protection`, the rebuild rule, what each target holds, and the gap of the info.

#### Scenario: Default in the model
- **GIVEN** `design.via_protection(protect(tenting="front"), locked=True)` in a blink variant
- **WHEN** `to_model` runs and `via_protection_locked` is called
- **THEN** `board.via_protection == ViaProtection(tenting_front=True, tenting_back=False)` and `via_protection_locked(design) is True`

#### Scenario: Refused calls
- **WHEN** `design.via_protection("tented")`, `design.via_protection(protect(), locked=1)` and a second `design.via_protection(protect())` are called
- **THEN** each raises `DslError`

#### Scenario: Built for both targets
- **GIVEN** a blink variant with `design.via_protection(protect(tenting=False))` and a via intent with `protection=protect(tenting=True)`
- **WHEN** it is built with `--dry-run --json` for target 9 and for target 10 and each planned board is read with `read_board`
- **THEN** both exit 0, each board's `via_protection` has both tenting fields `False`, and the script via has both tenting fields `True`

#### Scenario: A 10.0 feature for target 9
- **GIVEN** a blink variant whose via intent has `protection=protect(filling=True)`
- **WHEN** it is built with `--confirm` for target 9
- **THEN** the exit code is 7, stderr carries `FEN-7001` with `kicad.board.via-protection-too-new`, and nothing is written

#### Scenario: A default that no file carries
- **GIVEN** a blink variant with `design.via_protection(protect(plugging=True))` and two via intents without a protection
- **WHEN** it is built with `--dry-run --json` for target 10
- **THEN** the exit code is 0, and `issues` hold one `kicad.via.protection-not-exported` naming `plugging_front`, `plugging_back` and 2 vias
