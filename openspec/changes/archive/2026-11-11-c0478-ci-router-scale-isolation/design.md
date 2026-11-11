# Native routing scale isolation

## Context

Run 42966836398 attempts 1 and 2 reached the 600-second route budget on the two-layer 150-part
shapes fixture, leaving five and six subjects unknown respectively. Run 42956587864 passed the
same test in 442.56 seconds on the same code. The exact development commit also passed locally in
211.02 seconds with 121 proposals and zero unknown subjects.

## Decision

Keep one collection baseline for the KiCad 10 suite. Assign the whole scale file to partition 4.
Assign every other file with the existing hash modulo 4. Run partition 4 serially on its own job.
The audit reconstructs the same partition assignment from the full baseline and requires all
five receipts on the tested commit. The timeouts, deterministic proposal floors, resource
requirements and every existing test node stay in force.
