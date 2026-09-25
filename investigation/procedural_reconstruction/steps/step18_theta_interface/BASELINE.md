# Step 18 baseline

Branch: `step18-theta-interface`, created from main `357a9bad89fd4d6243dc80ce18f00c4986095c49`.
The peeled `grammar-v1.0` tag points to that commit. Its annotated tag object is
`97a6338cd4447ca11d5386e93fc265886ce71f7a`; neither is modified.

Command, from `investigation/procedural_reconstruction`:

```sh
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider
```

Before changes: 161 collected, one collection error, zero tests executed:
`tests/test_height_estimation.py` imported removed `split_strip`.
The current equivalent API is `split_vertical_strip`. Only the test import was
updated with an alias; no implementation or grammar change was needed.

After that repair: **166 passed, 125 subtests passed in 140.44s**.

Preexisting worktree changes were present in root README, modeling/grammar.py,
modeling/facade_program.py and Step16 api.py/static/index.html. Those are user
changes, not Step18 changes. Untracked data, batch outputs and source dumps are
also left untouched. Consequently this baseline describes the actual supplied
worktree, not a pristine checkout of the freeze. Frozen golden comparison must
be reported separately.
