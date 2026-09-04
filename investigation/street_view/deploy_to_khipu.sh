#!/bin/bash
# Script para copiar un dataset de Street View a Khipu y encolarlo automáticamente.

LOCAL_DIR=$1
REMOTE_PROJECT_NAME=$2

if [ -z "$LOCAL_DIR" ] || [ -z "$REMOTE_PROJECT_NAME" ]; then
    echo "Uso: bash deploy_to_khipu.sh <directorio_local> <nombre_proyecto_en_khipu>"
    echo "Ejemplo: bash deploy_to_khipu.sh data_custom_route mi_nueva_ruta"
    exit 1
fi

LOCAL_PATH=$(realpath "$LOCAL_DIR")
if [ ! -d "$LOCAL_PATH/images" ] || [ ! -f "$LOCAL_PATH/gps.csv" ]; then
    echo "Error: El directorio local debe contener una subcarpeta 'images/' y 'gps.csv'."
    exit 1
fi

echo "=============================================="
echo " 1. Creando carpeta de proyecto en Khipu...   "
echo "=============================================="
ssh cesar.perales@khipu "mkdir -p ~/tesis_colmap/datasets/$REMOTE_PROJECT_NAME/images"

echo "=============================================="
echo " 2. Subiendo imágenes y GPS (Esto puede tardar)..."
echo "=============================================="
scp -r "$LOCAL_PATH/images/"* cesar.perales@khipu:~/tesis_colmap/datasets/$REMOTE_PROJECT_NAME/images/
scp "$LOCAL_PATH/gps.csv" cesar.perales@khipu:~/tesis_colmap/datasets/$REMOTE_PROJECT_NAME/gps.csv

echo "=============================================="
echo " 3. Ejecutando el automatizador HLOC en Khipu..."
echo "=============================================="
ssh cesar.perales@khipu "bash ~/tesis_colmap/pipeline_gsv/submit_job.sh ~/tesis_colmap/datasets/$REMOTE_PROJECT_NAME"

echo "=============================================="
echo " ¡Despliegue exitoso! Tu trabajo está en la cola de Khipu."
echo " Revisa el estado entrando a Khipu y usando 'squeue -u cesar.perales'"
echo "=============================================="
