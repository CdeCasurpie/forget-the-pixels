# V4 Procedural Grammar Audit Report

## Overview
This report details the features lost in the transition from the legacy procedural grammar (`grammar.py`) to the new simplified V4 grammar (`v4_grammar.py`). The audit covers window details, facade composition, material diversity, roof features, and boundary details.

---

## A. Window & Opening Detail
The legacy grammar featured rich, layered window constructions that have been simplified into basic boxes in V4.

### Missing Features:
- **Deep Recesses & Reveals [Critical]**: Legacy calculated exact window inset depths, now reduced to a hardcoded depth.
- **Jambs [Important]**: Left and right inner frame pieces.
- **Head and Sill [Important]**: Top and bottom frame pieces.
- **Stone Surrounds [Nice-to-have]**: Projecting architectural stone borders (`opening_surround`, `opening_lintel`).
- **Mullions & Transoms [Important]**: Sub-divisions within the glass panel based on column/row configurations.
- **Interior Darkness Panels [Critical]**: Interior depth/darkness explicitly modeled.
- **Curtain Panels [Important]**: Curtains placed behind glass with vertical folds.
- **Balcony Windows [Important]**: Balcony slabs, complex railings (vertical/diamond patterns), and returns.

---

## B. Facade Composition
The legacy grammar applied compositional rules to break up large facades, all of which are absent in V4.

### Missing Features:
- **Plinth (Stone Base) [Critical]**: Base course generated at the bottom of the facade (`plinth`).
- **Floor Bands / Ornamented Ledger Boards [Important]**: Horizontal accent lines between floors (`floor_band`).
- **Pilasters [Important]**: Decorative vertical columns at the building edges (`corner_pilaster`).
- **Facade Projections [Important]**: Architectural massing like panels, frames, ledges, and curved canopies.
- **Exterior Stairs [Important]**: Complex straight or switchback exterior staircases.

---

## C. Material Diversity on Walls
Legacy grammar dynamically painted the facade using localized material bands.

### Missing Features:
- **Material Regions [Critical]**: Ability to map different materials to specific sub-regions/bands of a single wall.
- **Cladding [Important]**: Horizontal siding/joint lines explicitly modeled into the facade mesh (`cladding_joint`).
- **Dynamic Wall Materials [Important]**: Legacy detected concrete frames vs brick infill and adjusted geometry and material per section.

---

## D. Roof Features
The rooftop in legacy had multiple procedural elements to simulate mechanical and utility use.

### Missing Features:
- **Water Tanks [Critical]**: Cylindrical plastic water tanks with base platforms and structural ribs.
- **Corrugated Roof Sections [Important]**: Corrugated roof sheets with support posts.
- **Platform Detection [Important]**: Automatically detected utility platforms forming rooftop rooms with doors and caps.
- **Detailed Rebar Posts [Nice-to-have]**: Legacy spawned 2 thin, randomized-height rebars per corner; V4 uses simple, uniform thick posts.
- **Parapet Detailing [Important]**: Explicit `parapet_cap` elements over parapet walls.

---

## E. Boundary & Fence Details
Boundary generation was heavily reduced from a detailed multi-material assembly to basic extrusions.

### Missing Features:
- **Elaborate Gate Logic [Important]**: Detailed wood gates, metal gate flutes, and boundary posts.
- **Switchback Stairs / Garage Doors / Pedestrian Gates [Important]**: Highly articulated entry elements and gates compared to V4's basic horizontal paneling.
- **Staggered Mortar Joints [Nice-to-have]**: Procedural generation of staggered visible mortar on brick walls.
- **Boundary Cap [Important]**: Stone capping placed on top of boundary walls.
- **Garden Elements [Nice-to-have]**: Procedural generation of planters, planting soil, and foliage/shrubs placed around the boundary.

---

## Conclusion
The V4 grammar represents a significant regression in geometric detailing, material assignment precision, and architectural ornamentation. While it correctly implements structural massing and basic openings, restoring the *Critical* and *Important* features listed above is necessary to match the visual fidelity of the legacy procedural generator.
