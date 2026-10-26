## Context

- **Milestone.** v0.4, the agent track (c0077 to c0081). Written against `origin/dev` at `9aba2dff`.
- **What exists after c0079.** `src/fenolite/agent/skill/SKILL.md` (the start page, with its tested `fenolite-loop` block), an empty `references/` folder, `guide.pages()`, `fenolite guide`, `fenolite skill install`, the starter `blink`, and `cli.describe`. The start page keeps, as prose, the section "Small questions between the steps" with the reading commands of c0066 and later changes.
- **The surface to cover** (`9aba2dff`, 2026-10-07). 30 public commands: `analyze`, `bom`, `build`, `capabilities`, `catalog`, `check`, `diff`, `doctor`, `equivalent`, `explain`, `export`, `fill`, `fmt`, `inspect`, `kit`, `manifest`, `neighbors`, `net`, `netlist`, `pads`, `parity`, `place`, `pnp`, `region`, `render`, `restore`, `roundtrip`, `route`, `sync`, `template`; c0079 adds `guide`, `skill` and `init`, and c0078 `fetch`. 58 names in `fenolite.dsl.__all__`. On 2026-10-05 the counts were 13 and 38.
- **Where the knowledge is today.** `docs/dsl.md` (54 kB) and `docs/cli-contract.md` (154 kB): complete, written requirement by requirement, with change ids and hypothesis ids. They are in the source distribution and not in the wheel. `docs/placement.md`, `docs/routing.md`, `docs/copper.md`, `docs/exports.md`, `docs/analyses.md` and `docs/altium.md` hold the rest.
- **What a session showed.** On 2026-10-05 the loop was run by hand from a folder outside the repository, with a script written from `docs/dsl.md` and catalog ids found with `catalog list`. After the `direct` router, `check` returned twelve issues with empty hints, and their `where` values were file locators such as `/kicad_pcb/segment[0]`, not references. That session predates `fenolite explain` (c0066); task 0.1 repeats it on the tip of the day and writes what `check` and `explain` answer now. c0097 (board authoring) changes what a `copper.short` finding carries; the recipe `crossed` is written against the finding that is on `dev` that day.
- **The second backend.** `dev` writes Altium documents (c0084, c0085, c0086, c0088), and c0092 decides, per write kind, what leaves `experimental`. `capabilities` reports the result (`backends[].write_kinds`, `experimental`, `matrix`). The Altium verification kit (`fenolite kit`, c0091) is a run that a person performs in Altium Designer; an agent can build the kit and judge the files of a run, and cannot perform the run.
- **The repository's habit.** Pages are checked by tests (`test_agent_skill.py` parses the loop with the real parser; `test_release_record.py` and `test_format_facts.py` keep other pages honest), and generated files have a `--check` mode (`tools/gen_schemas.py`).
- **Constraints.** Authored for Fenolite: no text from a vendor's documentation, a standard or a company guide. No design-rule number presented as a rule (project plan, Q13: such tables are the user's). English. Short.

## Goals / Non-Goals

**Goals:**
- An agent that reads the start page and at most two other pages can write a design script for a small board and take it through `check`.
- Each page fits in one read: a few thousand tokens.
- No statement of a page can become false without a test failing.
- Recovery is a procedure with commands, not advice.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Completeness. The generated pages are complete; the written pages cover what a first board needs and say where the rest is.

## Decisions

1. **The pages.** Each has the front matter of c0079 (`topic`, `title`, `summary`). The table gives what each teaches, the commands that get their tested line there, and the names of `fenolite.dsl.__all__` that its design blocks use. Every public command and every taught name has exactly one home; a page may mention others.

   | topic | teaches | commands with their line here | DSL names in its design blocks |
   |---|---|---|---|
   | `design-script` | the shape of a script; modules, nets, parts and supplies; lengths with units; the board frame (origin at the outline's top-left corner, Y down); names and paths; the cycle edit, `build --dry-run`, `build --confirm`; what a rebuild keeps; a drawing sheet; taking placements back into the script | `init`, `build`, `sync`, `template` | `Design`, `Module`, `Net`, `Part`, `Power`, `connect`, `no_connect`, `mm`, `mil`, `inch`, `nm` |
   | `parts` | a part needs a symbol id and a footprint; the catalog and `catalog list --query`; KiCad's libraries through tables beside the script; pins by number and by name; `pad_map`; values with units and user properties; typed interfaces between parts | `catalog` | `ohm`, `farad`, `henry`, `volt`, `amp`, `watt`, `hertz`, `second`, `Interface`, `I2C`, `SPI`, `UART`, `USB2`, `Harness`, `DiffPair` |
   | `footprints` | `Footprint` and `Symbol` from dimensions; pads, slots, shared pads; what a person must still check against the datasheet; that such geometry is `INFERRED` | none | `Footprint`, `Symbol` |
   | `placement` | `place()`, sides and rotation, locked placements; staged parts and `place --strategy grid`; `place --move`; where the pads are and what is near a part; field placement; what the build refuses | `place`, `pads`, `neighbors`, `region` | none of its own |
   | `routing` | the routers and what each is for; how to get Freerouting; `route`, `--nets`, `--rip`, `unrouted`; scripted copper (`track`, `via`, `stitch`, arcs and vias inside a path); zones and `fill`; reading one net | `route`, `fill`, `net`, and `fetch` when it exists | `via_step`, `arc_to` |
   | `rules` | net classes against minimums; selectors; where a fabricator's limits go; that the examples' numbers are examples; `analyze` for current capacity, clearance and creepage | `analyze` | `select` |
   | `checks` | the stages of `check`; how to read an issue (`code`, `severity`, `where`) and `explain`; evidence levels; one fix per iteration; `--fields`, `--stages`, `--format concise` and `--limit` to keep replies small; the schematic's netlist and its parity with the board; `doctor` | `check`, `explain`, `netlist`, `parity`, `doctor`, `capabilities` | none of its own |
   | `files` | reading a file Fenolite did not write; whether editing it is safe (`roundtrip`); what changed between two files; whether two designs are equivalent; the canonical print; undoing a confirmed write | `inspect`, `diff`, `equivalent`, `roundtrip`, `fmt`, `restore` | none of its own |
   | `fabrication` | `export`, the bill of materials and the position file, the manifest and its states, `render`; what the files are; what is not produced | `export`, `render`, `bom`, `pnp`, `manifest` | none of its own |
   | `altium` | `build --target altium`: what is written, the options, the status and evidence of each write kind as `capabilities` reports it; the verification kit, a run that a person performs | `kit` | none of its own (one `fenolite-design altium` block) |
   | `recovery` | one recipe per exit code 2 to 7 and per common finding; reading the guide itself | `guide`, `skill` | none of its own |

   - `files` is new against the first draft of this proposal: 0.2.0 and the work of v0.3 added the reading, comparing and undoing commands, and no page had room for them.
   - A command that does not exist on `dev` at task 0.1 (`fetch` without c0078) has no line; a command that exists and is not in the table goes to the page whose subject is closest, and the choice is written under task 0.1.
   - `DSL_NOT_TAUGHT` starts with 27 names, in three groups:
     - what the build calls and a script never does: `to_model`, `placements`, `copper`, `fields`, `moves`, `module_moves`, `net_moves`, `planes`, `pad_zones`, `drawing_sheet_source`;
     - constants: `KEYS`, `DSL_BACKEND`, `BOARD_ORIGIN`;
     - records that the calls of a script return and a script never names: `CopperIntent`, `StitchIntent`, `TrackIntent`, `ViaIntent`, `FieldRequest`, `PadZoneRequest`, `ArcStep`, `ViaStep`, `PadEnd`, `PadRef`, `Placement`, `Length`, `Quantity`, `DslError`.
     - The other 31 names are in the table. `MechanicalIntent` (c0096) joins the third group when it is on `dev`.
   - A page ends with "Read next": at most three topics.
   - The start page gains an index: one line per topic with its summary, generated from the front matter. Its section "Small questions between the steps" shrinks to one line per page that now holds those commands.

2. **Three kinds of tested block.** A fenced block in a page or in the start page carries one of these tags, and nothing else may hold code:
   - **`fenolite-cmd`**: one `fenolite` command per line. The test parses each line with the parser of `build_parser(discover())`. Lines use concrete values and the paths of the starter (`blink/…`).
   - **`fenolite-design`**: a complete design script. The test writes it to a temporary folder and builds it with no library table and subprocess creation patched to raise: exit 0 and no issue of severity `error`, for targets 9 and 10. With the tag `fenolite-design altium` it is built with `--target altium` instead.
   - **`fenolite-recipe <sandbox>`**: lines of the form `<command>  # exit N`, optionally followed by `, has <code>`. The test prepares the named sandbox (`tests/unit/agent/_sandbox.py`), runs the lines in order in it, and checks each exit code and, where given, that the error object or the issues hold the code.
   - The tags `json` and `text` are allowed for output samples and are not run. Any other tag, and a block without a tag, fails the test with the file and the line.
   - Rejected: doctest-style fragments with a hidden preamble (an agent copies what it sees, so what it sees must be the whole script); marking some blocks "not tested" (the exception becomes the habit).

3. **Coverage.**
   - Every command of the registry that is not hidden must be the command of at least one line in a `fenolite-loop`, `fenolite-cmd` or `fenolite-recipe` block. The generated `commands` page does not count.
   - Every name of `fenolite.dsl.__all__` must appear in a `fenolite-design` block, or in `guide.DSL_NOT_TAUGHT`, a mapping from name to a one-line reason (Decision 1 lists the first 27).
   - Every code of the FEN registry must appear in the `recovery` page: the 17 codes of `9aba2dff` (`FEN-1001` to `FEN-7003`), `FEN-3006` and `FEN-6003` when c0078 is archived, and `FEN-1002`, `FEN-1003` and `FEN-4002` when c0120 is.
   - Issue codes are not covered by this rule: `fenolite explain` and its table (`cli/data/explain.toml`, c0066) already fail for a code without a meaning. The page `checks` teaches `explain`.
   - **Who pays.** The rule binds every change that lands after this one. A change that is on `dev` first is covered here at task 0.1. That holds for c0096, c0097 and c0099, which are implemented on their own branches and carry no guide line: `MechanicalIntent` and `place --strategy constrained|manual` (c0096) are the two items the rule sees; the `place.*`, `copper.clearance-unset`, `copper.item-unsupported`, `copper.rules-incomplete` and `body.*` issue codes are explained by `explain`, and the pages `placement` and `checks` name the commonest in a sentence.
   - `AGENTS.md` (Workflow) and `CONTRIBUTING.md` gain one line: a change that adds a public command or a public DSL name adds a tested line to a page. The coverage test is what enforces it.

4. **Generated pages.** `tools/gen_agent_guide.py [--check]` writes:
   - `references/commands.md`: one row per public command (name, summary, whether it writes) and, under each, its arguments, from `cli.describe`;
   - `references/dsl-reference.md`: one row per name of `fenolite.dsl.__all__` that is not in `DSL_NOT_TAUGHT`, with its kind and its signature from `inspect.signature`, and the first sentence of its docstring;
   - the index of pages inside `SKILL.md`, between two marker lines.
   - `--check` writes nothing and exits 1 when a file would change. `make check-fast` runs it, as it runs the schema generator's check.
   - Generated pages may be longer than written ones (Decision 5) and say in their first line that they are generated.

5. **Budgets.** A written page has at most 250 lines and 12 000 bytes; a generated page at most 600 lines; the start page stays under 200 lines (c0079). The whole skill folder stays under 150 000 bytes. A test checks all four.
   - Twelve thousand bytes is about three thousand tokens: a page costs an agent less than one large tool reply.

6. **Recovery recipes.** Each recipe has a heading that names the code, two or three sentences, and one `fenolite-recipe` block. The sandboxes are small projects made in `_sandbox.py` from the starter:

   | recipe | sandbox | what the block shows |
   |---|---|---|
   | exit 4, `FEN-4001` | `starter` | a write without a flag is refused; `--dry-run` shows the plan; `--confirm` writes |
   | exit 2, `FEN-2001` | `starter` | a wrong flag; the hint; the corrected line |
   | exit 3, `FEN-3001`, unknown lib id | `bad-lib-id` | the build names the id; `catalog list --query` finds one; the corrected script builds |
   | exit 3, `FEN-3004`, script error | `script-error` | the error's `where` is `line:<n>`; the corrected script builds |
   | exit 5, `copper.short` | `crossed` | a starter variant whose placement makes two straight tracks cross; `check --stages model.validate,copper.clearance` exits 5; `explain copper.short`; `place --move`, `route --rip`, and the same check exits 0 |
   | exit 6, router missing | `starter` | `route --router freerouting` without a jar; the hint; `route --router direct` instead |
   | exit 7, lossy refusal | `lossy` | a write that the target cannot hold is refused; what `--allow-lossy` accepts |

   - Each sandbox comes in a second, corrected form where the recipe edits the script: a recipe cannot edit a file, so its lines switch from `broken/design.py` to `fixed/design.py`, and the page shows the difference between the two as a `fenolite-design` block.
   - Recipes run with subprocess creation patched to raise, so none needs `kicad-cli`; a sandbox clears the variables that name a jar or a Java, so the router recipe starts no program. The findings of KiCad's own check (`kicad.drc.*`) are described in prose with the command to read them, and are not a recipe.
   - The `lossy` sandbox is the smallest case for which the suites already get `FEN-7001` from a write; task 0.1 names it.
   - The `crossed` sandbox asserts the code `copper.short` and the exit code 5, nothing of the finding's message or fields, so that c0097 can change what the finding explains without breaking the recipe.

7. **Writing rules for the pages.**
   - Plain statements, each one checkable against the code or a run. No change id, no hypothesis id, no history.
   - A number in a rule or a size is followed by "(example)" unless it is a Fenolite default, which is named as a default.
   - No company, no fabricator, no standard's table, no private path, no person. `tests/residue` scans the pages like any file; `test_pages.py` adds the check for the word "example" beside numbers in `rules.minimum` and `rules.netclass` calls inside prose.
   - The evidence label is stated wherever a page says that something is verified.
   - The page `altium` states no status of its own. It holds a table of the Altium write kinds with the status and the evidence level of each, written from `fenolite capabilities --json`, and `test_pages.py` compares the table with that reply: a kind that graduates (c0092) fails the test until the row is edited. The page says that the verification kit is a person's run.

8. **Order of work.** After `0.3.0`; after c0077 and c0079; after the harness of c0081. No requirement of this change is a delta of a living requirement, so no other proposal of v0.4 has to be ordered against its text; the coverage rule is the only tie (Decision 3). The harness of c0081 runs its first batch before these pages exist, with the start page of c0079 alone, and a second batch after. The two rows in `docs/evidence/agent-eval.md` are how this change is judged; a recipe or a page that the first batch shows to be missing is added here.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/agent/skill/references/{design-script,parts,footprints,placement,routing,rules,checks,files,fabrication,altium,recovery}.md` (new) | the eleven written pages |
| `src/fenolite/agent/skill/references/{commands,dsl-reference}.md` (new, generated) | the generated pages |
| `src/fenolite/agent/skill/SKILL.md` (extended) | the generated index between `<!-- pages:begin -->` and `<!-- pages:end -->` |
| `src/fenolite/agent/guide.py` (extended) | `DSL_NOT_TAUGHT: Mapping[str, str]`; `blocks(page) -> tuple[Block, ...]` with `Block(tag, argument, lines, line_number)` |
| `tools/gen_agent_guide.py` (new) | `main(argv)`; `--check` |
| `tests/unit/agent/test_pages.py`, `test_recipes.py`, `_sandbox.py` (new) | blocks, coverage, budgets, generated pages; recipes; `SANDBOXES` |
| `AGENTS.md`, `CONTRIBUTING.md`, `Makefile` (extended) | the rule for new commands and names; `check-fast` runs `gen_agent_guide.py --check` |

## Names introduced by this change

Guide topics `design-script`, `parts`, `footprints`, `placement`, `routing`, `rules`, `checks`, `files`, `fabrication`, `altium`, `recovery`, `commands`, `dsl-reference`. Block tags `fenolite-cmd`, `fenolite-design`, `fenolite-recipe`. API `fenolite.agent.guide.Block`, `guide.blocks`, `guide.DSL_NOT_TAUGHT`. Tool `tools/gen_agent_guide.py` with `--check`. Test sandboxes `starter`, `bad-lib-id`, `script-error`, `crossed`, `lossy`. No hypothesis id, no issue code, no error code, no command-line flag of `fenolite`, no result key, no model field, no source id. None of these names is in the tree at `9aba2dff`.

## Sources registered by this change

None. The pages state facts about Fenolite, each proved by a test of this change or of the change that built the feature. No text, table or figure of another publication is used.

## Hypotheses registered by this change

None. The claim that the pages help an agent is measured by c0081 and recorded in `docs/evidence/agent-eval.md`; it is not a format or tool fact.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Every command line of a page parses | mechanical | `test_pages.py -k cmd` |
| Every design block builds | the build's own level, hermetic | `test_pages.py -k design` |
| Every recipe gives its exit codes | mechanical | `test_recipes.py` |
| Coverage of commands, DSL names and FEN codes | mechanical | `test_pages.py -k coverage` |
| Generated pages are current | mechanical | `tools/gen_agent_guide.py --check` |
| Budgets and writing rules | mechanical | `test_pages.py -k "budget or rules"` |

## Budget (11 days)

| work | days |
|---|---|
| entry check; block parser in `guide`; the block and budget tests | 1.0 |
| generator and its two pages, the index | 1.0 |
| `design-script`, `parts` | 1.25 |
| `footprints`, `placement` | 1.0 |
| `routing`, `rules` | 1.25 |
| `checks`, `fabrication`, `altium` with its status table | 1.5 |
| `files`; the lines for the commands of 0.2.0 and v0.3 in the other pages; the units and interfaces in `parts` | 1.5 |
| sandboxes, `recovery` and its test | 1.5 |
| coverage test, `DSL_NOT_TAUGHT`, `AGENTS.md` and `CONTRIBUTING.md` | 0.5 |
| closing | 0.5 |
| **total** | **11.0** |

Cut order: (1) the `dsl-reference` page (the design blocks stay); (2) the `lossy` recipe; (3) the interfaces in `parts` (their names then go to `DSL_NOT_TAUGHT` with the reason "not taught yet"). The `altium` page is no longer first to go: the commands `kit` and `equivalent` have their line there. Not optional: the three block kinds and their tests, coverage of commands, `design-script`, `parts`, `routing`, `checks` and `recovery`.

## Risks / Trade-offs

- [Every new command now needs a page line] → one line in an existing block; the test names the missing command, and `AGENTS.md` states the rule.
- [Pages grow until they are the contract page again] → the byte budget is a test, and the generated pages hold the complete lists.
- [Complete scripts make pages long] → the scripts are small boards of three to six parts; one script per page is the norm.
- [A recipe passes while the advice is poor] → the test proves only that the commands behave as written; c0081 measures whether agents recover.
- [Two copies of the truth, `docs/` and the pages] → the pages hold no requirement text; every claim is a block that runs, so a divergence fails a test on one side.
- [Advice on design practice turns into rules of thumb with numbers] → Decision 7: numbers are marked as examples, and the page on rules says whose numbers apply.

## Migration Plan

- Additive: files in the package, one tool, tests.
- A change open when this one lands sees the coverage test fail for its new command until it adds a line; the rule is in `AGENTS.md` from the same commit.
- Rollback: remove the pages and the tests; `fenolite guide` then lists the start page only.

## Open Questions

- **Should the commonest `kicad.drc.*` findings get recipes that run on `kicad-cli`?** Default: not here; they need the tool, and `fenolite explain` gives each code a meaning and a fix. A later change can add an oracle-run recipe suite.
- **One page per command instead of pages per task?** Default: per task. The generated `commands` page is the per-command view.
- **A page of its own for interfaces and quantities?** Default: no; they are a section of `parts`. If `parts` passes its byte budget, the section becomes the page `interfaces` and the count of written pages is twelve.
