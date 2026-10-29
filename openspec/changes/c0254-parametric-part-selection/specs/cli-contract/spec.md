## ADDED Requirements

### Requirement: Pick command
`fenolite pick PATH [--candidates COMPONENT [--limit N]] [--update COMPONENT]... [--update-all] [--propose QUERY (--from FILE | --supplier NAME [--allow-offsite])]` SHALL be registered by `src/fenolite/cli/cmd_pick.py` with `mutates=True`; `PATH` names a design script or its folder. No subprocess MUST run, and without `--supplier` no network connection MUST be opened.

#### Scenario: Example is hermetic
- **GIVEN** `subprocess.run`, `subprocess.Popen` and `socket.socket` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `pick` with its `example_args` `(EXAMPLE_PICKS, "--json")`
- **THEN** the exit code is 0

### Requirement: Pick listing
Without `--update`, `--update-all` or `--propose`, `pick` SHALL be read-only: `result.picks` lists every query part with `path`, `query`, `device`, `row`, `catalog` and `state` (`ok`, `new`, `stale`, `row-changed`, `row-missing` or `no-match`), and an error state exits 5. `--candidates` MUST list the ranked candidates of one part, at most `--limit` (default 20), and each excluded row with its first failed constraint.

#### Scenario: A stale pick is listed
- **GIVEN** `examples/picks` whose lock holds `C_in` at 25 V and whose script now asks 50 V
- **WHEN** `fenolite pick examples/picks --json` runs
- **THEN** the exit code is 5 and the entry of `C_in` has the state `stale`

### Requirement: Pick updates
`--update` and `--update-all` SHALL re-resolve the named lock entries against the current catalog and plan one write of the design lock showing the old and new device of each path, under the mutation protocol. An unknown component path MUST be `FEN-2001`. The envelope MUST carry `pick.EVIDENCE` combined with the evidence of each picked row.

#### Scenario: Update a stale pick
- **GIVEN** the same `examples/picks`
- **WHEN** `fenolite pick examples/picks --update C_in --dry-run --json` runs, then `--confirm --plan <plan_id>`
- **THEN** the dry run plans one write of the design lock showing the old and the new device, the receipt lists the design lock with its SHA-256, and a following `fenolite build --dry-run` holds no `pick.stale`
