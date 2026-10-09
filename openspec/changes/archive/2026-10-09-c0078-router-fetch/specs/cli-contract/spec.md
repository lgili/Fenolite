## ADDED Requirements

### Requirement: Deferred writes
`fenolite.cli.api.PlannedWrite` SHALL have the fields `source: Callable[[], bytes] | None = None`, `size: int | None = None` and `sha256: str | None = None`, so that a command can plan a file whose bytes are costly to obtain without obtaining them.
- A write with a `source` MUST have empty `data` and both `size` and `sha256` set; a `PlannedWrite` that breaks this MUST raise `ValueError` when it is created.
- The plan (`result.plan`, with `--dry-run` and with the refusal of exit 4) MUST list such a write with its declared `bytes` and `sha256`, as it lists any other.
- Without `--confirm` the dispatcher MUST NOT call `source`.
- With `--confirm` the dispatcher MUST call `source()` once per deferred write, before it writes any file of the command, and MUST compare the length and the SHA-256 of what it returns with the declared values. A difference MUST exit 3 with `FEN-3006` and write nothing, not even the command's other files.
- An exception of `source` that is a `CliError` MUST keep its code; nothing is written.
- A write without a `source` MUST behave as before this requirement.
- The hidden command `_echo` MUST accept `--defer PATH`, which plans a deferred write of fixed bytes, and `--defer-bad PATH`, whose source returns bytes of another digest, so that the suites can exercise the dispatcher without a network.

#### Scenario: Dry run does not call the source
- **GIVEN** `_echo --defer out.txt`, whose planned write has a source that the test counts
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k deferred_dry_run` runs it with `--dry-run`, and then without any protocol flag
- **THEN** the first exits 0 and the second exits 4, both plans list `out.txt` with its declared size and digest, the source was called zero times, and the folder is empty

#### Scenario: Confirmed deferred write
- **WHEN** the same command runs with `--confirm`
- **THEN** the source was called once, `out.txt` holds its bytes, and `receipt.written[0].sha256` equals the declared digest

#### Scenario: Wrong bytes write nothing
- **GIVEN** `_echo --defer-bad out.txt --write other.txt`, whose source returns bytes that do not have the declared digest
- **WHEN** it runs with `--confirm`
- **THEN** the exit code is 3, stderr carries `FEN-3006`, and neither `out.txt` nor `other.txt` exists

### Requirement: Fetch error codes
The registry of `fenolite.cli.errors` SHALL hold `FEN-6003` (exit 6, `retryable: true`, "download failed") and `FEN-3006` (exit 3, "fetched file does not match the pinned size or SHA-256"), and `docs/cli-contract.md` MUST list both with the other codes.
- The hint of `FEN-6003` MUST name `--from FILE`.
- The message of `FEN-3006` MUST hold the digest that was expected and the one that was found.
- `src/fenolite/cli/data/explain.toml` MUST hold a table for each of the two codes ("Explain command").

#### Scenario: Codes are registered and documented
- **WHEN** `uv run pytest tests/unit/cli/test_exitcodes.py tests/consistency` runs
- **THEN** both codes are in the registry with exit codes 6 and 3, and the contract page names both

#### Scenario: Codes are explained
- **WHEN** `uv run pytest tests/unit/cli/test_explain_cmd.py` runs, and then `uv run fenolite explain FEN-6003 --json`
- **THEN** the suite passes with a table for each of the two codes, and the command exits 0 with a `fix` that names `--from`

### Requirement: Fetch command
`fenolite fetch NAME [--from FILE] [--dir DIR]` SHALL be registered by `src/fenolite/cli/cmd_fetch.py` with `mutates=True`, and SHALL install one external tool of the table `src/fenolite/cli/data/fetch.toml` after checking its size and its SHA-256. It is the only code of Fenolite that downloads a tool.
- **Table.** Each row MUST hold `name`, `version`, `file`, `bytes`, `sha256`, `url`, `licence`, `source`, `env` and `needs`. A row whose name starts with `_` is hidden: no hint and no documentation names it. The table MUST hold the row `freerouting` with version `2.4.1`, file `freerouting-2.4.1.jar`, the address `https://github.com/freerouting/freerouting/releases/download/v2.4.1/freerouting-2.4.1.jar`, the size in bytes and the SHA-256 that `docs/evidence/routing.md` records for the gate's jar, licence `GPL-3.0`, source `S-0223` and env `FENOLITE_FREEROUTING_JAR`; and the hidden row `_selftest`, whose address is `package:` and whose file is `fetch-selftest.txt` of the same folder. A test MUST fail when a public row's `source` is not an id of `docs/evidence/sources.md` or its `url` is not `https`, and when the `bytes` or the `sha256` of the row `freerouting` differs from the value on that evidence page.
- **Destination.** `fenolite.core.tools.tool_path(name, file)` (`routing`, "Tools folder"), or `DIR/<file>` with `--dir`.
- **Plan.** The command MUST return one deferred write (`Deferred writes`) for the destination, with the row's `bytes` and `sha256`, or no write when the destination already holds bytes of that size and digest.
- **No request without confirmation.** With `--dry-run`, and without any protocol flag, the command MUST open no network connection and MUST read no file named by `--from`.
- **Network.** Without `--from`, the source MUST request the row's address with `urllib.request`, with the header `User-Agent: fenolite/<version>` and no other added header, a timeout of 60 s, and no query parameter; it MUST follow a redirect only to an `https` address, and MUST read at most `bytes + 1` bytes. Any failure MUST exit 6 with `FEN-6003`.
- **File.** With `--from FILE` the source MUST read that file; a missing file MUST exit 3 with `FEN-3001`.
- **Result.** `result` MUST hold `name`, `version`, `file`, `path`, `bytes`, `sha256`, `url`, `licence`, `origin` (`network`, `file` or `package`), `installed`, `needs` and `env`. `env` MUST map the row's variable to the destination when `--dir` is given, and MUST be empty otherwise.
- **Unknown name.** An unknown or missing `NAME` MUST exit 2 with `FEN-2001` and a hint that lists the public names.
- **Data.** The command sends no design data, so `result.sends_data_offsite` of `capabilities` MUST stay `false`.
- **Evidence.** The envelope evidence is `UNVERIFIED`: installing a tool proves nothing about a board.
- `example_args` MUST be `("_selftest", "--dir", "tools", "--dry-run")` and `mutation_example_args` `("_selftest", "--dir", "tools")`; both MUST run no subprocess and open no connection. `docs/cli-contract.md` MUST have a section `fetch` with the plan, the result keys, the two error codes and the sentence that no other command downloads.

#### Scenario: Dry run of the real row makes no request
- **GIVEN** `urllib.request.urlopen` patched to raise, and `FENOLITE_TOOLS_DIR` set to an empty folder of the test
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k dry_run` runs `fenolite fetch freerouting --dry-run --json`
- **THEN** the exit code is 0, `result.plan` lists `freerouting/freerouting-2.4.1.jar` under that folder with the row's size and digest, `result.licence` is `GPL-3.0`, `result.needs` names Java 25, and the folder is still empty

#### Scenario: Table agrees with the evidence page
- **WHEN** `uv run pytest tests/unit/cli/test_fetch_cmd.py -k table` reads `fetch.toml` and `docs/evidence/routing.md`
- **THEN** the row `freerouting` holds the size and the digest of the page's rows `size` and `SHA-256`, an `https` address and the registered source `S-0223`

#### Scenario: Confirmation required
- **WHEN** `fenolite fetch freerouting --json` runs with the same patches
- **THEN** the exit code is 4, stderr carries `FEN-4001`, and no connection was opened

#### Scenario: Install from a file
- **GIVEN** the row `freerouting` replaced in the test by one whose size and digest are those of a small file the test wrote
- **WHEN** `fenolite fetch freerouting --from <that file> --confirm --json` runs
- **THEN** the destination holds the file's bytes, `result.origin` is `file`, and a second run plans nothing and reports `installed: true`

#### Scenario: Wrong file refused
- **GIVEN** the same row and a file with other bytes
- **WHEN** `fenolite fetch freerouting --from <it> --confirm` runs
- **THEN** the exit code is 3, stderr carries `FEN-3006` with both digests, and the destination does not exist

#### Scenario: Network failure
- **GIVEN** `fetch.download` patched to raise `URLError`
- **WHEN** `fenolite fetch freerouting --confirm` runs
- **THEN** the exit code is 6, stderr carries `FEN-6003` with `retryable` true and a hint naming `--from`, and nothing is written

#### Scenario: Self-test row through the consistency suite
- **WHEN** `uv run pytest tests/consistency -k fetch tests/unit/cli/test_hermetic_examples.py` runs
- **THEN** `fetch` passes the mutation protocol in an empty folder, writing `tools/fetch-selftest.txt`, with subprocess creation patched to raise

#### Scenario: Unknown tool
- **WHEN** `fenolite fetch kicad` runs
- **THEN** the exit code is 2, and the hint names `freerouting` and not `_selftest`
