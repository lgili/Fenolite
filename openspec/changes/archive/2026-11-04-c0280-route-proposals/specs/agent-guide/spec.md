## ADDED Requirements

### Requirement: Viewer guide page
The packaged agent guide SHALL include a written `viewer` topic with tested `view` lines for served checks, reviewed actions, role overlays and route proposals. `files` MUST retain a tested view entry and a pointer to `viewer`. All existing guide budgets MUST remain unchanged, and the topic index and command references MUST be generated.

#### Scenario: Combined viewer guide stays within budget
- **WHEN** `uv run pytest tests/unit/agent/test_pages.py -k "topics or budget or cmd_lines or coverage"` checks the integrated guide
- **THEN** `viewer` loads, its commands parse, all public commands remain covered, and every written page stays within 12,000 bytes and 250 lines
