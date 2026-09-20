# Source Code Architecture

The `src/` directory contains the core engine of the `forget-the-pixels` project. It is strictly divided into two distinct hemispheres, as defined in `ARCHITECTURE.md`.

## 1. Perception & Reconstruction Pipeline (Computer Vision)
These modules are responsible for acquiring Google Street View (GSV) panoramas, rectifying them, and using Machine Learning models (like MobileSAM) to extract facade segmentations and semantic boundaries.

- **`gsv_acquisition/`**: GSV panorama downloading and metadata parsing.
- **`datasets/`**: Standardization into the `ReconstructionPackage` format.
- **`multiview_input/`**: Data models for multi-camera ray observations.
- **`camera_selection/`**: Scoring algorithms (visibility cones, parcel adjacency) to select the best GSV cameras for a given lot.
- **`geometry_projection/`**: Translating between 3D world coordinates, 2D spherical equirectangular, and rectilinear planar projections.
- **`facade_observations/` & `facade_segmentation/`**: SAM/Mask2Former logic for identifying openings (windows/doors) and roof lines.
- **`structural_estimation/` & `height_estimation/`**: Fusing multiple camera rays to solve for the true metric height and floor counts of buildings.

## 2. Geometric Procedural Synthesis Pipeline (Modeling)
These modules define the rule-based, programmatic generation of 3D architectural meshes. They have **zero dependencies** on the CV/ML pipeline, taking pure typed inputs (contracts) and returning 3D meshes (GLB/OBJ).

- **`domain/`**: Pure data schemas (Pydantic/Dataclasses) such as `BuildingSpecification`, `SitePlan`, and `MassSpec`.
- **`cadastral_geometry/`**: 2D Shapely logic for manipulating parcel polygons and defining street exposures.
- **`procedural_modeling/`**: The core grammar engine. Generates Boolean intersections for footprints (`boundaries.py`, `exposure.py`), populates facades with ornaments (`grammar.py`), and constructs standard topological assemblies (`mesh_builder.py`).
- **`texturing/`**: Management of the PBR material vocabulary and texture atlas mapping.
- **`exporters/`**: Serialization into `.obj` (Z-up) or `.glb` (Y-up, PBR standard) formats.
- **`pipeline/`**: The orchestration interface that connects the two hemispheres, e.g., `reconstruct_building(...)`.
