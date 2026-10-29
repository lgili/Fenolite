## Decisions

1. Label undo steps as restoration or cleanup, and retain their affected path. Rollback attempts every
   restoration in reverse order. After a restoration failure or interruption, skip destructive cleanup
   so remaining .keep, .tmp and moved backup material stays beside its targets.
2. RecoveryError is separate from WriteError, with cli_code FEN-1004, the original failed write path,
   incomplete restoration paths and the preserved recovery paths. Its string does not expose absolute
   paths. Normal rollback failures keep their existing WriteError / FEN-1002 behavior.
3. A failed recovery of a backup must not prevent attempts to recover other targets. A KeyboardInterrupt
   or other BaseException during rollback is recorded as incomplete recovery rather than escaping as a
   misleading FEN-1003. SIGKILL and crashes remain outside a Python recovery guarantee.
4. The dispatcher returns ok=false, receipt=null and FEN-1004 with retryable=false. It exposes failed and
   preserved paths in result.recovery and gives a manual-inspection hint; error text uses paths relative
   to cwd, or names for files outside cwd, never raw system exception text with absolute paths.
   Recovery result paths remain locatable: use relative paths including ../ outside cwd; on a different
   Windows volume, use an absolute path only in the structured result, never the error text.
5. Preserve staged plans for inspection, but do not recommend replay before recovery and a new review.
   No automatic restoration or retry is attempted after incomplete rollback.
6. Prove both backup modes, failure during backup commit/undo, and an interruption during rollback with
   authored temporary files. Existing every-step single-failure tests remain unchanged and must pass.

## Risks and limits

Two simultaneous filesystem failures cannot be made transactional by Python. The guarantee is honest
reporting and retention of whatever original copies remain; a failed filesystem can still prevent
restoration. Cleanup after a successful commit keeps its existing behavior. Public error guidance must
stop treating retryable=false as necessarily a software bug: FEN-1004 requires recovery first.

Disposable-file cleanup through the existing _remove helper remains best effort when deletion raises
OSError; it is never used to restore or remove a changed target. The fix covers failed restoration,
including backup restoration, and does not promise that a faulty filesystem removes every temporary file.
