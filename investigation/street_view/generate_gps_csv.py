import json
import csv
import os

metadata_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data/imagenes_gsv_custom/metadata.json"
csv_file = "/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/gps.csv"

with open(metadata_file, "r") as f:
    data = json.load(f)

with open(csv_file, "w", newline='') as f:
    writer = csv.writer(f)
    writer.writerow(["filename", "lat", "lon", "alt"])
    
    # The cubemap images were split into 8 views per panorama.
    # The panorama filenames were something like "000_YTjFREHWWf3WLOhibSFgkA.jpg"
    # The perspective ones are "000_YTjFREHWWf3WLOhibSFgkA_view0.jpg"
    for pano_file, meta in data.items():
        base_name = pano_file.split(".")[0]
        lat = meta["lat"]
        lon = meta["lon"]
        # Dummy alt of 150m, since all street level is roughly flat relative to drone, 
        # or we can just use 0. COLMAP's model_aligner handles it.
        alt = 100.0 
        for i in range(8):
            view_filename = f"{base_name}_view{i}.jpg"
            writer.writerow([view_filename, lat, lon, alt])

print(f"Generated {csv_file}")
