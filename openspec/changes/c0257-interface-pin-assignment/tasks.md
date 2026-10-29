## 0. Entry check

- [ ] 0.1 Read `openspec list` and confirm, with the date and the base commit written under this task: c0248, c0249, c0251 and c0252 are archived; the names c0248 gave the device schema and its malformed-record code, and c0249 the lock schema, `--frozen` and its frozen-lock error; the interface kinds of c0252; whether `unused_no_connect` (c0247) can be deferred until after the solve; and the maintainer's answers to the open questions of `design.md` (whether this change is before or after 1.0). Proof: `npx -y @fission-ai/openspec validate c0257-interface-pin-assignment --strict`; `uv run pytest tests/unit/catalog tests/unit/dsl -k "device or lock or interface" -q`.

## 1. Device options

- [ ] 1.1 Add `options` to the device schema and loader of c0248, and the authored device `Example:MCU_QFN32` with an `I2C1` and a `UART2` option (scenario "A malformed option"). Proof: `uv run pytest tests/unit/catalog/test_options.py -q`.

## 2. DSL

- [ ] 2.1 Add `dsl/take.py` with `TakenInterface` and `Part.take`, the take keys, `option` and `pins` filters and the `DslError` refusals (scenario "Take and connect"). Proof: `uv run pytest tests/unit/dsl/test_take.py -q`.

## 3. Solve

- [ ] 3.1 Add `lens/pins.py`: fixed pins, locked-first, the canonical depth-first search with forward checking, `max_steps` (scenario "Second alternative when the first is taken"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k "second or search_limit" -q`.
- [ ] 3.2 The smallest conflicting set and `pins.unsatisfiable` (scenario "Three I2C takes on two alternatives"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k unsatisfiable -q`.
- [ ] 3.3 Measure the solve on an authored 64-pin device with eight takes and record the steps in `design.md` (risk "Exponential worst case"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k bench -q`.

## 4. Build, result and lock

- [ ] 4.1 Run the solve in the build after the script and before `unused_no_connect` is applied; add `result.pins` (scenario "Reviewed before writing"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k plan -q`.
- [ ] 4.2 Write and read the `[pins]` section of `<script stem>.lock`, `pins.lock-stale`, `pins.lock-dropped`, and the `--frozen` refusal (scenarios "A new take does not move a locked one", "Frozen refusal"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k "locked or frozen" -q`.
- [ ] 4.3 `PIN_ISSUE_CODES`, `explain.toml` tables and `docs/cli-contract.md` lines (scenario "Closed set"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k codes -q`; `uv run pytest tests/consistency -q`.

## 5. Example, docs and guide

- [ ] 5.1 `examples/pins/`: an authored design with an MCU, a sensor and a debug UART, built in the tests. Proof: `uv run pytest tests/unit/lens/test_pins.py -k example -q`; `make residue`.
- [ ] 5.2 Docs: `docs/pins.md` (new; options, `take`, the solve order, the lock, the codes), linked from `docs/dsl.md`. Proof: `uv run pytest tests/consistency -q`.
- [ ] 5.3 Agent guide: a tested line for `take` and for `pins.unsatisfiable` on the page `parts`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
- [ ] 6.2 Evidence: register `H-G-PIN-SOLVE-DETERMINISTIC` in `docs/hypotheses.md` with its measurement (three platforms, three seeds) and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
- [ ] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
