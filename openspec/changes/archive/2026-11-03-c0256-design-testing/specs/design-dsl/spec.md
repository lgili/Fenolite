## ADDED Requirements

### Requirement: Creation sites of script objects
While `run_design_script` runs, every `Part`, `Net` and `Interface` created SHALL record its creation site: the script-relative path and line of the deepest frame of the stack whose file lies in the script folder. Outside `run_design_script` nothing MUST be recorded, and an object created only by frames outside the script folder MUST have no site.

#### Scenario: Helpers report the line in the script folder
- **GIVEN** a script whose line 20 calls a function of a sibling `parts.py` that creates a part at its line 6
- **WHEN** `uv run pytest tests/unit/dsl/test_sites.py -k sibling` runs the script
- **THEN** the part's site is `parts.py:line:6`, and a part created at the Python prompt has no site

### Requirement: Unattached objects in a build
After the script returns, the build SHALL report one `build.unattached` warning, joining the `build` envelope as "Build issue codes" allows, for each object with a site, still alive, that never reached the design: a `Part` not in `design.parts`, a `Net` not in `design.nets`, an `Interface` not in `design.interfaces`. `where` MUST be its site; the message MUST name the kind and the ref or name; the warnings MUST be sorted by `where`, then name.

#### Scenario: A part never added
- **GIVEN** a script that creates `R5 = Part("R5", ...)` at line 14 and never adds it, and a net `SPARE` created at line 15 and never connected
- **WHEN** `uv run pytest tests/unit/lens/test_unattached.py -k lost` builds it with `--dry-run`
- **THEN** the exit code is 0 and the issues hold two `build.unattached` warnings, `design.py:line:14` naming `R5` and then `design.py:line:15` naming `SPARE`

#### Scenario: A complete script is quiet
- **WHEN** `fenolite build src/fenolite/dsl/_minimal.py --out out --dry-run --json` runs
- **THEN** the issues hold no `build.unattached`

### Requirement: Unattached code documented
`src/fenolite/cli/data/explain.toml` SHALL hold a table for `build.unattached` whose hint says to add, connect or delete the object, and `docs/cli-contract.md` SHALL list the code.

| code | severity | when |
|---|---|---|
| `build.unattached` | warning | a `Part`, `Net` or `Interface` created while the script ran never reached the design |

#### Scenario: Explained
- **WHEN** `fenolite explain build.unattached --json` runs
- **THEN** the exit code is 0 and the reply names the code with its severity `warning`
