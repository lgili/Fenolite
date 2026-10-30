## MODIFIED Requirements

### Requirement: Script copper in an Altium build
When the design carries resolved script copper, the Altium build SHALL write it. The design carries it as a `CopperSource` with `origin="script"`, whose `design` is the model that the KiCad build of the same script holds in memory after c0028's copper intents are resolved (`lens.build.build_design(…, copper_intents=…).design`): footprints placed, tracks and vias in the frame of the placements, nets of the script.
- **Hand-over in the build command.** When `dsl.copper(design)`, `dsl.generated(design)` or `dsl.role_copper(design)` is not empty and `--copper-from` is absent, `cli/cmd_build.py` MUST run `lens.build.build_design` in memory with the script's model, its placement requests, its copper layer count, the intents, the generated records and the role-copper request with the planner `fenolite.roles.copper.plan`, for the KiCad target of the context, and MUST pass `CopperSource(<that build's design>, "script")` to `build_altium`. No file of that KiCad build is written or planned, no layout of `--out` is read, and `kicad-cli` is not run. A script without intents, generated records and role copper MUST build as before, without the in-memory build.
- **Generated and role copper.** The source's generated and role zones MUST be written as polygons, its generated rule areas as keep-outs ("Rule areas, board items and area rules in an Altium build"), and its role clearance rules (`role.sw.*`, `role.hv.*`) as rules of the model; the in-memory build's `kicad.generate.*` and `roles.*` issues MUST pass into `issues` unchanged.
- **Zones.** The model given to `build_altium` MUST then hold no zone: the zones that the script declares (`design-dsl`, "Zones in the DSL") are in the source, which holds them as the KiCad build keeps them, so the build still takes one source.
- **Refusal.** When the in-memory build reports an error or returns no files, the Altium build MUST plan no file and exit 5 with those errors unchanged (`kicad.copper.*`, `kicad.frame.*`, `build.*`); `result.copper` and `result.pcb_document` are `null`. `lens.altium.refused_altium(design, *, name, issues, project_exists=False, form=…, sheets=…)` MUST give that output: no file, the given issues and the summary of a refused Altium build.
- **Nothing silent.** The warnings and infos of the in-memory build whose code starts with `kicad.copper.`, `kicad.generate.`, `roles.` or `kicad.frame.`, and its `layout.unplaced` warnings, MUST pass into `issues` unchanged, before the issues of the Altium build. So an intent that creates nothing (`kicad.copper.end-unplaced`, `kicad.copper.stitch-empty`) and dropped stitch candidates (`kicad.copper.stitch-skipped`) are reported. Its other warnings and infos concern KiCad files that are not written and MUST NOT pass.
- **Both sources.** With `--copper-from` the board wins ("Copper from a routed KiCad board"): the intents MUST NOT be resolved, and the build MUST give one `altium.not-lowered` info whose `where` is the path as given and whose message names the count and the keys of the intents. The kind "copper intents" extends the list of c0032's `altium.not-lowered` row. Generated and role-copper records with `--copper-from` MUST NOT be resolved and MUST give `kicad.generate.altium` ("Generated copper codes").
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

#### Scenario: Role copper built for Altium
- **WHEN** `fenolite build examples/roles/buck_shunt/good_roles.py --out B --target altium --dry-run --json` runs
- **THEN** the exit code is 0, `result.copper.source` is `script`, `result.copper.zones` counts the role zones of the KiCad build of the same script, and no issue is `kicad.generate.altium`
