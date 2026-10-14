<div align="center">

# Forget the Pixels

**Reconstrucción urbana procedural de Barranco, Lima**

Catastro editable · Evidencia fotográfica · Parámetros arquitectónicos · Mallas 3D

![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-Canvas-F7DF1E?logo=javascript&logoColor=black)
![GeoPandas](https://img.shields.io/badge/GeoPandas-139C5A?logo=geopandas&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?logo=opencv&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?logo=numpy&logoColor=white)
![glTF](https://img.shields.io/badge/Export-glTF%20%2F%20GLB-87C540?logo=opengl&logoColor=white)

[Inicio rápido](#inicio-rápido) · [Uso](#flujo-de-trabajo) · [Arquitectura](#arquitectura) · [Pruebas](#pruebas) · [Documentación](#documentación)

</div>

## Descripción

Forget the Pixels es un proyecto de reconstrucción urbana que combina geometría
catastral, fotografías panorámicas y una gramática arquitectónica para producir
edificios 3D editables y reproducibles. El área de trabajo actual es **Barranco,
Lima, Perú**.

La representación central es **theta (θ)**: un conjunto explícito de parámetros
de masas, niveles, fachadas, cubiertas y materiales. La gramática transforma esos
parámetros en geometría, manteniendo separadas la evidencia observada y las
decisiones de generación.

### Estado actual

| Componente | Capacidades | Estado |
|---|---|---|
| **A · Editor catastral** | Corregir lotes, cortar/fusionar, asignar manzanas, editar frentes y revisar fotografías | Operativo localmente |
| **B · Autor de thetas** | Seleccionar evidencia, ajustar sugerencias, preparar paquetes y versionar respuestas | Operativo con **proveedor mock temporal** |
| **House Grammar** | Resolver parámetros y generar edificios, detalles arquitectónicos y exportaciones GLB/OBJ | Motor disponible con experimentos y pruebas |
| **Public Space Grammar** | Calles, veredas, jardines, vegetación y mobiliario | Planificado; todavía no implementado |

**B aún no interpreta imágenes con IA ni genera mallas.** Su mock permite probar
el flujo completo de preparación y persistencia; el prompt y el contrato de
autoría son provisionales. La generación geométrica se ejecuta por separado en
`house_grammar/`.

## Tecnologías

| Área | Herramientas |
|---|---|
| Aplicaciones locales | Python, FastAPI, Uvicorn, Pydantic |
| Interfaz | HTML, CSS, JavaScript nativo, Canvas 2D, SVG, localStorage |
| Geometría geoespacial | GeoPandas, Shapely, PyProj |
| Imágenes y cálculo | OpenCV, Pillow, NumPy, SciPy |
| Modelado y exportación | Trimesh, mapbox-earcut, materiales PBR, GLB y OBJ/MTL |
| Adquisición y diagnóstico | streetlevel, Matplotlib, Pygame |
| Persistencia y desarrollo | JSON local, revisiones inmutables, pytest, Make, Git |

## Inicio rápido

### 1. Preparar el entorno

Desde la raíz del repositorio, en Linux o un entorno compatible con Make:

```bash
python3 -m venv .venv
source .venv/bin/activate
make install
```

Entorno de referencia: **Python 3.10**. Se necesita un navegador moderno;
**Node.js** se utiliza para comprobar sintaxis JavaScript con `make test`, sin
paso de compilación del frontend.

### 2. Disponer de los datos

Las aplicaciones trabajan con `data/barranco/`:

```text
data/barranco/
├── lotes/                  # SHP y fuentes catastrales
├── poses_barranco/         # Metadata y poses de cámaras
├── fotos_barranco/         # Panoramas locales
├── cadastral_offset.json   # Alineación catastral
├── editor/                # Correcciones y revisiones de A
└── theta_author/          # Formularios, paquetes y ejecuciones de B
```

La fuente catastral prioritaria es
`BARRANCO_LM_geogpsperu_SuyoPomalia.shp`, con sus archivos auxiliares. Las fotos
nuevas y los workspaces de A/B están excluidos de Git: un clon no reproduce por
sí solo el estado local de trabajo. Consulta [Datos compartidos](data/README.md).

Para explorar A sin el dataset real:

```bash
python3 -m apps.cadastral_editor.server --demo \
  --workspace /tmp/opencode/catastro-demo --port 8766
```

### 3. Iniciar las aplicaciones

Primero inicia A para que inicialice el catastro:

```bash
make a
```

Abre **http://127.0.0.1:8765**. Una vez inicializado el workspace, inicia B en
otra terminal con el mismo entorno activo:

```bash
make b
```

Abre **http://127.0.0.1:8767**. B lee las revisiones guardadas por A y puede
funcionar sin que el servidor de A permanezca abierto.

| Comando | Función |
|---|---|
| `make help` | Mostrar comandos y variables |
| `make install` | Instalar dependencias de A y B |
| `make a` | Iniciar el editor catastral |
| `make b` | Iniciar el autor de thetas |
| `make both` | Lanzar ambos servidores con el workspace ya inicializado |
| `make test` | Ejecutar pruebas A/B y comprobaciones JavaScript |

Puedes personalizar las rutas, puertos y el intérprete:

```bash
make b PORT_B=8770 DATA=/ruta/a/barranco PYTHON=python3
```

## Flujo de trabajo

### A · Corregir el catastro

1. Selecciona un lote en el mapa o búscalo por su ID.
2. Revisa su geometría y las fotografías cercanas con el prisma de referencia.
3. Ajusta posición, cortes, fusiones, manzanas y frentes según la evidencia.
4. Consulta el historial o exporta el resultado para etapas posteriores.

Las operaciones conservan ascendencia e IDs originales; los lotes nuevos reciben
IDs propios. Las revisiones se guardan localmente. La altura del prisma es una
**referencia de previsualización catastral**, no una medición arquitectónica.

### B · Preparar parámetros arquitectónicos

1. Selecciona un lote del catastro corregido.
2. Revisa las fotos candidatas y marca las que formarán parte del paquete.
3. Ajusta pisos, alturas, estilo y notas como sugerencias de autoría.
4. Pulsa **Preparar paquete** para congelar revisión, evidencia y prompt.
5. Pulsa **Generar theta · MOCK** y consulta el resultado o historial.

Los formularios se guardan automáticamente; la preparación y generación trabajan
en segundo plano. Los paquetes idénticos se reutilizan y los envíos repetidos se
deduplican. **Azul** identifica un paquete preparado; **verde**, un theta validado
por el adaptador mínimo. Esa validación no evalúa fidelidad visual ni sustituye
el resolver completo de la gramática.

### House Grammar · Generar una malla de ejemplo

Instala las dependencias del motor además de las de las aplicaciones:

```bash
python3 -m pip install -r house_grammar/requirements.txt
cd house_grammar
python3 steps/step18_theta_interface/run.py \
  --theta steps/step18_theta_interface/examples/01_simple.json \
  --output steps/step18_theta_interface/outputs/manual_01
```

El ejemplo genera un GLB, parámetros de entrada y resueltos, un manifiesto y
vistas diagnósticas. Consulta la [interfaz theta](house_grammar/steps/step18_theta_interface/README.md)
para interpretar el contrato y sus versiones.

## Arquitectura

```text
forget-the-pixels/
├── apps/
│   ├── cadastral_editor/    # A: edición de geometría y revisión fotográfica
│   └── theta_author/       # B: autoría, paquetes, proveedor y validación
├── packages/
│   ├── barranco_data/      # Persistencia, operaciones y manzanas
│   └── barranco_imaging/   # Proyección angular y prisma compartido
├── house_grammar/
│   ├── src/               # Dominio, geometría, modelado y exportación
│   ├── steps/             # Experimentos y herramientas reproducibles
│   ├── tests/             # Pruebas y fixtures geométricos
│   ├── assets/            # Recursos y materiales
│   └── data -> ../data/barranco
├── data/barranco/          # Fuentes y estado persistente compartido
├── Makefile
└── README.md
```

`house_grammar/` reemplaza la antigua ruta
`investigation/procedural_reconstruction/`. `packages/` es código compartido
necesario para A y B. La futura `public_space_grammar/` será un módulo hermano.

```text
Catastro + panoramas + poses
           │
           ▼
    A · Catastro corregido
           │ revisión + geometría + frentes
           ▼
    B · Evidencia y sugerencias → paquete → proveedor mock → context + theta

    Generación independiente:
    context + theta → resolver de House Grammar → malla → GLB / OBJ
```

El sistema conserva coordenadas de origen y revisiones. El catastro utiliza
**EPSG:32718**; el desplazamiento de importación se aplica una sola vez. La
proyección fotográfica compartida usa `angular-enu-v1` y un supuesto de terreno
plano. Las correcciones y ejecuciones se almacenan en JSON mediante escrituras
atómicas, sin base de datos externa.

## Pruebas

Desde la raíz, para las aplicaciones:

```bash
make test
```

Para la gramática, después de instalar sus dependencias:

```bash
cd house_grammar
python3 -m pytest -q
```

Las pruebas cubren persistencia, proyección, revisión catastral, trabajos
idempotentes, contratos theta, ensamblajes y regresiones geométricas. Las pruebas
de las aplicaciones usan workspaces temporales.

## Próximos pasos

- Conectar un proveedor multimodal real y revisar la guía de autoría arquitectónica.
- Integrar la validación completa y generación de mallas con el flujo de B.
- Evaluar fidelidad visual frente a fotografías, además de validez geométrica.
- Desarrollar `public_space_grammar/`: superficies, bordes, transiciones,
  vegetación y mobiliario con generación incremental.

## Documentación

- [Editor catastral: uso, operaciones y persistencia](apps/cadastral_editor/README.md)
- [Autor de thetas: flujo, contratos y sustitución del mock](apps/theta_author/README.md)
- [Paquetes compartidos](packages/README.md)
- [Datos compartidos](data/README.md)
- [Motor de edificios y experimentos](house_grammar/README.md)
- [Arquitectura del motor](house_grammar/ARCHITECTURE.md)
- [Interfaz theta y generación](house_grammar/steps/step18_theta_interface/README.md)
- [Familias arquitectónicas](house_grammar/ARCHITECTURAL_FAMILIES.md)
