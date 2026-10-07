## 0. Entry check

- [ ] 0.1 Read the living `cli-contract`, `release-gate` and `package-layering` specs and `openspec list`. Write under this task, with the date and the commit:
  - that `0.3.0` is released and that c0077 is archived (the starter depends on it; stop here otherwise);
  - whether c0092 is archived (it edits `agent/SKILL.md` and decides the status of the Altium write kinds that the start page points at) and, for every open change that names `agent/SKILL.md` (`grep -rln "agent/SKILL.md" openspec/changes --exclude-dir=archive`), the task that names it: change the path to `src/fenolite/agent/skill/SKILL.md` in this change's first commit;
  - whether c0078 is archived (the start page then names `fenolite fetch freerouting`, else it does not);
  - the public commands and the global flags of the day, from `fenolite capabilities --json --no-tools` and `fenolite build --help`, and the size of that reply;
  - whether another change modified "Agent guide is executable" since this proposal (then regenerate the MODIFIED delta from the living text).
  Register the page that documents the first row of `AGENT_DIRS` in `docs/evidence/sources.md` as S-0617. Proof: `openspec validate c0079-agent-guide --strict --no-interactive` passes after any re-base; `uv run pytest tests/unit/test_provenance.py tests/unit/verify/test_cited_ids.py -q`; `grep -c '^| S-0617 ' docs/evidence/sources.md` prints `1`.
- [ ] 0.2 Add the row `H-K-GUIDE-STARTER` to `docs/hypotheses.md` (backend `kicad`, level `INFERRED`, the test and criterion of `design.md`, result `pending`). Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `grep -c '^| H-K-GUIDE-STARTER ' docs/hypotheses.md` prints `1`.

## 1. The loader

- [ ] 1.1 Create `src/fenolite/agent/` with `__init__.py` and `guide.py` (front matter, `pages`, `page`, `skill_files`, `GuideError`), move `agent/SKILL.md` to `src/fenolite/agent/skill/SKILL.md` with `git mv`, and write `tests/unit/agent/test_guide.py` (scenarios "Guide loads from the installed package", "Malformed page is refused", "Guide stays stdlib-only"). Keep the file's text for now and point `tests/unit/test_agent_skill.py` and `tests/routing/test_acceptance_loop.py` at the new path. Proof: `uv run pytest tests/unit/agent tests/unit/test_agent_skill.py tests/unit/test_import_graph.py tests/unit/test_spdx_headers.py -q`; `uv run pyright src`; `uv build` lists `fenolite/agent/skill/SKILL.md` in the wheel.
- [ ] 1.2 Add starters to `guide` (`starters`, `render_starter`) and write `src/fenolite/agent/starters/blink/` (`starter.toml`, `design.py.tmpl`): tune the placement until `route --router direct` closes the three nets with a clean copper check for targets 9 and 10 (the hermetic proof of "Starter projects"). Proof: `uv run pytest tests/unit/cli/test_init_cmd.py -k starter -q` (written here, with the catalog rule); `uv build` lists the two starter files in the wheel.
- [ ] 1.3 Add `AGENT_DIRS`, `AGENTS_SECTION` and `SKILL_NAME` to `guide`, with the source comment per row (scenario "Rows are sourced"). Proof: `uv run pytest tests/unit/agent/test_guide.py -k agent_dirs tests/residue -q`.

## 2. Dispatcher and descriptions

- [ ] 2.1 Add `Result.text`, print it in text mode, and add the hidden option `--text-body` to `_echo` (scenarios of "Command text"). Proof: `uv run pytest tests/unit/cli/test_output.py tests/unit/cli/test_main.py tests/consistency -q`.
- [ ] 2.2 Write `src/fenolite/cli/describe.py` and `tests/unit/cli/test_describe.py` (scenarios of "Command description"). Proof: `uv run pytest tests/unit/cli/test_describe.py -q`; `uv run pyright src`.

## 3. Commands

- [ ] 3.1 Write `src/fenolite/cli/cmd_guide.py` and `tests/unit/cli/test_guide_cmd.py` (scenarios of "Guide command"). Proof: `uv run pytest tests/unit/cli/test_guide_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 3.2 Write `src/fenolite/cli/cmd_skill.py` and `tests/unit/cli/test_skill_cmd.py` (scenarios of "Skill command"), with a test that walks the folder before and after `--agents-md` and proves that only `AGENTS.md` and its backup changed. Proof: `uv run pytest tests/unit/cli/test_skill_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 3.3 Write `src/fenolite/cli/cmd_init.py` and the rest of `tests/unit/cli/test_init_cmd.py` (scenarios of "Init command"). Proof: `uv run pytest tests/unit/cli/test_init_cmd.py tests/consistency tests/unit/cli/test_hermetic_examples.py -q`.
- [ ] 3.4 Add `--brief` and `--command NAME` to `capabilities` and write `tests/unit/cli/test_capabilities_brief.py` (scenarios of "Brief capabilities" and "Command view of capabilities"). Write under this task the measured size of the brief result and of the default result. Proof: `uv run pytest tests/unit/cli/test_capabilities_brief.py tests/unit/cli/test_capabilities.py tests/unit/cli/test_capabilities_backends.py tests/unit/cli/test_capabilities_experimental.py tests/consistency -q`.

## 4. The start page and the block

- [ ] 4.1 Rewrite `src/fenolite/agent/skill/SKILL.md` ("Start page"): the rules, the new `fenolite-loop` block, what each step is for, when a step fails, how to read a page, "Small questions between the steps" with every command it names on `dev` that day plus `inspect`, the sentence that separates the guide from the Altium verification kit, and "Limits". Copy the block into `README.md`, and update `README.md` and `AGENTS.md` (the guide's path and `fenolite guide`). Update `tests/unit/test_agent_skill.py`: the order check, the hermetic prefix, the rules (scenarios "Block parses", "A stale flag fails", "First six lines need no tool", "Start page states the rules", "No command is lost"). Proof: `uv run pytest tests/unit/test_agent_skill.py tests/unit/agent tests/residue -q`; `grep -rn "agent/SKILL.md" README.md AGENTS.md tests src` prints only lines that hold `src/fenolite/agent/skill/SKILL.md`.
- [ ] 4.2 Write `tests/kicad/acceptance/test_skill_block.py` and remove `test_skill_block` from `tests/routing/test_acceptance_loop.py`; update the row of item 7 in `docs/release/v0.1.md` only if `tests/unit/test_release_record.py` requires the test to exist at the old place (then say there that the test moved). Proof: `uv run pytest tests/kicad/acceptance/test_skill_block.py -rA` on the local KiCad 10.0.6 and on KiCad 9.0.9; `uv run pytest tests/unit/test_release_record.py tests/unit/test_ci_workflow.py -q`.
- [ ] 4.3 Make the `wheel` CI job run `fenolite guide start --text` and `fenolite init blink --dry-run --json` from an empty folder with the installed wheel (scenario "Wheel carries the guide"), and update `tests/unit/test_ci_workflow.py`. Proof: `uv run pytest tests/unit/test_ci_workflow.py -q`; locally, `uv build` and then `uvx --from dist/*.whl fenolite guide start --text` from an empty folder exits 0. The `wheel` job of the pull request is read at the merge.

## 5. Documentation

- [ ] 5.1 Add to `docs/cli-contract.md`: the sections `guide`, `skill` and `init` with their result keys and exit codes; the brief view and the command view under "Discovery", with the fields of an argument and the key `targets.build`; `Result.text` under "Output", with what `--format concise` does beside it. Each statement is checked against a run of the command. Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue -q`.

## 6. Closing

- [ ] 6.1 Update the evidence labels: `H-K-GUIDE-STARTER` becomes `KICAD-VERIFIED (9.0.x, 10.0.x)` with the two runs, or records which line failed and why. Proof: `uv run pytest tests/unit/test_provenance.py tests/unit/test_hypotheses_register.py -q`.
- [ ] 6.2 Add to `CHANGELOG.md` under `## [Unreleased]`: "**The agent guide ships in the package**: `fenolite guide` prints it, `fenolite skill install` copies it to an agent's skill folder or adds a pointer to `AGENTS.md`, and `fenolite init` writes a starter project that passes `check` with the built-in catalog and router; `capabilities --brief` and `capabilities --command NAME` give a small first reply and a command's arguments as data. **`agent/SKILL.md` moved into `src/fenolite/agent/skill/`**, and its loop block now starts from an empty folder". Update the row of this change in `docs/roadmap.md`. Proof: `git diff --stat HEAD -- CHANGELOG.md docs/roadmap.md` lists both files.
- [ ] 6.3 Stop and report "ready for the long runs": `make check-fast`, the unit suite on Python 3.11 (`uv run --python 3.11 pytest tests/unit -q`), `uv run pytest tests/residue tests/corpus/test_manifest.py -q` after `git add -A`, `uv run python tools/residue/scan.py`, and `openspec validate --all --strict --no-interactive`. The full `make check` is run once by the coordinator on the rebased branch, not by the implementing agent. Proof: each command exits 0.
