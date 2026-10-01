# docs/evidence

Where Fenolite keeps the evidence behind its claims.

- `sources.md` — every public source consulted for format knowledge or behaviour (URL, licence of
  the source, what it was used for, date consulted). It is the only place ADRs, proposals and
  format pages cite.
- `../hypotheses.md` — the hypothesis register: each claim that is not yet verified, the test or
  kit request that settles it, and the result. `tests/unit/test_hypotheses_register.py` checks the
  register and every hypothesis id cited in live text; `fenolite.verify` reads it.
- Generated reports (evidence matrix, oracle runs) are added here by later changes.
