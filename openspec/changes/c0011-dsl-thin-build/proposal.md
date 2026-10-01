## Why

Plan item 0011 turns a short `design.py` into a KiCad project in one command. c0017, c0018 and c0010 write board, rules and project files from the model; nothing yet builds that model from a script. KiCad identifies board items by uuid and resolves project library rows through `${KIPRJMOD}` (S-0045, S-0046), so builds must be deterministic and self-contained before c0019 can preserve GUI edits and c0013 can check built projects.

## What Changes

- `src/fenolite/dsl/` (new; stdlib; `core` and `model` only): `Design`, `Module`, `Part`, `Net`, `connect`, `Interface`, `Power`, `DiffPair`, `Length` with `mm`/`mil`/`inch`/`nm`, `to_model`, `placements`, `KEYS`, `DslError`. A bare number is refused as a length. Ids come from names and module paths, never from the seed.
- `src/fenolite/lens/build.py` (new): `build_design` resolves lib ids (c0008), maps pins to pads by number, places footprints with c0017's `embed.place_footprint` (key = component path), stages unplaced parts beside the outline, validates, then calls c0010's `write_triad`. A design with an error writes nothing.
- `src/fenolite/cli/_script.py` and `cmd_build.py` (new): `fenolite build DESIGN.py --out DIR [--discard-layout]`, a mutating command. Files edited since the last build are refused (`build.layout-exists`, FEN-7001) until c0019.
- Output: the triad, footprints vendored into `DIR/lib/`, a per-target `fp-lib-table` (`libs.write_lib_table`), the `.fenolite/` layer files (`canonical.dump_texts`) and `.fenolite/build.json` (hashes of written files).
- `embed.with_property` gives built footprints a hidden `fenolite.path` property, for c0019.
- CLI: `GeometryError` gets FEN-3005; a refusal's `issues` reach the envelope.
- 9-format `Mini_R` and `Mini_LED` symbols; CC0 `examples/blink_2layer/` and `examples/blink_official/`; `docs/dsl.md`; sources S-0070 … S-0074 (Python documentation); hypotheses `H-K-BUILD-*`, probed first.

Budget: 8.5 working days (roadmap: 6.5); cut order to 7.25 in the design.

## Capabilities

### New Capabilities
- `design-dsl`: the DSL, the script runner, the `build` command and its outputs, issue codes, evidence, determinism and the blink examples.

### Modified Capabilities
- `design-model`: objects created from a design script as a fourth id case (MODIFIED `Identifier derivation`).
- `cli-contract`: FEN-3005 for geometry errors; refusals carry their issues (ADDED); keyed ids ignore `--seed` (MODIFIED `Determinism flags`).
- `kicad-file-backend`: path property on placed footprints (ADDED); `place_footprint`'s `copper` keyword (MODIFIED `Footprint embedding`).
- `kicad-library-resolution`: project library tables written per target (ADDED).
- `kicad-oracle`: built projects pass the build oracle on both majors (ADDED).
- `canonical-serialization`: layer texts in memory (ADDED).

## Non-goals

- Layout preservation and `moved()` (c0019); placement inside the outline (c0022); routing (c0016, c0023); zone fill (c0015).
- `check`, `inspect`, `doctor`, the `Oracle` protocol, the check copy set (`projectset.project_set`), the `drc.kicad` canary stage and RT1 of built designs (c0013); DRC findings as issues and connectivity attribution (c0020).
- Exports, manifest and render (c0024); `board_40parts`, the agent loop and the release gate (c0025); library fetch and cache (c0021).
- Paper, title block and drawing sheets (c0012).
- Custom DSL rules beyond `d.rules.netclass`, typed quantities, schematics, pad `pinfunction`/`pintype` and `sym-lib-table` in built projects (v0.2a, v0.2b); diff-pair lowering (v0.3).
- A sandbox: `build` runs the user's own `design.py` in-process.
- Any model entity, field, schema or id-prefix change.

## Evidence level required

- DSL, keyed ids, runner, determinism and readback: mechanical (hermetic tests).
- Build envelope: `INFERRED` (`H-K-BUILD-*`, `H-K-LIB-READ`, `H-K-PCB-WRITE`, `H-K-PRO-PATTERNS`), lowest wins.
- Blink example: `KICAD-VERIFIED` on 9.0.9 (`kicad-9`) and 10.0.6 (local and `kicad-10`): load, `pcb export pos` positions, no error-severity DRC violation with a firing canary, a violated class with a no-project control, and `fenolite.path` after a 10.0.6 re-save.
- Vendored-table parity on 9.0.9: recorded only while `H-K-LIB-DRC` is open.

## Impact

- Tests under `tests/unit/dsl`, `tests/unit/lens`, `tests/kicad/build`. No `package-layering` change.
- Registers: `sources.md`, `hypotheses.md`, `PROVENANCE.md`, `LEGAL-ANNEX.md`, `MANIFEST.toml`, probe files.
- No runtime dependency; one new command and code FEN-3005.
- Depends on c0010, c0017, c0018, c0009, c0014 and c0008.
