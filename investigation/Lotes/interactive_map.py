import geopandas as gpd
import folium

shp_path = "BARRANCO_LM_geogpsperu_SuyoPomalia.shp"
print("Cargando Shapefile...")
gdf = gpd.read_file(shp_path)

# Folium necesita las coordenadas en Latitud/Longitud (EPSG:4326)
print(f"Transformando CRS de {gdf.crs} a EPSG:4326...")
gdf_wgs84 = gdf.to_crs(epsg=4326)

# Calcular el centro del mapa
center_lat = gdf_wgs84.geometry.centroid.y.mean()
center_lon = gdf_wgs84.geometry.centroid.x.mean()

print("Generando mapa interactivo...")
m = folium.Map(location=[center_lat, center_lon], zoom_start=15, tiles='OpenStreetMap')

# Agregar los polígonos al mapa interactivo
folium.GeoJson(
    gdf_wgs84,
    name='Lotes de Barranco',
    style_function=lambda x: {
        'fillColor': '#3186cc',
        'color': 'black',
        'weight': 0.5,
        'fillOpacity': 0.4
    },
    tooltip=folium.GeoJsonTooltip(fields=['objectid', 'nom_local'], aliases=['ID Lote:', 'Nombre:'])
).add_to(m)

output_html = "barranco_lotes.html"
m.save(output_html)
print(f"¡Mapa interactivo generado exitosamente! Abre '{output_html}' en tu navegador.")
