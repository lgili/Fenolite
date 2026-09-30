# ADR-0004: Licence Apache-2.0; copyleft software only behind a process boundary

## Status
Accepted (2026-09-30)

## Context
Fenolite is meant to be used by individuals, companies and AI agents, embedded in other tools and
scripts, and to interoperate with an ecosystem where most Python hardware-as-code and KiCad
automation projects use permissive licences, while several important neighbours are copyleft:
KiCad itself and its file-format code (GPL), the Freerouting autorouter (GPL-3.0), one of the most
complete open-source readers/writers of another vendor's formats (AGPL-3.0), KiCad's official
footprint generators and library checkers (GPL-3.0), and KiCad's official symbol, footprint and
3D-model libraries (CC-BY-SA 4.0 with an exception for designs that use them).

## Decision
1. Fenolite is licensed under the **Apache License, Version 2.0**. Documentation is CC-BY-4.0;
   fixtures and templates authored for Fenolite are CC0-1.0.
2. **Copyleft software is used only behind a process boundary or a published plugin API, never
   imported or vendored.** Concretely: `kicad-cli` and the Freerouting JAR run as subprocesses
   exchanging files; KiCad's IPC API is reached only through its official MIT client in the
   `kicad-ipc` extra; AGPL/GPL oracles used in tests live in a separate environment set up by a
   script, outside `pyproject.toml`.
3. The official KiCad libraries are resolved from a local installation or fetched by tag at run
   time; their files are never committed or shipped in a wheel.
4. `NOTICE` lists only third-party works from which code or design was actually derived; sources
   consulted for facts are listed in `docs/evidence/sources.md` instead.
5. Contributions are accepted under the Developer Certificate of Origin (no CLA).

## Alternatives
- **MIT**: equally permissive and familiar, but has no explicit patent grant and no NOTICE
  mechanism for attribution; rejected by a small margin.
- **GPL-3.0 / AGPL-3.0**: would allow importing copyleft parsers directly, but would block use by
  companies and closed tools and contradict the goal of a widely embeddable library.
- **Importing copyleft libraries behind an "optional extra"**: the combination is still a
  derivative work under the Free Software Foundation's reading; rejected.

## Consequences
- Anyone can embed Fenolite, including in proprietary tools; patent grant and NOTICE are explicit.
- Some capabilities require an external tool installed next to Fenolite (`kicad-cli`, Java for
  Freerouting); `fenolite capabilities` and `fenolite doctor` report what is present.
- File-format support is written from public documentation, never from copyleft source code,
  which costs time and requires the provenance discipline of `LEGAL.md`.
- `tests/unit/test_no_copyleft_deps.py` (change c0003) enforces point 2 mechanically.

## Evidence
- Apache License 2.0 text in `LICENSE`.
- Licences of the neighbouring projects are recorded in `docs/evidence/sources.md` when first
  used by a change.
