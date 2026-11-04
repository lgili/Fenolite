## 0. Entry check

- [x] 0.1 Read `openspec/specs/cli-contract/spec.md`, `docs/cli-contract.md` and the open questions of the
  design, and record the maintainer's answers under this task. Proof: `openspec validate c0216-contract-v1 --strict`.
  - 2026-10-27: the maintainer accepted every recommended answer (roadmap, "Open decisions", row 49): `fenolite.dsl`
    and `fenolite.api` are frozen with the CLI (the surface's `library` section), envelopes say `v1` from the release
    of `1.0.0`, and hidden commands are out of the contract.

## 1. The surface

- [x] 1.1 `fenolite.cli.surface`: `Surface`, `cli_surface` and `to_json`, and `tools/gen_cli_surface.py` with
  `--check`, with the `library` section of `fenolite.dsl` and `fenolite.api`; commit `docs/cli-surface.json`
  (scenarios "Surface drift detected", "Hidden command left out").
  Proof: `uv run pytest tests/unit/cli/test_cli_surface.py -q`; `uv run python tools/gen_cli_surface.py --check`.
- [x] 1.2 `surface_changes` and its kinds, experimental and deprecated items included (scenarios "A removed
  option is breaking", "An experimental option may change", "A library parameter removed is breaking", "An
  addition is not breaking"). Proof:
  `uv run pytest tests/unit/cli/test_cli_surface.py -q`.
- [x] 1.3 `tools/gen_cli_surface.py --review`: the list for the pre-freeze review (unused options, hidden
  commands, issue codes no test raises), written to the maintainer's review file outside the repository.
  Proof: `uv run python tools/gen_cli_surface.py --review --out /tmp/review.md` writes the list.
- [x] 1.4 **Maintainer.** Review the list and decide, per item, keep, rename (the old name deprecated) or drop;
  record the answers under this task. Proof: the record under this task.
- [x] 1.5 Apply the decisions of 1.4, each rename with its deprecation. Proof: `uv run pytest tests/unit/cli
  tests/consistency -q`.
  Done 2026-11-04: the 1.4 record keeps every name (no rename, no drop), so no rename or deprecation
  applies. Proof on 2cf0c378: 3711 passed, 43 skipped.

## 2. Envelope, error and deprecation

- [x] 2.1 `CONTRACT_VERSION` in `cli/api.py`, `Command.schema` from it, and `schemas/fenolite.envelope.v1.json`
  and `schemas/fenolite.error.v1.json` from `tools/gen_schemas.py`; the `v0` files unchanged (scenarios of
  "Envelope"). Proof: `uv run pytest tests/consistency -q`; `uv run python tools/gen_schemas.py --check`.
- [x] 2.2 `Command.deprecated`, `deprecate()`, `cli.deprecated` in `fenolite explain`, and `result.contract`
  and `result.deprecated` of `capabilities` (scenarios of "Deprecated options and commands"). Proof:
  `uv run pytest tests/unit/cli/test_cli_surface.py tests/unit/cli/test_explain_cmd.py tests/unit/cli/test_capabilities.py -q`.
- [x] 2.3 `docs/cli-contract.md`, "Stability"; the agent guide names `result.contract` (run
  `uv run python tools/gen_agent_guide.py`). Proof: `uv run pytest tests/unit/agent/test_pages.py tests/consistency -q`.

## 3. Closing

- [ ] 3.1 Run the tests and the residue scan. Proof: `make check-fast`.
- [x] 3.2 Update the evidence labels: no label changes; the change claims nothing of a format. Proof:
  `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [x] 3.3 Update `CHANGELOG.md` under `## [Unreleased]`. Proof: `uv run pytest tests/unit/test_release_record.py -q`.

## Current-source selective preparation

- [x] 0.2 Review the current-source selective-port packet in c0216 before runtime changes; preserve
  current model0/CLI0 and every later field/validation. Historical bf6532a4 receipts are source material,
  not current test/freeze proof. Final inventories wait for the actual final c0348 source.

Current-source proof is recorded in current-source-proof.md. Human review1.4 remains pending;
this preparation does not activate CLIv1 or freeze a historical schema/model receipt.

## Actual current-source maintainer review, 2026-11-03

The user approved the original current-source57-command/713-option/185-export
packet, KEEP without renames/drops. The separately disclosed source613 delta
Design.kicad_project(path, *, sha256, preserve_minimums=False) was then
explicitly approved with the reply "Aprovo também esse método". Its False
default and import's True preservation mode were disclosed in the question.
The source-bound record is current-review-approved.json; the complete reviewed
row list is retained externally by its recorded hashes. CLI remainsv0 until
package1.0 as already decided.

The isolated c0218 activation additionally introduces migrate as command58.
It was NOT already one of the57; its explicit approval is a separate pending
complement, not inferred from the method or original packet approval. Root
exact-head validation and the later addition's review remain separate.

## Actual migrate supplement, 2026-11-03

The user's subsequent exact reply "Aprovo incluir migrate" approves the
explicitly disclosed58th visible command: migrate DIR for canonical schema1.0
folders, reviewed dry-run/plan/confirm, without executing CAD or design scripts.
This supersedes only the pending migrate complement above. Its actual current
descriptor and combined-surface digest are recorded in current-review-approved.json.
All original57 names and the separately approved native-project method remain
kept; no rename/drop or CLIv1 activation was requested. Root validation remains
separate from the human decisions. The surface's '*' row is global arguments,
not an additional command; visible counts exclude it.

- [x] 1.5b Make surface metadata for zero-or-more positional arguments independent of argparse's interpreter-specific internal required flag. Preserve actual parsing, required options and one-or-more positional requirements; do not regenerate/relax approved snapshots. Proof: authored controls and complete surface tests on Python3.11 and the current interpreter, plus existing registry snapshot match.

CI41611925152 Python3.11 job125835695056 exposed two required-added false positives (blocks target/family targets). Direct Python3.11 parsing accepts the omitted zero-or-more arguments despite action.required=True. Other interpreter jobs are separate evidence; no blanket compatibility success is inferred.

Task1.5b proof: authored forced-internal-flag RED reproduced the drift (1failed/2passed). After metadata-only correction the complete55 surface tests pass on Python3.11.13 and Python3.13.7, including the unchanged approved registry snapshot; required options and plus-arity positionals remain required. Focused pyright0, Ruff/format pass. No parser, public name/type/default, snapshot or CLI contract version changed.
