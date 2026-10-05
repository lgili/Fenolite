# Design

The current helper calls `run_raw`, which inherits global KiCad configuration and locale and reuses its board/output between the two probes. Use `KicadCli.run` with relative filenames and explicit input copies instead. Its existing runner creates a fresh temporary working directory for every call, removes inherited KICAD settings, assigns a private `KICAD_CONFIG_HOME` and selects the C locale. Configuration isolation alone still fails the non-root stress case: KiCad tries to create global cache and data directories. Pass explicit HOME, XDG_CACHE_HOME, XDG_DATA_HOME and TMPDIR/TMP/TEMP paths under a separate per-version test directory. This also gives KiCad a private instance-lock location.

Keep the accepted-version and next-version assertions: the latter must include both `Error loading drawing sheet` and `more recent version`. Also assert a zero exit and a produced SVG, because KiCad falls back to its default drawing sheet after reporting a rejected custom sheet. Do not retry, skip or match the incidental lock warning.

Validate the native test module, the same boundary helper concurrently in the pinned Linux KiCad 9 and 10 containers as root with HOME=/root (the CI environment), and under UID 1001, and `make check-fast`. Full-suite and remote CI proof remain a gate for the later batch integration; no merge or push is part of this fix.
