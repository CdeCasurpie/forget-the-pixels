# Feed-Forward 3D Generative Models Investigation

## Executive Summary
This report evaluates four state-of-the-art fast feed-forward 3D generative models (TripoSR, CRM, OpenLRM, LGM) based on their ability to run locally on an HPC cluster and their capacity to handle outdoor scenes—specifically isolating a single house from 3-4 Street View images.

## HPC Viability (Linux, NVIDIA GPUs, Open-Source)
**Verdict: Highly Viable**
All four models meet the criteria for local execution on an HPC cluster. 
- **Frameworks:** Built on PyTorch and require CUDA.
- **Weights:** Open-source weights are readily available on Hugging Face (TripoSR and CRM have permissive licenses; OpenLRM has non-commercial licenses).
- **Hardware:** They are heavily optimized for NVIDIA GPUs, requiring anywhere from 6GB to 24GB+ VRAM depending on the specific model and target resolution.

## Model Capabilities & Input (1 to 4 images)
These models are primarily designed as **Single-Image-to-3D** pipelines, not multi-view reconstructors. 
- **TripoSR:** Single image in, 3D mesh out (< 0.5s).
- **CRM:** Single image in, generates 6 orthographic views internally via diffusion, then outputs a mesh (~10s).
- **OpenLRM:** Single image in, predicts a NeRF/mesh.
- **LGM:** Single image in, generates multi-view internally, outputs 3D Gaussians (~5s).

*Note:* Natively feeding 3-4 arbitrary, uncalibrated real-world photos (like Street View) as a joint input is not their standard use case. They rely on internal multi-view diffusion models to hallucinate the unseen views from a single input image.

## Outdoor Scenes & Street View Applicability
**Verdict: Strictly Limited to Centered, Object-Centric Data**
None of these models are natively equipped to handle unconstrained outdoor scenes. They are designed for isolated objects.

1. **Training Data Bias (Objaverse):** All of these models heavily rely on datasets like Objaverse, which consist of isolated, synthetic, centered objects with clean backgrounds and canonical scaling/lighting.
2. **The "Street View House" Challenge:**
   - **Backgrounds & Occlusions:** Street View images have complex backgrounds, skies, foreground trees, and cars. Feed-forward models require the subject to be cleanly segmented (typically with an alpha matte).
   - **Domain Gap:** Real-world architecture under natural sunlight has a massive domain gap from synthetic 3D assets. The models will likely hallucinate poorly or produce blobby, toy-like geometry.
   - **Perspective:** Street View images are typically taken from ground level with strong perspective distortion. These models often assume a canonical or slight elevation viewing angle.
3. **Workaround Feasibility:** To use these models for a house, one would have to meticulously segment the house from the background in a single image. The unobserved sides of the house would be purely hallucinated based on Objaverse priors, resulting in highly inaccurate real-world representations.

## Conclusion
While TripoSR, CRM, OpenLRM, and LGM are exceptionally fast and run perfectly on local HPCs with NVIDIA GPUs, they are **object-centric models**. They are severely ill-suited for accurate reconstruction of a house from 3-4 Street View images due to their single-image nature and Objaverse-biased training. For reconstructing real-world architecture from sparse Street View images, few-shot NeRFs (e.g., FreeNeRF, SparseNeRF) or sparse 3D Gaussian Splatting approaches with depth priors are much more appropriate than feed-forward object generators.
