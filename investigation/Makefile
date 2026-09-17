PYTHON_ENV = env -u WAYLAND_DISPLAY /home/cesar/Escritorio/UTEC/PFC1_Lima/venv310/bin/python

help:
	@echo "======================================================================"
	@echo "    EXPERIMENTOS DE RECONSTRUCCIÓN SEMÁNTICA Y MALLADO"
	@echo "======================================================================"
	@echo ""
	@echo "make run-semantic"
	@echo "  -> Experimento 1: Segmentación base con Felzenszwalb y Ransac 3D."
	@echo "     Trata de aislar clusters de colores (ventanas, paredes) y "
	@echo "     ajustar planos matemáticos (RANSAC) para cada segmento."
	@echo ""
	@echo "make run-projected"
	@echo "  -> Experimento 2: Planos Proyectados."
	@echo "     Igual al anterior, pero aplana los puntos hacia la normal "
	@echo "     del plano encontrado antes de triangular, buscando hacer "
	@echo "     mallas tipo 'GTA 5' con geometría perfectamente limpia."
	@echo ""
	@echo "make run-delaunay"
	@echo "  -> Experimento 3: Delaunay Global 2D + Mapeo UV."
	@echo "     Omite la segmentación y usa la imagen completa. Proyecta "
	@echo "     todos los puntos 3D a la cámara, triangula en 2D y usa la "
	@echo "     foto real como textura UV. (Incluye controles avanzados de "
	@echo "     navegación como Raycast 'C' y Dolly 'W/S')."
	@echo ""
	@echo "make run-multiview"
	@echo "  -> Experimento 4: Mallado Multi-Cámara (En Desarrollo)."
	@echo "     Construirá un grafo global. Cada cámara proyecta sus puntos, "
	@echo "     crea conexiones (aristas) y las fusiona en un grafo unificado"
	@echo "     para formar una malla maestra de toda la cuadra."
	@echo "======================================================================"
	@echo "    PIPELINE AUTOMATIZADO DE STREET VIEW (HLOC + KHIPU)"
	@echo "======================================================================"
	@echo ""
	@echo "make run-gsv-route-selector"
	@echo "  -> Paso 1: Interfaz 2D para seleccionar interactivamente la ruta "
	@echo "     de panoramas desde Google Maps."
	@echo ""
	@echo "make run-gsv-downloader"
	@echo "  -> Paso 2: Descarga los panoramas y aplica el corte perspectivo "
	@echo "     matemático con FOV 135 para maximizar la superposición."
	@echo ""
	@echo "make run-gsv-step1"
	@echo "  -> Baseline nuevo: descarga panoramas 360 y guarda heading/orientación."
	@echo "     No ejecuta todavía proyección, SAM ni SAM3D Objects."
	@echo ""
	@echo "make run-gsv-step1-route"
	@echo "  -> Baseline nuevo usando custom_route.json como entrada."
	@echo ""
	@echo "make view-gsv-north"
	@echo "  -> Recorre los panoramas con N/B y muestra siempre la vista norte."
	@echo ""
	@echo "make run-gsv-khipu-deploy PROJECT_NAME=mi_ruta"
	@echo "  -> Paso 3: Sube la carpeta a Khipu y encola el trabajo HLOC."
	@echo "     (Ejecuta extraccion SuperPoint y emparejamiento LightGlue)."
	@echo ""
	@echo "make run-view-gsv-sparse"
	@echo "  -> Paso 4: Visualiza la nube alineada final tras descargarse."
	@echo "======================================================================"

run-semantic:
	$(PYTHON_ENV) semantic_meshing/interactive_mesher.py

run-projected:
	$(PYTHON_ENV) semantic_meshing_projected/interactive_mesher.py

run-delaunay:
	$(PYTHON_ENV) semantic_meshing_delaunay/interactive_mesher.py

run-multiview:
	$(PYTHON_ENV) semantic_meshing_multiview/interactive_mesher.py

# ==========================================
# Google Street View (Escáner Nativo 3D)
# ==========================================
build-gsv-cloud:
	@echo "Descargando Depth Maps y armando Nube Global..."
	$(PYTHON_ENV) semantic_meshing_gsv/build_gsv_cloud.py

run-gsv-cloud:
	@echo "Visualizando Nube Global de GSV..."
	$(PYTHON_ENV) semantic_meshing_gsv/view_gsv_cloud.py

run-multiview-gsv:
	@echo "Visualizando fotogrametria real de Street View con SuperPoint..."
	$(PYTHON_ENV) semantic_meshing_multiview/interactive_mesher_gsv.py

# ==========================================
# Pipeline HLOC GSV Automatizado
# ==========================================
PROJECT_NAME ?= gsv_default_project

run-gsv-route-selector:
	$(PYTHON_ENV) street_view/interactive_route_selector.py

run-gsv-downloader:
	$(PYTHON_ENV) street_view/download_custom_route.py

# ==========================================
# Baseline nuevo: Adquisición GSV, Paso 1
# ==========================================
GSV_STEP1_LAT ?= -12.137248
GSV_STEP1_LON ?= -77.020423
GSV_STEP1_COUNT ?= 10
GSV_STEP1_OUTPUT ?= proy_geom/steps/step1_acquisition/data/sample_route

run-gsv-step1:
	@echo "Descargando panoramas 360 para el baseline (Paso 1)..."
	$(PYTHON_ENV) proy_geom/steps/step1_acquisition/run.py \
		--lat $(GSV_STEP1_LAT) \
		--lon $(GSV_STEP1_LON) \
		--count $(GSV_STEP1_COUNT) \
		--output $(GSV_STEP1_OUTPUT)

run-gsv-step1-route:
	@echo "Descargando panoramas 360 desde custom_route.json..."
	$(PYTHON_ENV) proy_geom/steps/step1_acquisition/run.py \
		--route-json ../custom_route.json \
		--output proy_geom/steps/step1_acquisition/data/custom_route

view-gsv-north:
	@echo "Abriendo visor de validación: vista fija hacia el norte..."
	$(PYTHON_ENV) proy_geom/steps/step1_acquisition/view_north.py \
		--dataset proy_geom/steps/step1_acquisition/data/sample_route

run-gsv-khipu-deploy:
	bash street_view/deploy_to_khipu.sh street_view/data_custom_route $(PROJECT_NAME)

run-view-gsv-sparse:
	$(PYTHON_ENV) street_view/view_sparse_cloud.py street_view/sparse_sp_135_aligned/

# ==========================================
# Geo-Proyector Generativo (Lotes + Rerun)
# ==========================================
run-geo-proyector:
	@echo "Lanzando el Visualizador de Auditoría (Fase 1)..."
	$(PYTHON_ENV) lotes_projection/main.py

export-crops:
	@echo "Extrayendo metadatos 2D para Khipu (Fase 2)..."
	$(PYTHON_ENV) lotes_projection/export_crops.py

test-crop:
	@echo "Simulando input a SAM (eligiendo lote aleatorio)..."
	$(PYTHON_ENV) lotes_projection/test_local_crop.py

preview-lots:
	@echo "Mostrando en 3D los lotes que pasaron los filtros..."
	$(PYTHON_ENV) lotes_projection/preview_selected_lots.py
