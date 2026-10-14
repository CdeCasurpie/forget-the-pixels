"""Reproduce individually classified Step22 baseline lots, never explicit masses."""
import json
from pathlib import Path
import subprocess
import sys
import geopandas as gpd
import numpy as np
from shapely.geometry import Polygon

STEP=Path(__file__).resolve().parents[1]
ROOT=STEP.parent.parent
PY=sys.executable

# Classification is from each lot's present masked views; no auto-classifier.
# Values are hypotheses for existing src grammar, not surveyed measurements.
CASES=[
 (1134486,'restaurante_terraza', 'mixed_use',2,6.4,3,(.84,.83,.79),{'balconies':False},'Restaurante blanco con mesas exteriores y terraza; baja comercial y ventanas pequeñas arriba.'),
 (1137173,'grifo_marquesina','workshop',1,4.5,3,(.80,.79,.73),{'balconies':False},'Grifo con marquesina amplia sobre surtidores; familia workshop es aproximación de planta baja.'),
 (1135384,'comercio_ladrillo_blanco','mixed_use',2,6.7,3,(.85,.83,.78),{'balconies':False},'Dos niveles: bajo rojo ladrillo con arcos/portones, alto blanco con vanos rectos.'),
 (1135382,'casa_blanca_esquina','quiet_house',2,6.5,3,(.82,.88,.85),{'balconies':False},'Casa esquinera blanca verdosa: puerta arqueada, rejas, garaje lateral, jardín escaso.'),
 (1135572,'casa_ladrillo_balcon','republicano',2,6.9,2,(.64,.39,.31),{'balconies':True},'Fachada angosta ladrillo terracota, ventana enrejada y balcón superior.'),
 (1135370,'edificio_crema_balcones','balcony_apartments',3,9.2,3,(.76,.73,.64),{'balconies':True},'Edificio crema de tres niveles con balcones, vanos y entrada central.'),
 (1137568,'comercio_blanco_dos_plantas','mixed_use',2,6.3,2,(.84,.83,.77),{'balconies':False},'Comercio blanco en esquina, baja con grandes vanos y alta con cubierta ligera.'),
 (1138261,'edificio_azul_cristal','ribbon_windows',3,9.3,4,(.69,.78,.82),{'balconies':False},'Edificio azul gris de tres niveles con vanos verticales repetidos y baja vidriada.'),
 (1137619,'banco_neoclasico','republicano',1,5.4,4,(.78,.79,.76),{'balconies':False},'Banco de una planta con cornisa potente, pilastras y ventanas altas enrejadas.'),
 (1138323,'casona_amarilla_esquina','republicano',1,5.9,5,(.88,.77,.51),{'balconies':False},'Casona comercial esquinera amarilla con vanos altos arqueados y frontón central.'),
 (1138316,'muro_local_bajo','quiet_house',1,3.7,2,(.72,.64,.50),{'balconies':False},'Muro largo o local muy bajo con accesos dispersos; evidencia parcial y muy ocluida.'),
 (1138310,'lote_sin_vista_etiquetada','quiet_house',2,6.0,2,(.78,.77,.71),{'balconies':False},'Cinco cámaras marcadas absent: hipótesis genérica solo para no omitir el lote; ninguna fachada observada atribuible.'),
 (1138283,'vivienda_verde_tres_pisos','balcony_apartments',3,9.0,3,(.57,.61,.43),{'balconies':True},'Vivienda verde de tres plantas tras cerco de ladrillo, aberturas asimétricas y balcón.'),
 (1138401,'comercio_rojo_rejas','workshop',1,4.2,4,(.52,.31,.27),{'balconies':False},'Local o nave baja roja, múltiples rejas y franja comercial.'),
 (1138477,'edificio_blanco_balcones','balcony_apartments',3,9.6,3,(.83,.85,.82),{'balconies':True},'Edificio blanco de tres pisos con balcones metálicos y planta baja retranqueada.'),
 (1138183,'bloque_moderno_balcones','balcony_apartments',5,15.0,5,(.75,.77,.75),{'balconies':True},'Bloque moderno gris de unos cinco niveles: franjas de balcones corridos, núcleo oscuro.'),
 (1138209,'casona_amarilla_galeria','galeria_madera',2,7.2,3,(.85,.80,.64),{'balconies':False},'Casona amarilla de dos niveles con galería blanca, pórtico y techo inclinado.'),
]

def main():
    cadastre=gpd.read_file(ROOT/'data/lotes/BARRANCO_LM_geogpsperu.geojson').to_crs(32718)
    shapes={int(k):g for k,g in zip(cadastre.objectid,cadastre.geometry)}
    fronts_data=json.loads((STEP.parent/'step21_lot_fronts/lot_fronts.json').read_text())
    for lid,slug,family,floors,height,bays,color,facade,description in CASES:
        folder=STEP/'lotes'/f'{lid}_{slug}'
        if (folder/'before/manifest.json').exists():
            print(f'Already built: {lid}',flush=True)
            continue
        folder.mkdir(parents=True,exist_ok=True)
        (folder/'after').mkdir(exist_ok=True)
        # Complete geometric context is always read from original cadastre/fronts
        # by build_lot_before.py. Only architecture is supplied here.
        theta={'family':family,'height_m':height,'floors':floors,
               'massing':{'pattern':'single_block'},
               'facade':{'bay_count':bays,**facade},
               'primary_color':color,'roof':{'kind':'flat','parapet_m':.4},
               'site':{'fence':'none','garden':False}}
        if lid==1135384:
            theta['materials']=[{'slot':'stone','template':'brick','color':(.58,.32,.24)}]
        if lid==1138283:
            theta['site']={'fence':'ladrillos','garden':False}
        if lid==1138209:
            theta['roof']={'kind':'tile_shed','slope_deg':12,'parapet_m':0}
        # An irregular cadastral ring may contain 0.18 m slivers and multiple
        # street edges: global bay_count on ALL fronts fails. Assign each
        # canonical edge separately, keeping narrow slivers blank.
        geom=shapes[lid]
        from shapely.geometry.polygon import orient
        ring=list(orient(geom,sign=1).exterior.coords)[:-1]
        start=min(range(len(ring)),key=lambda i:ring[i])
        ring=ring[start:]+ring[:start]
        tagged=fronts_data[f'{lid}.0']
        street=[e for e in tagged['edges'] if e['edge_index'] in tagged['street_edge_indices']]
        controls=[]
        for i,a in enumerate(ring):
            b=ring[(i+1)%len(ring)]
            length=float(np.linalg.norm(np.asarray(b)-a))
            is_front=any(max(np.linalg.norm(np.asarray(a)-e['start_xy']),np.linalg.norm(np.asarray(b)-e['end_xy']))<.02
                         or max(np.linalg.norm(np.asarray(b)-e['start_xy']),np.linalg.norm(np.asarray(a)-e['end_xy']))<.02 for e in street)
            if is_front and length>2.4:
                count=min(bays,max(1,int((length-.64)/2.8)))
                config={'mode':'repeat','bay_count':count,'balconies':facade['balconies']}
            else:
                config={'mode':'explicit','openings':[],'projections':[],'material_regions':[]}
            controls.append({'mass_role':'main:0','edge':i,'controls':config})
        theta['facades']=controls
        (folder/'analisis_theta.json').write_text(json.dumps(theta,indent=2)+'\n')
        source=STEP/'edificios_a_probar'/str(lid)
        seg=json.loads((source/'segmentation.json').read_text())['images']
        present=sum(e['status']=='present' for e in seg.values())
        note=(f'# {lid} — {slug.replace("_"," ")}\n\n{description}\n\n'
              f'Vistas: {present} present / {len(seg)-present} absent.\n'
              'P = catastro original + frentes Step21; θ sin masas explícitas en '
              '`analisis_theta.json`. Altura inferida, no medida. `before/` guarda '
              'malla GLB, θ resuelto, renders y comparativas para cada foto present.\n\n'
              'Brechas a evaluar en `after/`: arcos, rótulos propios, detalles '
              'de cubierta, voladizos o vanos irregulares que el patrón repetido '
              'no capta. Si las vistas son absent no se atribuye una fachada real.\n')
        (folder/'README.md').write_text(note)
        cmd=[PY,str(STEP/'build_lot_before.py'),'--lot',str(lid),'--name',slug,
             '--seed',str(lid%97),'--theta-file',str(folder/'analisis_theta.json')]
        if not present:cmd.append('--include-absent')
        print(f'\n=== {lid} {slug} ({present} views) ===',flush=True)
        result=subprocess.run(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (folder/'build.log').write_text(result.stdout)
        print(result.stdout[-450:],flush=True)
        if result.returncode:
            print(f'FAILED {lid}: {result.returncode}',flush=True)
        else:
            print(f'OK {lid}',flush=True)

if __name__=='__main__':main()
