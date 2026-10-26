## Context

Change c0121 added `--altium-bodies off|extruded` with the default `off` and said how to switch it
("Decisions (2026-10-06)", 2: "the default in `cmd_build.py` and in the model writer, the scenario
'Without the option', the RT-A3 numbers of the evidence page, and `body2` only"). Step X8 of Part X of
`docs/evidence/altium-pcb.md` was reported as expected on 2026-10-09 (S-0724), and the maintainer decided
on 2026-10-09 that the Altium build writes component bodies by default (`docs/roadmap.md`, "Open
decisions", row 33).

## Decisions

1. **The build switches, the writers below it do not.** `DEFAULT_ALTIUM_BODIES` in
   `src/fenolite/cli/cmd_build.py` and the default of `bodies` in `lens.altium.build_altium` become
   `extruded`. The decision names the Altium build. `lens.altium.write_model`, `lower.from_design`,
   `lower.write_design`, `AltiumBackend.write` and `AltiumBackend.model_roundtrip` keep `off`: they write a
   model that was read (the rewrite, RT-A3 of `fenolite check`) and the RT-A3 numbers of
   `docs/evidence/altium-roundtrip.md` were measured with `off`; switching them needs the heavy corpus run
   and is not asked. c0121's list said "and in the model writer"; this change narrows it on purpose.
2. **The kit samples.** `fenolite kit` builds its samples through `build_altium` with the default. None of
   them holds a body with an outline, so their bytes do not move; the tests of the kit pin that.
3. **No byte of a committed file moves.** A script declares no extruded body with an outline (a
   `Part(height=…)` body has no outline and is reported, change c0140), so every example, every committed
   sample under `tests/data/altium/` and every pin of `tests/unit/lens/test_build_bytes_pinned.py` keeps
   its bytes; `body2` was always built with `extruded`. What moves is `result.pcb.bodies` (`extruded`
   without the option) and, for a design whose footprints hold bodies, the bodies that are written and
   the reasons of the `altium.not-lowered` infos of the bodies that are not.
4. **The record.** Unchanged: the form `saved`, the two stand-ins, the layer rule.

## Evidence

`H-A-PCBX-BODY-OPEN`, `-SHORT` and `-LIB` are `ALTIUM-VERIFIED(author-report; AD 26.5; 2026-10-09; no
artefact)`; `H-A-PCBX-BODY-ID` stays pending. The write stays experimental; this change moves no row.

## Risks / Trade-offs

- [A body that Altium refuses in a document other than `body2`] → `--altium-bodies off` gives the earlier
  files; the evidence is one author report on one sample, and the write stays experimental.
- [A user of the library calls `build_altium` and gets bodies where it got none] → stated in the changelog
  as a change of behaviour; `bodies="off"` restores it.
