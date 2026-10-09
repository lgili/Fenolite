## MODIFIED Requirements

### Requirement: Executable blocks
Every fenced block of the start page and of the written pages SHALL carry a tag that says how the suites prove it, and `tests/unit/agent/test_pages.py` SHALL prove each one.
- `fenolite.agent.guide.blocks(page) -> tuple[Block, ...]` MUST return `Block(tag, argument, lines, line_number)` for every fenced block, `tag` being the first word after the fence and `argument` the rest of that line.
- The tag MUST be one of `fenolite-loop`, `fenolite-cmd`, `fenolite-design`, `fenolite-recipe`, `json` and `text`. A block with another tag or with none MUST fail the test, which names the page and the line.
- **`fenolite-cmd`.** Every line MUST start with `fenolite ` and MUST be accepted by the parser of `fenolite.cli.main.build_parser(discover())`. A line MUST NOT hold `<` or `>`.
- **`fenolite-design`.** The block MUST be a complete design script that names lib ids of the built-in catalog or definitions it authors itself. The test MUST write it to an empty folder and build it with no library table and with `subprocess.run` and `subprocess.Popen` patched to raise: exit 0 and no issue of severity `error`, for targets 9 and 10. With the argument `altium` the test MUST build it with `--target altium` instead, with the same verdict; the notices that an Altium build gives for a kind that has not graduated are warnings and do not fail it. With the argument `kicad10` the test MUST build it for target 10 alone, with the same verdict: the block uses a feature that a KiCad 9 board cannot hold, which the build for target 9 refuses (exit 7). `fenolite.agent.guide.DESIGN_TARGETS` MUST map each accepted argument to its targets, and any other argument MUST fail the test, which names the accepted ones.
- **`fenolite-recipe`.** See "Recovery recipes".
- **`json` and `text`** hold samples of output and are not run.
- The generated pages MUST hold no fenced block.

#### Scenario: Every command line parses
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k cmd` runs
- **THEN** every line of every `fenolite-cmd` block is accepted by the parser

#### Scenario: Every design builds
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k design` runs
- **THEN** every `fenolite-design` block builds for its targets with exit 0 and no error issue, with no subprocess created

#### Scenario: A block for target 10 alone
- **GIVEN** the `fenolite-design kicad10` block of the page `fabrication`, which fills and caps the vias of a stitch with `protect(filling=True, capping=True)`
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k "design or target_ten"` runs
- **THEN** the block builds for target 10 with exit 0 and no error issue, it is not built for target 9 by "Every design builds", and its build for target 9 exits 7

#### Scenario: An untested block is refused
- **GIVEN** a copy of a page, made in the test, with a block tagged `python`, and another with a `fenolite-cmd` line `fenolite route blink/build --engine x`
- **WHEN** the block checks run on each copy
- **THEN** the first fails naming the tag and the line, and the second fails naming `--engine`
