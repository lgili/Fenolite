## MODIFIED Requirements

### Requirement: Start page
`src/fenolite/agent/skill/SKILL.md` SHALL be the one page an agent reads first, under 200 lines, and every statement of it SHALL hold for the installed version.
- It MUST state: `fenolite capabilities --brief --json` first; `fenolite guide <topic> --text` as the way to read a page; the exit codes 0 to 7 with what to do for each; `--dry-run` before `--confirm`; that an evidence level below `KICAD-VERIFIED` is unconfirmed; one fix per iteration, judged by `fenolite check`.
- It MUST hold exactly one fenced block tagged `fenolite-loop` (`release-gate`, "Agent guide is executable"), say what each step is for, and say that `place` and `fill` change nothing on the starter and when they matter.
- It MUST say that the pages printed by `fenolite guide` belong to the installed version and that a copied skill folder names the version it came from in its last line.
- It MUST keep a section on the commands that answer small questions between the steps, and that section MUST name `inspect`, `pads`, `doctor` and every other public command that `agent/SKILL.md` named at the commit before it moved. `tests/unit/test_agent_skill.py` MUST hold that list of names and fail for one that the page no longer names.
- It MUST say that `capabilities --json` holds `result.matrix`, the reply to read before choosing an operation on a file kind, and that the status of each Altium write kind is read there; it MUST NOT give that status as a fixed word of its own.
- It MUST say, in one sentence, that the Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer and is not the agent guide.
- It MUST hold a section "Designing a good board" that says a board on which `fenolite check` exits 0 is not therefore a good board, and that sends the agent to the page `board-practice` before it places a part of a real board.
- It MUST NOT name a company, a private path or a user name, and MUST NOT state a design-rule value as a rule.

#### Scenario: Start page states the rules
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k rules` reads the file
- **THEN** it finds each statement above, a table row for each exit code 0 to 7, fewer than 200 lines, and no private path

#### Scenario: No command is lost
- **GIVEN** the list, held in the test, of the 22 public commands that `agent/SKILL.md` names at `9aba2dff`: `build`, `capabilities`, `check`, `diff`, `doctor`, `explain`, `export`, `fill`, `fmt`, `inspect`, `kit`, `manifest`, `neighbors`, `net`, `netlist`, `pads`, `place`, `region`, `render`, `restore`, `roundtrip` and `route`
- **WHEN** `uv run pytest tests/unit/test_agent_skill.py -k commands_kept` reads the start page
- **THEN** it finds `fenolite <name>` for each of them and for `guide`, `skill` and `init`

#### Scenario: The start page sends the agent to the practice pages
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k practice` reads the start page
- **THEN** it finds the heading "Designing a good board" and the topic `board-practice` in that section

### Requirement: Guide pages
The agent guide SHALL hold twenty-two written pages under `src/fenolite/agent/skill/references/`, in the form that `fenolite.agent.guide` loads ("Packaged agent guide"): eleven tool pages, each teaching one part of making a board with Fenolite, and eleven practice pages, each teaching one part of designing a sound board.
- The tool topics MUST be `design-script`, `parts`, `footprints`, `placement`, `routing`, `rules`, `checks`, `files`, `fabrication`, `altium` and `recovery`.
- The practice topics MUST be `board-practice`, `board-schematic`, `board-floorplan`, `board-power`, `board-grounds`, `board-insulation`, `board-emc`, `board-routing`, `board-assembly`, `board-review` and `board-workflow`.
- `design-script` MUST teach: the shape of a script and its module-level `design`; `Design`, `Module`, `Net`, `Part`, `connect`, `no_connect` and `Power`; that a length carries a unit; the board frame (origin at the outline's top-left corner, Y down); and the cycle of an edit, `build --dry-run` and `build --confirm`, with what a rebuild keeps. It MUST hold the tested lines of `init`, `build`, `sync` and `template`.
- `parts` MUST teach: that a part needs a symbol id and a footprint; the built-in catalog and `catalog list --query`; KiCad's libraries through tables beside the script; pins by number and by name; `pad_map`; values with units (`ohm`, `farad`, `henry`, `volt`, `amp`, `watt`, `hertz`, `second`) and user properties; and the typed interfaces (`Interface`, `I2C`, `SPI`, `UART`, `USB2`, `Harness`, `DiffPair`). It MUST hold the tested line of `catalog`.
- `footprints` MUST teach `Footprint` and `Symbol` from dimensions, and MUST say that such geometry is `INFERRED` and what a person still checks against the part's datasheet.
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
- **THEN** it finds `start`, the eleven tool topics, the eleven practice topics beside them and the two generated ones, each with a title and a one-line summary, and every `Read next:` names existing topics

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

### Requirement: Page budgets and writing rules
The pages SHALL stay small enough to be read whole. A tool page SHALL state only what Fenolite does; a practice page SHALL state design practice and SHALL state what Fenolite does only where it names a command.
- A written page MUST have at most 250 lines and 12 000 bytes. A generated page MUST have at most 600 lines. The files of the skill folder together MUST stay under 260 000 bytes.
- A page MUST NOT name a company, a fabricator, a standard's table, a private path or a person, and MUST NOT hold a change id (`c0000` form) or a hypothesis id (`H-…`).
- A line of prose that holds a call of `rules.minimum` or `rules.netclass` with a number MUST hold the word `example`.
- A sentence that says a result is verified MUST name the evidence label.
- A practice page MUST NOT give a distance, a width, a current or a temperature as a limit; a figure on it is an input of a named public method or is marked as an example.
- `tests/unit/agent/test_pages.py` MUST check the sizes, the forbidden forms and the `example` rule.

#### Scenario: Budgets hold
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k budget` runs
- **THEN** every written page is within 250 lines and 12 000 bytes, every generated page within 600 lines, and the folder under 260 000 bytes

#### Scenario: Forbidden forms are reported
- **GIVEN** a copy of a page, made in the test, that holds `c0042` in a sentence
- **WHEN** the writing-rules check runs on it
- **THEN** it fails naming the page and the line
