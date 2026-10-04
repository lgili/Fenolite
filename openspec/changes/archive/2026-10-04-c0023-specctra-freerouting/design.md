## Context

- **Scope.** A split-off of plan item 0016 (plan D11): a Specctra DSN writer of Fenolite's own, an SES reader, and a Freerouting plugin, "budgeted at two weeks, time-boxed". The roadmap sizes it at 10 days and lists it first in the accepted v0.1 cut order ("Open decisions", row 2).
- **Why Fenolite writes DSN.** `kicad-cli` 9.0 and 10.0 have no Specctra export and no session import (S-0022, S-0037; checked on 9.0.9 and 10.0.6 at proposal time: neither `pcb export` list holds one, and `pcb import` of 10.0 takes no session). KiCad offers both only in its editor.
- **Freerouting (S-0220 to S-0223, S-0226; read 2026-10-03).**
  - Licence GPL-3.0. Latest release v2.4.1 (2026-09-03), which needs Java 25. An OCI image is published as `ghcr.io/freerouting/freerouting`.
  - Documented arguments: `-de <file>` (input design), `-do <file>` (output, written when routing has finished), `-mp <n>` (maximum autorouter passes), `-mt <n>` (optimiser threads), `--gui.enabled=false` (headless), `-da` (disable analytics). A documented example: `java -jar freerouting.jar -de MyBoard.dsn -do MyBoard.ses -mp 10 -mt 4`.
  - **Data leaving the machine.** Its settings documentation shows analytics enabled by default ("anonymous usage and diagnostic data"); `-da`, the setting `usage_and_diagnostic_data.disable_analytics` or the matching environment variable turn it off. Its API server is disabled by default.
  - **Determinism.** The 2.4.1 release notes say the multi-threaded optimiser stays disabled by default "for determinism". No seed option is documented.
  - Exit codes, and which DSN constructs it needs or ignores, are not documented.
- **The format (S-0224).** The Specctra Design Language Reference (version 10.0, May 2000) describes DSN and SES. Its notice says it may not be copied, reproduced or distributed without permission, and allows a copy for personal, informational and non-commercial use. Fenolite's rule is that format knowledge comes from public sources, recorded as facts with a source and a label, and that no grammar file or parser code is transcribed (`AGENTS.md`, ADR-0003).
  - A design file is `(pcb <id> …)` with the sections `parser`, `resolution`, `unit`, `structure` (layers, boundary, keep-outs, vias, rules), `placement`, `library` (images and padstacks), `network` (nets and classes) and `wiring`.
  - A session file is `(session <id> (base_design …) …)` with `placement`, `was_is` and `routes`; `routes` holds `resolution`, `parser`, `library_out` and `network_out`, whose nets hold wires and vias.
  - Read on 2026-10-04 (the Markdown rendition in the Freerouting repository at commit `339e8bb50fbbceec9645b4ddfd0399a4e9bf4963`, read on line, never saved or committed). Six statements of the reference differ from what this design assumed; they are listed under "Reconciled on 2026-10-04" and the decisions below are edited in place.
- **What exists in Fenolite.** c0016's `Router` protocol, registry, net selection, merge, `fenolite route` and the widened layering row for plugins (not on `main` on 2026-10-04: c0016 is being implemented in parallel); c0028's `BoardFrame.board_pads` with `PadCopper` entries (a disc, an open polyline with a width, or a ring with a width, in the board frame); c0022's `board_outline` rings, which live in `backends/kicad/outline.py`; net classes in the model; `backends/altium` as the precedent of a codec package that is not a registered backend.
- **Constraints.** Stdlib only. A backend never imports another backend, so `backends.specctra` works from the model and from `backends.base` data. GPL software only across a process boundary (ADR-0004). The time box is 10 days.

## Goals / Non-Goals

**Goals:**
- `fenolite route --router freerouting` routes the blink for targets 9 and 10 with 0 unconnected items, judged by KiCad's DRC.
- The DSN writer and the SES reader are exact in integers and independent of KiCad's files.
- No design data leaves the machine, and the proof of that is recorded.
- Every Specctra fact Fenolite relies on is confirmed by a probe or labelled `INFERRED`.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Completeness: the writer emits the subset the probes show Freerouting needs.

## Decisions

1. **A decision record first.** `docs/adr/0006-specctra-and-freerouting.md` is written `Proposed` by this change and set `Accepted` only by the maintainer (as ADR-0005). It records:
   - facts about DSN and SES are taken from S-0224 and written in Fenolite's own words in `docs/formats/specctra/`; no sentence, table, production or example of the reference is copied, and the reference is neither vendored nor linked from the package;
   - every fact the code relies on is also checked against a tool (Freerouting accepts it, or KiCad's editor writes it for an authored board);
   - Freerouting is GPL-3.0: it is run as a program, never imported, vendored, downloaded by Fenolite or read for format knowledge;
   - no cloud mode in v0.1.
   - **If the maintainer does not accept the use of S-0224**, the fallback is black-box only: the subset is learned from DSN files that KiCad's editor exports for authored boards (dev-time, recorded as observations under S-0020) and from Freerouting's acceptance. That costs about 3 more days and is the first reason to cut the change.

2. **Probe first.** *Order changed on 2026-10-04 by the maintainer's decision to work in parallel with c0016: the lexer, the writer (task 3.1) and the reader (task 3.2) were built before the probes, from S-0224 alone. Every DSN and SES fact therefore stays `INFERRED` until the probes run, and a probe that refutes a fact changes the fact page first and the writer second.* Task group 2 writes, by hand through a small script, the DSN of the authored two-pad board and of the built blink, runs Freerouting 2.4.1, and records seven outcomes before the writer is generalised: `dsn-accept`, `dsn-units`, `dsn-protect`, `dsn-route-t9`, `dsn-route-t10`, `dsn-repeat`, `dsn-offline`. They are recorded in `docs/evidence/routing/freerouting-2.4.1.json` and `docs/evidence/routing.md`, never in the `kicad-cli` probe files. Each has a fallback: Decisions 4 (resolution), 6 (protection), 9 (offline).

3. **Syntax.** `backends/specctra/lexer.py`: parenthesised lists of words and quoted strings.
   - The quote character is the one the file's `parser` section declares with `string_quote`. S-0224 names no default; the lexer starts with `"` (a Fenolite choice, so that a name quoted before the declaration still reads) and switches when it meets a declaration. The character after `string_quote` is read as it stands.
   - Blanks inside a quoted string are kept only when the file says `(space_in_quoted_tokens on)`; the default of S-0224 is `off`, where a blank ends the string. The lexer follows the file. The writer always declares `(string_quote ")` and `(space_in_quoted_tokens on)`, and quotes every name that is not a plain word (a word holds no blank, parenthesis, semicolon, quote character or line end).
   - S-0224 gives no escape, so a name that holds the quote character or a line end cannot be written (Decision 7).
   - Numbers are decimal integers or decimals; the reader converts them exactly with `fractions.Fraction`. Unknown lists are kept as generic nodes and ignored by the reader, with one `specctra.unknown-list` info per head.
   - Rejected: reusing the KiCad S-expression parser. Its lexical rules (escapes, bare atoms) are KiCad's.

4. **Units.** The writer emits `(resolution um 10)` and `(unit um)`: the database unit is 100 nm.
   - *Edited on 2026-10-04 after reading S-0224.* In a design file the numbers are in the declared unit, micrometres, and the resolution value only says how many database units one unit holds. So every length is rounded to database units, `u = round_half_even(nm / 100)`, and written as `u / 10` micrometres with at most one decimal (`100005` units is written `10000.5`). The largest error is 50 nm, far inside any pad. The writer reports `specctra.rounded` (info) with the count of lengths that were not multiples of 100 nm.
   - Y is negated: S-0224 measures rotation counter-clockwise from the positive X axis, which is the frame with Y up (an inference, part of `H-G-DSN-UNITS`); the model has Y down.
   - A pin offset is the rounded pad position minus the rounded footprint position, so the pad lands on its own rounded board position.
   - In a session file the numbers are database units: a value `v` under `(resolution <unit> <n>)` is `v / n` units. The reader takes the session's own `resolution` and converts back to nanometres with `Fraction`; a result that is not a whole nanometre is rounded half to even.
   - Fallback if `dsn-units` shows Freerouting rescaling or snapping: the row is refuted with a successor that records the observed grid, and `to_copper` snaps each wire end that lies within the observed error of a pad centre onto that centre.
   - Rejected: `(resolution um 1000)` for exact nanometres. It is untested territory for the router; 100 nm is the value in general use and is enough.

5. **Footprints without side or rotation semantics.** Each placed footprint is one `image` of its own, named by its reference, placed at its position with rotation 0 on the front. Its pins are at `BoardPad.position − footprint.position`, already rotated and flipped, and a bottom-side pad's padstack names the bottom layer. So the writer depends on no rule about how Specctra mirrors or rotates images.
   - Every placement is locked in place (`(lock_type position)`): the router moves no component.
   - *Added on 2026-10-04.* Pin ids are unique in an image and hold no hyphen (S-0224: a pin reference is `<component>-<pin>`). c0028 gives every pad that shares a number, so the second pad numbered `1` is written `1@2`, a pad without a number `@<n>`, and a hyphen in a number becomes `_`; each change is in `names.pins` and gives `specctra.renamed`. A reference follows the same rules, because a reader may split a pin reference at its first hyphen: a hyphen becomes `_`, a footprint without a reference gets `FP<n>`, and a reference already used gets `<ref>@2`.
   - A pad with a hole and no copper on a copper layer (a mounting hole) gets a disc of the drill diameter on that layer, so the router keeps clear of the hole.
   - Rejected: one image per library footprint with rotation and side in `place`. It is smaller, and wrong as soon as one mirroring convention is misread.

6. **What the writer emits.**
   - `structure`: one `layer` per copper layer in stack order, type `signal`; two boundaries (edited on 2026-10-04 after S-0224): a `rect` on the reserved layer `pcb` with the bounding box of the board ring, and a `path` of width 0 on the reserved layer `signal` with the ring itself, which is the area open to routing; cut-out rings as `keepout` polygons on `signal`; model keep-outs that forbid tracks or vias as `keepout`, `wire_keepout` or `via_keepout` polygons per copper layer; one `via` padstack per distinct (diameter, drill) of the selected nets; a default `rule` with width and clearance.
   - `library`: padstacks from `PadCopper` entries, per layer, relative to the pad position: a disc is a `circle`; an open polyline with a width is a `path` with that width; a ring of width 0 is a `polygon`; a convex ring with a width is the `polygon` of its outer hull (the construction of `copper_polygon`, redone in the codec with `geometry`, because `copper_polygon` lives in `backends.kicad` and a backend may not import another); a ring with a width that is not convex is its bounding rectangle grown by half the width, with `specctra.pad-approximated`. Equal padstacks are shared. An entry flagged `exact == False` gives `specctra.pad-approximated` (warning).
   - `network`: one `net` per net with pads, pins as `REF-PIN`; one `class` per net class with its nets, `width`, `clearance` and via. Nets not selected for routing are still declared, so the router keeps clear of them.
   - `wiring`: every existing track and via, as wires and vias of type `protect`, so the router keeps and avoids them. An arc is written as one protected wire whose path follows the arc within the kernel's arc error bound. Copper on a net without pads is written without a net, as an obstacle. Script copper (c0028) is copper like any other here: its marker is a KiCad uuid, which the codec never sees, and the model's tracks and vias have no `locked` field.
   - Not emitted: planes for zones (the zone is refilled after routing, c0015), pin and gate swapping, floor plans, colours.
   - Fallback if `dsn-protect` shows protected wiring ripped or moved: `to_copper` ignores session wires on nets that were not selected, and the merge never removes copper (c0016), so existing copper is safe in any case; the row records the behaviour.

7. **Names.** Net, reference and pin names are written quoted when needed, and `DsnResult.names` (a `Names` record) maps every emitted net, component, pin, layer and via-padstack name back to the model, and holds each component's written position and the protected wiring, which `to_copper` needs. A name that the syntax cannot carry (empty, or containing the quote character or a line end) gets a generated name and `specctra.renamed` (info).

8. **Session to copper.** `ses.read_session(text) -> Session` gives `wires` (net, layer, width, points) and `vias` (net, padstack name, position), in the session's units. `ses.to_copper(session, names, *, selected) -> RoutingResult` fields:
   - each wire of a selected net becomes one `Track` per segment; zero-length segments are dropped;
   - each via becomes a `Via` with the diameter and drill of the padstack the writer defined under that name; an unknown padstack name gives `specctra.unknown-padstack` (error) and no copper at all;
   - wires and vias on nets that were not selected, and those that equal protected input wiring, are ignored;
   - a session that moves or swaps anything gives `specctra.session-moved` (error) and no copper: a `place` whose position, side or rotation differs from what the writer wrote (a session may list every component, so the entries are compared, not merely detected), a `place` of an unknown component, or a `was_is` entry.
   - Ids are `derived_id(prefix, "specctra", key)` with a key made of the net name and the geometry, so equal sessions give equal ids.
   - A session via takes the layers of the padstack the writer defined under its name; the router is offered through vias only.
   - No source says whether the numbers of a session's `placement` are database units or the unit itself; a `place` entry is unmoved when either reading gives the written position. The probe `dsn-accept` of 2026-10-04 showed that Freerouting 2.4.1 writes the placement under its own `(resolution um 10)` in database units, so a placement that declares a resolution is read as database units only; either reading is accepted only for a placement that declares nothing.
   - A wire on a layer the design file lacks is malformed input: `FormatError`.

9. **Freerouting plugin** (`routing/plugins/specctra/freerouting.py`).
   - **Where it is.** `--router-path JAR`, else `FENOLITE_FREEROUTING_JAR`; `java` on `PATH` or `FENOLITE_JAVA`. `--router-path docker:<image>` runs the image instead, with the run folder mounted and `--network none`.
   - **Version.** `PINNED_VERSION = "2.4.1"`, `JAVA_MIN = 25`. `available()` checks the jar exists and `java -version` gives a major of at least 25 (c0013's `java_major`); it starts no router. A jar of another version is allowed with `route.tool-unpinned`.
   - **Run.** `java -jar <jar> -de board.dsn -do board.ses -mp <passes> -mt 1 -da --gui.enabled=false` in a fresh temporary directory, with `HOME` set to that directory so no user setting is read or written, a timeout (default 900 s), and `passes` from `--router-option max-passes=N` (default 20).
   - **Verdict.** Exit codes are not documented, so the result is judged by the session file: missing or unreadable gives `route.tool-failed`.
   - **Offline.** `-da` is always passed and cannot be turned off through `--router-option`. `dsn-offline` runs the image with `--network none` and requires a session; when it holds, the plugin's `sends_data_offsite` is `False`. Until it is recorded, the attribute is `True` and `route` needs `--allow-offsite`, so the default is the safe one.
   - `mt 1` keeps the documented deterministic optimiser.

10. **Doctor and capabilities.** c0016 lists every registered router. `doctor`'s `freerouting` entry adds `java_major` and `java_ok`; a jar without a Java 25 gives `doctor.tool-unsupported` naming the needed major.

11. **Hermetic tests.** `tests/_fakefreerouting.py` writes a fake `java` that checks its arguments and writes an authored session for the two-pad board. DSN and SES fixtures under `tests/data/specctra/` are authored for Fenolite; no file is copied from Freerouting, KiCad or the reference.

12. **CI.** The `routing` job of c0016 gains Java 25 (the Temurin action or the image's package) and a Freerouting jar downloaded at the pinned version, checked against a SHA-256 recorded in `ci.yml`, then `uv run pytest tests/routing -m needs_freerouting`. The job stays optional.

13. **Time box.** At day 6 the gate is checked: `dsn-accept` and `dsn-route-t10` must hold. If they do not, the change stops, what was learned is recorded in `docs/evidence/routing.md`, and the remaining work moves to v0.2a.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/specctra/__init__.py` (new) | package doc: a codec, not a registered backend |
| `src/fenolite/backends/specctra/lexer.py` (new) | `SNode`, `parse(text, *, file="") -> SNode`, `dumps(node) -> str` |
| `src/fenolite/backends/specctra/dsn.py` (new) | `UNIT_NM = 100`; `DsnDefaults(width, clearance, via_diameter, via_drill)`; `ViaStack(diameter, drill, layers)`; `Names(nets, components, pins, layers, vias, places, protected_wires, protected_vias)`; `DsnResult(text, names, issues)`; `write_dsn(design, *, pads: Sequence[BoardPad], outline: Sequence[Sequence[Point]], selected: Sequence[str], defaults: DsnDefaults) -> DsnResult`; `EVIDENCE`; `ISSUE_CODES` |
| `src/fenolite/backends/specctra/ses.py` (new) | `Wire`, `SessionVia`, `Place`, `Session`; `read_session(text, *, file="") -> Session`; `to_copper(session, names, *, selected) -> tuple[tuple[Track, ...], tuple[Via, ...], tuple[Issue, ...]]` |
| `src/fenolite/backends/specctra/PROVENANCE.md` (new) | sources and how each was used |
| `src/fenolite/routing/plugins/specctra/freerouting.py` (new) | `PINNED_VERSION`, `JAVA_MIN`, `FreeroutingRouter` |
| `pyproject.toml` | entry point `freerouting` in `fenolite.routers` |
| `src/fenolite/cli/cmd_doctor.py` (extended) | Java check for the router entry |
| `docs/formats/specctra/dsn.md`, `ses.md` (new) | fact tables with source, label and hypothesis |
| `docs/adr/0006-specctra-and-freerouting.md` (new) | Decision 1 |
| `tests/unit/backends/specctra/`, `tests/unit/routing/test_freerouting.py`, `tests/_fakefreerouting.py`, `tests/data/specctra/` (new) | hermetic |
| `tests/routing/test_freerouting_gate.py`, `test_freerouting_oracle.py` (new) | `needs_freerouting`, `needs_kicad` |

Layering: `backends.specctra` imports `core`, `model`, `geometry` and `backends.base`; `routing.plugins.specctra` imports `routing`, `model`, `geometry` and `backends.specctra` (c0016's row). The command passes `BoardPad`s and outline rings in the job's options through c0016's protocol extension point: `RoutingJob.extra` (Open Questions).

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0220 | https://github.com/freerouting/freerouting (README and LICENSE) | GPL-3.0 | what the tool is, its licence, the Java version, the OCI image |
| S-0221 | https://github.com/freerouting/freerouting/blob/master/docs/command_line_arguments.md | GPL-3.0 | `-de`, `-do`, `-mp`, `-mt`, `-da`, `--gui.enabled`, the documented example |
| S-0222 | https://github.com/freerouting/freerouting/blob/master/docs/settings.md | GPL-3.0 | analytics on by default and how to disable it; the API server off by default |
| S-0223 | https://github.com/freerouting/freerouting/releases/tag/v2.4.1 | GPL-3.0 | Java 25; single-threaded optimiser by default "for determinism" |
| S-0224 | SPECCTRA Design Language Reference, version 10.0, May 2000 (© 1996-2000 Cadence Design Systems; a copy is in the Freerouting repository under `docs/reference/`) | all rights reserved; its notice forbids copying and distribution; read for facts only, nothing copied (ADR-0006) | names and order of the DSN and SES sections, units and resolution, the shapes of padstacks, wires and vias |
| S-0225 | https://docs.kicad.org/10.0/en/pcbnew/pcbnew.html | GPL-3.0-or-later or CC-BY-3.0-or-later | that KiCad's editor exports Specctra DSN and imports sessions (to verify on the page) |
| S-0226 | https://github.com/freerouting/freerouting/blob/master/docs/self-hosting.md | GPL-3.0 | the image name and its tags |

Task 1.2 opens each page, records the commit or revision read and what the page states, and writes "not stated" otherwise. S-0227 to S-0229 stay unused.

Checked on 2026-10-04 before registering: S-0220 to S-0226 are free in `docs/evidence/sources.md` (the changes that once named ids of this range, c0040 to c0042, were moved to higher ranges at integration), and no `H-G-DSN-*` row exists in `docs/hypotheses.md`. No id was renumbered.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-DSN-ACCEPT | Freerouting 2.4.1 loads the DSN that Fenolite writes (sections of Decision 6, one image per footprint, `(resolution um 10)`) and writes a session for it (S-0221, S-0224) | `tests/routing/test_freerouting_gate.py::test_accept` | for the two-pad board and the blink: a session file exists and reads; outcome `dsn-accept` = `present` |
| H-G-DSN-UNITS | Design-file numbers are micrometres with Y up; session numbers are database units of the session's own resolution, Y up; each routed wire ends within 100 nm of the centre of the pads it joins (S-0224) | `::test_units` | for the two-pad board: after `to_copper`, both ends of the route lie within 100 nm of the pad centres; outcome `dsn-units` = `equal` |
| H-G-DSN-PROTECT | Wires and vias written as protected stay in place: the session neither moves nor removes them (S-0224) | `::test_protect` | for the blink with one net pre-routed: no session wire on that net differs from the input; outcome `dsn-protect` = `equal` |
| H-G-DSN-ROUTE | The blink routed by Freerouting has no unconnected item and no violation of severity error that the unrouted blink lacks, under `kicad-cli` of the board's major (S-0220) | `::test_route` | on 10.0.6 for target 10 and 9.0.9 for target 9: outcomes `dsn-route-t9`, `dsn-route-t10` = `equal` |
| H-G-DSN-REPEAT | With `-mt 1`, two runs on the same DSN give the same session wires and vias (S-0223) | `::test_repeat` | outcome `dsn-repeat` = `equal` or `different`, recorded either way |
| H-G-DSN-OFFLINE | With `-da`, Freerouting 2.4.1 routes with no network: the container run with `--network none` writes a session (S-0222) | `::test_offline` (needs Docker) | outcome `dsn-offline` = `present`; until it is recorded, the plugin's `sends_data_offsite` is `True` |

Backend `specctra` for the first three, `kicad` for `H-G-DSN-ROUTE`. Ids used without changing their level: `H-K-KRT-*` (none depended on), `H-G-FRAME-SHAPE`, `H-G-PLACE-OUTLINE`, `H-K-DRC-JSON`.

## Reconciled on 2026-10-04

The proposal was written before c0022, c0028, c0029, c0030 and c0031 landed, and before S-0224 was read. What differs, and where it was edited:

| what the proposal assumed | what is true | edited |
|---|---|---|
| probes before the writer | the maintainer started this change in parallel with c0016; the writer and the reader were built first, every fact stays `INFERRED` | Decision 2, tasks 2.2, 3.1 and 3.2 |
| a coordinate is written as a whole number of 100 nm units | in a design file numbers are in micrometres and the resolution only sets the precision; in a session they are database units (S-0224) | Decision 4; spec "Design files are written from the model" (units, scenario "Y is negated and rounded") and "Session files are read into copper" |
| the quote character is the declared one | S-0224 names no default quote character, and blanks end a quoted string unless `space_in_quoted_tokens` is `on` | Decision 3; spec "Specctra syntax" |
| the boundary is the board ring | a `rect` on layer `pcb` for the bounding box and a `path` on layer `signal` for the ring (S-0224) | Decision 6; spec, structure |
| pins are `REF-PIN` with the pad numbers | a pin id holds no hyphen and is unique in its image; c0028 returns every pad sharing a number | Decision 5; spec, names |
| `copper_polygon` gives the polygon of a rounded pad | it lives in `backends/kicad/frame.py`, which the codec may not import; the codec redoes the construction with `geometry`, and a `PadCopper` entry is a disc, an open polyline with a width, or a ring with a width (`filled`) | Decision 6; spec, components |
| `board_outline` is c0022's | it is `backends.kicad.outline.board_outline`, returning `BoardOutline.rings` (the board first, then the cut-outs), polygonised; the command passes the rings, the codec never imports it | Context; no API change |
| a session "that moves" is detected by the presence of `placement` | a session may list every component; the entries are compared with what was written | Decision 8; spec |
| `to_copper` returns c0016's `RoutingResult` | `routing` is not on `main`; `to_copper` returns tracks, vias and issues, and the plugin (task 4.1) builds the result | Decision 8, Files |
| protected wiring follows a model flag | the model's tracks and vias have no `locked` field (c0031 added one to zones only); script copper is marked by its KiCad uuid; every existing track and via is protected | Decision 6 |
| layering row of the codec | unchanged: `backends.<x>` may import `model`, `geometry` and `backends.base` (and `core`) | none |

### Fitted to c0016 as shipped (19b74bb), 2026-10-04

| what the proposal assumed | what c0016 shipped | what this change does |
|---|---|---|
| `RoutingJob.extra` exists as an extension point | `RoutingJob(design, nets, layers, options)` only | adds `extra` after `options`; `cmd_route` fills `board_pads` and `outline` (requirement "Job extras") |
| the plugin reads its location when constructed | the registry builds one instance per process, and `doctor` and `capabilities` use it | the jar and Java are read from the environment on use |
| `--router-path JAR` is passed to any router | `--router-path`, `--router-python` and `--timeout` were wired for `kicadroutingtools` only | `--router-path` and `--timeout` also build a `FreeroutingRouter`; the default timeout of this router is 900 s |
| the version of a jar is known | `available()` may start no router, and the jar's manifest carries no version | the pinned version when the manifest's build revision is the tag's commit, else the version in the file name, else `unknown` (`route.tool-unpinned`) |
| an ignored option is a warning | `routing.codes` had no such code | adds `route.option-ignored` (warning) |
| the plugin takes `BoardPad`s | the layering row lets a plugin import `routing`, `model`, `geometry` and its own backend, not `backends.base` | the pads cross as objects in `extra` and go to `write_dsn` unchanged |
| every board can be routed | c0016's authored `two_pads.kicad_pcb` has no outline | a board without an outline gives `route.tool-failed`; the tests write the two-pad bench of `tests/_specctra.py` as a KiCad board instead |
| the `route` extra might serve this router | it names a Python client of the hosted API | not used: the jar runs as a subprocess, and c0052 removes the extra |
| board defaults come from the command | the command resolves per-net values into `JobNet` | the writer takes class values from the model, and the board defaults from the design's `Default` class, else the constants of `fenolite route` |

Design rules of the model (`Rule` entities, which c0054 fills from `design.rules.minimum(...)`) are not
lowered into the design file: the router gets the net-class width, clearance and via, and KiCad's DRC,
which reads those rules from the project, stays the judge. Lowering clearance rules to Specctra `rule`
lists is left for a later change.

The container form was first tested with a fake `docker` only. The `dsn-offline` run of 2026-10-04 showed that
the published image's default command starts its API server and that its entry script does not take the jar's
arguments alone: the plugin now runs `java -jar /app/freerouting-executable.jar` followed by its arguments.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Lexer, writer structure, session reader | mechanical on authored files | `tests/unit/backends/specctra` |
| DSN accepted, units, protection | ORACLE-VERIFIED(freerouting 2.4.1) | `test_freerouting_gate.py` |
| Routed blink | KICAD-VERIFIED (9.0.x, 10.0.x), `H-G-DSN-ROUTE` | `::test_route` |
| Offline run | recorded, `H-G-DSN-OFFLINE`; decides `sends_data_offsite` | `::test_offline` |
| Format facts | INFERRED (S-0224) unless a probe confirms them | `test_format_facts.py` |

## Budget (10 days, time-boxed)

| work | days |
|---|---|
| ADR, registers, fact pages | 0.75 |
| probes with hand-written DSN | 2.0 |
| lexer | 0.5 |
| DSN writer | 2.5 |
| session reader and copper | 1.25 |
| plugin, doctor | 1.0 |
| oracle, CI | 1.0 |
| docs, closing | 1.0 |
| **total** | **10.0** |

Cut order inside the change: (1) keep-outs from rule areas; (2) polygon padstacks (bounding rectangle with `specctra.pad-approximated`); (3) the container mode (then `H-G-DSN-OFFLINE` stays pending and the plugin needs `--allow-offsite`); (4) the CI step. The change itself is the first cut of v0.1.

## Risks / Trade-offs

- [The reference's notice] → ADR-0006 and its fallback (Decision 1); facts only, own words, each confirmed by a tool.
- [Freerouting needs a construct the writer omits] → `dsn-accept` on day 2; the subset grows only by what the probe shows.
- [Analytics leave the machine] → `-da` always; the offline probe; `sends_data_offsite` stays `True` until proved.
- [Java 25 is not installed] → `available()` and `doctor` say so; the container mode needs only Docker.
- [Rounding to 100 nm leaves a wire end off a pad centre] → the largest error is 50 nm; `dsn-units` measures it; the DRC is the judge.
- [The time box runs out] → Decision 13.

## Migration Plan

Additive: a codec package, a plugin, one entry point, an ADR. To roll back, remove them.

## Open Questions

- **Is this change in v0.1?** The accepted cut order moves it to v0.2a first; c0016's gate verdict decides. Default: implement only if the gate fails on a major or the maintainer keeps it.
- **ADR-0006.** The maintainer decides whether facts may be taken from S-0224 (Decision 1). Default: yes, facts only.
- **How the plugin gets pads and the outline.** `routing` cannot import `backends.base`, and c0016's `JobPad` has no copper shapes. Default: this change ADDs `RoutingJob.extra: Mapping[str, object]` to the `routing` capability, filled by the command with `board_pads` and `outline`; a plugin that needs neither ignores it.
- **Default passes.** 20 autorouter passes is a Fenolite choice; to confirm with the blink timing.
- **Where the jar comes from in CI.** Default: the release asset of the pinned version, with its SHA-256 in `ci.yml`.
