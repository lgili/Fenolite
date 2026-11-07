---
topic: datasheets
title: Cited datasheet proposals
summary: Read a datasheet with your own tools, propose cited parameters, generate records and hand review to a person.
---

# Cited datasheet proposals

Read the document with your own PDF tools. Fenolite only checks its PDF header and SHA-256; it runs no
extraction tool. Start with the installed skeleton, then fill the printed facts and their citations.
Lengths are exact unit text; bounded ranges use `min..max`, and open bounds use `min` or `max` suffixes.

```fenolite-cmd
fenolite library propose --datasheet part.pdf --json
fenolite library propose --datasheet part.pdf --proposal part.proposal.toml --out devices/proposed --dry-run --json
fenolite library propose --datasheet part.pdf --proposal first.toml --proposal second.toml --out devices/proposed --licence CC0-1.0 --dry-run --json
```

The schema is `fenolite.proposal.v0`. A proposal has no geometry: never supply coordinates, pads,
outlines, polygons or a guessed pin. Copy dimensions, pin numbers and names from the selected package
variant; one proposal describes one variant. Every pin row, package, manufacturer land, rating and
ordering row needs `cite = { page = N }`, optionally naming one table or figure. A citation's presence
does not prove that its contents are correct.

Use `[[doubt]]` with a `field` and a `reason` for an unreadable value. Keep it until you read the page
again; never replace it with a guess or a remembered value. Alternates stay in the proposal and are
not written into generated pins. The default record licence is `see source terms`; selecting CC0
requires that you have established that licence for the facts you propose.

A grid array or package above 100 terminals requires two separate proposals. Make two independent
readings that do not see each other's output, or use a person for the second. Different proposer
names are a recorded claim of independence. Copy every printed `row_labels` entry and every
depopulated ball; two equal mistakes can still pass agreement. Fenolite checks counts, numbering,
ranges, sides, citations and agreement, then its generators draw and the library rules check them.

Read findings and correct the proposal before confirming. Errors exit 5 and plan no writes. Warnings
and doubts remain visible. Review `result.plan`, then confirm its `plan_id` to write exactly those bytes.
The folder holds unreviewed records, native drawings, a body model where available and canonical
proposal copies. Proposed device evidence stays `UNVERIFIED`; pipeline evidence is `INFERRED`.

```fenolite-cmd
fenolite library check devices/proposed/NAME --sheets review --dry-run --json
fenolite library review devices/proposed/NAME/device.toml --json
```

Hand the folder, the exact PDF and the base review sheet to a person. An agent never runs
`library review --accept`. A person supplies `--datasheet`, their `--reviewer` name and the current
`--sheet` digest. Open doubts, missing citations, a changed PDF or changed generated files block
acceptance. Reviewed or hand-edited folders cannot be replaced by another proposal.

Read next: `footprints`, `parts`, `checks`.
