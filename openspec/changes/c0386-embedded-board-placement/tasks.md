## 1. Evidence

- [ ] 1.1 Ask the altium-rounds-2 session or the maintainer for the Part Q outputs (Q7 to Q12 and phase A)
  and list, per variant, the saved panel and the Altium outputs that exist.
- [ ] 1.2 Measure the plain case from the `panel-a` Gerber and drill outputs against `board.PcbDoc`: the
  first copy's corner with Link Location off and the step per column and row. Record the facts with their
  source and label. Proof: an env-gated test reads the outputs and the saved panel.
- [ ] 1.3 Measure the turned, mirrored and linked variants when their outputs exist; record each, or keep
  the variant `UNKNOWN`.

## 2. Placement

- [ ] 2.1 Read each referenced document relative to the panel document; name a missing or unreadable one.
- [ ] 2.2 Place the copies of each proved variant with designators and nets kept apart per copy; lift the
  refusal for that variant only. Proof: authored panels plus the env-gated saved panels; KiCad load and DRC
  of the converted board.

## 3. Close

- [ ] 3.1 Docs (`pcb-document.md`, `conversion.md`), CHANGELOG, `openspec validate --strict`, focused tests,
  `make check-fast`.
