#!/bin/bash
#SBATCH --job-name=sam_generativo
#SBATCH --output=sam_gen_%j.out
#SBATCH --error=sam_gen_%j.err
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#SBATCH --mem=32G
#SBATCH --time=04:00:00

# INFO: Este script está diseñado para ejecutarse en Khipu usando SLURM.
# Requiere que se suban los siguientes archivos al nodo:
# 1. crops_metadata.json (generado en tu laptop con 'make export-crops')
# 2. Las fotos originales de tu dron (carpeta images/)
# 3. run_sam.py (Script de Inferencia)

# Activar entorno de conda con PyTorch y SAM (slam-gpu)
source ~/.bashrc
eval "$(/opt/miniconda3/bin/conda shell.bash hook)"
conda activate slam-gpu

# Las rutas en Khipu se pasarán como argumento en run_sam.py
python /home/cesar.perales/lotes_generativos/scripts/run_sam.py \
    --metadata /home/cesar.perales/lotes_generativos/crops_metadata.json \
    --images /home/cesar.perales/lotes_generativos/images \
    --output /home/cesar.perales/lotes_generativos/output_masks \
    --weights /home/cesar.perales/lotes_generativos/weights/mobile_sam.pt
