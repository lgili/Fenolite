## ADDED Requirements

### Requirement: Import supported technical layer tables exactly
Strict import SHALL emit technical_layers only when a supported source table differs from the default. Rebuilding the reviewed script MUST preserve the source technical names exactly. Unknown names, missing Edge.Cuts and unrelated unsupported content MUST remain explicit refusals; layer equivalence and acceptance policies MUST remain unchanged.

#### Scenario: Source omits both Eco rows
- **GIVEN** an authored source board omitting unused Eco1.User and Eco2.User
- **WHEN** strict import-copy and an explicit build run
- **THEN** no layer-table loss is reported and the rebuilt technical rows equal the source

#### Scenario: Other unsupported source content
- **WHEN** a source combines a supported short table with mixed outline widths or unknown layers
- **THEN** only concretely represented rows leave the ledger and unsupported content still refuses import
