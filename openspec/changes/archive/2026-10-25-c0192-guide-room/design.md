## Context

- **Request.** Free at least 5 KB of the guide's 150 000-byte budget so that later changes can teach what they
  add.
- **Measure (branch `c0184-visual-diff`).** 148 731 bytes in all. The largest files: `commands.md` 34 056,
  `SKILL.md` 14 038, `dsl-reference.md` 11 044, `rules.md` 10 363; every other page is under 10 000. In
  `commands.md` the usage lines took 5 417 bytes and the argument lines about 22 400; the largest sections
  were `build` (4 540), `route` (1 883), `export` (1 794) and `analyze` (1 768).

## Goals / Non-Goals

**Goals**
- See the proposal, "What Changes".

**Non-Goals**
- See the proposal.

## Decisions

1. **Cut the duplication in the generated page, not the written pages.** The usage line and the argument
   lines held the same flags. The written pages are already within their own budgets and each line of them
   was put there to teach something; cutting them would lose content.
2. **Keep the placeholder.** A placeholder such as `[LAYER=]LENGTH`, `REF=X,Y[,ROT[,SIDE]]` or `K,K` says the
   form of the value, which the help does not always repeat. It moves to the argument line (about 1.1 KB),
   so the saving is the flag names and brackets of the usage line, not the placeholders.
3. **Parse the usage line in the generator.** `fenolite.cli.describe` already builds the line from the
   parsers; the generator splits it into words outside brackets and maps each option's first flag to its
   placeholder. The description's fields and the JSON of `capabilities` stay as they are.
4. **Not chosen.** Moving the shared `--kicad-cli` and `--timeout` lines into the head: their help texts differ
   by command (`the kicad-cli of rt2`, `per kicad-cli run`). Dropping the summary table: it is the page's
   overview, and the summary in each section would cost the same bytes. Raising the budget: not needed now.

## Risks / Trade-offs

- An agent that read the old usage line for the full list now reads the argument lines below it, or
  `fenolite capabilities --command NAME --json`. The head of the page says how to read a section.
