# GIS & Photogrammetry Data (Lotes)

This directory contains the legacy datasets and intermediate files from the photogrammetry experiments, specifically for aligning drone point clouds, COLMAP sparse camera poses, and Cadastral Shapefiles.

## Scripts
The processing scripts for these datasets have been moved to `scripts/gis/` to separate logic from data:
- `align_lotes.py` / `align_2d_cv2.py`
- `check_camera_points.py`
- `extrude_lotes.py`
- `texture_lotes.py`

## Contents
- **shp_files/**: Cadastral polygon shapefiles for the test block in Barranco.
- **nube_sparse/ / nube_densa/**: COLMAP point clouds and camera poses.
- ***.obj / *.mtl**: Baked textured models from the alignment experiments.
