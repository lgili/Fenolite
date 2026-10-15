## ADDED Requirements

### Requirement: Removed pad shapes of a via record
`read.pcbprims.via_pad_removed(record)` SHALL give the layers on which a via record says that the via has no pad shape (change c0132; `docs/formats/altium/pcb-copper.md`, "Via", `H-A-IMP-VIA-PADLESS`).
- The subrecord of a via of at least 321 bytes holds a table of thirty-two bytes at offset 209, one per layer id from 1 to 32. The result MUST be the layer ids whose byte is not zero, in ascending order, as a tuple of integers.
- A subrecord shorter than 321 bytes MUST give the empty tuple: the rows of the page place the table in the forms of 321 bytes and more only.
- The function MUST read `ViaRecord.tail` only. `ViaRecord` MUST keep its fields, and `raw` and `tail` their bytes, so that a record is written back as it was read ("Lossless PCB records").
- The function MUST NOT depend on the length of the record beyond that bound: the nine further bytes of the 330-byte form are after the table and are not read.

#### Scenario: Table of a long record
- **GIVEN** the via record of `pcbrecords.via_record`, with the bytes at 210, 212 and 213 of its subrecord set to 1 and nine bytes inserted at 254
- **WHEN** `uv run pytest tests/unit/backends/altium/read/test_pcbprims.py -k pad_removed` decodes it
- **THEN** `via_pad_removed` gives `(2, 4, 5)`, the record as written gives `()`, a subrecord cut to 209 bytes gives `()`, and the decoded record's `raw` is the bytes that were given

#### Scenario: Public documents
- **WHEN** `FENOLITE_HEAVY=1 uv run pytest tests/corpus/test_altium_copper.py -k via_record_forms` reads the via records of the eight public PCB documents
- **THEN** their subrecord lengths are 299 (646 records), 321 (2 082), 330 (123) and 351 (82); every record of 330 bytes names layers, each of them between 2 and 5; and no other record names one
