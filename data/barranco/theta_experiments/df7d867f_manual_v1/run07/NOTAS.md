# Run07 — contrato de techos de catálogo

- `request.json` y `request_v2.json` activos: el techo básico de `f23` es plano;
  la cubierta gable ya declarada es el único emisor de sus pendientes/tejas.
- GLB, preview y tres comparaciones regenerados. 67 932 vértices,
  127 800 triángulos, 2 216 partes; envolvente aprobada.
- Los cinco diagnósticos topológicos corresponden a cuatro `window_grille` y un
  `door_leaf_grille`: varias componentes conexas dentro de cada registro, sin
  bordes abiertos/no-manifold, caras degeneradas o duplicadas en esos registros.
  No se han corregido aquí ni se califican como inocuos por defecto.
- La comparación sigue mostrando diferencias de escala, silueta y vanos frente
  a la fotografía. Este run verifica la migración del contrato; no reautoriza la
  arquitectura ni certifica fidelidad fotográfica.
- La vista preview usa el renderizador geométrico; para revisión con cámaras
  usar `comparisons/` y el GLB, no inferir fallos geométricos solo del preview.
