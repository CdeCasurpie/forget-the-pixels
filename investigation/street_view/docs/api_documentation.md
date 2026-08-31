# Comprehensive Report on Google Street View Data Acquisition for City-Scale Reconstruction

## 1. Introduction
This report outlines the methods for programmatically downloading Google Street View (GSV) data, specifically focusing on equirectangular panoramas, GPS/pose metadata, and depth maps. This data is foundational for computer vision tasks such as city-scale 3D reconstruction, Neural Radiance Fields (NeRFs), and 3D Gaussian Splatting.

## 2. Official Google Maps Street View APIs
Google provides official avenues for accessing GSV data, primarily through the Google Maps Platform.

### 2.1 Street View Static API & Metadata API
- **Capabilities**: The Static API delivers perspective-based JPEG images (flat, cropped) generated from specific camera parameters (field of view, heading, pitch). The Metadata API returns JSON containing the panorama ID, snapped coordinates (latitude/longitude), capture date, and copyright information.
- **Limitations**: **The official API does not provide full 360° equirectangular panoramas or depth maps.** Reconstructing an equirectangular image by requesting and stitching multiple overlapping perspective crops is not only technically suboptimal (due to projection distortions) but also violates Google's Terms of Service.
- **Costs**: Access requires a Google Cloud billing account and an API key. After exhausting the $200 monthly free tier, the Street View Static API costs approximately $7.00 per 1,000 requests. Metadata requests are typically free but still require authentication.

## 3. Open-Source Tools for Research & Computer Vision
Because the official APIs do not yield the equirectangular source files or structural depth data required for most 3D reconstruction pipelines, the research community relies on open-source Python libraries that interface with undocumented internal Google endpoints.

### 3.1 `streetlevel` (Highly Recommended)
- **Overview**: A robust, actively maintained Python library designed to fetch panoramas and metadata from multiple street-level imagery services, including Google Street View.
- **Capabilities**: 
  - Downloads full, stitched equirectangular panoramas.
  - Fetches precise metadata, including accurate GPS coordinates, capture dates, and camera pose (yaw, pitch, roll).
  - Native support for downloading and parsing Google's proprietary depth map format (base64-encoded structural data), converting it into usable distance arrays.
- **Costs**: Free (does not require an API key).
- **Limitations**: As it relies on internal endpoints, it is vulnerable to breaking if Google alters its service infrastructure.

### 3.2 `streetview` (by robolyst)
- **Overview**: A lightweight Python module for retrieving current and historical street view imagery.
- **Capabilities**: Excellent for converting GPS coordinates to panorama IDs and downloading raw image tiles.
- **Limitations**: It lacks native, built-in support for parsing depth maps and is generally less feature-rich for advanced CV needs compared to `streetlevel`.

### 3.3 `streetget`
- **Overview**: A tool frequently mentioned in older literature specifically designed for bulk downloading and handling depth maps for large datasets.
- **Limitations**: It is less actively maintained and less user-friendly to set up than the modern `streetlevel` library.

## 4. Integration into a City-Scale CV Pipeline
A standard computer vision pipeline for city-scale reconstruction utilizing GSV data typically follows these steps:

1. **Sampling & Metadata Collection**: 
   - Define a geographic bounding box or trajectory.
   - Use `streetlevel` to query panorama IDs within the defined area.
   - Extract GPS coordinates and 6-DoF pose data (heading, pitch, roll) to establish a global reference frame, which is critical for Structure-from-Motion (SfM) initialization.
2. **Data Acquisition**:
   - Concurrently download the high-resolution equirectangular panoramas and their corresponding depth maps.
3. **Preprocessing**:
   - Use depth maps to provide geometric priors and to segment/filter out dynamic objects (e.g., cars, pedestrians) that confuse multi-view stereo algorithms.
   - If utilizing standard feature-matching frameworks (like COLMAP) that struggle with heavy spherical distortion, convert the equirectangular images into 6-face perspective cubemaps.
4. **Reconstruction**:
   - Feed the poses, preprocessed images, and depth priors into optimization frameworks (e.g., NeRFs, 3D Gaussian Splatting, or traditional SfM/MVS) to generate the city-scale 3D model.

## 5. Conclusion & Recommendations
- For **commercial applications** or simple visual integration requiring strict Terms of Service compliance, use the **Google Street View Static API**.
- For **academic research and city-scale 3D reconstruction pipelines**, the **`streetlevel` Python library** is the definitive choice. It provides the necessary equirectangular imagery, exact camera poses, and depth maps required to achieve state-of-the-art results without the high costs and formatting limitations of the official API.
