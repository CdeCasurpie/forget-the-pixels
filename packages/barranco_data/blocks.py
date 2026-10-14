"""Connected parcels → dissolved block geometries (no changes to parcel XY)."""
from shapely.geometry import shape
from shapely.strtree import STRtree


def suggest_blocks(lots):
    """Assign ungrouped connected components, preserving all manual assignments.

    Intersection includes shared edges, point contact and overlaps. No buffer or
    distance threshold bridges streets/gaps. An unassigned component touching
    exactly one existing block joins it; multiple existing blocks stay separate.
    """
    active = sorted((l for l in lots.values() if l['status'] == 'active'), key=lambda l: l['lot_id'])
    polygons = [shape(l['geometry']) for l in active]
    tree = STRtree(polygons)
    parents = list(range(len(active)))

    def root(i):
        while parents[i] != i:
            parents[i] = parents[parents[i]]
            i = parents[i]
        return i

    adjacent = {}
    for i, lot in enumerate(active):
        if lot['block_id']:
            continue
        adjacent[i] = set()
        for j in tree.query(polygons[i], predicate='intersects'):
            j = int(j)
            if active[j]['block_id']:
                adjacent[i].add(active[j]['block_id'])
            else:
                parents[root(j)] = root(i)
    components = {}
    for i in adjacent:
        components.setdefault(root(i), []).append(i)
    assignments, ambiguous = {}, []
    occupied = {l['block_id'] for l in active if l['block_id']}
    for members in components.values():
        neighbors = set().union(*(adjacent[i] for i in members))
        if len(neighbors) == 1:
            block = next(iter(neighbors))
        else:
            base = 'M-' + min(active[i]['lot_id'] for i in members)
            block, suffix = base, 1
            while block in occupied:
                suffix += 1
                block = f'{base}-{suffix}'
            occupied.add(block)
            if neighbors:
                ambiguous.append(block)
        for i in members:
            assignments[active[i]['lot_id']] = block
    return assignments, ambiguous
