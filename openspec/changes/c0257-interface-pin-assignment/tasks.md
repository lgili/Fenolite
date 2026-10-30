## 0. Entry check

- [x] 0.1 Read `openspec list` and confirm, with the date and the base commit written under this task: c0248, c0249, c0251 and c0252 are archived; the names c0248 gave the device schema and its malformed-record code, and c0249 the lock schema, `--frozen` and its frozen-lock error; the interface kinds of c0252; whether `unused_no_connect` (c0247) can be deferred until after the solve; and the maintainer's answers to the open questions of `design.md` (whether this change is before or after 1.0). Proof: `npx -y @fission-ai/openspec validate c0257-interface-pin-assignment --strict`; `uv run pytest tests/unit/catalog tests/unit/dsl -k "device or lock or interface" -q`.
  - 2026-10-29, base b7dce51c (`cac/c0257-interface-pin-assignment` on c0252): c0248, c0249, c0251 and c0252 are merged in `circuits-as-code` but not archived. Names: the device schema is `fenolite.device.v0` with the malformed-record code `FEN-3004` (`DeviceFormatError`) and `options` reserved for c0257 (`FEN-3002` until now); the lock schema is `fenolite.lock.v0` with the reserved `[pins]` section (`LockSection`), `--frozen` and its error `FEN-7004` (`LockFrozenError`, one `lock.changed` per change); the interface kinds of c0252 are `KIND_MEMBERS` (`i2c`, `spi`, `uart`, `usb2`, `diff_pair` plus `power`, `ground`, `logic`); `unused_no_connect` is recorded at the call and applied by the build after `to_model`, so it runs after the solve. Open questions: the recommended answers are taken (`design.md`). Proofs: `openspec validate --strict` is valid; the catalog/dsl selection passes (238 tests).

## 1. Device options

- [x] 1.1 Add `options` to the device schema and loader of c0248, and the authored device `Example:MCU_QFN32` with an `I2C1` and a `UART2` option (scenario "A malformed option"). Proof: `uv run pytest tests/unit/catalog/test_options.py -q`.
  - 2026-10-29: done, proof passed. `DeviceOption` in `model.library`, `[[options]]` read and written canonically (kinds `i2c`, `spi`, `uart`, `usb2`, `diff_pair`, `pin`); the device lives in `examples/pins/devices/example_mcu_qfn32.toml` on the catalog's LQFP32 land (the QFN32 land's 0.5 mm pitch breaks the default 0.2 mm clearance).

## 2. DSL

- [x] 2.1 Add `dsl/take.py` with `TakenInterface` and `Part.take`, the take keys, `option` and `pins` filters and the `DslError` refusals (scenario "Take and connect"). Proof: `uv run pytest tests/unit/dsl/test_take.py -q`.
  - 2026-10-29: done, proof passed. `TakenInterface` is a `PortHandle` of the part (see `design.md`, implementation notes); `to_model` solves unapplied takes against an empty lock.

## 3. Solve

- [x] 3.1 Add `lens/pins.py`: fixed pins, locked-first, the canonical depth-first search with forward checking, `max_steps` (scenario "Second alternative when the first is taken"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k "second or search_limit" -q`.
  - 2026-10-29: done, proof passed (the scenario builds under seeds 1, 2, 3).
- [x] 3.2 The smallest conflicting set and `pins.unsatisfiable` (scenario "Three I2C takes on two alternatives"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k unsatisfiable -q`.
  - 2026-10-29: done, proof passed; the scenario uses `option="I2C1"` on the example MCU, and a pure-solve test checks that an unrelated take is left out of the set.
- [x] 3.3 Measure the solve on an authored 64-pin device with eight takes and record the steps in `design.md` (risk "Exponential worst case"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k bench -q`.
  - 2026-10-29: done, proof passed: 13 candidate trials, recorded in `design.md`.

## 4. Build, result and lock

- [x] 4.1 Run the solve in the build after the script and before `unused_no_connect` is applied; add `result.pins` (scenario "Reviewed before writing"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k plan -q`.
  - 2026-10-29: done, proof passed. The solve runs in `cli._lock.plan_lock` (through `cli._pins`) before `to_model`; `result.pins` is in every build reply (`[]` without takes), also for `--target altium`.
- [x] 4.2 Write and read the `[pins]` section of `<script stem>.lock`, `pins.lock-stale`, `pins.lock-dropped`, and the `--frozen` refusal (scenarios "A new take does not move a locked one", "Frozen refusal"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k "locked or frozen" -q`.
  - 2026-10-29: done, proof passed. The frozen scenario hand-connects `PB7`, the pin the example's lock holds (the example's first take gets `PB6/PB7`).
- [x] 4.3 `PIN_ISSUE_CODES`, `explain.toml` tables and `docs/cli-contract.md` lines (scenario "Closed set"). Proof: `uv run pytest tests/unit/lens/test_pins.py -k codes -q`; `uv run pytest tests/consistency -q`.
  - 2026-10-29: done, proofs passed. The literal scan skips `checks/readiness.py`, whose `"pins.unconnected"` names a readiness check, not a build finding.

## 5. Example, docs and guide

- [x] 5.1 `examples/pins/`: an authored design with an MCU, a sensor and a debug UART, built in the tests. Proof: `uv run pytest tests/unit/lens/test_pins.py -k example -q`; `make residue`.
  - 2026-10-29: done, proofs passed (`make residue`: 0 hits). `design.lock` is committed, as `sensor_rails/good.lock` is (example builds in the suite write it beside the script); the build tests copy the example without it, so the scenario "Reviewed before writing" plans its write.
- [x] 5.2 Docs: `docs/pins.md` (new; options, `take`, the solve order, the lock, the codes), linked from `docs/dsl.md`. Proof: `uv run pytest tests/consistency -q`.
  - 2026-10-29: done, proof passed; also `docs/cli-contract.md`, `docs/devices.md` and `examples/README.md`.
- [x] 5.3 Agent guide: a tested line for `take` and for `pins.unsatisfiable` on the page `parts`; then `uv run python tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.
  - 2026-10-29: done, proofs passed. One line on `parts` names `take`, `result.pins` and `pins.unsatisfiable` (the page was trimmed to stay within 250 lines and 12000 bytes); no public DSL name was added, so the generated pages are unchanged.

## 6. Closing

- [ ] 6.1 Run `make check-fast`, then the required CI jobs on the pushed head of the branch. Proof: `make check-fast`, and the required jobs green on the exact commit.
  - 2026-10-30: `make check-fast PYTEST_WORKERS=2` passes (16224 passed, 48 skipped). Left open: CI runs with the batch.
- [x] 6.2 Evidence: register `H-G-PIN-SOLVE-DETERMINISTIC` in `docs/hypotheses.md` with its measurement (three platforms, three seeds) and regenerate the evidence matrix. Proof: `uv run pytest tests/unit/test_hypotheses_register.py -q`; `uv run python tools/gen_evidence_matrix.py --check`.
  - 2026-10-29: done, proofs passed. The row is updated in place (status pending until the three-platform unit jobs of the batch's CI); the matrix needed no change.
- [x] 6.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]`. This waits for `0.7.0.dev0`: on `0.6.0` the v0.6 guard requires `[Unreleased]` empty. Proof: `uv run pytest tests/unit -k changelog -q`.
  - 2026-10-29: done (the coordinator allowed `[Unreleased]` on this branch), proof passed.
