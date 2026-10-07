## ADDED Requirements

### Requirement: Atomic writes of several files
`fenolite.core.io.atomic_write_all(writes, *, backup=True) -> tuple[WriteReceipt, ...]` SHALL write several files so that either every one is written or none is changed, and SHALL raise `WriteError` after putting everything back when any step fails. `atomic_write` stays as it is for a single file.
- `writes` is a sequence of `(path, data)`; the receipts MUST come in the same order and MUST equal those that `atomic_write` gives for each file.
- **Prepare.** The function MUST create the missing parent folders, remembering which it created; write and flush to disk every new content in a temporary file beside its target; and keep every existing target and every existing `<path>.bak` by a hard link beside it, or by a copy where the file system refuses a link.
- **Commit.** It MUST replace the targets with `os.replace` in the given order; then, with `backup` true, rename each kept target to `<path>.bak`, and otherwise remove it.
- **Roll back.** On any exception, `KeyboardInterrupt` and other `BaseException`s included, it MUST put back every replaced target and every `.bak` from what it kept, remove the targets that did not exist before, the temporary and kept files and the folders it created, and raise `WriteError(path, reason)`: `path` the file at which the step failed, `reason` the system's message without a path. `WriteError` MUST be a `FenoliteError` with `cli_code = "FEN-1002"`; an exception that is not an `OSError` MUST be raised again after the roll back instead.
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
