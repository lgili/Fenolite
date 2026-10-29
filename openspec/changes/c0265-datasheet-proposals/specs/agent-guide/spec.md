## ADDED Requirements

### Requirement: Datasheet proposal page
Besides the pages of "Guide pages", the guide SHALL hold the tool page `datasheets`. It MUST teach the loop of `library propose` (skeleton, proposal, dry run, fix, confirm), copying values with their page, that a proposal carries no geometry and no guessed pin, the two proposals of a dense package, and that an agent never runs `library review --accept`. It MUST hold the tested lines of `library propose`.

#### Scenario: The page through the command line
- **WHEN** `uv run fenolite guide datasheets --text` runs
- **THEN** the exit code is 0 and the text names `library propose`, `[[doubt]]`, `no geometry` and `review --accept`

#### Scenario: The page is indexed and within budget
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py` runs
- **THEN** the start page index lists `datasheets`, its `Read next:` names existing topics, and the page is within its budget
