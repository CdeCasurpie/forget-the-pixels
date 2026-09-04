#!/bin/bash

echo "Esperando a que termine la descarga local..."
while pgrep -f "download_custom_route.py" > /dev/null; do
    sleep 2
done
echo "Descarga terminada. Subiendo a Khipu..."

ssh cesar.perales@khipu "scancel -u cesar.perales"
ssh cesar.perales@khipu "rm -rf ~/tesis_colmap/gsv_custom_sift; mkdir -p ~/tesis_colmap/gsv_custom_sift/images"

scp -r /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/images/* cesar.perales@khipu:~/tesis_colmap/gsv_custom_sift/images/
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/gps.csv cesar.perales@khipu:~/tesis_colmap/gsv_custom_sift/gps.csv

ssh cesar.perales@khipu "cat << 'EOF_SLURM' > ~/tesis_colmap/run_sift_custom.sh
#!/bin/bash
#SBATCH --job-name=gsv_sift
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=colmap_sift_custom_log_%j.out

cd ~/tesis_colmap/gsv_custom_sift
export PATH=\"/home/cesar.perales/.conda/envs/colmap_env/bin:\$PATH\"

echo 'Generando geo_priors.txt desde gps.csv...'
python ~/tesis_colmap/colmap-usage-for-khipu/parsers/manual_gps.py gps.csv

echo 'Extrayendo caracteristicas SIFT...'
colmap feature_extractor \
    --database_path database.db \
    --image_path images \
    --ImageReader.camera_model PINHOLE \
    --ImageReader.single_camera 1

echo 'Inyectando GPS priors a la base de datos...'
cat << 'EOF_PY' > inject_gps.py
import sqlite3
import csv
import os

conn = sqlite3.connect('database.db')
c = conn.cursor()
with open('gps.csv', 'r') as f:
    reader = csv.reader(f)
    next(reader)
    for row in reader:
        fname = row[0]
        lat = float(row[1])
        lon = float(row[2])
        alt = float(row[3])
        c.execute(\"UPDATE images SET prior_tx=?, prior_ty=?, prior_tz=? WHERE name=?\", (lon, lat, alt, fname))
conn.commit()
conn.close()
print('Priors inyectados con exito.')
EOF_PY
python inject_gps.py

echo 'Emparejamiento Secuencial estricto...'
colmap sequential_matcher \
    --database_path database.db \
    --SequentialMatching.overlap 25 \
    --SequentialMatching.loop_detection 0

echo 'Mapeo 3D...'
mkdir -p sparse
colmap mapper \
    --database_path database.db \
    --image_path images \
    --output_path sparse

SPARSE_MODEL=\\\$(find sparse/0 -name \"cameras.bin\" -printf \"%h\n\" | head -1)
if [ -n \"\$SPARSE_MODEL\" ]; then
    echo \"Iniciando Alineacion Global GPS...\"
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
cd ~/tesis_colmap && sbatch run_sift_custom.sh"

echo "¡Script de SIFT y GPS enviado a Khipu con exito!"
