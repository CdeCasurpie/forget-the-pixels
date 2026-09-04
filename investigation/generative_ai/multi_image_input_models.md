# State-of-the-Art Multi-View 3D Reconstruction Models for Architecture

This report evaluates open-source, locally runnable Generative AI models that take multiple unposed images (e.g., 2 to 6 images) as input and output 3D meshes or dense 3D representations. The focus is on models that avoid the hallucination issues of single-image models, prioritizing architectural and building accuracy.

## 1. Top Candidates for Unposed Multi-View Input

### MASt3R (Matching and Stereo 3D Reconstruction)
- **Overview:** Developed by NAVER LABS Europe, MASt3R is a foundation model for 3D vision that builds on DUSt3R. It predicts 3D point maps and dense local features directly from uncalibrated (unposed) image pairs or sets.
- **Why it fits:** It is fully feed-forward and requires no pre-calculated camera poses (Structure-from-Motion is implicitly handled). It grounds matching in 3D space, which makes it extremely robust for buildings where images might have extreme viewpoint changes.
- **Output:** Dense 3D point maps. Can be integrated into meshing pipelines (e.g., Poisson surface reconstruction) or used as a prior for 3DGS. 
- **Open-Source & Local:** Yes, code and weights are open-source and run locally on consumer GPUs.

### MVSplat (Multi-View 3D Gaussian Splatting)
- **Overview:** A feed-forward model that builds a cost volume via plane sweeping to predict 3D Gaussian primitives from sparse multi-view images in a single forward pass (approx. 22 fps).
- **Why it fits:** By using a cost volume, MVSplat grounds its predictions in actual multi-view geometry rather than just regressing depth, significantly reducing "floater" artifacts common in other models. 
- **Output:** 3D Gaussian Splatting representation. (Note: Converting 3DGS to a clean architectural mesh requires additional extraction steps, like SuGaR or marching cubes, which can sometimes produce noisy meshes compared to point clouds).
- **Caveat:** It typically expects known camera poses. To use it with *unposed* images, it must be paired with a pose estimator like MASt3R or DUSt3R.

### FreeSplatter & Sparse-View 3DGS Architectures
- **Overview:** Models like FreeSplatter use transformer-based encoder-decoders to directly predict 3D Gaussian primitives from sparse images, implicitly handling camera parameters.
- **Why it fits:** Designed explicitly to overcome the severe overfitting and background collapse of standard 3DGS when given only 2-6 views. They often use depth-guided regularization (monocular depth priors).
- **Output:** 3DGS. Again, mesh extraction is a secondary step.

### MeshLRM / Flex3D (Large Reconstruction Models)
- **Overview:** Recent progress has seen the rise of feed-forward LRMs that directly output high-density triangular meshes (MeshLRM) or can process an arbitrary number of input views (Flex3D).
- **Why it fits:** They combine generative priors with flexible reconstruction, meaning they can fill in minor missing details (e.g., a small occluded corner of a building) without wholesale hallucinating the back of the building like single-image models. MeshLRM outputs watertight meshes directly.

## 2. Evaluation for Architectural Accuracy

When reconstructing buildings, geometric accuracy (straight lines, planar walls, sharp corners) is more critical than organic textures.
1. **Geometry vs. Hallucination:** Single-image models use diffusion priors to guess unseen areas. Multi-view models constrain the output to the provided views. MASt3R is highly recommended here because its cost-volume and 3D matching approach strictly respects the geometry seen in the images.
2. **Mesh vs. Dense Representation:** 3DGS models (MVSplat, Sparse-view 3DGS) produce excellent visual renders but extracting crisp architectural meshes from Gaussians is still an active research problem (they tend to be bumpy). MASt3R's dense point maps can be meshed using traditional algorithms (like Poisson) which often yield cleaner walls if the point map is accurate.
3. **Pose Independence:** Since the input images are *unposed*, a model must implicitly handle pose. **MASt3R / DUSt3R** are the undisputed state-of-the-art for pose-free, multi-view 3D alignment. 

## 3. Recommended Pipeline

For local, open-source architectural reconstruction from 2-6 unposed images:
- **Option A (Most robust for Meshes):** Use **MASt3R** to process the unposed images. It will align them and generate a dense, accurate 3D point cloud. Use standard point-to-mesh algorithms (e.g., Open3D Poisson surface reconstruction) to generate the final building mesh.
- **Option B (Best for Visuals/Novel View):** Use **MASt3R** to estimate the poses and initial geometry, then feed those poses and images into **MVSplat** or a sparse-view 3DGS optimizer that uses depth-regularization to get a highly photorealistic dense representation.
