# Golden regression set — Grammar V1

`generate_golden_v1.py` consumes the public grammar API
(`ParcelContext` + `BuildingProgram` + `generate_masses` +
`generate_v4_mesh` + `export_glb`) and writes the frozen reference
outputs to `outputs/generations_tests_v1.0/`.

Regenerate (from `investigation/procedural_reconstruction/`):

```bash
python scripts/golden_v1/generate_golden_v1.py --detail 2 --random-seed 20260923
```

With the frozen seed this must reproduce byte-equivalent geometry:
same labels, same `golden_jobs.json`, same `fingerprint_lod2.json`
triangle counts. Do not change the seed, the lots, or the defaults to
"improve" the set — that would defeat the freeze. Grammar changes
belong to a new version, not to this folder.
