# Honor an explicit import target without changing default imports

The public `--kicad-version` target is ignored by Python import whenever a supported source board major exists. A public mixed KiCad9 board/KiCad10 project therefore cannot preserve its project settings even when the user explicitly requests10. Correct only explicit target selection; retain source-major defaults, all project-version refusals and existing byte defaults. No native keys are dropped and no lossy waiver is added.
