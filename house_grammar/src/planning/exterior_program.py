"""R2.1: compact exterior use program over the existing articulated masses.

No rooms, partition walls, apertures or facade dimensions are planned here.
Absent intent is completed from qualitative profile priors, never from imagery.
An explicit local floor/front use replaces the building default.
"""
from domain.architectural_plan import ExteriorProgramPlan
from domain.generation_profile import profile_for
from planning.articulation import plan_articulation


def plan_exterior_program(request):
    massing = plan_articulation(request)
    data = massing.request
    building = data['building']
    authored = building.get('program', {})
    profile = profile_for(building.get('profile', 'barranco_residential'))
    floors = len(data['context']['levels_m']) - 1
    use = authored.get('use', profile['use'])
    residential = authored.get('residential',
                               ('multi_family' if use == 'mixed' or floors > 2 else 'single_family')
                               if use in ('mixed', 'residential') else 'none')
    evolution = authored.get('evolution', {'incremental': 'progressive',
                                          'adapted': 'adapted'}.get(profile['evolution'], 'unitary'))
    program = dict(use=use, residential=residential, evolution=evolution,
                   condition=authored.get('condition', 'ordinary'),
                   occupancy=authored.get('occupancy', 'occupied'),
                   # None means not specified (completion permitted); False forbids it.
                   fence=building.get('site', {}).get('fence'))
    local = {(row['body'], row['floor']): row for row in authored.get('floors', [])}
    storeys = []
    decisions = []
    for storey in massing.storeys:
        body, floor = storey['body'], storey['floor']
        row = local.get((body, floor), {})
        default = ('commercial' if floor == 1 else 'residential') if use == 'mixed' else use
        floor_use = row.get('use', default)
        sectors = {sector['front']: sector['use'] for sector in row.get('sectors', [])}
        storeys.append(dict(id=storey['id'], body=body, floor=floor,
                            use=floor_use, sectors=sectors))
        if 'use' not in row:
            decisions.append(dict(path=f'program/{body}/floor{floor}/use',
                                  value=floor_use, source='completion'))
    return ExteriorProgramPlan('exterior-program-v1', data, massing.to_dict(), program,
                               storeys, decisions)
