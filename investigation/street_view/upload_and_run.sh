#!/bin/bash

# Esperar a que el proceso de python termine (PID del task)
echo "Esperando a que termine la descarga local..."
while pgrep -f "download_custom_route.py" > /dev/null; do
    sleep 2
done
echo "Descarga terminada. Subiendo a Khipu..."

# Cancelar trabajos anteriores (el usuario lo pidió)
ssh cesar.perales@khipu "scancel -u cesar.perales"

# Crear directorio y subir
ssh cesar.perales@khipu "mkdir -p ~/tesis_colmap/gsv_custom_route/images"
scp -r /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/images/* cesar.perales@khipu:~/tesis_colmap/gsv_custom_route/images/
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/gps.csv cesar.perales@khipu:~/tesis_colmap/gsv_custom_route/gps.csv

# Crear el script de SLURM para el job de SuperPoint
ssh cesar.perales@khipu "cat << 'EOF_SLURM' > ~/tesis_colmap/run_sp_custom.sh
#!/bin/bash
#SBATCH --job-name=gsv_custom
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=colmap_sp_custom_log_%j.out

cd ~/tesis_colmap/gsv_custom_route
export PATH=\"/home/cesar.perales/.conda/envs/colmap_env/bin:\$PATH\"

echo 'Generando geo_priors.txt desde gps.csv...'
python ~/tesis_colmap/colmap-usage-for-khipu/parsers/manual_gps.py gps.csv

cat << 'EOF_HLOC' > run_hloc_seq.py
import sys, os
from pathlib import Path
from hloc import extract_features, match_features, reconstruction
import csv

images = Path('images/')
outputs = Path('hloc_outputs/')
outputs.mkdir(exist_ok=True)
sfm_pairs = outputs / 'pairs.txt'
sfm_dir = Path('sparse/0')
sfm_dir.mkdir(parents=True, exist_ok=True)

feature_conf = extract_features.confs['superpoint_aachen']
matcher_conf = match_features.confs['superpoint+lightglue']

image_list = []
with open('gps.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        image_list.append(row[0])

# Overlap = 25 (el usuario pidio 25)
overlap = 25
pairs = set()
for i in range(len(image_list)):
    for j in range(1, overlap + 1):
        if i + j < len(image_list):
            pair = tuple(sorted([image_list[i], image_list[i+j]]))
            pairs.add(pair)

with open(sfm_pairs, 'w') as f:
    for p in pairs:
        f.write(f\"{p[0]} {p[1]}\n\")
print(f\"Se generaron {len(pairs)} pares secuenciales.\")

features = extract_features.main(feature_conf, images, outputs)
matches = match_features.main(matcher_conf, sfm_pairs, features=features, matches=outputs / 'matches.h5')

reconstruction.main(sfm_dir, images, sfm_pairs, features, matches, image_list=image_list)
EOF_HLOC

echo 'Iniciando SuperPoint + LightGlue Secuencial...'
~/hloc_env_gpu/bin/python run_hloc_seq.py

SPARSE_MODEL=\\\$(find sparse/0 -name \"cameras.bin\" -printf \"%h\n\" | head -1)
if [ -n \"\$SPARSE_MODEL\" ]; then
    echo \"Iniciando Alineacion GPS...\"
    mkdir -p sparse/0_aligned
    colmap model_aligner \\
        --input_path \"\$SPARSE_MODEL\" \\
        --output_path sparse/0_aligned \\
        --ref_images_path geo_priors.txt \\
        --ref_is_gps 0 \\
        --alignment_type custom \\
        --alignment_max_error 3.0
fi
echo 'Completado!'
EOF_SLURM
cd ~/tesis_colmap && sbatch run_sp_custom.sh"

echo "¡Listo! El Job final ha sido enviado a Khipu."
