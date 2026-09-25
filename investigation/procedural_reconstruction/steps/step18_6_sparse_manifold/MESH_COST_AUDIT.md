# Geometry cost audit — grammar-v1.1-dev

Baseline source: a29df7b, parent of this branch. Historical tag grammar-v1.0:
97a6338cd4447ca11d5386e93fc265886ce71f7a. Theta values/resolver are architectural
inputs; tessellation and runtime batching are materialization concerns.

| Constructor / code | Representation and cost | Silhouette / shell cut | Decision |
|---|---|---|---|
| mesh_builder.panel / _rectilinear_cells | 0.5 m Cartesian cells; 4 cap triangles/cell plus sides | No silhouette benefit from distance cuts | Remove automatic refinement; use polygon boundaries and holes |
| mesh_builder.solid | Polygon extrusion, earcut caps, swept outer/inner rings | Real volume | Retain; audit disconnected clipping and ring connectivity |
| mesh_builder.box | 12 triangles uncut; chamfer adds arris ring | Architectural blocks | Retain; one closed component per connected solid |
| mesh_builder.beam | 32 triangles, 18 positions, 8 cylinder sides | Thin rods/rails | Reduce repeats through budget; preserve major rails |
| mesh_builder.foliage | 100 triangles/default ellipsoid | Secondary silhouette | Coarser sampling at BLOCK; retain plant placement |
| grammar._emit_wall_shells | Whole wall split by every frame, material and opening axis | Holes/recess structural; shallow frame overlay | Sparse base plus local independently closed overlays |
| grammar._cell_finish | 15 mm brick inset, concrete strips, 120 mm ground recess | Ground recess structural | Preserve dimensions; frame separated, actual recess bands remain |
| grammar.opening / prefabs.build_opening | Frames, reveals, glass, backing, rods, curtains | Opening true hole, trim overlay | Preserve hole; simplify microgeometry with LOD |
| prefab slim_frame | Extruded ring currently hits dense panel path | Frame overlay | Same sparse polygon-with-hole algorithm |
| prefabs.sign_letters | One box/active glyph pixel, 12 triangles each | Negligible silhouette | Disable at BLOCK, retain sign box |
| prefabs curtain_fold | One box/fold every 55 mm STREET | Behind glazing | Disable BLOCK, coarsen STREET |
| prefabs roller/louver/gate seams | One box/slat or seam | Superficial | Solid backing stays; omit repeats BLOCK |
| prefabs_facade panel/frame/ledge/canopy | Boxes or curved polygon extrusion | Overlay, no wall cuts | Keep independent solids |
| cornice / sill_band / pilaster | Stepped boxes, sometimes chamfer | Architectural relief | Keep major silhouette; no base tessellation |
| balcony / gallery / _balustrade | Slab, rail, many boxes, posts | Major projecting silhouette | Preserve slabs/major rails; coarser bars |
| awning / bay_window / eave | Affine roof slab, boxes, repeated rafters | Major silhouette | Preserve; repeats may be reduced |
| shutter / downpipe / sign_box | Leaves, repeated slats/clamps/letters | Leaves and sign architectural | Keep leaves/body; suppress microdetail BLOCK |
| facade_program / composition | Resolves openings, material zones, projections | No triangles directly | Architecture unchanged by sparse materializer |
| modeling.theta | Resolves controls, creates facade/roof/site assemblies | Authoritative identity | Same resolved architecture hashes before/after |
| roofscape.build_roof | Slabs, pitched closures, parapet rings | Major roof silhouette | Retain sparse extrusion and metric UVs |
| prefabs_roof water_tank/tank_elevated | Cylinder, ribs, stand | Tank/stand architectural | Preserve classes and position; ribs microdetail |
| antenna/laundry/rebar | Repeated beams | Thin secondary details | Keep main silhouette; budget repeated rods |
| hvac/duct/skylight/caseta/bulkhead | Boxes + cylindrical fan + repeated louvers | Major props architectural | Keep boxes; simplify louvers/corrugations BLOCK |
| boundaries.generate_boundaries | Determines fence/gate runs | No geometry directly | Preserve architectural decisions |
| site.draw_fence | Base/cap, bars, gates/flutes | Major site silhouette | Preserve runs/gates; coarsen bars, omit flutes BLOCK |
| site.plant_garden | Planters, soil and two foliage tiers per placement | Nuisance vegetation | Preserve deterministic placement; coarser foliage |
| detail.DetailBudget | Repeat density, not true tessellation budget | Must preserve architecture | BLOCK/STREET/CLOSE_UP control microgeometry only |
| glb_exporter | One node per authoring component; splits position/UV seams | No source geometry change | Add opt-in runtime grouping by semantic/material |
| glb_incremental | Copies JSON/BIN and rewrites aggregate per house | No geometry change | Measure after mesh fixes; keep pipeline scope limited |
| validation | Geometric containment + per-part indexed edge incidence | Closed connected components | Retain, plus sparse complexity/coverage invariants |

## Structural shell / overlay / material detail

True holes and large recesses modify the shell. Beams, columns, pilasters,
cornices, sills, frames, sunshades and shallow relief are independently closed
solids. Intersection within an architectural assembly is permitted. Paint is a
local thin coating, clipped around holes, never a global Cartesian cut. Tiny
mortar, weathering and joints belong to the material where practical; this
iteration does not invent new texture maps or remove major architectural forms.

UVs remain metric corner attributes. A long UV span is not a reason to subdivide
the source positions. Runtime vertices may split for UV seams as before.

## Export and PBR

The exporter caches PBR materials per material index within one building.
Separate building exports embed their own images; append_glb offsets and appends
images/materials without cross-building deduplication. Textured blocks therefore
can duplicate baseColor/normal/ORM payloads. Benchmarks use library=False to
isolate geometry. Runtime batching reduces nodes, not texture duplication.
Texture deduplication is a separate remaining export opportunity.

## Baseline validity

Full pre-change suite: 205 tests and 125 subtests passed (244.97 s).
The five manual examples have zero topology violations. Real cadastral fixtures
are also measured, including pre-existing defects; validators are not silenced
or weakened to make those cases pass. See per-case validation JSON and reports.

Timing measurements are wall-clock observations, not CPU-isolated laboratory
results. Initial baseline jobs overlap, so triangle/node/byte counts are the
strong comparisons; timing and process high-water RSS require that qualification.
