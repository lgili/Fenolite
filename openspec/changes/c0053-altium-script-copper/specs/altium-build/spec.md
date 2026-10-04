## MODIFIED Requirements

### Requirement: Script copper in an Altium build
When the design carries resolved script copper, the Altium build SHALL write it. The design carries it as a `CopperSource` with `origin="script"`, whose `design` is the model that the KiCad build of the same script holds in memory after c0028's copper intents are resolved (`lens.build.build_design(…, copper_intents=…).design`): footprints placed, tracks and vias in the frame of the placements, nets of the script.
- **Hand-over in the build command.** When `dsl.copper(design)` is not empty and `--copper-from` is absent, `cli/cmd_build.py` MUST run `lens.build.build_design` in memory with the script's model, its placement requests, its copper layer count and the intents, for the KiCad target of the context, and MUST pass `CopperSource(<that build's design>, "script")` to `build_altium`. No file of that KiCad build is written or planned, no layout of `--out` is read, and `kicad-cli` is not run. A script without intents MUST build as before, without the in-memory build.
- **Zones.** The model given to `build_altium` MUST then hold no zone: the zones that the script declares (`design-dsl`, "Zones in the DSL") are in the source, which holds them as the KiCad build keeps them, so the build still takes one source.
- **Refusal.** When the in-memory build reports an error or returns no files, the Altium build MUST plan no file and exit 5 with those errors unchanged (`kicad.copper.*`, `kicad.frame.*`, `build.*`); `result.copper` and `result.pcb_document` are `null`. `lens.altium.refused_altium(design, *, name, issues, project_exists=False, form=…, sheets=…)` MUST give that output: no file, the given issues and the summary of a refused Altium build.
- **Nothing silent.** The warnings and infos of the in-memory build whose code starts with `kicad.copper.` or `kicad.frame.`, and its `layout.unplaced` warnings, MUST pass into `issues` unchanged, before the issues of the Altium build. So an intent that creates nothing (`kicad.copper.end-unplaced`, `kicad.copper.stitch-empty`) and dropped stitch candidates (`kicad.copper.stitch-skipped`) are reported. Its other warnings and infos concern KiCad files that are not written and MUST NOT pass.
- **Both sources.** With `--copper-from` the board wins ("Copper from a routed KiCad board"): the intents MUST NOT be resolved, and the build MUST give one `altium.not-lowered` info whose `where` is the path as given and whose message names the count and the keys of the intents. The kind "copper intents" extends the list of c0032's `altium.not-lowered` row.
- **Evidence.** With a script source the envelope MUST also combine `backends.kicad.copper.EVIDENCE` and `backends.kicad.frame.EVIDENCE`, lowest wins; the level stays `INFERRED` and the build stays experimental.
- The build MUST check a script source as "Copper from a routed KiCad board" checks a board (components, footprints, pad nets, outline, copper nets), so a source built from another script is refused. It MUST take the source's placements and give no `altium.placement-from-board` for this origin.
- The lens MUST NOT import `fenolite.dsl` or resolve intents itself: `lens.altium` receives a model (`package-layering`).
- Via types, layers and planes follow "Copper issue codes" and "Internal planes in an Altium build".
- `result.copper.source` MUST be `script`.

#### Scenario: Script source equals the committed sample
- **GIVEN** the KiCad build of the routed sample's script in memory, with the sample's copper put into its model
- **WHEN** `build_altium` runs on the script's model with that design as a `CopperSource` of origin `script`
- **THEN** `result.copper.source` is `script`, no issue is an error, and `routed.PcbDoc` equals the committed `tests/data/altium/routed/routed.PcbDoc` byte for byte

#### Scenario: Source of another script refused
- **GIVEN** the same source, and a script whose `R1` has another footprint
- **WHEN** `build_altium` runs
- **THEN** `files` is empty and `issues` holds one `altium.copper-board-mismatch` whose `where` is `R1`

#### Scenario: Routed blink built for Altium
- **WHEN** `fenolite build examples/blink_routed/design.py --out B --target altium --confirm --json` runs
- **THEN** the exit code is 0, `result.copper` holds `"source": "script"`, `"from": null`, `"tracks": 11`, `"arcs": 0`, `"vias": 7` and `"placements_from_board": 0`, `evidence.hypotheses` contains `H-G-FRAME-ROUTE`, `B` holds no `.kicad_pcb`, and `B/blink_routed.PcbDoc` read back holds 11 tracks and 7 vias on the nets `LED_DRV`, `LED_A` and `GND`

#### Scenario: Script source and board source give the same bytes
- **GIVEN** a confirmed KiCad build of `examples/blink_routed/design.py` in `K`
- **WHEN** the script is built with `--target altium` into `A`, and into `B` with `--copper-from K/blink_routed.kicad_pcb`
- **THEN** `A/blink_routed.PcbDoc` equals `B/blink_routed.PcbDoc` byte for byte, the second build reports `"source": "board"` and one `altium.not-lowered` info that names 4 copper intents and the board's path, and the first reports no such info

#### Scenario: Intent error refuses the Altium build
- **GIVEN** a variant of the routed blink whose track `led_drv` ends at `D1` pad `2` instead of `R1` pad `1`
- **WHEN** it is built with `--target altium --confirm --json`
- **THEN** the exit code is 5, `issues` holds `kicad.copper.net-conflict`, `result.copper` is `null` and nothing is written

#### Scenario: Intent to a staged part is reported
- **GIVEN** a variant of the routed blink without `d1.place(…)`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0, `issues` holds one `layout.unplaced` naming `D1` and two `kicad.copper.end-unplaced` (the keys `gnd` and `led_a`), and `result.copper` holds `"tracks": 4` and `"vias": 5`

#### Scenario: Zone and intents in one script
- **GIVEN** a variant of the routed blink with `design.zone(gnd, layers=("B.Cu",), clearance=mm(0.3))`
- **WHEN** it is built with `--target altium --dry-run --json`
- **THEN** the exit code is 0 and `result.copper` holds `"source": "script"`, `"tracks": 11`, `"vias": 7` and `"zones": 1`

#### Scenario: Script without intents is unchanged
- **WHEN** `fenolite build examples/blink_2layer/design.py --out B --target altium --dry-run --json` runs
- **THEN** `result.copper.source` is `none`, and the planned `blink.PcbDoc` equals the committed `tests/data/altium/blink/blink.PcbDoc`

## ADDED Requirements

### Requirement: Script copper oracle
`tests/kicad/altium/test_script_copper_oracle.py` SHALL prove with `kicad-cli` that the copper a script declares reaches the Altium document (S-0161, S-0166; `H-A-PCB-CU-KICAD`).
- The test MUST build `examples/blink_routed/design.py` with `fenolite build --target altium --confirm`, import the written `blink_routed.PcbDoc` with `kicad-cli pcb import --format altium`, and read the imported board with `fenolite.backends.kicad.pcb.read_board`.
- The expected copper MUST be the tracks and vias of `lens.build.build_design(…, copper_intents=dsl.copper(design)).design`, the script's intents resolved, never the Altium document read by Fenolite.
- Relative to each board's outline corner and within 10 nm, the imported board MUST hold every expected track with its layer, net name, end points and width, and every expected via with its position, net name, diameter, drill and through span, and MUST hold no other track, arc, via or zone. Every footprint MUST be at the script's position, rotation and side.
- Net classes and uuids are not compared, and the test MUST say why.
- The test MUST be skipped on `kicad-cli` 9.x (no `pcb import`, S-0166) and carries the `needs_kicad` marker. A pass settles no Altium row.

#### Scenario: Script to Altium and back
- **WHEN** `uv run pytest tests/kicad/altium/test_script_copper_oracle.py` runs with `kicad-cli` 10.0.6
- **THEN** the import exits 0 with no error in its report, and the imported board holds the 11 tracks and 7 vias of the script, item for item, and the three footprints at their placements

### Requirement: Script copper sample and author report
`docs/evidence/altium-pcb.md` SHALL gain step C7 in Part C, under the rules of c0035's "PCB author reports", so the maintainer can check a document whose copper comes from a script.
- **C7** MUST name the build command of `examples/blink_routed/design.py` for the Altium target, the SHA-256 of the `blink_routed.PcbDoc` it gives, and the expected result in Altium Designer: no repair prompt; 11 tracks and 7 through vias on two copper layers, on the nets `LED_DRV`, `LED_A` and `GND`; no connection line on those three nets. It names `H-A-PCB-CU-TRACK` and `H-A-PCB-CU-VIA` and MUST say that it registers no new row and stays pending until reported.
- The sample is built outside the repository; no file of it is committed.
- `docs/altium.md`, section "Copper", MUST describe route 1 as it works: the script's `track`, `via` and `stitch` calls reach the document with `--target altium`, the refusal on an intent error, and the rule that `--copper-from` wins. It MUST NOT say that script copper waits for another change. `docs/cli-contract.md` MUST say the same for `result.copper.source` `script`.

#### Scenario: Protocol names the script copper bytes
- **WHEN** `uv run pytest tests/unit/cli/test_build_altium_script_copper.py -k protocol` builds the routed blink for Altium and reads the page
- **THEN** step C7 names the SHA-256 of the fresh `blink_routed.PcbDoc`

#### Scenario: Route 1 is documented as working
- **WHEN** `docs/altium.md` is read
- **THEN** its section "Copper" names `Design.track`, `examples/blink_routed` and `kicad.copper.`, and `grep -c "when it lands" docs/altium.md` prints `0`
