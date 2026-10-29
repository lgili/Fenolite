## Context

c0175's design, decision 9, sketched the package. The mutation protocol already gives atomic writes, `.bak`
files and receipts (`{written: [{path, sha256}], backup, id}`), and `fenolite restore` reads a receipt from an
envelope. This change adds what happens before a write (is the file open, is it there) and around an edit
of someone else's project (a stable copy, a guarded return).

## Decisions

1. **Companions follow the references.** A design file brings the documents of its stem and the library
   tables beside it. Then every file inside the folder that one of those names is added, until no new file
   appears: sheets, library folders, 3D models. A folder brings every project file in it (KiCad and
   Altium documents, Fenolite scripts, library folders; not backups, locks or hidden folders).
2. **Stable means equal after all reads.** Each file is read, then every hash is taken again. A file that
   moved is read again, at most three times; one that never settles is `safety.unstable` (error, so
   nothing is written). c0175's draft said exit 3; an error finding gives exit 5 under the protocol.
3. **`snapshot.json` is a receipt.** `publish` accepts it, or an envelope or receipt of a confirmed write
   (read by `restore`'s reader, paths relative to `--in`). A file of `DST` is replaced only when its
   current hash is the recorded one; a file the receipt does not name is a conflict too. The protocol
   writes all or nothing beside an error. c0175's draft replaced the other files beside a conflict; here
   `--skip-changed` asks for that explicitly, and the conflicts become `safety.skipped` warnings.
4. **The warning lives in the dispatcher.** Every writing command plans its files. The dispatcher checks
   each planned path for KiCad's lock file and adds `safety.open-session`, so no command can forget it.
5. **Online-only by attributes, before any read.**
   - Windows: `FILE_ATTRIBUTE_OFFLINE`, `RECALL_ON_OPEN` and `RECALL_ON_DATA_ACCESS` in
     `st_file_attributes`.
   - macOS: `SF_DATALESS` in `st_flags`, its value the one Python 3.13 reports, for older Pythons.
   - `FEN-3007` is an error, not a finding, because nothing can be read; it is retryable.
6. **Refs rewrite atoms, not documents.** The paths are the written atoms (the JSON string in a project
   file); a repoint replaces those texts and leaves every other byte. An Altium project is listed and
   reported `refs.not-writable`.

## Risks / Trade-offs

- A stale lock file left by a crash gives the same warning; `doctor --sessions` marks a lock whose file is
  gone as `stale`, and the hint says that a closed tool's lock may be deleted.
- `publish` deletes nothing, so a file removed from the copy stays in `DST`.

## Open Questions

None.
