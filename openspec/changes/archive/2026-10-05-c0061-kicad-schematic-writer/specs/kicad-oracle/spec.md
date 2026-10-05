## ADDED Requirements

### Requirement: Schematic naming facts are probed
`tests/kicad/schematic/test_naming_probes.py` (marker `needs_kicad`, major-aware) SHALL settle on 9.0.9 and 10.0.6 the facts the schematic generator is written from, with sheets that `tests/kicad/schematic/_gencases.py` writes into `tmp_path`, and SHALL record each outcome as a probe of `PROBES`.
- **Pin frame** (`H-K-SCH-PINFRAME`). For each rotation (0, 90, 180, 270) and mirror (none, `x`, `y`), an instance of the 32-pin IC with one global label at each point `schlayout.pin_point` gives MUST leave no `pin_not_connected` violation (probes `sch-pin-frame-<angle>-<mirror>`, the mirror spelled `none`, `x` or `y`; outcome `absent`). A control whose labels follow another frame MUST leave pins open, or the probe is `inconclusive`. `schlayout.PROVED_FRAMES` MUST equal the pairs that are `absent` on both majors.
- **Unconnected pins** (`H-K-SCH-UNCONNECTED`). The names `sch export netlist` gives pins on no net MUST equal `netnames.unconnected_name` for: the named pins of the 32-pin IC and the two pins without a name of an authored probe symbol (probes `sch-unconnected-plain`, `sch-unconnected-unnamed`), named and unnamed pins of the three units of `Mini_DualGate` (`sch-unconnected-units`), and one pin per character class of an authored probe symbol: a blank, `/`, `+`, `~`, an overbar group, a digit start, a name used by two pins, `-`, `_`, `.` and braces (`sch-unconnected-chars`). Outcome `equal`; a class whose name differs MUST be recorded as `different` and left out of `PROVED_PIN_CHARS`.
- **Label texts** (`H-K-SCH-SLASH`). The net name of a global label MUST equal its text for the texts of `_gencases.LABEL_TEXTS` (letters, digits, blank, brackets, braces, parentheses, quote, backslash, a non-ASCII letter, `+`, `.`, `-`, `_`, `:`, `,`, `#`, `$`, `~`, `=`) (probes `sch-label-plain`, `sch-label-chars`), and `netnames.stored_name` of its text when it holds `/` (`sch-label-slash`). With a pad stored as `stored_name`, parity MUST report no `net_conflict` (`sch-parity-slash-stored`, outcome `absent`); with the pad stored raw, it MUST (`sch-parity-slash-raw`, outcome `present`).
- **Power** (`H-K-SCH-POWER`). A net with one `power_in` pin MUST give `power_pin_not_driven`, and MUST NOT once `fenolite:PWR_FLAG` is on it (`sch-power-flag`, outcome `absent`). Two hidden `power_in` pins of one name with labels of different nets MUST end on one net (`sch-hidden-power-joined`, outcome `present`), and the same pins embedded without `hide` MUST end on their two nets (`sch-shown-power-separate`, outcome `equal`).
- **Library rows** (`H-K-SCH-LIBTABLE`). Without a project table, ERC MUST report `lib_symbol_issues` (`sch-lib-missing`, outcome `present`). With the libraries of "Symbols of a built project", it MUST report neither `lib_symbol_issues` nor `lib_symbol_mismatch`, for a plain symbol (`sch-lib-vendored`) and for a pin-pad variant (`sch-lib-variant`), outcome `absent`.
- Oracle tests MUST assert on the reports read through `tests/_erc.py`, MUST run every tool through `KicadCli.run` on copies, and both probe files MUST be regenerated with `FENOLITE_PROBES_WRITE=1`.
- A probe whose outcome contradicts `design.md` MUST change the design and the affected requirement before the generator relies on it, and the task note MUST say which fallback was applied.

#### Scenario: Probes on both majors
- **GIVEN** `kicad-cli` 9.0.9 in the pinned image and 10.0.6 locally
- **WHEN** `uv run pytest tests/kicad/schematic/test_naming_probes.py tests/kicad/test_probe_results.py -rA` runs on each
- **THEN** every probe of this requirement has an outcome in the committed probe file of that version, and `sch-pin-frame-0-none` is `absent` on both

#### Scenario: Hidden power pins join
- **GIVEN** the probe sheet with two hidden `power_in` pins named `VSS`, labelled `GND` and `OTHER`
- **WHEN** its netlist is exported on 10.0.6
- **THEN** both pins are on one net, and the probe records `present`

#### Scenario: Slash stored
- **GIVEN** a sheet whose global label is `mod/LED_A`
- **WHEN** its netlist is exported
- **THEN** the net is named `mod{slash}LED_A`

### Requirement: Generated schematics pass ERC and parity
`tests/kicad/schematic/test_generated_oracle.py` (marker `needs_kicad`, major-aware) SHALL prove on 9.0.9 and 10.0.6 that the projects `build` writes are accepted by KiCad's ERC and by its parity test, for `examples/blink_2layer` and for an authored units design (one `Mini_DualGate` with marks, one part with a `pin_pad_map`, one module net with a slash), each built into `tmp_path` for the running major.
- **ERC** (`H-K-SCH-MINIMAL`). `sch erc --format json --severity-all --exit-code-violations` MUST exit 0 with no violation in any sheet (probes `sch-gen-erc-blink` and `sch-gen-erc-units`, outcome `equal`).
- **ERC controls.** Each of these edits of the built blink MUST give its violation: the label of one pin removed (`pin_not_connected`); the power flag of `VIN` removed (`power_pin_not_driven`); `sym-lib-table` removed (`lib_symbol_issues`).
- **Parity** (`H-K-SCH-PARITY`). `pcb drc --schematic-parity --format json --severity-all` MUST give an empty `schematic_parity` list for both designs.
- **Stand-in.** `tests/kicad/lens/test_update_stand_in.py` MUST show that `kicad-cli` loads a board rebuilt after the update stand-in (`layout-lens`, "Boards updated from the schematic keep their layout") and that its parity test and ERC report nothing.
- **Parity controls.** One pad moved to another net MUST give `net_conflict`; the Value of one footprint changed MUST give `footprint_symbol_mismatch`; one reference renamed on the board MUST give `missing_footprint` and `extra_footprint`; the paths of two footprints exchanged MUST give nothing.
- **Netlist.** The nets of `sch export netlist` MUST be, as sets of (reference, pin number): the nets of the built circuit with pins mapped to pads, plus one single-pin net per entry of `pad_nets` with that entry's name.
- **Check.** `fenolite check <dir> --json` MUST report no issue of severity `error` other than `kicad.drc.unconnected-items` (the designs are unrouted), with `netlist.assignment_compare` at 0 differences and `roundtrip` `ok`.
- **Re-save** (`H-K-SCH-RESAVE`, major 10). `sch upgrade --force` on a copy MUST leave ERC without violations, and a second re-save MUST be byte-identical (probe `sch-gen-resave`, outcome `equal`). The heads that the first re-save adds, drops or reorders MUST be written through `tests/_boards.py::census` and copied into `docs/evidence/kicad-schematic.md`; a difference MUST NOT fail the test.
- **Read-only.** The built folder's snapshot MUST be equal before and after every tool run.

#### Scenario: Blink on both majors
- **GIVEN** the blink built for the running major
- **WHEN** `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k "erc or parity" -rA` runs on 9.0.9 and on 10.0.6
- **THEN** ERC exits 0 with no violation, `schematic_parity` is empty, and every control gives its finding

#### Scenario: Units design
- **GIVEN** the units design built for the running major
- **WHEN** the same tests run
- **THEN** ERC reports no violation and no unplaced unit, parity is empty, and the netlist lists the mapped part's pins by pad number

#### Scenario: Check on a built project with a schematic
- **WHEN** `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k check` runs `fenolite check` on both built designs
- **THEN** `netlist.assignment_compare` reports 0 differences, and no issue names an `unconnected-` net as a difference

#### Scenario: Re-save recorded on 10.0.6
- **WHEN** `uv run pytest tests/kicad/schematic/test_generated_oracle.py -k resave -rA` runs with `FENOLITE_CENSUS_OUT` set
- **THEN** the probe `sch-gen-resave` records `equal`, and the census names the heads the re-save changed
