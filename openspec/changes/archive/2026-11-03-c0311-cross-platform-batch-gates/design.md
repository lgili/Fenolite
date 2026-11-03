## Context

CI run `41187585440` on `8d74a798` identifies six Windows failures. `/abs` is rooted but not fully absolute on Windows; temporary Git repositories inherit checkout newline settings; a subprocess text stream translates JSON line endings; tests search native paths and quoted commands as unparsed strings. KiCad 10 receives a host temporary path that is absent inside its container.

## Decisions

1. Decided 2026-11-01: relative library output validation rejects a native path anchor. This includes rooted paths and drive-relative paths, without changing valid relative folders.
2. Decided 2026-11-01: library Git fetches set `core.autocrlf=false` and `core.eol=lf` on checkout/clone commands. This removes dependence on the caller's global Git configuration while retaining upstream attributes.
3. Decided 2026-11-01: tests of canonical JSON emit UTF-8 bytes through the binary stream. Path and command assertions parse their representations instead of assuming POSIX separators or absent shell quoting.
4. Decided 2026-11-01: KiCad 10 uses a dedicated directory below `/tmp`, and the artifact glob points to that same directory. Local validation still uses an external TMPDIR.
5. Decided 2026-11-01: run `41305101514`, job `124843785751`, checked out `b8b24842c1b792a0fcb37a6a7e5ca0270b90efd6` and printed KiCad 10.0.6. Its heavy import rows 06 and 18 returned exit 0 and equivalent=true; their only failed assertion was the missing census table row. Copy their emitted aggregate JSON into the evidence table with source hashes and CI provenance. Keep the full equivalence assertion and heavy tests unchanged, and add a corpus-independent unit preflight for complete table coverage. The job failed overall (2 failed, 3584 passed, 118 skipped, 3 xfailed); a new exact-commit CI result is still required.

6. Decided 2026-11-01: merge the newer `circuits-as-code` LF checkout and rooted-path fixes additively. Retain the dedicated container `/tmp` directory and matching artifact glob, whose full execution was observed in job `124843785751`. Preserve both newline modes in the parameterized tests and exclude system Git configuration.

## Validation

Run focused library/get/replay, describe, overlay and workflow tests, then the serialized local fast gate. Windows and KiCad execution remain CI proofs on the exact pushed commit. No fixture's expected payload bytes are weakened or normalized in assertions.
