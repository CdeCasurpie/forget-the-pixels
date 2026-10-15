"""Congela un paquete existente de B; ninguna escritura vuelve a A/B."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil

from shapely.geometry import shape, LineString
from shapely.geometry.polygon import orient

from .schemas import ROOT
from .workflow import resolve, wall_chart, validate_floor_grid
from .rendering import prepare_images
from domain.theta import canonical


def write_json(path, value):
    path = Path(path)
    temporary = path.with_suffix(path.suffix+'.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    temporary.replace(path)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def make_base(package):
    lot = package['snapshot']['lot']; form = package['human_parameters']
    if form.get('massing_mode') == 'fixed' and form.get('massing', {}).get('cuts'):
        raise ValueError('Este piloto requiere trasladar primero los cortes humanos fijos al contrato de masas.')
    polygon = orient(shape(lot['geometry']))
    if polygon.geom_type != 'Polygon' or polygon.interiors or not polygon.is_valid:
        raise ValueError('El piloto requiere una parcela Polygon válida sin huecos.')
    origin = list(polygon.centroid.coords[0])
    world = list(polygon.exterior.coords)[:-1]
    start = min(range(len(world)), key=lambda i:world[i])
    world = world[start:] + world[:start]
    front_lines = [shape(f['geometry']) for f in lot['fronts'] if f['is_front']]
    fronts = [i for i,a in enumerate(world) if any(
        LineString([a,world[(i+1)%len(world)]]).intersection(line.buffer(1e-6)).length>.001
        for line in front_lines)]
    if not fronts:
        raise ValueError('El paquete no tiene frente utilizable.')
    floors = form['floors']['value']
    if isinstance(floors, bool) or floors is None or int(floors) != floors or floors < 1:
        raise ValueError('El piloto asistido requiere pisos humanos enteros conocidos.')
    floors = int(floors)
    regular = form.get('floor_height_m')
    if regular is None:
        total = form['height']['value']
        if total is None:
            raise ValueError('Faltan cotas para construir la base humana.')
        regular = total / floors
    first = form.get('first_floor_height_m') if form.get('first_floor_different') else regular
    if first is None:
        raise ValueError('Falta altura sugerida del primer piso.')
    levels = [0.] + [round(first+i*regular,6) for i in range(floors)]
    parcel = [[x-origin[0],y-origin[1]] for x,y in world]
    constraints = dict(floors=floors,
        height_m=form['height']['value'] if form['height']['mode']=='fixed' else None,
        floor_policy='fixed_by_user_instruction; overrides legacy suggested flag',
        style_policy='suggested', parcel_policy='fixed', fronts_policy='fixed')
    request = dict(context=dict(parcel=parcel, fronts=fronts, crs=package['snapshot']['crs'],
        metric_origin=[*origin,0]), theta=dict(schema_version='0.3', family='quiet_house',
        architectural_style=None, massing=dict(pattern='explicit'),
        masses=[dict(role='principal', footprint=parcel, levels_m=levels)],
        facade=dict(mode='explicit', openings=[], projections=[], material_regions=[]), facades=[],
        roof=dict(kind='flat',parapet_m=0,props=[]), roofs=[],
        trim=dict(cornice=dict(enabled=False),plinth=dict(enabled=False)),
        site=dict(fence='none',garden=False,runs=[],zones=[]),
        balconies=[],vertical_members=[],crowns=[],entablatures=[],roof_assemblies=[],canopies=[],entrances=[],
        materials=[]), nuisance=dict(seed=23, curtains=False), config=dict(detail=2))
    validate_floor_grid(request, levels, constraints)
    resolved = resolve(request)
    return dict(request=request, constraints=constraints, floor_levels_m=levels,
                accepted=[], decisions=[], inventory=None, opening_ledger=[],
                walls=wall_chart(resolved), resolved_architecture=json.loads(canonical(resolved)),
                review=None, last_artifact=None)


def prepare(package_path, output, editor=None):
    package_path, output = Path(package_path).resolve(), Path(output).resolve()
    package = json.loads(package_path.read_text())
    lot = package['snapshot']['lot']
    editor = Path(editor or ROOT/'data/barranco/editor')
    current_id = json.loads((editor/'current.json').read_text())['revision']
    current = json.loads((editor/'revisions'/f'{current_id}.json').read_text())
    active = current['lots'].get(lot['lot_id'])
    if not active or active['status'] != 'active' or active['geometry_revision'] != lot['geometry_revision']:
        raise ValueError('El paquete quedó desactualizado frente al catastro actual.')
    autosave = package_path.parent.parent.parent/'autosaves'/f"{lot['lot_id']}.json"
    if autosave.exists() and json.loads(autosave.read_text())['form'] != package['human_parameters']:
        raise ValueError('Hay un formulario más reciente; preparar su paquete en B primero.')
    if package['human_parameters']['geometry_revision'] != lot['geometry_revision']:
        raise ValueError('Formulario y geometría no corresponden.')
    if len(package['evidence']) < 1:
        raise ValueError('No hay fotos seleccionadas.')
    state = make_base(package)
    copied = []
    for i,e in enumerate(package['evidence'],1):
        source = (package_path.parent/e['attachment']).resolve()
        if not source.is_relative_to(package_path.parent) or digest(source) != e['sha256']:
            raise ValueError('Adjunto ausente, ajeno al paquete o con hash incorrecto.')
        copied.append((source,dict(deepcopy(e), attachment=f'evidence/{i:03d}.jpg')))
    output.mkdir(parents=True, exist_ok=False)
    inputs = output/'inputs'; (inputs/'evidence').mkdir(parents=True)
    for source,e in copied:
        shutil.copyfile(source, inputs/e['attachment'])
    write_json(inputs/'source_package.json',package)
    write_json(inputs/'evidence.json',[e for _,e in copied])
    write_json(inputs/'human.json',package['human_parameters'])
    write_json(inputs/'snapshot.json',package['snapshot'])
    write_json(output/'manifest.json',dict(experiment_version='staged-theta-v1',
        lot_id=lot['lot_id'], geometry_revision=lot['geometry_revision'],
        cadastral_revision_at_prepare=current_id, source_package=str(package_path),
        source_package_sha256=digest(package_path), model='claude-haiku-4-5',
        input_policy='assisted; human floors fixed, style suggested',
        base_status='parcel prism is a scaffold, not an observed building footprint'))
    checkpoint=output/'checkpoints/00_base'; checkpoint.mkdir(parents=True)
    write_json(checkpoint/'state.json',state)
    write_json(checkpoint/'request.json',state['request'])
    write_json(output/'state.json',state)
    prepare_images([e for _,e in copied],inputs,state['floor_levels_m'][-1],
                   state['request']['context']['parcel'],state['request']['context']['fronts'],
                   state['request']['context']['metric_origin'][:2])
    return state
