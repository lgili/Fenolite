## Decisions

1. Keep one candidate per requested relative path, with the bytes and SHA-256 already stored by
   `StableFile`. After reading the current retry list, hash every requested path in the original order;
   do not limit that validation pass to the retry list.
2. The next read round contains exactly the paths whose current hash differs from their candidate.
   The global round budget remains the initial round plus at most `RETRIES == 3` retry rounds, preserving
   bounded work even when saves alternate between different files. `StableRead.retries` continues to
   count additional file-content reads, not rounds or hash checks. The hook keeps its current meaning:
   after a content read, with the global attempt index (0 for the initial round).
3. At the final allowed round, return all mismatches from the complete validation pass as `unstable`.
   They need not have changed in every round. `snapshot` already refuses all writes for any such row;
   change its message to describe the exhausted retry budget without inventing four reads per file.
4. This is an optimistic observed-hash check over a caller-supplied list, not an atomic snapshot of a
   filesystem. It detects persistent changes observed by validation, including changes to previously
   settled files on later rounds. Without locks it cannot promise that the source stays unchanged after
   the last check, detect an ABA save restored between checks, or observe additions outside the list.
   The documentation states these limits and advises taking a copy when writers have paused when an
   application-level consistent save is required.
5. Use authored two-file byte sequences and the existing read hook for repeatable tests. Confirm a
   former stable file is reread after another file's retry changes it; confirm repeated cross-file
   writes terminate and produce `safety.unstable` with no destination files; confirm metadata and
   manifest hashes agree with the accepted bytes when the sources settle. Do not introduce timing
   sleeps or rely on scheduler races.
6. `snapshot` is the sole caller of `read_stable`. `publish` instead reads source files and uses receipt
   and transaction guards; its semantics are outside this focused repair. No shared IO implementation
   is changed, and no evidence label is raised.
7. Carry the same observed-hash guarantee through the public command help and generated guide, CLI
   contract, `safety.unstable` explanation and `H-G-SNAPSHOT-STABLE` hypothesis. The exhausted shared
   budget does not imply four reads of each unstable file. Matching hashes do not prove a project-wide
   instant or that no intervening save occurred, including the receipt comparison's existing ABA limit.
   This corrects the description without changing publish behavior or raising evidence.

## Validation

Run the snapshot regressions, the safety test directory and affected CLI consistency cases. Run Ruff on
changed Python files and strict OpenSpec validation. The batch coordinator runs the single quick gate
and the eventual complete CI; neither a completed spec nor a native/filesystem atomicity claim follows
from the focused tests alone.
