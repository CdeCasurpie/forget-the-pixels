# 3D House Generation from Street View Images using Multi-View Diffusion & SDF/NeuS

This document evaluates the use of state-of-the-art multi-view diffusion models (Wonder3D, Zero123++, SyncDreamer) combined with SDF/NeuS extraction to generate 3D house models from limited Street View inputs (3-4 front views).

## 1. Hallucinating Unseen Parts (The Back of the House)

Since Street View only provides frontal perspectives, generating a complete 3D model requires the system to "hallucinate" the sides and back of the house. These models rely on large-scale generative priors to infer missing geometry and textures.

*   **Zero123++:** Acts as a base model for consistent multi-view diffusion, leveraging Stable Diffusion to understand relative camera transformations. It attempts to maintain global semantics but can struggle with high-uncertainty areas (like the back of a house), sometimes resulting in generic or blurred rear facades.
*   **SyncDreamer:** Uses a **synchronized multiview diffusion** approach with a 3D-aware feature attention mechanism. It correlates features across different views to ensure that the hallucinated unseen parts remain geometrically and color-consistent with the input view. 
*   **Wonder3D:** Employs a **cross-domain diffusion model** that generates multi-view normal maps alongside color images. Enforcing information exchange across views and modalities through cross-domain attention produces high-fidelity, consistent geometry. This makes Wonder3D particularly strong at guessing structural elements (like roofs and walls) for the back of the house, even if the exact texture is inferred.

**Challenges & Mitigations:** The main issue with hallucinations is structural outliers (e.g., unexpected holes, warped textures). When applied to architectural models, inconsistencies can break the geometry. Emerging techniques (such as those used in *HouseCrafter*) or multi-view continuity constraints can help ensure the transition between the known front and hallucinated back is smooth and physically plausible.

## 2. SDF / NeuS Extraction for 3D Houses

Extracting a clean 3D architectural mesh requires precise surface reconstruction. 

*   **Why NeuS/SDF over NeRF?** Standard NeRFs use volume density, which can result in foggy or noisy meshes. NeuS (Neural Implicit Surfaces) represents surfaces as the zero-level set of a Signed Distance Function (SDF). This yields superior, clean, and manifold meshes suitable for flat walls, sharp corners, and 3D architecture.
*   **Pipeline Integration:** The generated multi-view images (from Wonder3D, Zero123++, etc.) are used as inputs for the NeuS reconstruction process. 
*   **Geometric Guidance:** Wonder3D's inclusion of multi-view normal maps provides a significant advantage here. Feeding these normal maps into the SDF extraction pipeline drastically improves the geometric accuracy and surface smoothness of the house compared to using RGB images alone.

## 3. Hardware Requirements (HPC Cluster)

The models evaluated have distinct VRAM requirements for **inference** (generating the views and extracting the mesh).

*   **Zero123++:** Very lightweight, requiring only about **~5 GB of VRAM**. It can comfortably run on lower-end GPUs.
*   **SyncDreamer:** More memory-intensive, requiring at least **10 GB of VRAM** for reduced settings, though 16GB+ is recommended for optimal quality.
*   **Wonder3D:** Requires **12 GB to 14 GB of VRAM** for smooth local inference.
*   **NeuS Extraction:** Typically requires **10-16 GB of VRAM** depending on the resolution and batch size of the optimization process.

**HPC Recommendation:** For an HPC cluster, a single node equipped with an NVIDIA RTX 3090, RTX 4090 (24GB VRAM), A10G (24GB VRAM), or A100 is highly recommended. 24GB of VRAM provides a comfortable overhead to run the diffusion model and the subsequent NeuS extraction pipeline seamlessly without out-of-memory (OOM) errors.

## 4. Open-Source Availability

All evaluated tools are widely available for research and commercial exploration:

*   **Zero123++:** Open source, distributed under the Apache-2.0 license.
*   **SyncDreamer:** Open source (available on GitHub).
*   **Wonder3D:** Open source (available on GitHub).
*   **NeuS / SDFusion:** The foundational codebases for NeuS and various SDF-based extraction methods are fully open source and actively maintained by the 3D vision community.
