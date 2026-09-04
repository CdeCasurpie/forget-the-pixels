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
