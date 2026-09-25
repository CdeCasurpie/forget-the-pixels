# Step 18.5 baseline, before contract changes

Checked on branch `step18-theta-interface`, HEAD `d6f2093`. The peeled
`grammar-v1.0` tag and `main` both pointed to `357a9ba`. Only the root
`README.md` had preexisting local changes; it was not included in this work.

From `investigation/procedural_reconstruction`, before hardening:

| Check | Result |
|---|---|
| `pytest tests/test_theta.py -q -p no:cacheprovider` | 25 passed in 42.96 s |
| `pytest -q -p no:cacheprovider` | 191 passed, 125 subtests passed in 174.98 s |
| `python steps/step18_theta_interface/check_golden.py` | 3/3 exact geometry, UV, material and component fingerprints match |

The audit was made against `src/domain/theta.py`, `src/modeling/theta.py`,
`src/pipeline/theta.py` and tests directly. See README hardening section for
the findings and post-change gate.
