## 0. Entry check

- [ ] 0.1 Read `openspec list`, this change's proposal and design, and the living requirements it builds on: "No-connect marks in the DSL" (modified here), "No-connect marks in a build", "Placement rules in the DSL", "Attaching parts to interfaces" and "Build issue codes" in `design-dsl`. Write here, with the date and the base commit: whether another open change holds a delta of "No-connect marks in the DSL" (if one was archived, regenerate the MODIFIED block from the living text); whether c0248 has fixed the names of device ends and of the `must_connect` flag (Decisions 1 and 6 follow them); whether the pinned blink digests of `tests/unit/lens/test_build_bytes_pinned.py` moved since `0.6.0`; and the maintainer's answers to open questions 1 to 4 of `design.md`. Proof: `openspec validate c0247-connection-helpers --strict`; `uv run pytest tests/unit/dsl/test_no_connect.py tests/unit/dsl/test_placement_rules.py -q`.

## 1. DSL

- [ ] 1.1 Add `Part.a`, `Part.b` and `Part.two_terminal`, with the end lookup that c0248 will extend (Decision 1; scenario "Ends are pins one and two"). Proof: `uv run pytest tests/unit/dsl/test_wiring.py -k ends -q`.
- [ ] 1.2 Add `src/fenolite/dsl/wiring.py` with `series` (Decision 2; scenarios "Fuse and diode in series", "A part turned around and a named joint", "Refused chains"). Proof: `uv run pytest tests/unit/dsl/test_wiring.py -k series -q`.
- [ ] 1.3 Add `decouple`, lowering its rules through `Design.near` (Decision 3; scenarios "Decoupling rule recorded", "Without a rule", "Refused decoupling"). Proof: `uv run pytest tests/unit/dsl/test_wiring.py -k decouple tests/unit/dsl/test_placement_rules.py -q`.
- [ ] 1.4 Add `pull_up` and `pull_down` (Decision 4; scenarios "I2C pull-ups", "A pull-down on one net", "Refused pull resistors"). Proof: `uv run pytest tests/unit/dsl/test_wiring.py -k pull -q`.
- [ ] 1.5 Add `Part.unused_no_connect`, `Part.unused_request`, and the side channels `convert.unused_marks` and `convert.two_terminal`; update the docstring rule of `no_connect` (Decision 5; scenarios "Request recorded, model unchanged", "Called twice", and the modified "No-connect marks in the DSL"). Proof: `uv run pytest tests/unit/dsl/test_wiring.py -k unused tests/unit/dsl/test_no_connect.py -q`.
- [ ] 1.6 Re-export the four helpers from `fenolite.dsl` (scenario "Re-exports"). Proof: `uv run pytest tests/unit/test_import_graph.py tests/unit/dsl/test_wiring.py -k reexport -q`.

## 2. Build

- [ ] 2.1 `lens/build.py`: take `unused` and `two_terminal`, check two-pin parts and resolve unused pins after the explicit marks, with `must_connect_pins(component, device)` reading `power_in` (Decisions 6 and 7; scenarios "A three-pin part used through its ends", "Kept pins stay open without a mark", "An open supply pin is not marked", "A kept supply pin is not reported"); add both codes to `BUILD_ISSUE_CODES`, `explain.toml` and `docs/cli-contract.md` (scenario "New code in the closed set"). Proof: `uv run pytest tests/unit/lens/test_build_unused_pins.py tests/unit/lens/test_build_issues.py tests/unit/lens/test_build_no_connect.py tests/consistency -q`.
- [ ] 2.2 Pass the side channels from `cli/cmd_build.py`, `cli/cmd_silk.py`, `exports/impedance.py` and the API and MCP build paths. Proof: `uv run pytest tests/unit/cli -k build -q`.
- [ ] 2.3 `lens/altium.py`: the same resolution and codes, so both targets mark the same pins. Proof: `uv run pytest tests/unit/lens/test_altium_no_connect_golden.py tests/unit/lens/test_build_unused_pins.py -k altium -q`.

## 3. Example, documentation and agent guide

- [ ] 3.1 `examples/blink_2layer/design.py`: replace the explicit marks with `u1.unused_no_connect()` and the LED wiring with `series(led_drv, r1, led_a, (d1.b, d1.a), gnd)`; no pinned digest may move (scenario "The blink keeps its pinned bytes"). Proof: `uv run pytest tests/unit/lens/test_build_bytes_pinned.py -q`; CI's KiCad job runs ERC on it (`KICAD-VERIFIED`).
- [ ] 3.2 `docs/dsl.md`: a section "Connection helpers" (ends, `series`, `decouple`, `pull_up`/`pull_down`, generated net names, `unused_no_connect`, must-connect pins, the two codes), and the section "No-connect marks" updated. Proof: `uv run pytest tests/consistency -q`.
- [ ] 3.3 Agent guide: in `src/fenolite/agent/skill/references/design-script.md`, a `fenolite-design` block that uses `series`, `decouple`, `pull_up`, `pull_down`, `part.a`/`part.b` and `unused_no_connect`, and a line on the two build codes; then regenerate the reference page. Proof: `uv run python tools/gen_agent_guide.py`; `uv run pytest tests/unit/agent/test_pages.py -q`.

## 4. Closing

- [ ] 4.1 Run the fast checks and the focused tests of every task above. Proof: `make check-fast`; `uv run pytest tests/unit/dsl tests/unit/lens/test_build_unused_pins.py tests/unit/agent/test_pages.py -q`.
- [ ] 4.2 Evidence labels: record in `design.md`, "Evidence level per behaviour", the CI run whose KiCad job built the blink of task 3.1 (`KICAD-VERIFIED`). Proof: the required CI jobs pass on the exact commit (`gh run view <id>`).
- [ ] 4.3 `CHANGELOG.md`: an entry under `## [Unreleased]` ("Added: connection helpers `series`, `decouple`, `pull_up`, `pull_down`, named ends `a`/`b`, and `unused_no_connect()` with the build codes `build.not-two-terminal` and `build.must-connect-unconnected`"). This waits until `dev` has opened `0.7.0.dev0`, because the guard of v0.6 requires `[Unreleased]` to be empty. Proof: `uv run pytest tests/unit/test_release_record_v06.py tests/unit/test_release_tool.py -q` (or the changelog guards in force at that time).
- [ ] 4.4 Publish the batch branch (with c0246) and confirm CI green on its exact commit (unit and KiCad jobs) before archiving. Proof: `gh run list --branch <branch> --limit 1` shows success for the commit; `npx -y @fission-ai/openspec validate c0247-connection-helpers --strict`.
