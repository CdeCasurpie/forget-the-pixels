"""Five architectural families, five presets each; dimensions remain independent."""
from dataclasses import dataclass


@dataclass(frozen=True)
class BalconyPreset:
    pattern: str
    material: str
    kind: str = 'projecting'
    upper: str = 'none'
    ornate: bool = False


CATALOG = {
 'republicano': {
    'iron_vertical': BalconyPreset('vertical','metal'),
    'iron_rings': BalconyPreset('rings','metal'),
    'turned_gallery': BalconyPreset('turned','wood','gallery'),
    'open_lattice': BalconyPreset('grid','wood','gallery','lattice'),
    'sober_box': BalconyPreset('panels','wood','box','glass'),
 },
 'barroco': {
    'scroll_iron': BalconyPreset('scrolls','metal',ornate=True),
    'bowed_iron': BalconyPreset('bowed','metal',ornate=True),
    'ornate_balusters': BalconyPreset('vase','stone',ornate=True),
    'ornate_box': BalconyPreset('panels','wood','box','glass',True),
    'fretwork_gallery': BalconyPreset('turned','wood','gallery','fretwork',True),
 },
 'clasico': {
    'single_baluster': BalconyPreset('vase','stone'),
    'double_baluster': BalconyPreset('double_vase','stone'),
    'mixed_parapet': BalconyPreset('mixed','plaster'),
    'geometric': BalconyPreset('cross','metal'),
    'column_gallery': BalconyPreset('vase','stone','gallery'),
 },
 'madera': {
    'vertical_timber': BalconyPreset('vertical','wood'),
    'turned_timber': BalconyPreset('turned','wood'),
    'cross_frames': BalconyPreset('cross','wood'),
    'lattice_panels': BalconyPreset('lattice','wood'),
    'continuous_box': BalconyPreset('panels','wood','box','lattice'),
 },
 'moderno': {
    'slim_vertical': BalconyPreset('vertical','metal'),
    'horizontal_rods': BalconyPreset('horizontal','metal'),
    'glass_posts': BalconyPreset('glass','metal'),
    'glass_channel': BalconyPreset('frameless','metal'),
    'louver_parapet': BalconyPreset('louvers','metal'),
 },
}
PATTERNS = frozenset(p.pattern for family in CATALOG.values() for p in family.values()) | {'cables'}


def preset(style,variant):
    if style not in CATALOG:raise ValueError('Unknown balcony style')
    name=next(iter(CATALOG[style])) if variant=='auto' else variant
    if name not in CATALOG[style]:raise ValueError(f'Variant {name} does not belong to {style}')
    return name,CATALOG[style][name]
