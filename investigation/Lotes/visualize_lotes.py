import geopandas as gpd
import matplotlib.pyplot as plt
import os

# 1. Cargar el Shapefile
shp_path = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
print(f"Cargando Shapefile: {shp_path}...")
gdf = gpd.read_file(shp_path)

# 2. Análisis Básico de la Data
print("\n--- INFORMACIÓN DEL DATASET ---")
print(f"Total de polígonos (lotes): {len(gdf)}")
print("\nColumnas disponibles en el DBF:")
print(gdf.columns.tolist())

print("\nPrimeras 3 filas de datos:")
print(gdf.head(3))

print(f"\nSistema de Coordenadas Original (CRS): {gdf.crs}")

# 3. Visualización Básica (Matplotlib)
print("\nGenerando mapa base...")
fig, ax = plt.subplots(figsize=(10, 10))
gdf.plot(ax=ax, color='lightblue', edgecolor='black', linewidth=0.2)

ax.set_title("Lotes Catastrales - Distrito de Barranco", fontsize=16)
ax.set_xlabel("Longitud")
ax.set_ylabel("Latitud")

# Guardar la imagen localmente para no depender de la ventana gráfica si falla
output_img = "mapa_lotes_barranco.png"
plt.savefig(output_img, dpi=300, bbox_inches='tight')
print(f"Mapa guardado como: {output_img}")

# Mostrar en pantalla si hay interfaz gráfica
try:
    plt.show()
except Exception as e:
    print("No se pudo abrir ventana gráfica interactiva, revisa la imagen guardada.")
