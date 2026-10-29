## MODIFIED Requirements

### Requirement: Page budgets and writing rules
The pages SHALL stay small enough to be read whole. A tool page SHALL state only what Fenolite does; a practice page SHALL state design practice and SHALL state what Fenolite does only where it names a command.
- A written page MUST have at most 250 lines and 12 000 bytes. A generated page MUST have at most 750 lines. The files of the skill folder together MUST stay under 300 000 bytes.
- A page MUST NOT name a company, a fabricator, a standard's table, a private path or a person, and MUST NOT hold a change id (`c0000` form) or a hypothesis id (`H-…`).
- A line of prose that holds a call of `rules.minimum` or `rules.netclass` with a number MUST hold the word `example`.
- A sentence that says a result is verified MUST name the evidence label.
- A practice page MUST NOT give a distance, a width, a current or a temperature as a limit; a figure on it is an input of a named public method or is marked as an example.
- `tests/unit/agent/test_pages.py` MUST check the sizes, the forbidden forms and the `example` rule.

#### Scenario: Budgets hold
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k budget` runs
- **THEN** every written page is within 250 lines and 12 000 bytes, every generated page within 750 lines, and the folder under 300 000 bytes

#### Scenario: Forbidden forms are reported
- **GIVEN** a copy of a page, made in the test, that holds `c0042` in a sentence
- **WHEN** the writing-rules check runs on it
- **THEN** it fails naming the page and the line
