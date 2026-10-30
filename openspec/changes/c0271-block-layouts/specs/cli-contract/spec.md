## ADDED Requirements

### Requirement: Block capture command
`fenolite blocks capture BOARD --instance PATH [-o FILE] [--origin pose|anchor] [--anchor LOCAL] [--no-copper]` SHALL return `result.capture` with `instance`, `block`, `version`, `file`, the counts of parts, tracks, arcs, vias and zones, and `left`. An unknown instance or one that is not a block instance MUST be `FEN-2001` naming the closest instance paths; a block outside the working directory without `-o` MUST be `FEN-2001`.

#### Scenario: Not a block instance
- **WHEN** `uv run pytest tests/unit/cli/test_blocks_capture.py -k usage` runs `fenolite blocks capture OUT --instance dutt --json`, and `--instance dut` for a shipped block without `-o`
- **THEN** both exit 2 with `FEN-2001`, the first hint naming `dut`, the second naming `-o`, and nothing is planned
