## Context

- **Goal and date.** On Monday 2026-10-05 the maintainer starts a real board in Altium Designer from a Fenolite design. The chosen route is Fenolite's own clean-room writer: `fenolite build` writes a project file and a schematic in Altium's ASCII form, Altium compiles it, and the PCB is created inside Altium by its engineering change order ("Design » Update PCB Document"). There is no PcbDoc writer. This change pulls the first item of v0.4 ("writers for the four document kinds, starting with the ASCII schematic format", `docs/roadmap.md`) forward as an experimental writer; v0.3 (read) and the rest of v0.4 stay as planned.
- **The DSL (c0011, archived 2026-10-02).** `Part(ref, lib_id, footprint=None, value="")`, `Net`, `connect`, `Power`, `DiffPair`, `Module`, `Design`. `to_model` returns a model `Design` and reads no library:
  - one `Component` per part, with `lib_symbol_ref = lib_id`, `lib_footprint_ref = footprint or ""`, `value`, empty `pins` and `properties == {"fenolite.path": <component path>}`;
  - nets whose `PinRef.pin` is the designator as written (`U1[3]` gives `"3"`);
  - `Power(hv, lv)` as `Interface(kind="power", members={"hv": <net id>, "lv": <net id>})`;
  - net classes, modules, and an outline only when `board()` was called;
  - ids `derived_id(prefix, "dsl", <key>)` keyed by names and paths (`dsl.KEYS`), never by the seed.
- **The build (c0011).** `cli/cmd_build.py` runs the script, calls `to_model` and `placements`, and `lens.build.build_design` writes a KiCad project only. Reusable pieces: `BuildOutput`, `read_record`, `check_existing` (an output changed since the last build is refused with `LayoutExistsError`, `FEN-7001`, unless `--discard-layout`), `RECORD_FILE`, `RECORD_SCHEMA`, `CACHE_DIR` and the rule "validate fully, then write" (c0011 Decision 11).
- **Backend protocol (living `backend-protocol`).** A registered `Backend` must list `detect` and `read` in `operations` ("Capability reports"), its `write` writes the design's board ("Write capability fields"), and the scenario "Built-in backend listed" expects one built-in backend, `kicad`.
- **Layering (living `package-layering`).** `backends.<x>` may import `model`, `geometry` and `backends.base`; `lens` may import `model` and `backends`; `cli` may import anything. A package `backends.altium` fits the existing row, and `lens/altium.py` may import it and `lens.build`. No layering change.
- **Spelling of the backend option.** c0012's committed `template build SPEC --target kicad` uses `--target` to name the backend.
- **Requirements that other changes modify.** c0019, c0021 and c0027 MODIFY `design-dsl` "Build command"; c0019 and c0027 also "Built project files", "Build issue codes" and "Build evidence"; c0019 also "Edited outputs are not overwritten". c0019's version of "Build command" adds: "Later requirements MAY add `build` options, steps of `cmd_build` and keys of `result`; each such requirement names this one."
- **Evidence rules.** `Level.ALTIUM_VERIFIED_AUTHOR_REPORT` exists, and `release_verified` is `False` for it (`verification-evidence`). The register writes author reports as `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <date>; no artefact)` ("Author-report rows"); `register_problems` checks that form only for `H-A-WRITE-*` and `H-A-PH-*`. `LEGAL.md` block A allows reporting what a licensed tool does with files one may use; P3 and P4 forbid files and licences one may not use for this.
- **Format facts (public sources, recorded by the format research of 2026-10-02).**
  - Altium saves a schematic as "SCH ASCII Version 5.0", a text file with the extension `.SchDoc` (S-0133). The file starts with the header record `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=<records after it>` (S-0002, S-0130, S-0131).
  - Each record is one line of `|KEY=VALUE` fields; a key ends at the first `=`; booleans are `T`, and false is usually omitted. No escape for `|` is documented; KiCad's reader joins a line ending with `|>` to the next one and trims values. Plain values are 8-bit code-page text, and `%UTF8%` keys repeat them in UTF-8 (S-0130, S-0131, S-0133).
  - Records after the header are numbered from 0; record 0 is the sheet `RECORD=31`; owners precede their children, and `OWNERINDEX` holds the owner's number (S-0130, S-0131).
  - Lengths are integers in units of 10 mil (with an optional `_FRAC` of 1/100 000 unit); the origin is the bottom-left corner and Y grows upwards; a component's children carry absolute sheet coordinates (S-0130, S-0131). The KiCad page's "base value in mils" contradicts its own sheet table (S-0002).
  - `SHEETSTYLE` 0 to 4 are A4, A3, A2, A1 and A0, with drawing areas from 1150 × 760 to 4460 × 3150 units; `USECUSTOMSHEET=T` with `CUSTOMX` and `CUSTOMY` gives a custom size (S-0002, S-0130, S-0131).
  - Component `RECORD=1` (`LIBREFERENCE`, `DESIGNITEMID`, `SOURCELIBRARYNAME`, `PARTCOUNT` = parts + 1, `CURRENTPARTID`, `DISPLAYMODECOUNT`, `UNIQUEID`); rectangle 14; pin 2 (`LOCATION` is the body end, the electrical end lies `PINLENGTH` away from the body, `PINCONGLOMERATE` holds the direction and the shown texts, `ELECTRICAL=4` is passive); designator 34; parameter 41 (`NAME=Comment`; a text that starts with `=` names another parameter); footprint chain 44 → 45 (`MODELNAME`, `MODELTYPE=PCBLIB`, `MODELDATAFILE0` = the library file) → 46, 48 (S-0130, S-0131, S-0135, S-0137, S-0142, S-0144).
  - Wire 27 (`LOCATIONCOUNT`, `X1`, `Y1`, …), net label 25 (its lower-left hotspot must touch a wire or a pin; labels connect within the sheet), power port 17 (`STYLE` 2 bar, 4 power ground; same-named ports connect across the design) (S-0130, S-0131, S-0140).
  - Component unique ids are eight letters from `A` to `Y`; they link schematic and PCB components, with designators as the fallback; duplicate component ids are reported by the compiler and not repaired (S-0130, S-0139).
  - The `.PrjPcb` is an ASCII file listing the project documents: `[DocumentN]` sections with `DocumentPath`, relative to the project folder; `[Design]` with `Version`; CR LF (S-0132, S-0134, S-0142, S-0143).
  - Placed components are cached in the design, and models are linked by name, not copied (S-0137). "Tools » Update From Libraries" takes its source from the component's library link, lists unknown parts as `<Not Found>`, and offers full replacement or "Replace selected attributes" with separate switches for graphics, parameters and models (S-0136). The change order finds footprints in the project's libraries, the installed libraries and the search paths, the project folder first (S-0138, S-0141).
- **Tools.** `kicad-cli` 10.0.6 is installed locally. It chooses a schematic reader from the extension (`.kicad_sch`, else KiCad's legacy reader) and never tries its Altium importer (S-0132). On 2026-10-02, authored ASCII files with CR LF and with LF line ends, and a one-line text file, gave "Failed to load schematic" and exit 3 for every command tried (`sch export netlist`, `sch erc`, `sch upgrade`, `sch export svg`) (S-0020). So `kicad-cli` cannot check this writer.
- **Schedule.** Friday night and Saturday: implementation in a separate git worktree. Saturday: the maintainer opens the first sample in Altium. Sunday: fixes. Monday: use.

## Goals / Non-Goals

**Goals:**
- `fenolite build DESIGN.py --out DIR --target altium` writes `<name>.PrjPcb` and an ASCII `<name>.SchDoc` that Altium opens, compiles into the design's nets, and turns into a PCB through the engineering change order.
- One component per part: a generic rectangular body with the pins the design uses, the designator, the value as comment, the library link that "Tools » Update From Libraries" follows, and the footprint link that the change order places.
- Bytes that depend only on the design, and component unique ids keyed by component path, so a rebuild keeps the links between schematic and PCB.
- A hand-checkable sample for the maintainer on Saturday morning, a test protocol for every open question, and evidence that says exactly what was observed.
- No byte of a KiCad build changes.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Real symbol graphics, and connectivity after a full "Update From Libraries" when the library symbol's pins sit elsewhere (Decision 6, `H-A-SCH-UPDATE`).
- Pin numbers or names taken from any library: the writer reads nothing.
- Placement on the PCB, which Altium's change order creates; DSL placements are reported as not lowered.

## Decisions

1. **The target is an option of `build`: `--target {kicad,altium}`, default `kicad`.** `cmd_build` keeps one runner, one envelope and one mutation path, and branches after `to_model`.
   - The ADDED requirement "Altium build target" (`altium-build`) names `design-dsl` "Build command" as the requirement it extends, as c0019's text allows. With `--target kicad` every byte and key stays as today.
   - Rejected: a separate command `build-altium` (a second runner and envelope for one branch). Rejected: a `Design(target=…)` keyword (the same design may be built for both targets, and c0019, c0027 and c0028 already change the DSL). Rejected: `--backend` (c0012 spells the same idea `--target`). Rejected: guessing the target from the lib ids (implicit).

2. **A writer package, not a registered backend.** `src/fenolite/backends/altium/` holds every format fact of this change and its `PROVENANCE.md`. It imports `core` and `model` only.
   - It is not registered in `backends.registry`; `fenolite capabilities` lists it under a new `result.experimental` (Decision 16).
   - Rejected: an `AltiumBackend` in the registry. It would need `read` (the living "Capability reports" requires `detect` and `read`), a `write` that writes a schematic where "Write capability fields" says board, and a second built-in backend where "Backend registry" expects one: three MODIFIED requirements for an experimental writer. v0.3 registers the backend with its reader.
   - Rejected: the writer inside `lens` (format knowledge belongs to the backend package and its provenance).

3. **Orchestration in `src/fenolite/lens/altium.py`.** `build_altium(design, *, name, placed=(), project_exists=False) -> BuildOutput` runs the checks, sets the generic pins, validates, calls the writer, and adds `.fenolite/` and the record. It reuses `lens.build.BuildOutput`, `read_record`, `check_existing`, `RECORD_FILE`, `RECORD_SCHEMA` and `CACHE_DIR`.
   - `cmd_build` computes `placed` (the paths in `placements(design)`) and `project_exists` (`DIR/<name>.PrjPcb` is a file), calls `check_existing` with the record, and returns the plan.
   - Rejected: a target switch inside `lens.build.build_design`, whose signature c0019 and c0027 change (resolver, vendoring, preservation); none of its KiCad steps applies. Rejected: orchestration in `cmd_build` (c0011 keeps it in `lens`, where it is tested without the CLI).

4. **Input is the model, and nothing else is read.** The Altium build uses `to_model`'s components, nets and power interfaces. It builds no `LibraryResolver`, opens no library and parses no KiCad or Altium file; the edited-output check only hashes existing outputs (Decision 12). Board, placements, net classes and diff pairs are kept in the model (`.fenolite/`) and reported with `altium.not-lowered` (info), one issue per kind.
   - Rejected: requiring `--allow-lossy` for them (every Altium build would need the flag, which teaches agents to pass it by reflex).

5. **Links.** `Part.lib_id` and `Part.footprint` are `<library>:<name>`, split at the first `:`.
   - The library part is a file name and cannot hold `:`; the name may. Both parts must be non-empty, else `altium.lib-id-form` or `altium.footprint-form` (error). Both are written verbatim, extension included (`MyParts.SchLib`, `MyParts.IntLib`, `MyParts.PcbLib`).
   - Library link on the component record: `LIBREFERENCE` and `DESIGNITEMID` = the name, `SOURCELIBRARYNAME` = the library. Altium shows "Design Item ID" and "Source" and takes the update source from them (S-0002, S-0130, S-0136, S-0137); the key-to-field mapping is inferred (`H-A-SCH-LINK`, `H-A-SCH-UPDATE`).
   - Footprint link: record 44 owned by the component, record 45 owned by it with `MODELNAME`, `MODELTYPE=PCBLIB`, `DATAFILECOUNT=1`, `MODELDATAFILEENTITY0` = the footprint name, `MODELDATAFILEKIND0=PCBLIB`, `MODELDATAFILE0` = the PCB library, `ISCURRENT=T`, then records 46 and 48 owned by 45 (S-0130, S-0131, S-0135, S-0142, S-0144). That `MODELDATAFILE0` gives the dialog's "Library name" mode is inferred (`H-A-SCH-LINK`).
   - `footprint=None` writes no footprint records and gives `altium.no-footprint` (warning): the change order cannot place such a part.
   - The change order finds footprints in the project's libraries, the installed libraries and the search paths, the project folder first (S-0138), so `docs/altium.md` tells the maintainer to put the PCB library beside the project or install it.
   - Rejected: checking that the libraries exist (reading Altium files is v0.3). Rejected: adding a missing extension (a guess).

6. **Generic bodies from the designators the design uses.** For each component, the designators that its nets name become its pins, in natural order (runs of digits compared as integers and before letters, so `2` before `10`).
   - Each pin has designator = name = the text as written, and electrical type passive (`ELECTRICAL=4`, S-0130). `Component.pins` of the written model holds them with keyed ids `pin:<path>:<designator>` (c0011's key form), so `.fenolite/` and `Design.validate()` see them.
   - Geometry, a Fenolite choice in mils on a 100-mil grid: pins 200 long and 100 apart; the first ⌈n/2⌉ pins on the left from top to bottom, the rest on the right; body width `max(600, 100 · ⌈(100 + 2 · 70 · L) / 100⌉)` for the longest shown pin name of `L` characters (70 mil per character is Fenolite's estimate for the 10-point font); body height `100 · (rows + 1)`, at least 200. A component without a connected pin is a body without pins.
   - Records (S-0130, S-0131): component 1 at the body's top-left corner (`PARTCOUNT=2` for one part, `CURRENTPARTID=1`, `DISPLAYMODECOUNT=1`, `OWNERPARTID=-1`, no orientation); rectangle 14 from the bottom-left `LOCATION` to the top-right `CORNER`; pin 2 with `LOCATION` at the body end, `PINLENGTH=20`, `PINCONGLOMERATE` = direction (2 left, 0 right) + 0x10 (number shown) + 0x08 only when the name differs from the designator, so names equal to designators are not drawn twice. Children carry absolute coordinates. Colours are the values seen in Altium files (`COLOR=128`, `AREACOLOR=11599871`).
   - The top-left corner as the component location is a Fenolite choice: a library symbol replaced by "Update From Libraries" is placed at this point.
   - A designator should be the footprint's pad designator. `U1["GND"]` gives a pin `GND` that the change order cannot match to a pad; `docs/altium.md` says to connect by pin number. Fenolite cannot check this without a library reader.
   - "Tools » Update From Libraries" with full replacement replaces the body by the library symbol (S-0136). No source says whether wires follow the moved pins, so a pin whose position differs may leave its stub (`H-A-SCH-UPDATE`). "Replace selected attributes" with graphical attributes off keeps the body and updates parameters and models only (S-0136); `docs/altium.md` recommends it. The supported Monday route is the change order from the generic schematic.
   - Rejected: pins from a library (no reader before v0.3). Rejected: net names as pin names (they repeat the label, and renaming a net would change every body). Rejected: empty names (a pin record has both fields; the designator costs nothing).

7. **Connectivity: a stub per pin, then a net label or a power port.** Every pin gets one horizontal wire from its electrical end outward (`RECORD=27`, `LOCATIONCOUNT=2`, `X1`, `Y1` at the pin's end), and only that end of a pin is electrical (S-0130, S-0131, S-0140).
   - A net that is a member of a `power` interface gets a power port (`RECORD=17`) at the stub's outer end, pointing away from the body (`ORIENTATION` 2 on the left, 0 on the right), with `SHOWNETNAME=T`: `STYLE=4` (power ground) when the net is only ever the `lv` member, `STYLE=2` (bar) otherwise. Same-named ports connect across the design (S-0131, S-0140).
   - Every other net gets a net label (`RECORD=25`) whose lower-left hotspot lies on the stub: at the outer end of a left stub, 100 mil from the pin's end on a right stub, so the text sits over its own stub (S-0130, S-0140).
   - Stub length: 200 mil for a port; `max(300, 100 · ⌈(70 · L + 150) / 100⌉)` for a label of `L` characters.
   - A net never gets both labels and ports. Stubs never touch each other, so no junction is written.
   - Sheet-level records follow all component blocks, per component in path order and per pin in natural order: the stub, then its label or port.
   - Rejected: wires drawn between parts (a router, and noise on the sheet). Rejected: hidden pins that connect by name (invisible, and gone after "Update From Libraries"). Rejected: power ports for every net (ports are global names; using them for signals hides intent). Rejected: labels directly on pin ends without wires. Altium accepts them (S-0140), but the text would overlap the pin and the body.

8. **Deterministic grid layout.** Components are placed in component-path order, so a module's parts stay together.
   - Each part's cell holds its body, pins, stubs, labels, ports and texts, plus 200 mil on each side; a port takes 100 mil plus 70 mil per character beyond its stub. Cells are packed in rows, left to right and top to bottom, inside the drawing area less 500 mil on each side; a row is as high as its tallest cell. Every coordinate is a multiple of 100 mil, so no `_FRAC` key is needed.
   - The sheet is the first ISO size (A4, A3, A2, A1, A0, landscape; `SHEETSTYLE` 0 to 4, drawing areas 11 500 × 7600 to 44 600 × 31 500 mil) whose area holds the packing. Otherwise it is custom (`USECUSTOMSHEET=T`, `CUSTOMX`, `CUSTOMY`): the A0 width or the widest cell plus the margins, and the needed height rounded up to 1000 mil, with `altium.sheet-custom` (warning) (S-0002, S-0130, S-0131).
   - The layout works top-down; the writer converts Y to the file's upward axis from the sheet height.
   - Rejected: one fixed sheet (overflows on large designs). Rejected: boxes per module (hierarchy is out of scope; path order already groups them). Rejected: a force-directed placer (slow, and not a review aid).

9. **The ASCII form, and text it cannot carry is refused.**
   - Header `|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=<n>` with the exact record count (S-0002, S-0130, S-0131); one record per line, `|KEY=VALUE` fields from a leading `|`, no trailing `|`, keys in the fixed order of `altium-schematic-writer`; record 0 is the sheet; owners first.
   - Line ends CR LF (S-0142, S-0143; `H-A-SCH-LINEEND`). Bytes are printable 7-bit ASCII: plain values depend on the code page, and Altium versions differ (S-0130, S-0133).
   - `ascii.text_problem` refuses `|`, any character outside 0x20 to 0x7E, an empty text, a leading or trailing space (readers trim, S-0131), and a comment that starts with `=` (a parameter reference, S-0130). The build reports `altium.text-unwritable` (error) for the design name, refs, comments, net names, library and item names, and pin designators.
   - No line ends with `|>` (S-0131): every line ends with a value that holds no `|`.
   - Sheet record 31: one font (`FONTIDCOUNT=1`, `SIZE1=10`, `FONTNAME1=Times New Roman`, `SYSTEMFONT=1`; the font name is a Fenolite choice), border on, no title block, snap and visible grids of 10 units, hotspot grid 4, `DISPLAY_UNIT=4`, `AREACOLOR=16317695`, and the sheet size (S-0130).
   - Rejected: escaping or replacing characters (no public source documents an escape; a silent change would rename nets). Rejected: `%UTF8%` keys now (a second encoding path for a first sample; Open Questions).

10. **Stable component unique ids.** `unique_id(key)`: the SHA-256 of `fenolite.altium.uniqueid:<key>` as a big-endian integer, written as its eight lowest base-25 digits, least significant first, `A` for 0 to `Y` for 24 (form: S-0130; 25⁸ ≈ 1.5 · 10¹¹ values). A component's `UNIQUEID` is `unique_id(<component id>)`, and c0011 keys component ids by path.
    - Altium links schematic and PCB components by this id, with designators as the fallback (S-0139), so a rebuild that keeps paths keeps the PCB links (`H-A-SCH-RELINK`).
    - Altium does not repair duplicate component ids (S-0139): two components with one id give `altium.unique-id-collision` (error).
    - No other record gets a unique id. Whether Altium creates a missing one is data for `H-A-SCH-UID`; the writer always writes them.
    - Rejected: random ids (every rebuild would look like new components to the change order, losing the links to the PCB).

11. **The project file is written once.** `<name>.PrjPcb` is `[Design]`, `Version=1.0`, an empty line, `[Document1]`, `DocumentPath=<name>.SchDoc`, CR LF, 7-bit ASCII and no byte-order mark (S-0132, S-0134, S-0142, S-0143; `H-A-PRJ-OPEN`). It is planned only when it does not exist in `--out`; an existing one is kept, listed in `result.kept`, and reported with `altium.project-kept` (info), whatever `--discard-layout` says. To regenerate it, delete it.
    - Rejected: rewriting it under the edited-output rule. Altium rewrites the project file when the maintainer adds the PCB document, so every rebuild would need `--discard-layout`, which would remove the PCB document from the project. Rejected: merging the existing file (reading Altium files is out of scope). Rejected: a byte-order mark (AltiumSharp writes one, S-0142, but no source says Altium needs it; ASCII without a mark is plain in every code page).

12. **Edited schematics are refused, as in c0011.** The schematic, and the project file when planned, go through `check_existing` with the record of the last build: unchanged since then, or byte-identical, is allowed; otherwise `LayoutExistsError` (`FEN-7001`, exit 7) unless `--discard-layout`, which keeps a `.bak`. A schematic saved by Altium counts as edited, whatever form Altium saved it in. Hashing an output is not reading its format.
    - Rejected: preserving edits made in Altium (needs a reader; v0.3 and later).

13. **`.fenolite/` and the record.** The six layer texts come from `canonical.dump_texts` of the model with generic pins, so the design, its classes, interfaces and outline survive in Fenolite's own form. `.fenolite/build.json` keeps c0011's schema `fenolite.build-record.v0` with `target` set to the string `altium`; `read_record` reads only `schema` and `files`.
    - c0013's `check` takes a `.kicad_pcb` path, and an Altium build folder has none, so its built-project marker never misreads this folder.
    - Building both targets into one `--out` is allowed but not advised: each build checks only its own planned files, and the record names the target that wrote last.
    - Rejected: no `.fenolite/` (the edited-output rule needs the record). Rejected: a new record schema (no reader needs it).

14. **A closed table of `altium.*` issue codes** (`lens.altium.ALTIUM_ISSUE_CODES`; table in `altium-build`, "Altium build issue codes"). An error returns no file and exits 5 (c0011 Decision 11). `model.*` and `build.layout-exists` pass through.
    - Rejected: adding rows to `lens.build.BUILD_ISSUE_CODES` (its requirement is modified by c0019 and c0027). Rejected: a new `FEN-` code (exit 5 and exit 7 already cover the refusals).

15. **Letter case: always refuse.** Net names, or refs, that differ only in letter case give `altium.name-case-collision` (error), whatever Altium does with them (c0011 Decision 14).

16. **Experimental in `capabilities`** (ADDED `cli-contract` "Experimental features in capabilities"). `result.experimental` lists `{name, command, option, write_kinds, evidence}` per feature. This change adds `altium-schematic-writer`, `build`, `--target altium`, `["altium_prjpcb", "altium_schdoc_ascii"]` and the evidence of `ALTIUM_BUILD_EVIDENCE`. The Altium build result also carries `experimental: true`.
    - Rejected: a flag inside `result.backends` (it lists registered backends only, with exactly eight keys). Rejected: an info issue on every Altium build (noise; the result key and the capabilities entry are enough).

17. **Evidence: `INFERRED`, plus author reports on named bytes.** `lens.altium.ALTIUM_BUILD_EVIDENCE` is `INFERRED` with every `H-A-SCH-*` and `H-A-PRJ-*` row, combined with `backends.altium.project.EVIDENCE`; it stays `INFERRED` for every build.
    - The maintainer's check follows `docs/evidence/altium-schematic.md` (`altium-build`, "Altium author reports"). Part A uses the committed sample files and two variants, named by SHA-256. Part B uses a design and libraries the maintainer created or may use, with a licence the maintainer may use for this (`LEGAL.md` A, P3, P4); only generic outcomes are recorded, and no file of the session enters the repository.
    - Saturday steps and the rows they settle:

      | step | what the maintainer does | rows |
      |---|---|---|
      | A1 | check the SHA-256 values, open `altium_sample.PrjPcb`, note any prompt and whether the schematic is listed | `H-A-PRJ-OPEN` |
      | A2 | open `altium_sample.SchDoc` (CR LF); note prompts, the sheet size, 8 components with bodies, pin numbers, designators and comments, 13 power ports and 6 net labels | `H-A-SCH-OPEN`, `H-A-SCH-LINEEND` |
      | A3 | compile; note every message of level error or fatal, unique-identifier messages included; compare the Navigator nets with the page's table | `H-A-SCH-NETS`, `H-A-SCH-UID` |
      | A4 | select `U2`; note Design Item ID, Source, the footprint name, and the PCB Library mode of its footprint model | `H-A-SCH-LINK` |
      | A5 | "Save As" SCH ASCII under a new name; note only the key names Altium added and whether the `UNIQUEID` values are kept | `H-A-SCH-UID`, data for `H-A-SCH-OPEN` |
      | A6 | open the LF variant; open the variant without `UNIQUEID`, compile, save as ASCII, note whether `UNIQUEID` keys appear | `H-A-SCH-LINEEND`, `H-A-SCH-UID` (data) |
      | B1 | make the libraries available (beside the project or installed), add a PCB document, save the project, run "Design » Update PCB Document", validate and execute; note added components and nets and every red cross | `H-A-SCH-ECO`, `H-A-PRJ-KEEP` |
      | B2 | change one value, rebuild with `--target altium --confirm` (the project file is kept), compile, run the change order again; note the listed changes | `H-A-SCH-RELINK`, `H-A-PRJ-KEEP` |
      | B3 | on a copy, "Tools » Update From Libraries" with full replacement; note `<Not Found>` parts, replaced bodies and pins left unconnected; on another copy, "Replace selected attributes" with graphics off; note whether every net is kept | `H-A-SCH-UPDATE` |

    - A confirmed row gets `ALTIUM-VERIFIED(author-report; AD <major>.<minor or x>; <date>; no artefact)`. A refuted row keeps its id and names a successor that states what Altium did. Without a report, rows stay `INFERRED` with `pending (author report)`. `tests/unit/test_altium_rows.py` checks this form for both stems, because `register_problems` checks it only for `H-A-WRITE-*` and `H-A-PH-*`, and changing that rule would modify `verification-evidence`.
    - Rejected: raising the envelope after the report (an author report never promotes an operation, and it covers the files opened, not every design).

18. **No second reader.** `kicad-cli` cannot read any `.SchDoc` (Context, S-0132, S-0020), so this change plans no `kicad-cli` oracle and no `ORACLE-VERIFIED` label.
    - Rejected: a probe that always gives `reject` (it proves nothing about the file). Rejected: a manual import in KiCad's schematic editor (KiCad documents ASCII support, S-0002, but a GUI step cannot run in CI and still says nothing about Altium); the maintainer may try it, and nothing is recorded from it.

19. **A hermetic readback of Fenolite's own records.** `tests/_altium_read.py` parses the records Fenolite writes (test code, never product code) and rebuilds the nets from geometry: pin electrical ends, stubs, label hotspots and port connection points, with same-named labels or ports joined. `tests/unit/backends/altium/test_readback.py` checks that they equal the model's nets, that every owner index names an earlier record, that `WEIGHT` equals the record count, and that no line ends with `|>`; a label moved off its stub must make it fail.
    - It is the only mechanical check of connectivity before Altium's own; it is written from `docs/formats/altium/`, as the writer is, so a shared misreading of a source is caught only by the maintainer's check.
    - Rejected: string comparison only (golden files pin bytes, not meaning).

20. **Spec placement.** New capabilities `altium-schematic-writer` (the writer) and `altium-build` (the target, outputs, codes, evidence, sample, reports, documentation); ADDED `cli-contract` "Experimental features in capabilities". No MODIFIED requirement.
    - Archive order: this change is implemented and archived before c0019, c0021 and c0027. Their MODIFIED "Build command" texts are based on the living text, which does not name `--target`. When they are implemented, `cmd_build`'s new steps (`--vendor`, preservation, the cache) apply to `--target kicad` only, and the coordinator rebases their deltas to keep the `--target altium` branch.
    - Rejected: MODIFIED "Build command" here (three changes already modify it).

21. **Task order: a sample first.** Group 2 ends with a hand-checkable sample, built from `examples/altium_sample/design.py`, committed under `tests/data/altium/sample/` with its two variants and handed to the maintainer with the protocol. The readback, determinism, edited-output tests and documentation follow while the maintainer tests. The report and its fixes come next, then closing.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/altium/__init__.py` (new) | package docstring: an experimental writer, not a registered backend |
| `src/fenolite/backends/altium/PROVENANCE.md` (new) | the provenance table of every source used |
| `src/fenolite/backends/altium/ascii.py` (new) | `Field = tuple[str, str]`; `HEADER_TEXT`; `LINE_END = b"\r\n"`; `header_record(count: int) -> tuple[Field, ...]`; `format_record(fields: Sequence[Field]) -> str`; `encode_records(records: Sequence[Sequence[Field]]) -> bytes` (header with the record count, line ends, ASCII check); `text_problem(text: str, *, parameter: bool = False) -> str \| None`; `coord_fields(name: str, x: int, y: int) -> tuple[Field, Field]` (mils in the file frame; `ValueError` off the 100-mil grid) |
| `src/fenolite/backends/altium/symbols.py` (new) | `natural_key(text: str) -> tuple[tuple[int, int \| str], ...]`; `@dataclass(frozen=True) GenericPin(designator: str, name: str, side: Literal["left", "right"], row: int)`; `@dataclass(frozen=True) GenericSymbol(pins: tuple[GenericPin, ...], width: int, height: int)`; `generic_symbol(pins: Sequence[tuple[str, str]]) -> GenericSymbol`; `GRID = 100`, `PIN_LENGTH = 200`, `PIN_PITCH = 100`, `BODY_MIN_WIDTH = 600`, `CHAR_WIDTH = 70` (mils) |
| `src/fenolite/backends/altium/layout.py` (new) | `@dataclass(frozen=True) SheetSize(name: str, width: int, height: int, style: int \| None)`; `SHEET_SIZES` (A4 … A0); `@dataclass(frozen=True) PinNet(net: str, kind: Literal["label", "port"], style: Literal["ground", "bar"] \| None)`; `@dataclass(frozen=True) PartSpec(key: str, ref: str, comment: str, library: str, symbol: str, footprint: tuple[str, str] \| None, unique_id: str, body: GenericSymbol, nets: Mapping[str, PinNet])`; `PlacedPart`, `Stub`; `@dataclass(frozen=True) SheetPlan(size: SheetSize, parts: tuple[PlacedPart, ...], stubs: tuple[Stub, ...])`; `layout_sheet(parts: Sequence[PartSpec]) -> SheetPlan`; `MARGIN = 500`, `CELL_MARGIN = 200` |
| `src/fenolite/backends/altium/schdoc.py` (new) | `write_schdoc(plan: SheetPlan) -> bytes` (records in the fixed order) |
| `src/fenolite/backends/altium/prjpcb.py` (new) | `write_prjpcb(*, schematic: str) -> bytes` |
| `src/fenolite/backends/altium/project.py` (new) | `write_project(design: Design, *, name: str, project: bool = True, issues: list[Issue] \| None = None) -> dict[str, bytes]`; `split_link(text: str) -> tuple[str, str] \| None`; `unique_id(key: str) -> str`; `power_styles(design: Design) -> dict[str, Literal["ground", "bar"]]` (net id → style); `WRITE_KINDS = ("altium_prjpcb", "altium_schdoc_ascii")`; `EVIDENCE: Evidence` |
| `src/fenolite/lens/altium.py` (new) | `build_altium(design: Design, *, name: str, placed: Sequence[str] = (), project_exists: bool = False) -> BuildOutput`; `generic_pins(design: Design) -> Design`; `ALTIUM_ISSUE_CODES: Mapping[str, Severity]`; `ALTIUM_BUILD_EVIDENCE: Evidence`; `EXPERIMENTAL: Mapping[str, object]` (the capabilities entry without its evidence); `TARGET = "altium"` |
| `src/fenolite/cli/cmd_build.py` (extended) | `--target {kicad,altium}` (default `kicad`); the Altium branch; kinds `altium_prjpcb`, `altium_schdoc_ascii` |
| `src/fenolite/cli/cmd_capabilities.py` (extended) | `result.experimental`, built inside `_run` from `lens.altium.EXPERIMENTAL` and `ALTIUM_BUILD_EVIDENCE` |
| `examples/altium_sample/design.py` (new, CC0) | the sample design (`altium-build`, "Altium sample project"); listed in `examples/README.md` |
| `tests/data/altium/sample/altium_sample.PrjPcb`, `altium_sample.SchDoc`, `variants/altium_sample_lf.SchDoc`, `variants/altium_sample_nouid.SchDoc` (new, authored) | golden sample files and the two check variants, in `tests/data/MANIFEST.toml` |
| `.gitattributes` (new) | `*.SchDoc -text`, `*.PrjPcb -text` |
| `docs/altium.md` (new) | Building for Altium: command, forms, generic bodies, labels and ports, layout, project file, edited outputs, codes, experimental status, Altium steps and limits |
| `docs/formats/altium/schematic-ascii.md`, `docs/formats/altium/project.md` (new) | fact tables with sources, labels and `H-A-SCH-*` / `H-A-PRJ-*` hypotheses |
| `docs/evidence/altium-schematic.md` (new) | the protocol of Decision 17, the expected nets of the sample, the SHA-256 values and the reports |
| `docs/dsl.md`, `docs/cli-contract.md`, `docs/evidence/sources.md`, `docs/hypotheses.md`, `LEGAL-ANNEX.md`, `CHANGELOG.md` (extended) | pointer section, `--target` and `result.experimental`, sources, hypotheses, session rows, changelog |
| `tests/unit/test_altium_rows.py` (new) | the form of every `H-A-SCH-*` and `H-A-PRJ-*` row, without changing `register_problems` |
| `tests/_altium_read.py` (new) | `read_records(data: bytes) -> list[dict[str, str]]`; `nets_from_sheet(records: list[dict[str, str]]) -> dict[str, set[tuple[str, str]]]` (test code only) |
| `tests/unit/backends/altium/test_ascii.py`, `test_symbols.py`, `test_layout.py`, `test_schdoc.py`, `test_prjpcb.py`, `test_project.py`, `test_readback.py` (new) | hermetic writer tests |
| `tests/unit/lens/test_altium_build.py`, `test_altium_issues.py`, `test_altium_existing.py`, `test_altium_determinism.py`, `test_altium_golden.py` (new) | hermetic build tests |
| `tests/unit/cli/test_build_altium.py`, `test_capabilities_experimental.py` (new) | command flow and capabilities |
| `tests/unit/test_format_facts.py` (extended) | also checks `docs/formats/altium/*.md` |

Layering: `backends.altium` imports `core` and `model`; `lens.altium` imports `core`, `model`, `backends.altium` and `lens.build`; `cli` imports `lens.altium`. Every edge is in `package-layering`, so `ALLOWED` in `tests/unit/test_import_graph.py` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0130 | https://github.com/vadmium/python-altium/blob/master/format.md and `…/ascii.py` | WTFPL v2 (repository licence and README) | per-record keys of the schematic (header, records 1, 2, 14, 17, 25, 27, 29, 31, 34, 41, 44 to 48), value types, 10-mil units, Y up, depth-first order, zero-based index after the header, the eight-letter unique id, `=` parameter references; one text line per record |
| S-0131 | https://gitlab.com/kicad/code/kicad/-/blob/master/common/io/altium/altium_ascii_parser.cpp, `…/eeschema/sch_io/altium/sch_io_altium.cpp`, `…/altium_parser_sch.cpp` and `…/altium_parser_sch.h` (read 2026-10-02) | GPL-2.0-or-later (facts only; nothing transcribed or followed) | the reader's view of the ASCII form: lines, fields, `\|>` joins, trimming, encodings, the header value, indexing, owner order, absolute child coordinates, unit scale, pin end, record and style enumerations, sheet sizes |
| S-0132 | https://gitlab.com/kicad/code/kicad/-/blob/master/kicad/import_proj.cpp and `…/eeschema/eeschema_helpers.cpp` (read 2026-10-02) | GPL-3.0-or-later (facts only) | `.PrjPcb` `[DocumentN]` sections with `DocumentPath` relative to the project folder; `kicad-cli` picks a schematic reader by extension |
| S-0133 | https://www.altium.com/documentation/altium-nexus/sch-dlg-schconfirmfileformatformfile-format-sch-ad; https://help.altair.com/Pollex/topics/pollex/modeler/logic_import_altium_designer_format_t.htm; https://prodocs.easyeda.com/en/import-export/import-altium-designer/ and https://docs.easyeda.com/en/Import/Import-Altium-Designer/; https://filext.com/file-extension/SCHDOC | Altium, Altair, EasyEDA and filext pages: all rights reserved (read for facts, nothing copied) | the save type "SCH ASCII Version 5.0" ("Advanced Schematic ascii (*.SchDoc)"); the `\|HEADER=Protel` signature; AD17 and later save ASCII as UTF-8, older versions in the system code page |
| S-0134 | https://www.altium.com/documentation/altium-designer/tutorial/creating-project-schematic-document | Altium documentation, all rights reserved (read for facts) | the project file is an ASCII file listing the project documents and settings |
| S-0135 | https://www.altium.com/documentation/altium-designer/pcb-dlg-schpcblibdialogpcb-model-ad and https://www.altium.com/documentation/altium-dxp-developer/integrated-library-api | Altium documentation, all rights reserved (read for facts) | footprint model name and the PCB Library modes (Any, Library name, Library path, component library); model type and file kind `PCBLIB` |
| S-0136 | https://altium.com/documentation/altium-designer/workspacemanager-dlg-libraryupdateformupdate-from-library-ad?version=21 and https://altium.com/documentation/node/250046/printable/print?version=22 | Altium documentation, all rights reserved (read for facts) | "Update From Libraries": source from the library link, full replacement or selected attributes (graphics, parameters, models), `<Not Found>` parts |
| S-0137 | https://www.altium.com/documentation/altium-designer/schematic-part-properties and https://www.altium.com/documentation/altium-designer/components-libraries/file-based-libraries/schematic | Altium documentation, all rights reserved (read for facts) | Design Item ID, Source, Designator and Comment of a placed part; placed components are cached in the design; models are linked by name |
| S-0138 | https://www.altium.com/documentation/altium-designer/accessing-defining-managing-project-options and https://www.altium.com/documentation/cstu/project-options-search-paths | Altium documentation, all rights reserved (read for facts) | footprint search: project and installed libraries, then search paths; the project folder first |
| S-0139 | https://altium.com/documentation/altium-nexus/sch-dlg-resetpartsheetsymboluniqueidsreset-part-and-sheet-symbol-unique-ids-ad and https://altium.com/documentation/altium-nexus/workspacemanager-err-uniqueidentifierserrorsunique-identifiers-errors-ad | Altium documentation, all rights reserved (read for facts) | component unique ids link schematic and PCB, designators as fallback; duplicate component ids are reported, not repaired |
| S-0140 | https://www.altium.com/documentation/altium-designer/sch-obj-netlabelnet-label-ad, https://altium.com/documentation/altium-nexus/schematic-power-port and https://www.altium.com/documentation/altium-circuitmaker/schematic-pin | Altium documentation, all rights reserved (read for facts) | net labels on wires, buses and pins with a lower-left hotspot, sheet scope; same-named power ports join across the design, styles do not set the net; only the pin end away from the body is electrical; pin types |
| S-0141 | https://altium.com/documentation/node/312493/printable/print | Altium documentation, all rights reserved (read for facts) | "Design » Update PCB Document" opens the change order; validate, execute, marked invalid changes |
| S-0142 | https://github.com/issus/AltiumSharp (project model and schematic writer files) | Apache-2.0 per repository metadata, MIT per README (both permissive; facts only) | `.PrjPcb` sections and keys, `Version=1.0`, CR LF ("Altium uses CRLF"), byte-order mark kept, `DocumentPath` relative; records 44 → 45 → 46, 47 and 48 |
| S-0143 | https://github.com/tscircuit/altiumts and https://github.com/tscircuit/circuit-json-to-altium | MIT | an ASCII schematic and project reader that keeps CR LF or LF; a project writer with `[Design]` and `[DocumentN]` in CR LF (checked in a viewer only) |
| S-0144 | https://github.com/phosphor-tools/phosphor-eda and https://github.com/newmatik/altium-schdoc-viewer | MPL-2.0 (facts only) and MIT | names of records 44 to 48; `MODELDATAFILE0` is the library file of the model; footprint name from `MODELNAME`; the value from the `Comment` parameter |

Extended "used for" cells, with no new id:
- **S-0002** (KiCad dev docs, Altium import formats): the ASCII variant starts with `|HEADER=`, records end with a line end, both binary and ASCII schematics are imported, record numbers, owner keys and the sheet-size table; its "base value in mils" contradicts its own table.
- **S-0020** (`kicad-cli` 10.0.6 run as an oracle): authored `.SchDoc` files in CR LF, in LF and as plain text give "Failed to load schematic", exit 3, for every command tried (`sch export netlist`, `sch erc`, `sch upgrade`, `sch export svg`; 2026-10-02).

Consulted, not registered (no requirement relies on them): https://github.com/wavenumber-eng/altium_monkey (AGPL-3.0). Only facts are taken; no code or text is copied. The GPL KiCad files are read for facts only, recorded in Fenolite's words in `docs/formats/altium/`, and the code is written from those pages (`LEGAL.md` A2, P2). If a URL is already registered when this change is implemented, the existing id is cited and the row is not duplicated.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-SCH-OPEN | Altium Designer opens the ASCII `.SchDoc` that Fenolite writes, without an error or repair prompt, and shows its objects as written (S-0130, S-0133) | kit request (author report, step A2 of `docs/evidence/altium-schematic.md`) on the committed sample | no error, warning dialog or repair prompt; an A4 sheet; 8 components with 19 pins, 13 power ports and 6 net labels |
| H-A-SCH-LINEEND | Altium opens an ASCII schematic whose lines end with CR LF; whether it opens the same file with LF alone is recorded (S-0131, S-0142, S-0143) | kit request (author report, steps A2 and A6) | the CR LF sample opens; the LF variant's outcome is recorded |
| H-A-SCH-UID | Altium accepts the written component unique ids (eight letters from A to Y) without a unique-identifier message and keeps them on an ASCII save; whether it creates missing ids is recorded (S-0130, S-0139) | kit request (author report, steps A3, A5 and A6) | no unique-identifier message on compile; the 8 values are kept; the outcome of the variant without ids is recorded |
| H-A-SCH-NETS | Compiling the sample gives exactly the design's nets: each stub joins its pin's electrical end, each label joins the stub it lies on, each port joins the stub it ends, and same-named labels or ports join one net (S-0130, S-0131, S-0140) | kit request (author report, step A3) | the 6 nets of the page's table with exactly their pins; no message of level error or fatal |
| H-A-SCH-LINK | Each component shows the library link written from `lib_id` (Design Item ID and Source) and the footprint written from `footprint` as its current model, in the "Library name" mode with the written library (S-0130, S-0135, S-0137) | kit request (author report, step A4) | the values equal the written ones; another mode refutes the row, and its successor states the mode |
| H-A-SCH-ECO | "Design » Update PCB Document" adds every component with its linked footprint and every net of a compiled Fenolite schematic to a new PCB document, when the footprint library is beside the project or installed (S-0138, S-0141) | kit request (author report, step B1) on a design and libraries the maintainer may use | every component and net added; no change marked invalid |
| H-A-SCH-RELINK | After a rebuild that changes one value and keeps every component path, a second change order changes only that component's comment, because the unique ids are unchanged (S-0139) | kit request (author report, step B2) | one modification listed, and no component added or removed |
| H-A-SCH-UPDATE | "Tools » Update From Libraries" finds the library part named by the written link; full replacement replaces the generic body, and the pins left unconnected are recorded; "Replace selected attributes" with graphics off keeps the body and every net (S-0136, S-0137) | kit request (author report, step B3) on copies | the parts are found; the count of unconnected pins after full replacement is recorded; every net is kept after the selected-attributes update |
| H-A-PRJ-OPEN | Altium Designer opens the `.PrjPcb` that Fenolite writes (CR LF, no byte-order mark), lists the schematic and compiles it, with defaults for every key it does not hold (S-0132, S-0134, S-0142) | kit request (author report, steps A1 and A3) | the project opens with the schematic listed, and compiles |
| H-A-PRJ-KEEP | After a PCB document is added and the project is saved, the project lists both documents; a rebuild keeps that file, and the change order still runs (S-0134, S-0142) | kit request (author report, steps B1 and B2) | both documents listed after the rebuild; the change order runs; the key names Altium added are recorded |

Cited, not settled here: `H-A-WRITE-SCHDOC` (the author's earlier writer; unrelated to this writer, and not changed).

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Record syntax, header count, line ends, encoding, text refusal | mechanical (unit tests); the form itself `INFERRED` (S-0002, S-0130, S-0131) | `tests/unit/backends/altium/test_ascii.py` |
| Generic bodies, natural order, geometry, pin records | mechanical; field meaning `INFERRED` (S-0130, S-0131) | `test_symbols.py`, `test_schdoc.py` |
| Layout, sheet choice, custom sheet | mechanical; sheet sizes `INFERRED` (S-0002, S-0130, S-0131) | `test_layout.py` |
| Designator, comment, library and footprint links | mechanical; their reading by Altium `INFERRED` until `H-A-SCH-LINK` is reported | `test_schdoc.py`, golden files |
| Connectivity by geometry (stubs, labels, ports) | mechanical (Fenolite's own records read back, with a negative control) | `test_readback.py` |
| Unique ids | mechanical (form, pinned value, path keys) | `test_project.py`, `test_altium_determinism.py` |
| Project file content | mechanical; `INFERRED` until `H-A-PRJ-OPEN` is reported | `test_prjpcb.py` |
| Build steps, outputs, record, kept project, edited-output refusal, codes | mechanical | `tests/unit/lens/test_altium_*.py`, `tests/unit/cli/test_build_altium.py` |
| `result.experimental` | mechanical | `test_capabilities_experimental.py`, `tests/consistency` |
| The sample opens, compiles to its nets, shows its links in Altium | `ALTIUM-VERIFIED(author-report; AD <x.y>; <date>; no artefact)`, never release-verified | Part A of `docs/evidence/altium-schematic.md` |
| Change order, relink, "Update From Libraries" | author report on the maintainer's own design and libraries (Part B), generic outcomes only | Part B |
| Any reading by a tool other than Altium | none: `kicad-cli` cannot read `.SchDoc` (Decision 18) | — |
| The `build --target altium` envelope for any design | `INFERRED` (Decision 17) | `ALTIUM_BUILD_EVIDENCE` |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, provenance, format pages, facts and rows tests | 0.5 |
| 2. first sample: ASCII records; bodies and layout; schematic, project and `write_project`; `lens.altium`, `--target` and capabilities; sample, variants, golden files and protocol | 3.0 |
| 3. readback, determinism and edited outputs, documentation | 1.0 |
| 4. the maintainer's report and its fixes | 0.75 |
| 5. closing | 0.5 |
| **total** | **5.75** |

This is a size, not a calendar estimate. Cut order if the report needs more fixes than planned: (1) the custom sheet, replaced by a refusal past A0 (−0.25); (2) the two check variants, leaving `H-A-SCH-LINEEND` and the id-generation data open (−0.25); (3) the hermetic readback, kept as golden files only (−0.5). Not optional: the record form, bodies, links, labels and ports, layout, project file, `--target`, the edited-output rule, determinism, the sample and its protocol.

## Risks / Trade-offs

- [Altium refuses the file, or asks to repair it, on Saturday] → The sample is ready before any hardening; the protocol records the exact message and the key names Altium adds on a save; Sunday is for fixes; every key the writer writes has a public source. If the file cannot be opened by Monday, the maintainer starts the board without this writer; nothing in this change depends on that outcome.
- [No independent reader before Altium] → `kicad-cli` cannot read `.SchDoc`; the readback test is written from the same pages as the writer, so a misread source passes both; the Saturday check is the first independent reading, which is why the sample comes first.
- ["Update From Libraries" detaches stubs] → Documented (`docs/altium.md`, `H-A-SCH-UPDATE`); "Replace selected attributes" with graphics off keeps the body (S-0136); the supported route is the change order from the generic schematic; a later reader can place stubs where the library pins are.
- [Designators written as pin names] → The change order cannot match them; `docs/altium.md` says to connect by pin number; the sample uses numbers only.
- [Footprint mode other than "Library name"] → The change order still finds the footprint when the library is beside the project or installed (S-0138); `H-A-SCH-LINK` records the mode.
- [Altium saves the schematic in another form] → Any change counts as an edit; the rebuild refuses until `--discard-layout`, which keeps a `.bak`.
- [The project file grows stale after a design rename] → A rename gives new file names and a new project file; the old files stay (the mutation protocol never deletes), as c0011 documents for vendored files.
- [Line ends or encoding are wrong] → CR LF and 7-bit ASCII follow the sources; the LF variant tells whether line ends matter at all.
- [c0019, c0021 and c0027 rebase onto `--target`] → Decision 20; the ADDED requirement names "Build command", as c0019's text asks.
- [The licence the maintainer can use for the check] → Rows are registered only when `LEGAL.md` A holds (Decision 17); otherwise they stay `INFERRED`, and Monday's use is not affected.

## Migration Plan

- Additive: a new package `backends/altium/`, a new module `lens/altium.py`, an option `--target` whose default keeps every KiCad build byte for byte, a new key `result.experimental` in `capabilities`, a CC0 example, golden files, documentation and tests. No model, schema, layering, dependency or FEN-code change.
- Rollback: remove them; KiCad builds are unchanged, and Altium projects already written stay ordinary files.

## Open Questions

- **Pin positions and "Update From Libraries".** The default writes generic bodies and promises no connectivity after a full library update. A v0.3 reader could write stubs where the library pins are. Default: v0.3.
- **Pin names.** Default: name = designator, not drawn. Alternatives: the net name, or an empty name.
- **Libraries in the project.** Should the build copy the named `.SchLib`/`.PcbLib` files beside the project and list them, as c0011 vendors KiCad footprints? Default: no; the maintainer puts them beside the project or installs them (S-0138).
- **Line ends.** Default: CR LF. If step A6 shows that LF also opens, nothing changes; if only LF opens, Sunday's fix switches.
- **Missing unique ids.** Default: always written. If Altium creates them (step A6), a later change may still keep them, for the PCB links.
- **Byte-order mark in the project file.** Default: none (Decision 11); `H-A-PRJ-OPEN` settles it.
- **Sheet series.** Default: ISO A4 to A0. ANSI sizes are a later option.
- **`result.target` type.** Default: the string `altium` for Altium builds; KiCad builds keep the KiCad major.
- **A registered Altium backend.** Default: not before the v0.3 reader.
- **`--target` in "Build command".** Default: the first of c0019, c0021 and c0027 that archives after this change folds the option into its text (Decision 20).
- **A hidden `fenolite.path` parameter on components.** Default: no; unique ids keyed by path carry the identity.
- **Net classes for Altium.** Default: not lowered (`altium.not-lowered`); a later change may write class directives.
- **Non-ASCII text.** Default: refused. A later change may write `%UTF8%` keys (S-0130, S-0131).
- **Naming.** Public prose calls Altium "the second backend" (`docs/roadmap.md`). The flag value, package name and pages name it, as `docs/formats/README.md` and the evidence labels already do. Default: name it.
- **Part B on the maintainer's own design.** Default: registered only under `LEGAL.md` A; otherwise recorded nowhere.
