## 0. Entry check

- [x] 0.1 Read `openspec/specs/cli-contract/spec.md`, `docs/cli-contract.md` and the open questions of the
  design, and record the maintainer's answers under this task. Proof: `openspec validate c0216-contract-v1 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): `fenolite.dsl`
    and `fenolite.api` are frozen with the CLI (the surface's `library` section), envelopes say `v1` from the release
    of `1.0.0`, and hidden commands are out of the contract.
  - 2026-10-29: re-read against the living spec after the archives of 2026-10-28: "Envelope" is unchanged there, so
    the MODIFIED block stands; the ADDED text was split into six requirements to pass `--strict` (no requirement over
    500 characters), the scenario of a removed option now names `inspect --streams` (`--fields` is a global option,
    listed under `"*"`), and the measured counts are those of 2026-10-29 (49 visible commands, 24 `FEN-` codes, 707
    issue codes in 70 tables).

## 1. The surface

- [x] 1.1 `fenolite.cli.surface`: `Surface`, `cli_surface` and `to_json`, and `tools/gen_cli_surface.py` with
  `--check`, with the `library` section of `fenolite.dsl` and `fenolite.api`; commit `docs/cli-surface.json`
  (scenarios "Surface drift detected", "Hidden command left out", "Library names listed", "The Altium writer
  options are experimental").
  Proof: `uv run pytest tests/unit/cli/test_cli_surface.py -q`; `uv run python tools/gen_cli_surface.py --check`.
  - 2026-10-29: the same file is generated under Python 3.11, 3.12 and 3.13, with and without the extras.
- [x] 1.2 `surface_changes` and its kinds, experimental and deprecated items included (scenarios "A removed
  option is breaking", "An experimental option may change", "A library parameter removed is breaking", "An
  addition is not breaking"). Proof:
  `uv run pytest tests/unit/cli/test_cli_surface.py -q`.
- [x] 1.3 `tools/gen_cli_surface.py --review`: the list for the pre-freeze review (unused options, hidden
  commands, issue codes no test raises), written to the maintainer's review file outside the repository.
  Proof: `uv run python tools/gen_cli_surface.py --review --out /tmp/review.md` writes the list.
  - 2026-10-29: the list of the dev of that day holds no option named nowhere, 13 options without a test, 11 flags
    with several shapes across commands, 6 `--altium-*` options outside the experimental feature, the hidden
    command `_echo` and 54 issue codes no test names; it went to the maintainer for 1.4.
- [ ] 1.4 **Maintainer.** Review the list and decide, per item, keep, rename (the old name deprecated) or drop;
  record the answers under this task. Proof: the record under this task.
- [ ] 1.5 Apply the decisions of 1.4, each rename with its deprecation. Proof: `uv run pytest tests/unit/cli
  tests/consistency -q`.

## 2. Envelope, error and deprecation

- [ ] 2.1 `CONTRACT_VERSION` in `cli/api.py`, `Command.schema` from it, and `schemas/fenolite.envelope.v1.json`
  and `schemas/fenolite.error.v1.json` from `tools/gen_schemas.py`; the `v0` files unchanged (scenarios of
  "Envelope"). Proof: `uv run pytest tests/consistency -q`; `uv run python tools/gen_schemas.py --check`.
- [ ] 2.2 `Command.deprecated`, `deprecate()`, `cli.deprecated` in `fenolite explain`, and `result.contract`
  and `result.deprecated` of `capabilities` (scenarios of "Deprecated options and commands"). Proof:
  `uv run pytest tests/unit/cli/test_cli_surface.py tests/unit/cli/test_explain_cmd.py tests/unit/cli/test_capabilities.py -q`.
- [ ] 2.3 `docs/cli-contract.md`, "Stability"; the agent guide names `result.contract` (run
  `uv run python tools/gen_agent_guide.py`). Proof: `uv run pytest tests/unit/agent/test_pages.py tests/consistency -q`.

## 3. Closing

- [ ] 3.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [ ] 3.2 Update the evidence labels: no label changes; the change claims nothing of a format. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 3.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/test_release_record.py -q`.
