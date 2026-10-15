# 02 · Solo masas, retiros y cotas de pisos

Parte del prisma base y del inventario. Ajusta la huella construida a los cuerpos
visibles, dejando patios/retiros cuando corresponda. Entrega floor_levels_m y
EXACTAMENTE UNA de components o masses (la otra se omite o es null).

**Preferido: components**, regiones relativas al catastro. Parte de parametric_scaffold
y front_frames ya calculados. No necesitas calcular vértices XY ni normales:
region.front_edge elige el marco; u=[0,1] ocupa su anchura; depth_m=[retiro,fondo]
establece distancias hacia dentro. fit=parcel recorta con precisión al polígono
original. Si usas depth_m, deja depth en su default [0,1]. Cada componente tiene
id, region, levels_m y opcionalmente cutouts/support/kind. Los demás campos de
MassComponent (vanos, zonas, trim, techo) no se editan en esta etapa.

Ejemplo SOLO de sintaxis, adaptar dimensiones al lote real:
{"floor_levels_m":[0,3.0,5.6],"components":[{"id":"principal","region":{"front_edge":0,"u":[0,1],"depth_m":[2.0,16.0],"fit":"parcel"},"levels_m":[0,3.0,5.6]}]}

La alternativa masses usa ArchitecturalMass: role, footprint XY y levels_m. Úsala
solo si los vértices están conocidos y aportan una forma que las regiones no expresan.
No gastes el turno haciendo aritmética de coordenadas rotadas que el motor ya resuelve.

floor_levels_m es metadata del experimento, NO una clave nueva de theta. Tiene
N+1 cotas para N pisos humanos, empieza en 0 y termina en la coronación del cuerpo.
Las alturas sugeridas/primer piso diferente son el punto de partida; cambia una
cota sugerida solo con justificación. Alturas fijas no se cambian. Saltos: 2.2–6 m.

Cada masa comienza en una cota de esa retícula y termina como máximo en la última.
Debe incluir todas las cotas de la retícula interiores a su intervalo y ninguna
cota interior extra. Un anexo puede tener techo más bajo entre cotas, siempre que
sus alturas de piso sean válidas. Al menos un cuerpo llega a la coronación total;
todos los pisos deben tener volumen construido. Esto evita añadir pisos ocultos
mediante masas apiladas. Las masas elevadas deben estar apoyadas y no interpenetrarse.

Usa roles estables (principal, anexo, superior...). Puedes representar retiros
superiores mediante masas apiladas apoyadas. Conserva el perímetro catastral y el
marco de orientación. No supongas que el borde inferior de una foto es el frente 0.
No generes aún huecos, balcones, molduras, cercos ni materiales. El techo plano de
andamiaje se reemplazará después. Frontones y parapetos no se cuentan como piso.

El motor calculará IDs, aristas, exposición y dominios de pared para las siguientes
etapas. No inventes referencias principal:0 sin consultar ese resultado después.
