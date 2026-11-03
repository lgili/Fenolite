## ADDED Requirements

### Requirement: Blocks command verbs
`fenolite blocks <verb>` SHALL be registered by `src/fenolite/cli/cmd_blocks.py` with the verbs `list`, `show`, `doc` and `where`. Each verb SHALL be listed by `capabilities` as the command `blocks <verb>` with its own arguments. `list`, `show`, `where` and `doc --text` MUST NOT write, and none of the verbs MUST open a network connection or run an external tool.

#### Scenario: Verbs in capabilities
- **WHEN** `fenolite capabilities --json` runs
- **THEN** the commands hold `blocks list`, `blocks show`, `blocks doc` and `blocks where`

### Requirement: Blocks list command
`fenolite blocks list [--from FILE]... [--category C]` SHALL give `result.blocks`, one row per catalog entry sorted by id then source, each with `id`, `version`, `summary`, `category`, `licence`, `evidence`, `source`, `deprecated` and the record digest, without elaborating any block. A duplicate id MUST give `blocks.duplicate-id` (error, exit 5).

#### Scenario: List with a file source
- **WHEN** `fenolite blocks list --from tests/data/blocks/divider.py --json` runs
- **THEN** the exit code is 0 and `result.blocks` holds `Acme:divider` with `source` `file` and `version` `1.0.0`

### Requirement: Blocks show command
`fenolite blocks show ID [--from FILE]...` SHALL give `result.block`, the `fenolite.block.v0` record with `source` and the module name, never an absolute path. An unknown id MUST exit 2 with `FEN-2001` whose hint lists up to five closest ids; a block that cannot be elaborated MUST exit 3 with `FEN-3004`.

#### Scenario: Show the authored divider
- **WHEN** `fenolite blocks show Acme:divider --from tests/data/blocks/divider.py --json` runs
- **THEN** `result.block.ports` lists `HI`, `LO` and `OUT`, and `result.block.digests` holds `record`, `definition` and `interface`

#### Scenario: Unknown id
- **WHEN** `fenolite blocks show Acme:divder --from tests/data/blocks/divider.py --json` runs
- **THEN** it exits 2 with `FEN-2001` and the hint names `Acme:divider`

### Requirement: Blocks doc command
`fenolite blocks doc ID [--from FILE]...` SHALL print the generated page with `--text`, or with `--out DIR` plan one file `DIR/<namespace>/<name>.md` (kind `block-doc`) and write it only under `--confirm`, through the mutation protocol, with a receipt.

#### Scenario: Page planned, not written
- **WHEN** `fenolite blocks doc Acme:divider --from tests/data/blocks/divider.py --out D --dry-run --json` runs
- **THEN** `result.plan` holds `D/Acme/divider.md` of kind `block-doc`, and `D` is unchanged

### Requirement: Blocks where command
`fenolite blocks where ID [PATH]...` SHALL read every `*.lock` file below each path (default the working directory) as a c0249 lock, import nothing and run no script, and SHALL give `result.uses` with `lock`, `design`, `instance` and `version`, sorted. A lock that does not parse MUST give `blocks.lock-unreadable` (warning) and be skipped.

#### Scenario: Two designs use one block
- **GIVEN** the folders `a/` and `b/`, whose locks map `sense_a` and `adc` to `Acme:divider@1.0.0` and `@1.1.0`
- **WHEN** `fenolite blocks where Acme:divider a b --json` runs
- **THEN** `result.uses` holds two rows, `a/design.lock` with `sense_a` and `1.0.0`, and `b/design.lock` with `adc` and `1.1.0`

### Requirement: Blocks view of inspect
`fenolite inspect FILE --blocks` SHALL be a third view of "Inspect command", for a c0249 lock file or a `circuit.json`, and SHALL give `result.blocks`: per block id and version, the instance paths, and for a `circuit.json` each instance's recorded parameters. Giving `--blocks` with another view MUST exit 2 with `FEN-2001`.

#### Scenario: Where-Used in one design
- **GIVEN** a built design with `sense_a` and `sense_b` of `Acme:divider` 1.0.0
- **WHEN** `fenolite inspect B/.fenolite/circuit.json --blocks --json` runs
- **THEN** `result.blocks` holds one row `Acme:divider` `1.0.0` with the instances `sense_a` and `sense_b` and their parameters
