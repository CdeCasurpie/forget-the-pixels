# 12 · Revisar el conjunto contra las mismas cámaras

Recibe fotos limpias, identificación, comparaciones finales, inventario, historial
de decisiones, theta resuelto y diagnósticos. No escribas nuevas piezas en este turno.

Examina primero: identidad del edificio, pisos y silueta. Después retiros/volúmenes,
distribución de puertas y ventanas por piso, balcones/galerías, remates/cubierta,
cerco y materiales. Distingue error de geometría de error de cámara, oclusión y
limitación de apariencia del render. La altura de cámara es asumida (2.5 m actual).

Devuelve verdict=accept/revise/insufficient_evidence, findings y limitations.
Cada finding debe indicar target_stage (02_masas, 04_puertas, etc.), elemento,
discrepancia concreta, cambio solicitado y view_ids. Si aceptas, findings debe
estar vacío; limitaciones no bloqueantes siguen en limitations.

Una malla válida no prueba parecido. Rejas con barras desconectadas pueden dar
incidencias topológicas sin fuga de muro: informa el diagnóstico con precisión.
No declares evaluación visual si faltan comparaciones. No pidas cambiar pisos
humanos para resolver una diferencia: señala identidad/cámara/masa como causa
posible y deja la contradicción documentada.

Una corrección temprana obliga a regenerar etapas dependientes desde una rama;
no se parcha el JSON final ignorando referencias y validaciones anteriores.
