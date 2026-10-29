## ADDED Requirements

### Requirement: Family command
`fenolite family {list|show ID|lint PATH...|decode MPN...|encode QUERY|expand ID} [--project PATH] [--families DIR]... [--limit N]` SHALL be registered by `src/fenolite/cli/cmd_family.py` with `mutates=False`. It MUST run no subprocess, open no network connection and write no file; an unknown family id MUST be `FEN-2001`, and an error finding MUST exit 5.

#### Scenario: Family example is hermetic
- **GIVEN** `subprocess.run`, `subprocess.Popen` and `socket.socket` patched to raise
- **WHEN** `uv run pytest tests/unit/cli/test_hermetic_examples.py` runs `family` with its `example_args` `("expand", "Example:EX_MLCC", "--project", EXAMPLE_FAMILIES, "--json")`
- **THEN** the exit code is 0 and `result.candidates` lists at most 50 MPNs in canonical order with `truncated` set
