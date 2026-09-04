# TRELLIS.2 Parameter Tuning Guide for Architectural Generation

This guide analyzes the advanced hyperparameters of Microsoft's TRELLIS.2 3D generation model (based on the Structured LATent, or SLAT, architecture) and provides concrete recommendations to eliminate organic, "melted" artifacts when generating rigid architecture and buildings.

## 1. Deep Dive into TRELLIS.2 Parameters

TRELLIS uses a multi-stage flow-matching / diffusion process. The parameters control how the model navigates the latent space across its three primary generation stages.

### Stage 1: Sparse Structure Generation
This stage creates the foundational "skeleton" or bounding geometry of the object using a Sparse 3D VAE.
*   **Guidance Strength:** Mathematically acts as Classifier-Free Guidance (CFG). It dictates how strongly the generated geometry vector is pushed away from an unconditional "average" shape toward the specific input image or text.
*   **Guidance Rescale:** High guidance can cause vectors to overshoot, causing "over-saturation" artifacts or broken geometry. Rescale mathematically normalizes the magnitude of the guided step back to a stable distribution.
*   **Sampling Steps:** The number of Euler/ODE solver steps used to denoise the structure. Higher steps mean a more precise approximation of the flow trajectory, reducing mathematical errors.
*   **Rescale T (Temperature/Time Rescale):** Adjusts the timestep scheduling curve. It can concentrate sampling steps in the critical early or late phases of the noise schedule.

### Stage 2: Shape Generation (Shape SLAT)
This stage fleshes out the sparse skeleton into a dense surface geometry.
*   **Same Parameters:** Here, they control the *surface details* rather than the global bounding box.

### Stage 3: Material Generation (Texture SLAT)
This stage wraps the shape in textures, generating color and material properties.
*   **Same Parameters:** Control adherence to the requested color palette and surface material (e.g., concrete, glass).

### Global Parameters
*   **Resolution:** The 3D grid resolution (e.g., 512³, 1024³) for the latent space. Higher resolution means smaller voxels.
*   **Decimation Target:** A post-processing threshold. TRELLIS generates a high-poly mesh (often via isosurface extraction). Decimation reduces the triangle count to this target number.

---

## 2. Fixing the "Melted" Look: Architectural Tuning Recommendations

Buildings require strict, planar, and rigid geometry. The "melted wax" look occurs when the model is given too much creative freedom (allowing organic hallucinations) or when grid resolution/polygon counts are mismatched with the desired output.

### Stage 1: Sparse Structure (Enforcing the Grid)
To force blocky, rigid shapes, the model must absolutely trust your input over its own organic priors.
*   **Guidance Strength:** **HIGH (8.5 - 10.0)**. Force the model to strictly adhere to the prompt/image so it doesn't default to an organic shape.
*   **Guidance Rescale:** **Moderate (0.6 - 0.7)**. Essential here to prevent the high Guidance Strength from causing structural collapse or floating artifacts.
*   **Sampling Steps:** **HIGH (50+)**. Architectural foundations need high precision.

### Stage 2: Shape Generation (Flattening the Surfaces)
This is where the "melting" usually happens. If guidance is too low here, the model attempts to "smooth" or add creative bumps to the walls.
*   **Guidance Strength:** **HIGH (7.5 - 9.0)**. You want the Shape stage to rigidly respect the blocky Sparse Structure. Do not let it hallucinate organic curves.
*   **Guidance Rescale:** **Moderate (0.5)**.
*   **Sampling Steps:** **Medium-High (30 - 40)**.

### Stage 3: Material Generation
*   **Guidance Strength:** **Low to Moderate (2.0 - 4.0)**. Too high guidance in textures can cause noisy, high-contrast visual artifacts that look like dirt or melting textures.

### Global Tweaks for Architecture
*   **Decimation Target:** **LOWER IT**. Counterintuitively, a very high polygon count allows for the tiny micro-variations that look like melted, wobbly walls. Lowering the decimation target (e.g., targeting fewer polygons) forces the mesh extractor to merge small variations into larger, flat geometric planes—which is exactly what architecture needs.
*   **Resolution:** **HIGH (1024 or 1536)**. Low resolution means the voxels are large. When a mesh is extracted from large voxels, straight edges become aliased or smoothed out into blobs. High resolution ensures sharp 90-degree corners can be accurately represented before decimation.

> **Summary for Architecture:** High Resolution + High Guidance (Stages 1 & 2) + Lower Decimation Target = Rigid, Blocky Buildings.
