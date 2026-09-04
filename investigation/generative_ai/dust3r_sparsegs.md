# Investigation: 3D Reconstruction from Sparse Uncalibrated Images

## Overview
Reconstructing a single building from 3-4 uncalibrated Street View images requires methods capable of handling missing camera poses (intrinsics/extrinsics) and extreme sparsity. We evaluated **DUSt3R** and **Sparse-view Gaussian Splatting (PixelSplat, SparseGS)** for this specific scenario.

## 1. DUSt3R (Dense and Unconstrained Stereo 3D Reconstruction)
DUSt3R treats 3D reconstruction as a pointmap regression problem rather than using traditional feature matching, making it highly robust for uncalibrated, "in-the-wild" images.

*   **Capabilities (3-4 images):** Excellent. It uses a global alignment strategy to bring all pairwise pointmaps into a common 3D reference frame. It operates entirely without camera calibration or pose priors.
*   **Output (Mesh/Point Cloud):** It natively outputs a **dense point cloud**, not a watertight mesh. To obtain a clean mesh, a post-processing step (like Poisson surface reconstruction via Open3D, MeshLab, or community tools like `DUSt3R-Mesh`) is required. Point cloud cleaning (e.g., in CloudCompare) is highly recommended before meshing.
*   **Open Source & Weights:** The code is open source. However, the pre-trained weights are distributed under the **CC BY-NC-SA 4.0 license**, restricting their use to **non-commercial purposes only**.
*   **HPC Runnability:** Yes, it is GPU-intensive and standard PyTorch-based, meaning it will run efficiently on an HPC cluster.

## 2. Sparse-view Gaussian Splatting (PixelSplat, SparseGS)
While Gaussian Splatting yields high-quality rendering, standard models and even sparse-view variants heavily rely on known camera poses.

*   **PixelSplat:**
    *   Designed for fast, feed-forward 3D radiance field reconstruction from image pairs.
    *   **Limitation:** It generally expects posed images or a known stereo baseline framework, meaning raw uncalibrated Street View images would pose a significant challenge without a prior Pose Estimation step.
    *   **Open Source:** Code is under the MIT license, but pre-trained weights usually require training on standard datasets (like RealEstate10k or ACID).
*   **SparseGS:**
    *   Specifically engineered for sparse views (e.g., 3-12 images), addressing "floaters" and "background collapse" using depth priors.
    *   **Limitation:** Like standard 3DGS, it **requires camera poses**. It cannot directly process uncalibrated images.
    *   **Open Source:** Yes, open-source on GitHub, but typically users must train the pipeline themselves on their specific datasets to generate the ply models (weights).

## 3. Alternative Recommendations for Uncalibrated 3DGS
If the goal is to leverage Gaussian Splatting directly on uncalibrated images without using DUSt3R as an intermediate pose-estimator, newer methods have emerged:
*   **StructSplat:** A recent framework explicitly designed to operate on uncalibrated images, bypassing the need for Structure-from-Motion (SfM) or known poses.
*   **Splatt3R:** A zero-shot feed-forward model that reconstructs 3D Gaussian Splats from uncalibrated image pairs.

## Conclusion & Recommendation
For the specific task of generating a 3D model of a single building from 3-4 **uncalibrated** images:
1.  **DUSt3R** is the most reliable current approach for uncalibrated pose-free geometry. You can extract the point cloud, clean it, and mesh it using standard 3D tools. Keep in mind the non-commercial license of the weights.
2.  **PixelSplat / SparseGS** will struggle directly due to the lack of camera poses. You would either need to use DUSt3R to estimate the poses first and feed them into SparseGS, or switch to an uncalibrated 3DGS model like **StructSplat**.
