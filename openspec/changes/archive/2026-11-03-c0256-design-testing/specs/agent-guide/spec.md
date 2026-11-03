## ADDED Requirements

### Requirement: Bounded command reference pages
The generated command reference SHALL keep an index and linked argument pages, each no larger than
12000 UTF-8 bytes. The pages MUST retain every public command and its argument descriptions, be
included in the packaged guide index, and be reproduced by tools/gen_agent_guide.py.

#### Scenario: Full reference within the page budget
- **WHEN** the agent-guide tests generate the reference
- **THEN** every argument remains documented, every reference page is at most 12000 bytes, and --check reports no drift
