## 1. Inventory

- [x] 1.1 Count unmapped kinds and scopes on authored and public documents; rank them.
      Public counts and the reason each form stays open: `docs/formats/altium/rule-file.md`, "Closed
      scope grammar" (S-0580, S-1531). The maintainer's boards were counted outside the repository.

## 2. Mapping

- [x] 2.1 Clearance and Width scopes. Operators in any letter case map (`H-A-RD-PRJ-SCOPE-CASE`,
      INFERRED), and Width, Routing Via Style, Hole Size and Minimum Annular Ring map with either
      `NETSCOPE` (`H-A-RD-PRJ-NETSCOPE-ONE`, INFERRED); the coordinator chose these two classes on
      2026-11-04. The other forms stay declared losses with their reasons (`rule-file.md`).
- [x] 2.2 Plane and polygon connect styles: a declared loss (`no-counterpart`; the board keeps the
      Polygon Connect Style records, c0215). Listed in `rule-file.md`.
- [x] 2.3 Solder mask and paste expansion: a declared loss (`no-counterpart`; the pad expansion modes
      are `INFERRED`). Listed in `rule-file.md`.

## 3. Close

- [ ] 3.1 Docs, CHANGELOG, `openspec validate --strict`, focused tests, `make check-fast`.
