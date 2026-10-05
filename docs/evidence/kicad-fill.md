# KiCad zone-fill evidence (c0015)

All test boards here are authored for Fenolite or fetched through the public corpus manifest. KiCad is
run only as a subprocess on temporary copies (S-0020, S-0022). The pinned images are S-0029.

| run | KiCad | result |
|---|---|---|
| `tests/kicad/fill/test_fill_probes.py tests/kicad/test_probe_results.py` | local 10.0.6 | `fill-save-t9` and `fill-save-t10`: present; `fill-lift-t9` and `fill-lift-t10`: equal; `fill-repeat`: equal |
| Same proof in pinned image | 9.0.9 | `fill-load9`: load; 9.0.9 has no refill flags |
| `tests/kicad/fill/test_fill_demos.py` | local 10.0.6 | 21 readable non-heavy public demo boards, 42 independent refill runs: 71 netted zones; 63 stale, 0 unfilled, 8 current; 0 boards with differing refill results |
| `tests/kicad/fill/test_docker_cli.py` | pinned 10.0.6 image vs local 10.0.6 | equal filled board text |
| `test_kept_fill_matches_refill` | local 10.0.6 | unchanged blink rebuild keeps the fill and a refill agrees; class-clearance edit drops the fill with `zone.fill-stale`, then a new fill is current |

The class-clearance edit changed the digest but did not change this blink's resulting polygon, even
when the PWR clearance rose to 5.0 mm. Dropping that fill is conservative and correct; the new fill
was verified with another refill. No demo board showed unstable fills. If later refills differ,
`zone.fill` reports `zone.fill-unchecked` and leaves the stale judgment unmade.

`H-K-CLI-DOCKER` remains `INFERRED` and is verified locally only. Run again on 2026-10-04 for the v0.1
record: Docker 28.3.2, the image `kicad/kicad:10.0.6@sha256:18693567392b80da435f9fa952ce3a3e534c66eb5a6033f5b9c80aa3b19dd3ec`
and the local `kicad-cli` 10.0.6 gave equal filled text
(`tests/kicad/fill/test_docker_cli.py::test_container_matches_local` passed). No CI job runs this test:
the jobs that hold a KiCad binary run inside a container and cannot start one, and the others hold no KiCad
binary to compare with. The local result is an observation, not a portable guarantee.
