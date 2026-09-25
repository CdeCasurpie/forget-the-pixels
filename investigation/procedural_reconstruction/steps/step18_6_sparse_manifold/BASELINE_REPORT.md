# Baseline before sparse materialization

Branch starts at a29df7b on step18-theta-interface; ThetaCandidate 0.2 intact.
Full suite: **205 passed, 125 subtests passed, 244.97 s**. Geometry/topology
validators are included in that suite and additionally run on the ten fixtures.

| Case | Triangles | Parts | GLB bytes | Topology violations |
|---|---:|---:|---:|---:|
| simple | 13440 | 186 | 484404 | 0 |
| republicano | 16320 | 321 | 732688 | 0 |
| galeria | 14948 | 308 | 690564 | 0 |
| mixed | 23216 | 455 | 1051764 | 0 |
| stepped-back | 30464 | 574 | 1350256 | 0 |
| lot 1850, small | 8650 | 177 | 414240 | 1 |
| lot 1851, medium | 23784 | 226 | 964788 | 0 |
| lot 1849, large/irregular | 43930 | 597 | 1942884 | 4 |
| lot 2451, heavy | 50552 | 1682 | 3066236 | 1 |
| lot 1843, additional irregular | 38838 | 1096 | 2208012 | 1 |

All five cadastral cases report pre-existing envelope violations. Example 1850
contains an open plinth (6 boundary edges). These are measured failures, not
waived acceptance criteria. Individual JSON reports preserve detailed results.

Exact inputs are frozen under benchmarks/inputs; cadastral ordering and sample
selection are in benchmarks/cases.json. Reports include bounds, resolved
architecture SHA256, vertices, triangles, source parts/components, GLB nodes and
primitives, bytes, timings, process high-water RSS and semantic cost breakdown.
Initial jobs overlapped, so timings are indicative rather than isolated CPU
comparisons. RSS is a process high-water mark, not incremental per-house memory.

Baseline renders/GLBs are in outputs/baseline/individual (gitignored). They use
the same fixed orthographic directions, resolution, colors and light as after.
No PBR images are embedded in cost measurements. The historical golden set and
grammar-v1.0 tag are untouched; exact triangle equality is not a v1.1 criterion.

The original 120-house partial run measured 2,624,110 triangles, 42,782 GLB
nodes/meshes, 43,389 primitives, 111.12 MiB and 783.3 MiB peak process RSS.
Controlled 50-house results are captured separately by the benchmark runner.
