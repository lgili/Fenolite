## 1. Loss instead of block

- [ ] 1.1 Authored regression: a generated circuit too large for A0 blocks `convert --allow-lossy` today.
- [ ] 1.2 Return the refusal as the declared loss; exit 7 without `--allow-lossy`.

## 2. Sheets and pages

- [ ] 2.1 Keep the source's sheets as KiCad sheets when the circuit carries sheet paths.
- [ ] 2.2 Paginate a flat generated circuit; prove with KiCad 9/10 ERC that the pages load.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
