"""Small explicit adapter to theta 0.3; no mesh and no style-family defaults.

This is a limited structural validation, NOT the complete legacy resolver.
Front IDs stay in authoring; input-parcel edge indices are computed from geometry.
"""
from shapely.geometry import shape, LineString, Polygon
from shapely.geometry.polygon import orient
from .contracts import Proposal


def compile_response(raw, package):
    proposal = Proposal.model_validate_json(raw)
    form = package['human_parameters']
    errors = []
    levels = proposal.levels_m or [proposal.height_m*i/proposal.floors for i in range(proposal.floors+1)]
    if (len(levels) != proposal.floors+1 or levels[0] != 0 or abs(levels[-1]-proposal.height_m) > .001
            or any(b <= a for a,b in zip(levels, levels[1:]))):
        errors.append('levels_m: niveles deben ser crecientes, empezar en 0 y terminar en height_m')
    for field, output in [('height', 'height_m'), ('floors', 'floors'), ('style', 'style')]:
        if form[field]['mode'] == 'fixed' and form[field]['value'] != getattr(proposal, output):
            errors.append(f'{output}: contradice decisión humana fijada')
    if form['massing_mode'] == 'fixed' and form['massing'] != proposal.massing.model_dump():
        errors.append('massing: contradice configuración fijada')
    lot = package['snapshot']['lot']
    polygon = shape(lot['geometry'])
    footprint = polygon
    fronts = {f['id']: f for f in lot['fronts'] if f['is_front']}
    for i, cut in enumerate(proposal.massing.cuts):
        if cut.front_id not in fronts:
            errors.append(f'massing.cuts[{i}].front_id: frente desconocido o no habilitado')
            continue
        line = shape(fronts[cut.front_id]['geometry'])
        if cut.kind == 'bite':
            if cut.width_m >= line.length:
                errors.append(f'massing.cuts[{i}].width_m: debe ser menor que el frente')
                continue
            a, b = (0, cut.width_m) if cut.end == 'start' else (line.length-cut.width_m, line.length)
            line = LineString([line.interpolate(a), line.interpolate(b)])
        footprint = footprint.difference(line.buffer(cut.depth_m, cap_style=2))
    if footprint.geom_type != 'Polygon' or footprint.is_empty or not footprint.is_valid or footprint.interiors or footprint.area < 6:
        errors.append('massing: cortes producen huella no admitida (fragmentada, huecos o área < 6 m²)')
    if errors:
        return proposal.model_dump(), None, dict(status='invalid', errors=errors)
    origin = list(polygon.centroid.coords[0])

    def local(poly):
        return [[x-origin[0], y-origin[1]] for x, y in orient(poly).exterior.coords[:-1]]

    parcel = local(polygon)
    # Overlap, not endpoint or nearest-edge guessing, maps partial frontage to parcel edges.
    coords = list(orient(polygon).exterior.coords)
    front_indices = [i for i in range(len(coords)-1) if any(
        LineString(coords[i:i+2]).intersection(shape(f['geometry'])).length > .001 for f in fronts.values())]
    request = dict(context=dict(parcel=parcel, fronts=front_indices), theta=dict(
        schema_version='0.3', architectural_style=proposal.style,
        massing=dict(pattern='explicit'), masses=[dict(role='house', footprint=local(footprint),
            levels_m=levels)],
        facade=dict(mode='explicit', openings=[], projections=[], material_regions=[]), facades=[],
        roof=dict(kind='flat', parapet_m=0, props=[]), site=dict(fence='none', garden=False, runs=[]),
        trim=dict(cornice=dict(enabled=False), plinth=dict(enabled=False))))
    warnings = ['Validación estructural del adaptador mínimo; resolver completo de gramática pendiente.',
                'Cubierta plana y fachada vacía son placeholders; no son observaciones.',
                'Altura aplicada al cuerpo; referencia de cubierta/parapeto requiere revisión.']
    if proposal.massing.delegate_complex:
        warnings.append('Configuración compleja pendiente de interpretación; mock conserva masa simple.')
    if any(getattr(proposal, field) is not None for field in ('construction', 'material', 'color')):
        warnings.append('Construcción/material/color conservados en proposal; su adaptación a theta aún está pendiente.')
    return proposal.model_dump(), request, dict(
            status='valid', scope='minimal_adapter_without_mesh', errors=[], warnings=warnings,
            coordinate_frame=dict(crs=package['snapshot']['crs'], origin_xy=origin),
            compiler_version='minimal-explicit-v1',
            visual_fidelity='not_evaluated', grammar_resolver='not_run')
