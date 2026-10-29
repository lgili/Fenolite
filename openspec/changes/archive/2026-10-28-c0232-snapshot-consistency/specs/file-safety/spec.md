## MODIFIED Requirements

### Requirement: Stable snapshot
`fenolite snapshot PATH --out DIR` SHALL copy a design file with its companions, or every project file of a folder, and SHALL accept the candidate copy only when a validation pass observes that the SHA-256 of every requested file equals the hash of the bytes held for that file.
- Every validation pass MUST cover the complete requested file set, including files that did not change in an earlier pass. The first pass follows the initial reads, and each later pass follows the reads of all files changed in the preceding pass.
- A file whose observed hash changed MUST be read again within at most three retry rounds after the initial round. `retries` MUST count the additional file-content reads, not hash checks. If a validation pass at the end of that budget still finds mismatches, every such path MUST be reported with `safety.unstable` (error), and nothing MUST be written, even when a path first changed during that final round.
- `DIR/snapshot.json` (schema `fenolite.snapshot.v0`) MUST list every copied file with the SHA-256 of its copied bytes.
- This observation MUST NOT be presented as an atomic filesystem snapshot or a source lock. The guarantee covers the requested paths and the hashes observed in validation; it cannot detect arbitrary saves after a file's last hash check, bytes changed and restored between checks, or new files outside the requested set.
- Public help, the generated agent guide, CLI contract, issue explanation and supporting hypothesis MUST describe this observed-hash guarantee consistently. They MUST NOT claim that acceptance proves one project-wide instant or no intervening save, or that every unstable file was read four times.

#### Scenario: A file saved during the copy
- **GIVEN** an authored project and a hook that saves its board once after its first read
- **WHEN** `uv run pytest tests/unit/safety/test_snapshot.py -k saved` reads the companions of the board
- **THEN** the copy holds the saved content of the board, and one retry is counted

#### Scenario: A previously settled file changes during another file's retry
- **GIVEN** two authored files A and B, B changes during the initial round, and A changes while B is read again
- **WHEN** the complete-set validation runs after that retry
- **THEN** it detects A's new hash, rereads A within the remaining budget, and accepts only the bytes validated by a pass over both files

#### Scenario: A new mismatch exhausts the shared retry budget
- **GIVEN** successive saves keep B changing until the final allowed read round, which changes only A after A passed earlier validation
- **WHEN** the final complete-set pass runs
- **THEN** it names A as unstable, counts only the additional reads actually performed, and the snapshot command writes no files or manifest

#### Scenario: The source has no concurrent save
- **GIVEN** an empty requested set or authored files whose bytes do not change
- **WHEN** the initial read and complete-set validation finish
- **THEN** the result reports no unstable path and zero retries; each copied file and manifest row hold matching hashes

#### Scenario: An engineer interprets a snapshot result
- **WHEN** the engineer reads the command help, CLI contract, supporting hypothesis or explanation of safety.unstable
- **THEN** these describe checks of observed hashes and a shared retry budget without promising an atomic project save or four reads of each unstable file
