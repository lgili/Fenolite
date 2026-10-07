## 0. Entry check

- [ ] 0.1 Read the living `agent-guide` and `cli-contract` specs, `openspec list` and `fenolite capabilities --brief --json`. Write under this task, with the date and the commit:
  - that `0.3.0` is released and that c0077 and c0079 are archived (stop here otherwise);
  - the public commands on `dev` that day, each with the page of Decision 1 that takes its line. The table of Decision 1 places the 30 commands of `9aba2dff`, the three of c0079 and `fetch`; a command that is not in it (one of c0096, c0097, c0099 or of another change archived since) is placed here;
  - the names of `fenolite.dsl.__all__` that day, each with its page or its reason in `DSL_NOT_TAUGHT` (`MechanicalIntent` when c0096 is on `dev`);
  - the codes of the `FEN-` registry that day;
  - the Altium write kinds with the status and the evidence level that `capabilities` reports for each (the table of the page `altium`);
  - the smallest case for which the suites already get `FEN-7001` from a write (the `lossy` sandbox);
  - what `check` and `explain` answer for two crossed tracks (the session of 2026-10-05 repeated: the codes, whether `hint` is empty, the form of `where`), on the `copper.short` finding as it is with or without c0097;
  - the first batch of `docs/evidence/agent-eval.md` if c0081 has run one, with the failures it lists (each becomes a recipe or a paragraph of a page).
  Proof: `openspec validate c0080-agent-authoring-guide --strict --no-interactive` passes after any re-base, and the notes hold each of the lists above.

## 1. Blocks and their tests

- [ ] 1.1 Add `Block` and `blocks(page)` to `src/fenolite/agent/guide.py`, and write the block checks of `tests/unit/agent/test_pages.py`: allowed tags, `fenolite-cmd` through the real parser, `fenolite-design` built hermetically for targets 9 and 10 or for Altium (scenarios "Every command line parses", "Every design builds", "An untested block is refused"). They pass on the start page alone. Proof: `uv run pytest tests/unit/agent/test_pages.py -k "cmd or design or untested" tests/unit/agent/test_guide.py -q`; `uv run pyright src`.
- [ ] 1.2 Add the budget and writing-rule checks (scenarios of "Page budgets and writing rules"). Proof: `uv run pytest tests/unit/agent/test_pages.py -k "budget or rules" -q`.

## 2. Generated pages

- [ ] 2.1 Write `tools/gen_agent_guide.py` with `--check`, the pages `references/commands.md` and `references/dsl-reference.md`, the index between the markers of the start page, and `guide.DSL_NOT_TAUGHT` with a reason per name; add the generator's check to `make check-fast` (scenarios of "Generated guide pages"). Proof: `uv run python tools/gen_agent_guide.py --check` exits 0; `uv run pytest tests/unit/agent/test_pages.py -k generated tests/unit/test_spdx_headers.py -q`; `grep -c gen_agent_guide Makefile` is at least 1.

## 3. Written pages

Each task writes its pages from the code and from runs of the commands, in Fenolite's own words, gives every command of Decision 1 its tested line, and keeps the block, budget and writing-rule tests green.

- [ ] 3.1 Write `design-script` and `parts` (with the units and the interfaces). Proof: `uv run pytest tests/unit/agent/test_pages.py -k "topics or cmd or design or budget or rules" -q`; `uv run fenolite guide design-script --text` and `uv run fenolite guide parts --text` exit 0.
- [ ] 3.2 Write `footprints` and `placement`. Proof: the same test selection; `uv run fenolite guide placement --text` names `fenolite pads` and `place --move`.
- [ ] 3.3 Write `routing` and `rules` (scenario "A page through the command line"). Name `fenolite fetch freerouting` only when c0078 is archived. Proof: the same test selection; `uv run fenolite guide routing --text` names `direct`, `--rip`, `design.track` and `fenolite fill`.
- [ ] 3.4 Write `checks`, `files` and `fabrication`, and turn the section "Small questions between the steps" of the start page into one line per page. Proof: the same test selection; `uv run pytest tests/unit/test_agent_skill.py -q`; `uv run fenolite guide files --text` names `roundtrip`, `diff`, `equivalent` and `restore`.
- [ ] 3.5 Write `altium` with its table of write kinds; its script is tagged `fenolite-design altium` (scenario "Altium status follows capabilities"). Proof: `uv run pytest tests/unit/agent/test_pages.py -k "design or altium_status" -q`.

## 4. Recovery

- [ ] 4.1 Write `tests/unit/agent/_sandbox.py` (`SANDBOXES`: `starter`, `bad-lib-id`, `script-error`, `crossed`, `lossy`, each with its corrected form where the recipe needs one) and `tests/unit/agent/test_recipes.py` with the recipe runner (scenario "A recipe that lies fails"). The sandboxes are built in code from the starter; no file is added under `tests/data`, so `tests/data/MANIFEST.toml` does not change. Proof: `uv run pytest tests/unit/agent/test_recipes.py -k "runner or lies" tests/corpus/test_manifest.py -q`.
- [ ] 4.2 Write the page `recovery`: the seven recipes and the table of the remaining codes (scenarios "Recipes behave as written", "Crossed tracks are repaired", "Every error code is named"). Proof: `uv run pytest tests/unit/agent/test_recipes.py tests/unit/agent/test_pages.py -k "recipes or crossed or fen_codes or budget" -q`.

## 5. Coverage

- [ ] 5.1 Add the coverage checks (scenarios of "Guide covers the public surface"), add the missing lines they report, and add the rule to `AGENTS.md` (Workflow) and `CONTRIBUTING.md`. Proof: `uv run pytest tests/unit/agent/test_pages.py -k coverage tests/unit/test_agent_skill.py tests/residue -q`.

## 6. Closing

- [ ] 6.1 Update the evidence: no hypothesis is registered by this change. If c0081's harness exists, ask the maintainer for the second batch and record its row beside the first in `docs/evidence/agent-eval.md`; if it does not, or the maintainer does not start the batch, say so under this task. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 6.2 Add to `CHANGELOG.md` under `## [Unreleased]`: "**The agent guide teaches how to design a board**: eleven pages (`fenolite guide <topic>`) on the design script, parts, footprints, placement, routing, rules, checks, reading and comparing files, fabrication files, the Altium target and recovery, plus generated command and DSL references. Every command line, design script and recovery recipe of the guide is run by tests, and **a new command, DSL name or error code must be added to it**". Update the row of this change in `docs/roadmap.md`. Proof: `git diff --stat HEAD -- CHANGELOG.md docs/roadmap.md` lists both files.
- [ ] 6.3 Stop and report "ready for the long runs": `make check-fast` (which now runs `tools/gen_agent_guide.py --check`), the unit suite on Python 3.11 (`uv run --python 3.11 pytest tests/unit -q`), `uv run pytest tests/residue tests/corpus/test_manifest.py -q` after `git add -A`, `uv run python tools/residue/scan.py`, `uv build` (the wheel lists the thirteen pages), and `openspec validate --all --strict --no-interactive`. The full `make check` is run once by the coordinator on the rebased branch, not by the implementing agent. Proof: each command exits 0.
