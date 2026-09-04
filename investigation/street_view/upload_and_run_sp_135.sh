#!/bin/bash
ssh cesar.perales@khipu "scancel -u cesar.perales"
ssh cesar.perales@khipu "rm -rf ~/tesis_colmap/gsv_custom_sp_135; mkdir -p ~/tesis_colmap/gsv_custom_sp_135/images"

scp -r /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/images/* cesar.perales@khipu:~/tesis_colmap/gsv_custom_sp_135/images/
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/street_view/data_custom_route/gps.csv cesar.perales@khipu:~/tesis_colmap/gsv_custom_sp_135/gps.csv

ssh cesar.perales@khipu "cat << 'EOF_SLURM' > ~/tesis_colmap/run_sp_135.sh
#!/bin/bash
#SBATCH --job-name=sp_135
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --time=03:00:00
#SBATCH --output=colmap_sp_135_log_%j.out

cd ~/tesis_colmap/gsv_custom_sp_135
export PATH=\"/home/cesar.perales/.conda/envs/colmap_env/bin:\$PATH\"

rm -f database.db
rm -rf sparse

echo 'Generando geo_priors.txt desde gps.csv...'
python ~/tesis_colmap/colmap-usage-for-khipu/parsers/manual_gps.py gps.csv

cat << 'EOF_PY' > run_hloc.py
from pathlib import Path
from hloc import extract_features, match_features, reconstruction
from hloc.utils import database
import os

images = Path('images')
outputs = Path('.')
sfm_pairs = outputs / 'pairs-sequential.txt'
sfm_dir = outputs / 'sparse'

# Configuración de SuperPoint + LightGlue
feature_conf = extract_features.confs['superpoint_aachen']
matcher_conf = match_features.confs['superpoint+lightglue']

print('Extrayendo SuperPoint...')
features = extract_features.main(feature_conf, images, image_list=None, feature_path=outputs)

print('Generando pares secuenciales (Overlap 10 para vistas superpuestas)...')
import glob
img_list = sorted([os.path.basename(p) for p in glob.glob('images/*.jpg')])
with open(sfm_pairs, 'w') as f:
    for i in range(len(img_list)):
        for j in range(1, 11):
            if i + j < len(img_list):
                f.write(f'{img_list[i]} {img_list[i+j]}\n')

print('Emparejando con LightGlue...')
matches = match_features.main(matcher_conf, sfm_pairs, features=features, matches=outputs)

print('Triangulando (Mapping)...')
camera_params = '212.08,212.08,512,512'
reconstruction.main(
    sfm_dir,
    images,
    sfm_pairs,
    features,
    matches,
    camera_mode=pycolmap.CameraMode.SINGLE,
    camera_model='PINHOLE',
    camera_params=camera_params,
    min_match_score=0.1
)
EOF_PY

# Ajustar script run_hloc.py para evitar el error de pycolmap import no declarado:
sed -i '4i import pycolmap' run_hloc.py

python run_hloc.py

SPARSE_MODEL=\\\$(find sparse/0 -name \"cameras.bin\" -printf \"%h\n\" | head -1)
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
cd ~/tesis_colmap && sbatch run_sp_135.sh"
