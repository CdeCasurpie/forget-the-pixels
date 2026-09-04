#!/bin/bash
while pgrep -f "download_custom_route_pano.py" > /dev/null; do
    sleep 2
done

ssh cesar.perales@khipu "scancel -u cesar.perales"
ssh cesar.perales@khipu "rm -rf ~/tesis_colmap/gsv_custom_native_pano; mkdir -p ~/tesis_colmap/gsv_custom_native_pano/images"

scp -r /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_pano_route/images/* cesar.perales@khipu:~/tesis_colmap/gsv_custom_native_pano/images/
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_pano_route/gps.csv cesar.perales@khipu:~/tesis_colmap/gsv_custom_native_pano/gps.csv

ssh cesar.perales@khipu "cat << 'EOF_SLURM' > ~/tesis_colmap/run_pano_custom.sh
#!/bin/bash
#SBATCH --job-name=pano_colmap
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=colmap_pano_log_%j.out

cd ~/tesis_colmap/gsv_custom_native_pano
export PATH=\"/home/cesar.perales/.conda/envs/colmap_env/bin:\$PATH\"

python ~/tesis_colmap/colmap-usage-for-khipu/parsers/manual_gps.py gps.csv

cat << 'EOF_PY' > run_pano.py
from pathlib import Path
from pycolmap.panorama import reconstruct, PanoramaReconstructionOptions, Matcher
import os

images = Path('images')
outputs = Path('.')
opts = PanoramaReconstructionOptions(
    matcher=Matcher.SEQUENTIAL,
    show_progress=True
)
print('Iniciando Pycolmap Panorama Reconstruct (Nativo)...')
recs = reconstruct(
    input_image_path=images,
    output_path=outputs,
    options=opts
)
EOF_PY

python run_pano.py

SPARSE_MODEL=\\\$(find . -name \"cameras.bin\" -printf \"%h\n\" | head -1)
if [ -n \"\$SPARSE_MODEL\" ]; then
    echo \"Iniciando Alineacion Global GPS...\"
    mkdir -p sparse_aligned
    colmap model_aligner \\
        --input_path \"\$SPARSE_MODEL\" \\
        --output_path sparse_aligned \\
        --ref_images_path geo_priors.txt \\
        --ref_is_gps 0 \\
        --alignment_type custom \\
        --alignment_max_error 3.0
fi
echo 'Completado!'
EOF_SLURM
cd ~/tesis_colmap && sbatch run_pano_custom.sh"
