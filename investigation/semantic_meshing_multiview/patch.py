import re
with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/semantic_meshing_multiview/interactive_mesher.py', 'r') as f:
    code = f.read()

merge_old = """
    try: tri = Delaunay(pts_2d)
    except: return False
    
    # Texturas (Materiales)
    img_path = os.path.join(PATH_IMG, img_obj.name)
    img_rgb = cv2.cvtColor(cv2.imread(img_path), cv2.COLOR_BGR2RGB)
"""

merge_new = """
    # ---------------------------------------------------------
    # PROPUESTA A/B: INYECCIÓN DE WIREFRAMES (LSD) CON INTERPOLACIÓN DE PROFUNDIDAD
    # Llenamos los "huecos" arquitectónicos encontrando bordes en la imagen 2D
    # e interpolando su profundidad en 3D para anclar la malla a las esquinas reales.
    # ---------------------------------------------------------
    global dense_points, dense_colors
    from scipy.interpolate import LinearNDInterpolator
    
    img_path = os.path.join(PATH_IMG, img_obj.name)
    img_bgr = cv2.imread(img_path)
    img_rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img_gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    
    # 1. Interpolar Profundidad (LinearNDInterpolator) de los puntos esparcidos conocidos
    interp_z = LinearNDInterpolator(pts_2d, z_vals)
    
    # 2. Detector de Líneas (Line Segment Detector)
    lsd = cv2.createLineSegmentDetector(0)
    lines, _, _, _ = lsd.detect(img_gray)
    
    new_pts_2d = []
    new_pts_z = []
    
    if lines is not None:
        for line in lines:
            x1, y1, x2, y2 = line[0]
            # Solo procesar lineas de tamaño decente (eliminar ruido)
            if np.linalg.norm([x2-x1, y2-y1]) > 20:
                # Muestrear inicio, medio y fin de la linea
                samples = [
                    (x1, y1),
                    (x2, y2),
                    ((x1+x2)/2, (y1+y2)/2)
                ]
                for (u, v) in samples:
                    z = interp_z(u, v)
                    if not np.isnan(z): # Si está dentro del casco convexo de los puntos COLMAP
                        new_pts_2d.append([u, v])
                        new_pts_z.append(float(z))
                        
    # 3. Proyectar de vuelta al Mundo 3D e Inyectar
    if len(new_pts_2d) > 0:
        new_pts_2d = np.array(new_pts_2d)
        new_pts_z = np.array(new_pts_z)
        
        # Desproyección a Cámara
        cx, cy = K[0, 2], K[1, 2]
        fx, fy = K[0, 0], K[1, 1]
        x_cam = (new_pts_2d[:, 0] - cx) * new_pts_z / fx
        y_cam = (new_pts_2d[:, 1] - cy) * new_pts_z / fy
        pts_cam_new = np.vstack((x_cam, y_cam, new_pts_z))
        
        # Cámara a Mundo
        pts3d_new = (np.linalg.inv(R) @ (pts_cam_new - t)).T
        
        # Inyectar a la Nube Global
        start_idx = len(dense_points)
        dense_points = np.vstack((dense_points, pts3d_new))
        
        # Color promedio gris para estos vertices inyectados
        gray_colors = np.ones((len(pts3d_new), 3)) * 0.5
        dense_colors = np.vstack((dense_colors, gray_colors))
        
        # Añadir al pool de puntos para esta vista
        pts3d = np.vstack((pts3d, pts3d_new))
        z_vals = np.concatenate((z_vals, new_pts_z))
        pts_2d = np.vstack((pts_2d, new_pts_2d))
        
        # Nuevos pt_indices (identificadores globales)
        new_indices = list(range(start_idx, start_idx + len(pts3d_new)))
        pt_indices = np.concatenate((pt_indices, new_indices))
        
        print(f"\\033[92m[WIREFRAME]\\033[0m Inyectados {len(new_pts_2d)} puntos estructuradores para llenar huecos en bordes.")

    try: 
        tri = Delaunay(pts_2d)
    except: 
        return False
"""

if merge_old in code:
    code = code.replace(merge_old, merge_new)
    
    # Y actualizamos el filtro estadístico adaptativo
    filter_old = """    # Filtro Z-Stretch (Lo que pidió el usuario: no dibujar triangulos rotos estirados en Z)
    z_diffs = np.abs(z_vals[edges[:, 0]] - z_vals[edges[:, 1]])
    MAX_Z_STRETCH = np.percentile(z_diffs, 85) * 1.5 """
    
    filter_new = """    # ---------------------------------------------------------
    # PROPUESTA D: Z-STRETCH ESTADÍSTICO ADAPTATIVO
    # Usamos estadística robusta (Median Absolute Deviation) para cortar discontinuidades
    # sin romper la malla donde sí existe geometría contigua.
    # ---------------------------------------------------------
    z_diffs = np.abs(z_vals[edges[:, 0]] - z_vals[edges[:, 1]])
    median_z = np.median(z_diffs)
    mad_z = np.median(np.abs(z_diffs - median_z))
    # Umbral adaptativo robusto (Media + 3 * MAD ajustada)
    MAX_Z_STRETCH = median_z + 4.0 * mad_z """
    
    code = code.replace(filter_old, filter_new)
    
    with open('/home/cesar/Escritorio/UTEC/PFC1_Lima/forget-the-pixels/investigation/semantic_meshing_multiview/interactive_mesher.py', 'w') as f:
        f.write(code)
    print("Patch exitoso.")
else:
    print("Fallo el parcheo.")
