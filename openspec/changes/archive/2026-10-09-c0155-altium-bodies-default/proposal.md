## Why

Change c0121 writes the extruded component bodies of a board into the Altium PCB document and library on
request (`--altium-bodies extruded`) and kept the option `off` "until step X8 of Part X is reported"
(roadmap, "Open decisions", row 33; c0121's design, "Decisions (2026-10-06)", 2). Step X8 was reported on
2026-10-09 (S-0724): the file set `saved`, with its two stand-in keys, opened in Altium Designer 26.5 with
the bodies as written (`H-A-PCBX-BODY-OPEN`, `-SHORT`, `-LIB`, author reports). On 2026-10-09 the
maintainer decided that the Altium build writes component bodies by default.

## What Changes

- **Behaviour change:** `fenolite build --target altium` without `--altium-bodies` writes the extruded
  component bodies (`--altium-bodies extruded` is the default); `--altium-bodies off` gives the files of
  earlier versions, byte for byte. `result.pcb.bodies` reads `extruded` when the option is not given.
- `lens.altium.build_altium(bodies=...)` defaults to `extruded`, so the library build and the command
  agree. The writers below the build (`lens.altium.write_model`, `lower.from_design`, `lower.write_design`,
  `AltiumBackend.write` and `AltiumBackend.model_roundtrip`) keep `bodies="off"` as their default: they
  serve the round trips and the rewrite of a read document, whose recorded numbers were measured without
  bodies (Non-goals).
- A design whose footprints hold no extruded body with an outline gives the same files as before: a
  script declares no such body today, so the examples, the committed samples and the pinned builds do not
  move; only a model that holds such bodies (an import, a model built in Python) gains body records.
- Docs: `docs/altium.md`, `docs/cli-contract.md`, the agent guide (generated), `docs/evidence/altium-pcb.md`
  (step X8), `docs/roadmap.md` (row 33 decided), `CHANGELOG.md`.

Size: 0.25 design-day (a size, not time).

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-build`: MODIFIED "Component bodies in an Altium build" (added by c0121; the default is `extruded`).
- `altium-pcb-writer`: MODIFIED "Component bodies are reported" (modified by c0121; the scenario "Body
  height" is built with `--altium-bodies off`).

## Non-goals

- No change of the record, its form (`saved`) or its stand-ins; no change of what is or is not written of
  a body.
- No change of the default of the round trips (RT-A2 of a build excepted, which follows the build) or of
  a rewrite: the RT-A3 table of `docs/evidence/altium-roundtrip.md` stays the table of the default `off`.
- No write kind leaves `experimental`; no row moves. `H-A-PCBX-BODY-ID` (the counts of step X8.6) stays
  pending.

## Evidence level required

The default rests on `H-A-PCBX-BODY-OPEN` and `H-A-PCBX-BODY-LIB`, `ALTIUM-VERIFIED(author-report; AD 26.5;
2026-10-09; no artefact)`, and on the maintainer's decision of 2026-10-09. The write stays experimental.

## Impact

- Code: `src/fenolite/cli/cmd_build.py` (`DEFAULT_ALTIUM_BODIES`, the help text), `src/fenolite/lens/altium.py`
  (`build_altium`), docstrings that say the option is off by default.
- Tests: `tests/unit/cli/test_build_altium.py` (the default), `tests/unit/lens/test_altium_bodies.py`.
- Archive order: after c0121, whose requirement it modifies; c0121 waits for c0090.
