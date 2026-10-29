## ADDED Requirements

### Requirement: Forget stored roles
`fenolite roles` SHALL accept `--forget NET[,NET]` and `--forget-group NAME`, both repeatable, to remove a stored confirmation (role and current) or a stored group decision, so the net or group is inferred again. They MUST write only through the reviewed-plan protocol, to the role document or `.fenolite/rules.json`. Forgetting a declared role MUST be `FEN-2001`, naming the script.

#### Scenario: Forget after accept
- **GIVEN** a copy of the `bad` buck in `tmp_path` whose `SW` was accepted
- **WHEN** `uv run pytest tests/unit/cli/test_roles_cmd.py -k forget` runs `--forget SW --dry-run`, then `--confirm --plan <plan_id>`
- **THEN** the dry run writes nothing, and afterwards `SW` reads as inferred and the stored role set equals the one before the accept
