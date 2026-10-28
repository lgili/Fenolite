## MODIFIED Requirements

### Requirement: Atomic writes of several files
`fenolite.core.io.atomic_write_all(writes, *, backup=True) -> tuple[WriteReceipt, ...]` SHALL write several files so that either every one is written or none is changed, and SHALL raise `WriteError` after a completed rollback when a step fails. If rollback itself fails, it SHALL retain recovery material and raise `RecoveryError` instead of claiming no change. `atomic_write` stays as it is for a single file.
- `writes` is a sequence of `(path, data)`; the receipts MUST come in the same order and MUST equal those that `atomic_write` gives for each file.
- **Prepare.** The function MUST create the missing parent folders, remembering which it created; write and flush to disk every new content in a temporary file beside its target; and keep every existing target and every existing `<path>.bak` by a hard link beside it, or by a copy where the file system refuses a link.
- **Commit.** It MUST replace the targets with `os.replace` in the given order; then, with `backup` true, rename each kept target to `<path>.bak`, and otherwise remove it.
- **Roll back.** On any exception, `KeyboardInterrupt` and other `BaseException`s included, it MUST put back every replaced target and every `.bak` from what it kept, remove the targets that did not exist before, attempt cleanup of temporary and kept files and created folders, and raise `WriteError(path, reason)`: `path` the file at which the step failed, `reason` the system's message without a path. `WriteError` MUST be a `FenoliteError` with `cli_code = "FEN-1002"`; an exception that is not an `OSError` MUST be raised again after the roll back instead.
- **Incomplete rollback.** Restoration and cleanup MUST be distinct. If a restoration step raises any exception, the remaining restoration steps MUST still be attempted, destructive cleanup MUST be skipped, and existing kept originals, temporary files and moved backups MUST be preserved. `RecoveryError` MUST be a `FenoliteError` with `cli_code = "FEN-1004"`, the original failing path, incomplete restoration paths and preserved recovery paths; it MUST take precedence over the original failure or interruption.
- An exception that arrives after the last target and the last backup are in place MUST NOT undo the write: what was kept is removed and the receipts are returned.
- Two entries with one path MUST raise `ValueError` before anything is touched.
- The function MUST use the standard library only and MUST NOT follow a symbolic link out of the folder of a target.

#### Scenario: A failure in the middle changes nothing
- **GIVEN** three targets of which the first exists with a `.bak`, and a patch that makes the replacement of the third raise `PermissionError`
- **WHEN** `uv run pytest tests/unit/core/test_io_all.py -k rollback` calls `atomic_write_all`
- **THEN** `WriteError` names the third path, the first target and its `.bak` hold their previous bytes, the second and third targets do not exist, and the folder holds no temporary file

#### Scenario: Folders made for the write are removed
- **GIVEN** a target `a/b/c.txt` under a folder `a` that does not exist, and a second target that fails
- **WHEN** the function runs
- **THEN** `a` does not exist afterwards

#### Scenario: Receipts equal single writes
- **WHEN** two files are written with `atomic_write_all` in one folder and with `atomic_write` one by one in another
- **THEN** the receipts are equal apart from the folder, and both folders hold the same files, `.bak` files included

#### Scenario: Without links
- **GIVEN** `os.link` patched to raise `OSError`
- **WHEN** the rollback scenario runs
- **THEN** its outcome is the same

#### Scenario: An interrupt rolls back and passes on
- **GIVEN** a patch that raises `KeyboardInterrupt` after the first replacement
- **WHEN** the function runs over two existing files
- **THEN** both hold their previous bytes and `KeyboardInterrupt` is raised

#### Scenario: A failed restoration retains the original
- **GIVEN** two existing files, a failure replacing the second and a failure restoring the first
- **WHEN** atomic_write_all rolls back with backup true or false
- **THEN** RecoveryError names the incomplete restoration and the first file's original bytes remain in a recovery file; WriteError is not raised

#### Scenario: A failed backup restoration preserves recovery material
- **GIVEN** existing targets and backups and a failure after one backup was committed
- **WHEN** restoring that backup fails
- **THEN** other restoration steps are attempted and the remaining original target and backup bytes stay recoverable

#### Scenario: An interruption during rollback is reported truthfully
- **GIVEN** a write failed or was interrupted
- **WHEN** a restoration raises KeyboardInterrupt
- **THEN** RecoveryError replaces the original exception and recovery files are retained
