## Context

- **Milestone.** v0.4, the agent track (c0077 to c0081). Written against `origin/dev` at `9aba2dff`.
- **The name.** The package of this change is the agent guide: module `fenolite.agent.guide`, capability `agent-guide`. The maintainer decided on 2026-10-07 that the word "kit" stays with the Altium verification kit (`fenolite kit`, `cli/_kit.py`, the requirement "Kit command", c0091). The two have nothing in common, and no name of this change holds that word.
- **Scope.** Project plan, decision D8: "Skills: `AGENTS.md` + `agent/SKILL.md`", with the package layout `src/fenolite/agent/` ("SKILL.md, mcp_server.py"), and "MCP as the primary surface" among the rejected alternatives. The layering table already has the row `agent` → `cli` (`package-layering`, "Allowed import edges").
- **What exists.**
  - `agent/SKILL.md` (131 lines at `9aba2dff`): seven rules, one `fenolite-loop` block of ten commands on `examples/blink_2layer` (the fifth with `--router freerouting`, the tenth `inspect`), what to do when a step fails, a section "Small questions between the steps" that c0066 and later changes filled (`explain`, `roundtrip`, `diff`, `net`, `region`, `neighbors`, `netlist`, `fmt`, `manifest`, `kit`, `restore`, `pads`), and "Limits". `tests/unit/test_agent_skill.py` parses the block with the real parser and compares it with the block of `README.md`; `tests/routing/test_acceptance_loop.py::test_skill_block` runs it with Freerouting.
  - `pyproject.toml`: the wheel is `packages = ["src/fenolite"]`; the source distribution's allowlist has no `/agent`. Files inside the package that are not Python already ship (`backends/kicad/data/tokens.toml`).
  - `cli/api.py`: `Command(name, help, mutates, register, run, example_args, mutation_example_args, example_tools, paged, default_limit)` with the properties `hidden` and `schema`; `register` fills an `argparse` parser. `cli/main.py` adds the global flags `--json`, `--text`, `--fields`, `--limit`, `--cursor`, `--format`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version` and `--allow-lossy` to every command, and prints text mode with `output.render_text(envelope)`: the status line, the input, `result`, one line per issue, the evidence and the receipt. The consistency suite requires text output to start with `fenolite <name>: ok`.
  - `capabilities`: `commands` (`name`, `mutates`, `schema`, `hidden`, and `paged` and `default_limit` for a paged command), `backends`, `experimental`, `matrix`, `extras`, `tools`, `routers`, `sends_data_offsite`. Router availability is in `doctor` only. The backend `altium` has no `write_kinds` yet: its writers are under `experimental`, and c0092 (open on `dev`) moves each kind that graduates.
  - `build --target` takes `kicad` or `altium`.
  - The catalog (c0075, c0076) resolves `Fenolite:` ids with no library table, and c0077 makes a catalog-only board pass `check`.
- **Measured on 2026-10-07**, `dev` at `9aba2dff`: `capabilities --json --no-tools` is 20.7 kB, of which `matrix` is 12.1 kB, `experimental` 3.4 kB, `commands` 3.1 kB and `backends` 1.3 kB; it lists 30 public commands and one hidden one. On 2026-10-05, at `1882644`, the reply was 5.4 kB with 13 commands. The built-in `direct` router closes a two-pad net with one straight track and checks nothing.
- **Constraints.** Stdlib only. Every new command follows the envelope, the exit codes and the mutation protocol, and passes the consistency suite. No network. No file written outside the folder the caller names.

## Goals / Non-Goals

**Goals:**
- After `pip install fenolite`, one command prints the guide and one command gives a project that passes `check`.
- One description of each command's arguments, taken from the parser itself, that the guide's tables read and that another front end (the MCP server of v0.5b) can read later.
- The first reply an agent reads stays small while the default view grows.
- Nothing in the guide can drift from the code without a failing test.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- Teaching design. The pages of c0080 do that; this change carries them.

## Decisions

1. **The package `fenolite.agent`.**
   ```
   src/fenolite/agent/
     __init__.py
     guide.py
     skill/SKILL.md
     skill/references/<topic>.md        (written by c0080; none here)
     starters/blink/starter.toml
     starters/blink/design.py.tmpl
   ```
   - The skill folder is the open "agent skill" layout: a `SKILL.md` with front matter (`name`, `description`) and files it points to. An agent that supports skills loads the body when a task matches and a reference page only when it needs one.
   - A page starts with front matter of exactly `topic`, `title` and `summary`. `guide` reads front matter with a small parser of `key: value` lines; no YAML library.
   - `guide` reads everything through `importlib.resources.files("fenolite.agent")` and imports the standard library only.
   - Starters end in `.tmpl`: they are not package modules, the licence-header test does not scan them, and they carry their own `CC0-1.0` line into the user's project.
   - Rejected: keeping the guide in `docs/` and shipping `docs/` in the wheel (the contract page alone is 154 kB at `9aba2dff`, written for contributors); a separate distribution for the skill (two versions to keep equal); the module name `kit` (taken, see Context).

2. **`guide` API.** `Page(topic, title, summary, text)`; `pages()` returns `start` first and the others by topic; `page(topic)`; `skill_files()` returns each file of `skill/` with its relative path and bytes; `Starter(name, summary, files)`; `starters()`; `render_starter(name, design_name)`.
   - The page `start` is the body of `SKILL.md`: its title is the first heading and its summary the front matter's `description`.
   - Loading validates: a missing key, an unknown key, a duplicate topic or a topic that is not `[a-z0-9-]+` raises `GuideError`. A test loads everything.

3. **`Result.text`.** `Result` gains `text: str | None = None`. In text mode the dispatcher prints the status line, an empty line and that text, in place of the `input`, `result` and `evidence` lines of the generic rendering. JSON mode ignores it.
   - The status line stays, so the consistency suite's rule holds for every command.
   - Issue lines and receipt lines, when the envelope has any, follow the text after one empty line, in the form `render_text` gives them today. A page of the guide has neither.
   - `--format concise` (c0066) folds the envelope's issues before either mode prints them, so it applies to those lines and has no effect on the text. `--limit` and `--cursor` cut a command's paged list; a command that sets `text` declares no paged list.

4. **`fenolite guide [TOPIC]`** (`mutates=False`).
   - Without a topic: `result.topics`, one `{topic, title, summary, lines}` per page; the text is one line per page.
   - With a topic: `result` is `{topic, title, summary, text, version}`, `text` being the page's body and `version` the Fenolite version; text mode prints the body.
   - An unknown topic exits 2 with the closest topics in the hint.
   - An agent reads a page with `fenolite guide routing --text`. The JSON form is for programs.

5. **Command descriptions.** `cli/describe.py`:
   - `Argument(name, flags, kind, type, choices, default, required, repeatable, help)`, with `kind` one of `positional`, `option`, `flag` and `type` one of `string`, `integer`, `number`, `boolean`.
   - `describe(command) -> CommandDescription(name, summary, mutates, usage, arguments)`; `global_arguments()` for the flags every command takes.
   - The description comes from the parser that `build_parser` makes for the command, so `--dry-run` and `--confirm` appear for mutating commands and nothing is declared twice.
   - A test compares, for every command, the option strings of its description with the ones its `--help` prints.
   - The global flags are read from the same parser, so `--limit`, `--cursor` and `--format` (c0066) are listed today, and the `--plan` and `--progress` that c0120 proposes will be listed when they exist.
   - Rejected: a hand-written table of arguments (it would drift); JSON Schema here (a front end that needs it derives it from `Argument`).

6. **Two views of `capabilities`.** The default result is unchanged.
   - `--brief`: `result` holds exactly `fenolite_version`, `commands` (`name`, `summary`, `mutates`, without hidden commands), `targets` (`{build: ["altium", "kicad"], kicad: [9, 10], default: 10}`), `tools`, `routers` (`name`, `available`, `reason`), `guide` (`topic`, `title`, `summary`), `starters` (`name`, `summary`) and `sends_data_offsite`.
     - `targets.build` is the list of choices of `build --target`, read from the parser through `describe`; `targets.kicad` and `targets.default` are the target majors and the default major of the `kicad` backend's entry. So the brief view says that an Altium target exists. It does not say how far that target is verified: that is per write kind, in `backends[].write_kinds`, `experimental` and `matrix` of the default view (c0092), and the start page says where to read it.
     - `available` and `reason` come from `Router.available()`, which runs `java -version` at most. With `--no-tools` they are `null`.
     - A test keeps the brief result of `--no-tools` under 300 bytes per listed command plus 2 000 bytes: at most 11.9 kB for the 33 public commands that exist after this change (12.2 kB with `fetch` of c0078), against the 20.7 kB of the default view today. Task 3.4 records the measured size; it differs from the default in what it holds (summaries, availability, pages, starters) and in what it leaves out as the default grows.
     - `--brief` is not `--format concise`: the first chooses another `result` for this one command, the second folds the issues of any command. They may be given together.
   - `--command NAME`: `result.command` is that command's entry of the default view plus `summary`, `usage` and `arguments`; `result.global_arguments` lists the global flags once.
   - The two flags exclude each other. Both keep `--fields`.
   - Rejected: changing the default result (living requirements fix its keys: "Capabilities command", "Backends in capabilities", "Experimental features in capabilities", "Routers in capabilities and doctor", "Evidence matrix in capabilities"; c0092 adds "Altium kinds in capabilities"); a new command `describe` (discovery stays in one place).

7. **`fenolite skill show`** and **`fenolite skill install [--agent NAME | --dir DIR] [--agents-md]`** (`mutates=True`).
   - `show` plans nothing: `result` holds `name`, `description`, `version`, `files` (`path`, `bytes`, `sha256`) and `agents` (`agent`, `dir`).
   - `install` plans `<dir>/fenolite/SKILL.md` and `<dir>/fenolite/references/<topic>.md`. `<dir>` is `DIR`, or the row of `guide.AGENT_DIRS` for `NAME`, relative to the working directory.
   - `AGENT_DIRS` starts with one row, `claude-code` → `.claude/skills`. A row is added only with the public page that documents that agent's project skill folder, registered in `docs/evidence/sources.md` and named in a comment beside the row. The first row's source is S-0610.
   - The installed `SKILL.md` ends with one added line, `<!-- installed from fenolite <version> -->`, so a stale copy can be told from the installed package. The packaged file has no such line.
   - `--agents-md` also plans `AGENTS.md` in the working directory: the fixed section `guide.AGENTS_SECTION` between the lines `<!-- fenolite:begin -->` and `<!-- fenolite:end -->`. A file without the markers gets the section appended; a file with them gets the text between them replaced; no file gets one created. The section tells any agent to run `fenolite guide start --text` before a board task. Agents that read `AGENTS.md` and no skill folder are served this way.
   - Neither `--agent`, `--dir` nor `--agents-md` exits 2.
   - Everything goes through the mutation protocol: a plan, backups of overwritten files, a receipt.

8. **`fenolite init DIR [--starter NAME] [--name NAME] [--force]`** (`mutates=True`).
   - Plans `DIR/design.py` from the starter's template, with the token `@NAME@` replaced by the design name. The default starter is `blink`; the default name is the last component of `DIR`. A name that is not a design name (`^[A-Za-z0-9][A-Za-z0-9_.-]*$`) exits 2.
   - An existing `DIR/design.py` is refused with exit 2 unless `--force` is given; with it, the protocol's backup applies.
   - `result` holds `starter`, `name`, `design` and `next`, the two commands to run next (`fenolite build DIR/design.py --out DIR/build --dry-run`, then `--confirm`). A test parses `next` with the real parser.
   - An unknown starter exits 2 and names the starters.

9. **The starter `blink`.** A two-pin header, a resistor and a LED from the catalog, three two-pad nets, a 30 mm by 20 mm board, board minimums, every part placed.
   - The placement is chosen so that the straight track of each net crosses no other pad or track. `route --router direct` then closes the board with no external tool, and `check` passes.
   - Comments in the script say what each block is, in a dozen lines, and say that a real board needs a router or scripted copper.
   - Rejected: scripted copper in the starter (the loop would skip `route`, the step agents most need to see); unplaced parts (the grid placement would decide whether straight tracks short).

10. **The guide's loop.** `SKILL.md` keeps one `fenolite-loop` block of at most ten lines, now on the starter:
    ```
    fenolite capabilities --brief --json
    fenolite init blink --confirm --json
    fenolite build blink/design.py --out blink/build --dry-run --json
    fenolite build blink/design.py --out blink/build --confirm --json
    fenolite place blink/build --strategy grid --confirm --json
    fenolite route blink/build --router direct --confirm --json
    fenolite fill blink/build --confirm --json
    fenolite check blink/build --json
    fenolite export blink/build -o blink/fab --all --manifest --confirm --json
    fenolite render blink/build -o blink/views --svg --png --confirm --json
    ```
    - `place` and `fill` change nothing on this board; the guide says so and says when they matter. They stay in the block because the order is what an agent must learn.
    - `inspect`, the tenth line of the block on `dev`, leaves it: ten lines are the limit, and `init` and the brief view come first. It moves to "Small questions between the steps".
    - `tests/unit/test_agent_skill.py` parses the block and runs its first six lines with subprocess creation patched to raise. `tests/kicad/acceptance/test_skill_block.py` runs all ten on the running `kicad-cli`, for both majors.
    - The loop on `examples/` with Freerouting stays where it is (`release-gate`, "Acceptance loop"); only `test_skill_block` leaves the `routing` job.
    - The rest of the file keeps what the guide holds at `9aba2dff`, in under 200 lines:
      - the seven rules, with `capabilities --brief` first and `capabilities --json` (`result.matrix`) as the reply to read before choosing an operation on a file kind; the exit-code table; `--fields`, `--format concise` and `--limit`;
      - `fenolite guide <topic> --text` as the way to read more;
      - "when a step fails";
      - "Small questions between the steps", with `inspect` and `pads` added to the commands it names today. The section stays prose here. c0080 turns its command lines into tested `fenolite-cmd` blocks, in the start page or in the pages `checks` and `placement`, and owns the section from then on;
      - one sentence that the Altium verification kit (`fenolite kit`) is a run that a person performs in Altium Designer and is not this guide;
      - "Limits", with the status of the Altium target as `capabilities` reports it after c0092, and no fixed word for it.
    - `README.md` holds the same block and names the guide's new path and `fenolite guide`; `AGENTS.md` item 7 of "Using the `fenolite` CLI" follows.

11. **The wheel.** `tests/unit/agent/test_guide.py` checks that `importlib.resources` finds the skill and the starter in the installed package. The `wheel` CI job, which installs the built wheel in a clean environment, also runs `fenolite guide start --text` and `fenolite init blink --dry-run` from an empty folder.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/agent/__init__.py`, `agent/guide.py` (new) | `Page`, `Starter`, `SkillFile`, `GuideError`; `pages()`, `page(topic)`, `skill_files()`, `starters()`, `render_starter(name, design_name)`; `AGENT_DIRS`, `AGENTS_SECTION`, `SKILL_NAME` |
| `src/fenolite/agent/skill/SKILL.md` (moved from `agent/SKILL.md`, rewritten) | the start page |
| `src/fenolite/agent/starters/blink/` (new) | `starter.toml`, `design.py.tmpl` |
| `src/fenolite/cli/describe.py` (new) | `Argument`, `CommandDescription`; `describe(command)`, `global_arguments()` |
| `src/fenolite/cli/cmd_guide.py`, `cmd_skill.py`, `cmd_init.py` (new) | `COMMAND`s |
| `src/fenolite/cli/api.py`, `main.py`, `output.py` (extended) | `Result.text`; text mode prints it |
| `src/fenolite/cli/cmd__echo.py` (extended) | the hidden option `--text-body` |
| `src/fenolite/cli/cmd_capabilities.py` (extended) | `--brief`, `--command NAME` |
| `README.md`, `AGENTS.md` (changed) | the block; the guide's place |
| `tests/unit/agent/test_guide.py`, `tests/unit/cli/test_describe.py`, `test_guide_cmd.py`, `test_skill_cmd.py`, `test_init_cmd.py`, `test_capabilities_brief.py` (new) | hermetic |
| `tests/unit/test_agent_skill.py` (changed); `tests/kicad/acceptance/test_skill_block.py` (new); `tests/routing/test_acceptance_loop.py` (`test_skill_block` removed) | the block |
| `docs/cli-contract.md` (extended) | sections `guide`, `skill`, `init`; the two views under "Discovery"; `Result.text` under "Output" |

## Names introduced by this change

- Hypothesis `H-K-GUIDE-STARTER`. Source id S-0610.
- Commands `guide`, `skill` (`show`, `install` with `--agent`, `--dir`, `--agents-md`) and `init` (`--starter`, `--name`, `--force`); flags `--brief` and `--command` of `capabilities`; hidden `_echo` option `--text-body`.
- Result keys: of the brief view `fenolite_version`, `commands[].summary`, `targets` (`build`, `kicad`, `default`), `routers[].available`, `routers[].reason`, `guide`, `starters`; of the command view `command` (with `summary`, `usage`, `arguments`) and `global_arguments`; of `guide` `version`, `topics` (`topic`, `title`, `summary`, `lines`) and `text`; of `skill` `name`, `description`, `version`, `files`, `agents`, `action`, `target`; of `init` `starter`, `name`, `design`, `next`.
- API: `Result.text`; `fenolite.cli.describe` (`Argument`, `CommandDescription`, `describe`, `global_arguments`); `fenolite.agent.guide` (`Page`, `Starter`, `SkillFile`, `GuideError`, `pages`, `page`, `skill_files`, `starters`, `render_starter`, `AGENT_DIRS`, `AGENTS_SECTION`, `SKILL_NAME`).
- No error code, no issue code, no model field. None of these names is in the tree at `9aba2dff`.

## Sources registered by this change

One, S-0610 (the first id of the block S-0610 to S-0619 that the coordinator gave the agent track; `docs/evidence/sources.md` ends at S-0601 at `9aba2dff`): the public documentation page that names the project skill folder of the agent in the first row of `AGENT_DIRS`. It is read for that one fact. Task 0.1 registers it.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-GUIDE-STARTER | The ten lines of the guide's block, run in an empty folder with only Fenolite and `kicad-cli` installed, exit 0 on 9.0.9 and on 10.0.6, and `check` reports no design-rule violation and no unconnected item for the starter routed by the `direct` router | `tests/kicad/acceptance/test_skill_block.py` | every line exits 0 on both majors; `check`'s DRC summary has zero violations and zero unconnected items |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Guide loader, front matter, packaged files | mechanical | `test_guide.py`; the `wheel` job |
| `guide`, `skill`, `init`, the two views of `capabilities` | mechanical | their unit tests; the consistency suite |
| Descriptions agree with `--help` | mechanical | `test_describe.py` |
| Starter builds and its copper check is clean | INFERRED (the board read) | `test_init_cmd.py -k starter` |
| The block closes the loop | KICAD-VERIFIED, `H-K-GUIDE-STARTER` | `test_skill_block.py` on 9.0.9 and 10.0.6 |

## Budget (8.25 days)

| work | days |
|---|---|
| entry check, register | 0.25 |
| guide loader and front matter | 0.75 |
| `Result.text` and `guide` | 0.75 |
| `describe` and the two views of `capabilities` | 1.5 |
| `skill show`, `skill install`, the `AGENTS.md` section | 1.0 |
| `init` and the starter | 1.0 |
| the start page with the sections of 0.2.0 and 0.3.0, `README.md`, `AGENTS.md`, moved tests | 1.5 |
| the block on both majors, the `wheel` job | 0.5 |
| contract page | 0.5 |
| closing | 0.5 |
| **total** | **8.25** |

Cut order: (1) `--agents-md`; (2) `skill show`; (3) `capabilities --command` (the module `describe` stays: the brief view's summaries and c0080's tables use it). Not optional: the packaged guide, `guide`, `skill install`, `init` with a starter that passes `check`, the brief view, and the block on both majors.

## Risks / Trade-offs

- [A copied skill grows stale] → the version line in the installed file; the guide says that `fenolite guide` always matches the installed version.
- [Agent folders change] → one table, one source per row, and `--dir` works for any agent.
- [The brief view becomes a second contract] → its keys are fixed by one requirement and built from the same functions as the default view.
- [The `direct` router suggests it is enough] → the starter and the start page say what it is for; c0080's routing page names `fetch` and scripted copper.
- [The block needs `kicad-cli` for four of its lines] → the unit test runs the six that need none; the oracle test runs all ten on both majors.
- [Other changes name `agent/SKILL.md`] → c0066 is archived. c0092 (open on `dev`, task 5.1) edits the file and should be archived first; c0108, c0111 and c0120 (v0.4) name it in a guide task and land after this change. Task 0.1 lists every open change that names the path and edits each task to the new one in this change's first commit.
- [Two things called a guide: the command and the module] → `fenolite guide` is the command and `fenolite.agent.guide` the loader it calls; one reads the other, and no third name is needed.
- [The start page states the status of the Altium target and it changes] → it states no fixed word: it points at `capabilities --json` (`result.matrix`, and `write_kinds` after c0092), which is where the status is kept.

## Migration Plan

- `agent/SKILL.md` moves; no stub stays. `README.md`, `AGENTS.md` and two test files follow in the same commit. `docs/release/v0.1.md` keeps its sentence about the v0.1 session: it is a record.
- Additive otherwise: three commands, two flags of `capabilities`, one field of `Result`.
- Rollback: restore the file at the root and remove the commands; projects made by `init` are plain design scripts and stay valid.

## Open Questions

- **Should the brief view carry the status of each Altium write kind?** Default: no; `targets.build` names the target and the default view holds the status (Decision 6).
- **More starters here?** Default: `blink` only. c0081's tasks show which first projects agents need.
- **Should `fenolite guide` print the start page when it has no topic?** Default: no; it lists the pages, and `guide start` prints it.
- **A user-wide install by agent name.** Default: no; `--dir` names any folder, and a table of home folders per agent would need a source per row.
