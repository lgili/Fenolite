## MODIFIED Requirements

### Requirement: Guide pages
The agent guide SHALL hold twenty-three written pages under `src/fenolite/agent/skill/references/`, in the form that `fenolite.agent.guide` loads ("Packaged agent guide"): twelve tool pages, each teaching one part of making a board with Fenolite, and eleven practice pages, each teaching one part of designing a sound board.
- The tool topics MUST be `design-script`, `parts`, `footprints`, `placement`, `routing`, `rules`, `checks`, `files`, `fabrication`, `altium`, `recovery` and `library-items`.
- The practice topics MUST be `board-practice`, `board-schematic`, `board-floorplan`, `board-power`, `board-grounds`, `board-insulation`, `board-emc`, `board-routing`, `board-assembly`, `board-review` and `board-workflow`.
- `design-script` MUST teach: the shape of a script and its module-level `design`; `Design`, `Module`, `Net`, `Part`, `connect`, `no_connect` and `Power`; that a length carries a unit; the board frame (origin at the outline's top-left corner, Y down); and the cycle of an edit, `build --dry-run` and `build --confirm`, with what a rebuild keeps. It MUST hold the tested lines of `init`, `build`, `sync` and `template`.
- `parts` MUST teach: that a part needs a symbol id and a footprint; the built-in catalog and `catalog list --query`; KiCad's libraries through tables beside the script; pins by number and by name; `pad_map`; values with units (`ohm`, `farad`, `henry`, `volt`, `amp`, `watt`, `hertz`, `second`) and user properties; and the typed interfaces (`Interface`, `I2C`, `SPI`, `UART`, `USB2`, `Harness`, `DiffPair`). It MUST hold the tested line of `catalog`.
- `footprints` MUST teach `Footprint` and `Symbol` from dimensions, and MUST say that such geometry is `INFERRED` and what a person still checks against the part's datasheet.
- `library-items` MUST teach reviewed acquisition, licence acceptance, pins, offline restoration and repository tooling, and MUST hold tested lines of `get`.
- `placement` MUST teach `place()`, sides, rotation and locked placements, staged parts and `place --strategy grid`, `place --move`, and field placement. It MUST hold the tested lines of `place`, `pads`, `neighbors` and `region`.
- `routing` MUST teach the registered routers and what each is for, `route` with `--nets` and `--rip`, the meaning of `unrouted`, scripted copper (`track`, `via`, `stitch`, `via_step`, `arc_to`), zones and `fill`. It MUST hold the tested lines of `route`, `fill` and `net`, and of `fetch` when that command is registered.
- `rules` MUST teach net classes against minimums and selectors (`select`), MUST say that the limits are the user's or the fabricator's and that the page's numbers are examples, and MUST hold the tested line of `analyze`.
- `checks` MUST teach the stages of `check`, the fields of an issue, `explain`, the evidence levels, one fix per iteration, and `--fields`, `--stages`, `--format concise` and `--limit`. It MUST hold the tested lines of `check`, `explain`, `netlist`, `parity`, `doctor` and `capabilities`.
- `files` MUST teach how to read a file that Fenolite did not write, how to tell whether editing it is safe, how to compare two files or two designs, and how to undo a confirmed write. It MUST hold the tested lines of `inspect`, `diff`, `equivalent`, `roundtrip`, `fmt` and `restore`.
- `fabrication` MUST teach `export`, the bill of materials, the position file, the manifest and `render`, and MUST hold the tested lines of `export`, `render`, `bom`, `pnp` and `manifest`.
- `altium` MUST teach `build --target altium` and what it writes. It MUST hold a table with one row per Altium write kind, giving the status (in `write_kinds`, or `experimental`) and the evidence level that `fenolite capabilities --json` reports for that kind, and MUST NOT state a status in any other words; a test MUST compare the table with the reply and fail when they differ. It MUST say that the Altium verification kit is a run that a person performs in Altium Designer, and MUST hold the tested line of `kit`.
- `recovery` MUST follow "Recovery recipes", and MUST hold the tested lines of `guide` and `skill`.
- `board-practice` MUST teach the order of work (requirements and domains, floorplan, power and grounds, sensitive signals, routing, copper pours, checks, review), what a check cannot see, and that every limit comes from the user's standard or the fabricator.
- `board-schematic` MUST teach one master for every change, net classes on the schematic, connectivity compared by pin sets with single-pin nets, the order of fuses, DC ratings read with their test conditions, parts copied from references, and the tested line of `parity`.
- `board-floorplan` MUST teach partition by voltage domain and by function, a power flow in one direction, placing the parts that close the current loops first, mechanical keep-outs, decoupling at the pin, and the tested lines of `neighbors` and `region` as the way to look.
- `board-power` MUST teach loop area, copper sized for current and temperature rise with IPC-2152 named as the public method, wide pours instead of thin tracks, necks, parallel vias, and the tested line of `analyze` with `--kinds power`.
- `board-grounds` MUST teach ground domains, one tie between two domains and where it goes, the Kelvin connection of a sense element, the return path under a signal, how to prove a single tie, and the tested line of `net`.
- `board-insulation` MUST teach clearance and creepage, the inputs that set a distance (working voltage, pollution degree, material group, overvoltage category, altitude, insulation grade) with IEC 60664-1 named as the public method, slots and grooves, copper under parts and on both faces, the tested line of `analyze` with `--kinds clearance,creepage`, and that a measurement is not a compliance claim.
- `board-emc` MUST teach an immunity basis agreed first, the order of the mains entry, the raw and filtered sides kept apart, the earth bond in copper, protection of a pin in stages, loops compared by inductance, and that only a test closes an EMC requirement.
- `board-routing` MUST teach planning the ways across a barrier before routing (count the crossings), routing the critical nets first, 45° corners and no acute angle, few jogs, sensitive nets away from switching nodes, and the tested line of `route` with `--nets`.
- `board-assembly` MUST teach designators and their legibility, polarity and pin 1, test access per net with the tested line of `testpoints`, fiducials, footprints named by IPC-7351 with a courtyard, 3D bodies, and that the board is the master that a library is made from.
- `board-review` MUST teach the self-review checklist before a board is handed over, what reviewers reject, how a decision and an open item are recorded, and the tested line of `ready`.
- `board-workflow` MUST teach working on a copy, a SHA-256 taken before a write and compared before the next, never writing a file a person has open, one folder per version, the reviewed plan of `--plan`, `fenolite restore`, and labelling synthetic results.
- A public command that this list does not name MUST have its tested line on the tool page whose subject is closest ("Guide covers the public surface").
- Every page MUST end with a line `Read next:` naming at most three topics that exist.
- The start page MUST hold an index of the pages, one line per topic with its summary, between the lines `<!-- pages:begin -->` and `<!-- pages:end -->`.

#### Scenario: The eleven pages load
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k topics` calls `guide.pages()`
- **THEN** it finds `start`, the twelve tool topics, the eleven practice topics beside them and the generated references, each with a title and a one-line summary, and every `Read next:` names existing topics

#### Scenario: A page through the command line
- **WHEN** `uv run fenolite guide routing --text` runs
- **THEN** the exit code is 0 and the text names `direct`, `--rip`, `design.track` and `fenolite fill`

#### Scenario: A practice page through the command line
- **WHEN** `uv run fenolite guide board-grounds --text` runs
- **THEN** the exit code is 0 and the text names `single tie`, `Kelvin` and `fenolite net`

#### Scenario: Altium status follows capabilities
- **GIVEN** the reply of `fenolite capabilities --json --no-tools`, and a copy of it, made in the test, in which one Altium kind has moved from `experimental` to `write_kinds`
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k altium_status` compares the table of the page `altium` with each
- **THEN** the page agrees with the real reply, and the comparison with the copy fails naming the kind
