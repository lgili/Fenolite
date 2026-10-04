## Why

Change c0038 taught the experimental Altium PCB writer to hold copper and specified the hand-over of
script copper: `CopperSource(design, "script")`, requirement "Script copper in an Altium build". It left
one task to c0028 (its design, "Interface for c0028"): make `fenolite build --target altium` pass that
source. c0028 landed without the task.

Today a script that declares copper (`Design.track`, `Design.via`, `Design.stitch`) builds an Altium
project with **no** track and no via, and no issue says so:
`fenolite build examples/blink_routed/design.py --target altium` reports `result.copper.source == "none"`
and 0 tracks, while the KiCad build of the same script writes 11 tracks and 7 vias. `docs/altium.md`
still says that script copper is "handed over by change c0028 when it lands".

## What Changes

- `cli/cmd_build.py`, Altium branch: when the script holds copper intents and `--copper-from` is absent,
  the KiCad build of the script runs in memory (`lens.build.build_design` with the intents; no file is
  written), and its model is passed as `CopperSource(built.design, "script")`. The script's zones travel
  with that source.
- An error of that in-memory build (`kicad.copper.*`, `kicad.frame.*`, any other) refuses the Altium
  build: exit 5, nothing written. Its copper warnings and infos (`kicad.copper.end-unplaced`,
  `kicad.copper.stitch-empty`, `kicad.copper.stitch-skipped`) and `layout.unplaced` pass into `issues`, so
  an intent that creates nothing is never silent.
- With `--copper-from`, the existing rule holds ("`--copper-from` wins over any other source"): the
  intents are not resolved, and one `altium.not-lowered` info names them and the board.
- `lens.altium.refused_altium(...)`: the output of a build refused before the lens ran.
- A unit test file for the CLI path, and a `kicad-cli` oracle: the routed blink built for Altium and
  imported back holds the tracks and vias that the script declares.
- `docs/altium.md` ("Copper", route 1), `docs/cli-contract.md`, and step C7 in
  `docs/evidence/altium-pcb.md` for the maintainer.

## Capabilities

### Modified Capabilities (no new capability)

- `altium-build`: MODIFIED "Script copper in an Altium build"; ADDED "Script copper oracle" and "Script
  copper sample and author report".
- `design-dsl`: MODIFIED "Zones in a build" (one bullet: the source that carries the script's zones).

## Non-goals

- No new record, key or format fact: the records are those of c0038.
- No new issue code and no change to the copper logic of `lens.altium.build_altium`.
- No copper guard (`copper-check`, c0029) for the Altium target; `--copper-check` stays a usage error
  there.
- No arcs, keep-outs or blind vias from the DSL: it declares none.
- No change to `docs/roadmap.md` (its Phase 4 sentence on c0028 is noted for the release change).
- No `ALTIUM-VERIFIED` claim.

## Evidence level required

- The build stays experimental and `INFERRED`, as the Altium PCB writer labels itself
  (`PCB_BUILD_EVIDENCE`). With script copper, the envelope also combines the evidence of the copper
  resolver and of the board frame (`H-G-FRAME-UUID`, `H-G-FRAME-ROUTE`), lowest wins.
- The new oracle is one more proof of `H-A-PCB-CU-KICAD` (`ORACLE-VERIFIED(kicad-cli)`, 10.0.6). It
  settles no Altium row.
- Step C7 is pending until the maintainer opens the sample in Altium Designer. It names
  `H-A-PCB-CU-TRACK` and `H-A-PCB-CU-VIA`, which keep their level.
- Sources: none new. The change cites S-0161 and S-0166 (`kicad-cli pcb import`), already in
  `docs/evidence/sources.md`.

## Impact

- Code: `src/fenolite/cli/cmd_build.py`, `src/fenolite/lens/altium.py` (one helper).
- Tests: `tests/unit/cli/test_build_altium_script_copper.py`,
  `tests/kicad/altium/test_script_copper_oracle.py`.
- Docs: `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md`, `CHANGELOG.md`.
- Behaviour change: an Altium build of a script with copper intents now writes that copper, and can be
  refused by an intent error that it ignored before.
