## ADDED Requirements

### Requirement: Via protection of script copper
`resolve_copper` SHALL give every via it creates the protection of the intent that makes it: the `protection` attribute of the via step, of the via intent or of the stitch intent, read by attribute like `kind`. A step or an intent without the attribute gives `ViaProtection()`, so the intents of earlier scripts and tests keep their meaning.
- A `protection` that is not a `fenolite.model.board.ViaProtection` MUST give `kicad.copper.bad-intent` naming the key, and the intent creates nothing.
- Every via of a stitch MUST carry the stitch's protection.
- `merge_copper` MUST compare `Via.protection` with the other modelled fields of "Script copper is regenerated": an existing script via whose protection differs from its regenerated copy MUST give the `kicad.copper.regenerated` info, and the copy's protection is written. Whether an item without a copper uuid is a duplicate MUST still be judged without it, so a user's copy that differs only by its protection is removed as before.
- The board default is not copied into script vias: a script via whose fields are `None` follows `Board.via_protection` as any via does (`kicad-file-backend`, "Via protection defaults on boards").
- `copper.py` keeps the import rule of "Copper module": `ViaProtection` comes from `fenolite.model`, never from `fenolite.dsl`.

#### Scenario: Via intent with a protection
- **GIVEN** the blink built for target 10 and the via intent `tp1` on `GND` with `protection=ViaProtection(tenting_front=True, tenting_back=False)`
- **WHEN** `uv run pytest tests/unit/backends/kicad/test_copper_tracks.py -k protection` resolves it
- **THEN** the created via has that protection, and an intent without the attribute gives a via whose protection is `ViaProtection()`

#### Scenario: Every stitch via protected
- **GIVEN** a stitch intent along a polyline on `GND` with `protection=ViaProtection(filling=True, capping=True)`
- **WHEN** it is resolved
- **THEN** every created via has `filling == True` and `capping == True`

#### Scenario: Protection edited in KiCad is regenerated
- **GIVEN** the blink resolved with the via intent `tp1`, after which the via's protection is changed to `ViaProtection(tenting_front=False, tenting_back=False)`, its uuid kept
- **WHEN** it is resolved again with the same intents
- **THEN** the via has the intent's protection again, and one `kicad.copper.regenerated` info names its uuid

#### Scenario: Not a protection
- **GIVEN** a via intent whose `protection` attribute is the string `"tented"`
- **WHEN** it is resolved with `issues=found`
- **THEN** nothing is created, and `found` holds one `kicad.copper.bad-intent` naming its key
