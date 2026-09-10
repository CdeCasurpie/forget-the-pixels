#!/bin/bash
set -e
echo "[INFO] Copiando scripts a Khipu..."
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/lotes_projection/khipu/run_sam.py khipu:/home/cesar.perales/lotes_generativos/scripts/
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/lotes_projection/khipu/job_sam_lotes.sh khipu:/home/cesar.perales/lotes_generativos/scripts/

echo "[INFO] Copiando JSON Metadata..."
scp /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/lotes_projection/crops_metadata.json khipu:/home/cesar.perales/lotes_generativos/

echo "[INFO] Copiando Nube de Imágenes (esto puede demorar un poco)..."
rsync -avz /home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/Lotes/images/ khipu:/home/cesar.perales/lotes_generativos/images/

echo "[INFO] Descargando pesos de MobileSAM en Khipu..."
ssh khipu "wget -nc -O /home/cesar.perales/lotes_generativos/weights/mobile_sam.pt https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt"

echo "[INFO] ¡Listo para lanzar el Job!"
