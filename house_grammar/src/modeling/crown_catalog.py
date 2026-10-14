"""Attribute-based, deterministic classification with an explicit override."""
FAMILIES = ('triangular','segmental','semicircular','stepped','stepped_segmental',
            'curved_pointed','concave_shoulders','compound_curve','broken','rectangular_attic')
STYLES = ('republicano','barroco','clasico','madera','moderno')


def classify(design):
    if design.family!='auto':
        if design.family not in FAMILIES:raise ValueError('Unknown crown family')
        return design.family,'explicit family override'
    if design.silhouette not in ('angular','curved','pointed','mixed'):raise ValueError('Unknown crown silhouette')
    if design.open_center:return 'broken','open central field'
    if design.concave_shoulders:return 'concave_shoulders','concave shoulders toward central block'
    if design.stepped:
        return ('stepped_segmental','stepped shoulders and curved centre') if design.silhouette in ('curved','mixed') else ('stepped','angular stepped silhouette')
    if design.central_block:return 'rectangular_attic','raised central attic'
    return {'angular':('triangular','two straight slopes'),
            'curved':('segmental','low curved crown'),
            'pointed':('curved_pointed','two curved branches meeting at apex'),
            'mixed':('compound_curve','concave and convex branches')}[design.silhouette]
