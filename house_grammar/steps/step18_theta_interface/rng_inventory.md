# RNG source inventory

Generated with `python steps/step18_theta_interface/audit_rng.py`.

| Code | Function | Call | Class | Pathway | Reason |
|---|---|---|---|---|---|
| src/modeling/facade_program.py:117 | resolve_family | rng.choice(pool) | THETA | V4 | Family or balcony/gallery/awning depth |
| src/modeling/facade_program.py:374 | _relief | rng.uniform(1.0, 1.3) | THETA | V4 | Family or balcony/gallery/awning depth |
| src/modeling/facade_program.py:380 | _relief | rng.uniform(0.9, 1.25) | THETA | V4 | Family or balcony/gallery/awning depth |
| src/modeling/facade_program.py:261 | _upper_openings | rng.uniform(0.75, 1.05) | THETA | V4 | Family or balcony/gallery/awning depth |
| src/modeling/facade_program.py:262 | _upper_openings | rng.random() | XI | V4 | Curtain presence/coverage; architectural opening unchanged |
| src/modeling/facade_program.py:262 | _upper_openings | rng.uniform(0.2, 0.55) | XI | V4 | Curtain presence/coverage; architectural opening unchanged |
| src/modeling/families.py:15 | apply_family | np.random.default_rng(spec.seed) | CONFIG | legacy_only | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/families.py:18 | apply_family | rng.choice(candidates) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/families.py:104 | apply_family | rng.integers(len(palette)) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/families.py:57 | apply_family | rng.choice(["wood_panel","metal_gate"]) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/families.py:70 | apply_family | rng.uniform(-0.15, 0.15) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/families.py:75 | apply_family | rng.choice(["vertical","grid","diamond"]) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/families.py:74 | apply_family | rng.choice([.25,.55,.85]) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:963 | generate_mesh | np.random.default_rng(spec.seed) | CONFIG | legacy_only | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/grammar.py:1182 | generate_v4_mesh | np.random.default_rng(spec.seed) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/grammar.py:785 | _roof_details_body | rng.uniform(0.6, 1.2) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:718 | _roof_details_body | rng.integers(len(candidates)) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:940 | _boundary_and_garden_body | rng.uniform(-0.035, 0.04) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:943 | _boundary_and_garden_body | rng.uniform(-0.09, 0.09) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:944 | _boundary_and_garden_body | rng.uniform(-0.09, 0.09) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/grammar.py:1280 | generate_v4_mesh | rng.random() | THETA | V4 | Shared architectural stream; facade services and cladding |
| src/modeling/grammar.py:1281 | generate_v4_mesh | rng.random() | THETA | V4 | Shared architectural stream; facade services and cladding |
| src/modeling/layout.py:87 | propose_building | np.random.default_rng(seed) | CONFIG | legacy_only | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/layout.py:89 | propose_building | rng.integers(len(palettes)) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/layout.py:109 | propose_building | rng.uniform(0.95, 1.05) | UNUSED | legacy_only | Not reached by V4; preserved for old API |
| src/modeling/massing.py:241 | generate_masses | np.random.default_rng(program.seed if seed is None else seed) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/massing.py:128 | _podium_tower | rng.uniform(2.0, 4.0) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:139 | _stepped_back | rng.uniform(2.2, 3.6) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:150 | _corner_accent | rng.uniform(4.0, 7.0) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:194 | choose_pattern | rng.choice([name for name, _ in options], p=weights / weights.sum()) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:114 | _front_rear | rng.integers(1, 3) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:124 | _podium_tower | rng.integers(1, 3) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:258 | generate_masses | rng.random() | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:109 | _front_rear | rng.uniform(0.38, 0.55) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:207 | _rooftop_addition | rng.uniform(0.25, 0.5) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/massing.py:210 | _rooftop_addition | rng.uniform(0.80, 0.95) | THETA | V4 | Mass pattern, split, setback or addition; never nuisance |
| src/modeling/materials.py:71 | appearance_for_style | np.random.default_rng(seed) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/materials.py:72 | appearance_for_style | rng.uniform(-.018, .018) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/mesh_builder.py:791 | foliage | rng.uniform(0.90, 1.10) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/prefabs_roof.py:220 | rebar_cluster | rng.uniform(0.55, 1.15) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/roofscape.py:179 | scatter_props | rng.permutation(len(grid)) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:214 | plan_roof | np.random.default_rng(resolve_seed(seed, lot_id, mass.id, "roof", "plan")) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/roofscape.py:214 | plan_roof | resolve_seed(seed, lot_id, mass.id, "roof", "plan") | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/roofscape.py:115 | _tile_surface | rng.uniform(2.4, 3.6) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:186 | scatter_props | rng.choice(kinds, p=probabilities) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:189 | scatter_props | rng.uniform(0, 360) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:190 | scatter_props | rng.uniform(0.88, 1.12) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:248 | plan_roof | rng.uniform(0.35, 0.75) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:220 | plan_roof | rng.random() | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:260 | plan_roof | np.random.default_rng(                     resolve_seed(seed, lot_id, mass.id, "roof", "props")                 ) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/roofscape.py:395 | _build_roof_body | np.random.default_rng(prop.seed) | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/roofscape.py:173 | scatter_props | rng.uniform(0, step) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:173 | scatter_props | rng.uniform(0, step) | THETA | V4 | Roof class/depth/parapet or significant rooftop object layout |
| src/modeling/roofscape.py:261 | plan_roof | resolve_seed(seed, lot_id, mass.id, "roof", "props") | CONFIG | V4 | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/roofscape.py:205 | scatter_props | rng.integers(0, 2**31 - 1) | XI | V4 | Seed for internal object detail, after object identity/layout chosen |
| src/modeling/site.py:155 | plant_garden | rng.uniform(0.30, 0.42) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/site.py:153 | plant_garden | rng.uniform(0, 0.3) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/site.py:154 | plant_garden | rng.uniform(0, 0.3) | XI | V4 | Foliage, rebar or small color variation; not massing |
| src/modeling/theta.py:571 | _rng | np.random.default_rng(int.from_bytes(digest[:8],"little")) | CONFIG | candidate | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/theta.py:364 | _composition | np.random.default_rng(0) | CONFIG | candidate | Seed/stream creation. Stream creation, not an architectural value; consumers classified separately |
| src/modeling/theta.py:603 | generate_resolved | _rng(nuisance.seed,f"roof/{roof.mass_id}/{prop.kind}/{prop.position}").integers(0,2**31) | XI | candidate | Only curtain/foliage/rebar streams; roof object identity explicit |
| src/modeling/theta.py:593 | generate_resolved | _rng(nuisance.seed,f"{f.edge_id}/curtain/{i}").uniform(.15,.55) | XI | candidate | Only curtain/foliage/rebar streams; roof object identity explicit |
