## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living `design-model`, `design-dsl`, `placement`, `verification-loop`, `cli-contract`, `layout-lens` and `altium-pcb-writer` specs. Write under this task, with the date:
  - whether `0.3.0` is released and c0121 is archived (its rule for the stored board of an Altium build and its kind `body` are named here);
  - whether c0099 is on `dev`: `ComponentBody` has `z_min`, `z_max` and `projection_unknown`, and "Component bodies" holds the sentence on the outward height of a part. **If it is not, stop: this change is not started before c0099** (the maintainer's decision 3 of 2026-10-07);
  - whether c0113 and c0103 are on `dev` ("Placement rules stage", "Placement rules judged", "Place command" with `result.rules`, "Placement legality in a build" with `result.placement.rules`, "Rule areas in the DSL", `Keepout.name`). Without c0113, tasks 4 to 6 wait; tasks 1 to 3 go on;
  - whether a sentence of those living requirements contradicts an ADDED requirement of this change (then turn that ADDED requirement into a MODIFIED delta regenerated from the living text, and say so in `design.md`, Decision 11);
  - whether c0096 is on `dev` and its body checker reads a part's height (then it calls `outward_height`; write the file and line);
  - whether any other change has given a component, a part or a footprint a height field since `9aba2dff` (then stop and report: one source).

  Proof: `openspec validate c0140-part-height-rules --strict --no-interactive` passes after any regeneration; `grep -n "z_max" src/fenolite/model/board.py` prints the field.
  - 2026-10-07, at `origin/dev` `9aba2dff` (proposal written, nothing built): c0099, c0113, c0103 and c0096 are not on `dev`; c0121 is open on `dev`; `0.3.0` is not released; `ComponentBody` has no signed bounds; no source file under `src/fenolite/dsl` names `ComponentBody`.

## 1. One reader of a part's height

- [ ] 1.1 Add `outward_height` to `src/fenolite/model/board.py` and write `tests/unit/model/test_outward_height.py` (scenarios "Largest known body", "No known height"; "One reader" is completed by task 4.1). Add the paragraph to `docs/design-model.md` under "Component bodies": the one function, and that no other field holds a part's height. Proof: `uv run pytest tests/unit/model/test_outward_height.py tests/unit/test_import_graph.py`; `uv run pyright src`.

## 2. Height limits in the model

- [ ] 2.1 Add `HeightLimit` and `RuleSet.heights` to `src/fenolite/model/rules.py` with their checks; extend `tests/unit/model/test_rules.py` (scenarios "Limits round trip", "Refused values"). Proof: `uv run pytest tests/unit/model`; `uv run pyright src`.
- [ ] 2.2 Regenerate `schemas/fenolite.model.v0/rules.json`; load a file of an older build and write it again (scenario "Files of an older build"); describe the field in `docs/design-model.md` with the sentence that **0.2.x and 0.3.0 cannot read a `rules.json` that carries `heights`** (scenario "Compatibility is documented"). Proof: `uv run python tools/gen_schemas.py --check`; `uv run pytest tests/unit/model -k "older or documented"`.

## 3. The script and the build

- [ ] 3.1 Add `Part(…, height=None)`, `Part.height`, `dsl.heights` with its re-export, `Design.height_limit` and the limits in `to_model` (`src/fenolite/dsl/part.py`, `design.py`, `convert.py`, `__init__.py`); write `tests/unit/dsl/test_part_height.py` (scenarios "A height recorded", "Refused calls", "Unchanged designs"). Proof: `uv run pytest tests/unit/dsl tests/unit/test_import_graph.py`; `uv run pyright src`.
- [ ] 3.2 `lens.build.build_design(…, heights=None)`: one body on the placed footprint of each named path; `lens.preserve.merge_layout` keeps the built footprint's `bodies` on the footprint it keeps; `cmd_build` hands `dsl.heights(design)` over. Write `tests/unit/lens/test_build_bodies.py` (scenario "The body is stored and survives a rebuild", and that every KiCad file of the build has the bytes of a build without `height=`, for targets 9 and 10). Proof: `uv run pytest tests/unit/lens/test_build_bodies.py tests/unit/lens tests/unit/test_import_graph.py`.
- [ ] 3.3 Check that no byte moved for a design that states no height and no limit: the blink and the routed blink built for targets 9 and 10 and for the Altium target with a fixed seed and timestamp give, file by file and `.fenolite/` included, the SHA-256 recorded from the commit before task 1.1. Proof: `uv run pytest tests/unit/lens -k unused_keys`.

## 4. Height limits judged

- [ ] 4.1 With c0113 on `dev`: add `heights_of` and `judge_heights` to `src/fenolite/checks/placement.py`, `heights` to what `rules_of` gives, the codes `placement.too-tall` and `placement.height-unknown` to `checks/codes.py`, and their two tables to `src/fenolite/cli/data/explain.toml` (`meaning` and `fix` of at most 400 characters, `see = "check"`); write `tests/unit/checks/test_height_limits.py` (the five scenarios of "Height limits judged") and complete "One reader". Proof: `uv run pytest tests/unit/checks/test_height_limits.py tests/unit/checks/test_codes.py tests/unit/model/test_outward_height.py tests/unit/cli/test_explain_cmd.py tests/unit/test_import_graph.py`; `uv run pyright src`.

## 5. The stage, `place` and `build`

- [ ] 5.1 The stage `placement.rules` runs `judge_heights` on a built project with a limit, on KiCad projects and on Altium documents, and calls `placed_extents` only then (scenarios "A part above a limit fails the check", "No limit, no extents", "A limit on a built Altium project"). Proof: `uv run pytest tests/unit/checks/test_placement_stage.py -k height`; `uv run pytest tests/unit/cli/test_check_altium.py -k height`; `uv run pytest tests/unit/cli/test_check_readonly.py`.
- [ ] 5.2 `cmd_place`: the height report after the moves and `result.rules.height` (scenarios "A move under a low area", "No limit, same reply"). Proof: `uv run pytest tests/unit/cli/test_place_cmd.py tests/unit/cli/test_hermetic_examples.py`.
- [ ] 5.3 `cmd_build.placement_guard`: `judge_heights` as warnings and `result.placement.rules.height`; the Altium target counts the limits in the info of kind `placement-rule` and stores no unwritten body (scenarios "Limits reported as warnings", "An Altium build stores and announces"). Check that `rulemap.TABLE` still has one row per `RuleKind` and none for a height limit. Proof: `uv run pytest tests/unit/cli/test_build_placement_guard.py -k height`; `uv run pytest tests/unit/cli/test_build_altium.py -k height`; `uv run pytest tests/unit/backends/altium -k "rulemap or table"`.

## 6. Documentation

- [ ] 6.1 Update `docs/placement.md` (height limits: the one source of height, the face rule, who is judged, unknown heights, what the volume analysis of c0099 covers instead), `docs/dsl.md` (`Part(height=…)`, `height_limit`, that the body has no outline), `docs/cli-contract.md` (the two codes, the family `height` in `summary.rules`, `result.rules` and `result.placement.rules`) and `docs/altium.md` (a script height is not written into an Altium document, so a limit on the Altium target is judged only for parts whose document holds a body; the rule kind `Height` is not written). Proof: `uv run pytest tests/consistency tests/unit/test_repo_layout.py tests/residue`.
- [ ] 6.2 If c0080 is on `dev`, add one tested line each for `Part(height=…)` and `height_limit` to its guide pages; otherwise write under this task that the lines are owed to c0080. Proof: `uv run pytest tests/unit/agent -q` when c0080 is on `dev`; else `git log --oneline -1 -- openspec/changes/c0080-agent-authoring-guide` prints nothing.

## 7. Closing

- [ ] 7.1 Stop and report "ready for the long runs"; an agent in a worktree does not run the full `make check`. Proof: `make check-fast PYTEST_WORKERS=4` exits 0; `uv run --isolated --python 3.11 --extra dev pytest tests/unit -q -n 4 -p no:cacheprovider` exits 0; after `git add -A`, `uv run pytest tests/residue tests/corpus/test_manifest.py` and `uv run python tools/residue/scan.py` exit 0 (this change adds no file under `tests/data/`; the manifest test proves it); `openspec validate c0140-part-height-rules --strict --no-interactive` and `openspec validate --all --strict --no-interactive` pass; `python3 tools/dco_check.py <base>..HEAD` prints nothing. The full `make check` is the coordinator's, once, on the rebased branch at the merge.
- [ ] 7.2 Add to `CHANGELOG.md` under Unreleased: "A part can state its height (`Part(height=…)`): it becomes a body of its footprint, kept in `.fenolite/`, and `design.height_limit(area, max=…)` limits the parts under a named rule area. `check` (stage `placement.rules`), `place` and `build` report `placement.too-tall` and `placement.height-unknown`. A part's height has one source, its bodies, read by `outward_height`. A `rules.json` with `heights` cannot be read by 0.2.x or 0.3.0." Add the row c0140 to `docs/roadmap.md` (section of v0.4) and to `openspec/README.md` where changes are listed. Proof: `git diff --stat CHANGELOG.md docs/roadmap.md` lists both files.
