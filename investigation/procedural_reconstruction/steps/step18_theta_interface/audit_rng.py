"""Source-linked RNG inventory. AST locations, enclosing function and code hash.

This is an inventory, not a reachability proof; legacy and candidate paths are
labelled separately. PARAMETER_AUDIT.md describes actual mesh consumers.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=Path(__file__).resolve().parent
METHODS={'default_rng','Random','seed','resolve_seed','uniform','choice','integers','random','permutation','normal','randint','shuffle'}


def classify(path, function, expression):
    file=path.stem
    if any(expression.startswith(prefix) for prefix in ('np.random.default_rng(', 'resolve_seed(', 'random.Random(')):
        return 'CONFIG','legacy_only' if file in ('layout','families') or (file=='grammar' and function!='generate_v4_mesh') else 'candidate' if file=='theta' else 'V4','Stream creation, not an architectural value; consumers classified separately'
    if file=='theta':
        if function in ('_rng','generate_resolved'):
            return 'XI','candidate','Only curtain/foliage/rebar streams; roof object identity explicit'
        return 'CONFIG','candidate','Fixed RNG for family relief; sampled depths overwritten by theta'
    if file in ('layout','families','composition') or (file=='grammar' and function!='generate_v4_mesh'):
        return 'UNUSED','legacy_only','Not reached by V4; preserved for old API'
    if file=='massing':
        return 'THETA','V4','Mass pattern, split, setback or addition; never nuisance'
    if file=='facade_program':
        if '0.2, 0.55' in expression or expression.endswith('.random()'):
            return 'XI','V4','Curtain presence/coverage; architectural opening unchanged'
        return 'THETA','V4','Family or balcony/gallery/awning depth'
    if file=='roofscape':
        if function=='scatter_props' and '.integers(' in expression:
            return 'XI','V4','Seed for internal object detail, after object identity/layout chosen'
        if function=='_build_roof_body':
            return 'XI','V4','Object internal variation, object identity already planned'
        return 'THETA','V4','Roof class/depth/parapet or significant rooftop object layout'
    if file in ('site','mesh_builder','prefabs_roof','materials'):
        return 'XI','V4','Foliage, rebar or small color variation; not massing'
    if file=='grammar' and function=='generate_v4_mesh':
        return 'THETA','V4','Shared architectural stream; facade services and cladding'
    if file=='randomness':
        return 'CONFIG','V4','Stable stream derivation'
    return 'CONFIG','outside_V4','Experiment/vision utility outside architectural V4'


def inventory():
    rows=[]
    for path in sorted((ROOT/'src').rglob('*.py')):
        if path.name in ('codebase_dump.py','dump_codebase.py'):
            continue
        text=path.read_text()
        tree=ast.parse(text)
        parent={child:node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
        for node in ast.walk(tree):
            if not isinstance(node,ast.Call):
                continue
            name=getattr(node.func,'attr',getattr(node.func,'id',''))
            if name not in METHODS:
                continue
            expression=ast.get_source_segment(text,node) or ast.unparse(node)
            if name not in ('resolve_seed','default_rng','Random') and not any(x in expression for x in ('rng','random','_rng')):
                continue
            ancestor=node
            while ancestor in parent and not isinstance(ancestor,(ast.FunctionDef,ast.AsyncFunctionDef)):
                ancestor=parent[ancestor]
            function=getattr(ancestor,'name','<module>')
            category,reach,reason=classify(path,function,expression)
            if name in ('default_rng','resolve_seed','Random'):
                reason='Seed/stream creation. '+reason
            rows.append(dict(code=f'{path.relative_to(ROOT)}:{node.lineno}',function=function,
                             expression=expression,classification=category,pathway=reach,reason=reason,
                             source_sha256=hashlib.sha256(text.encode()).hexdigest()))
    return rows


if __name__=='__main__':
    rows=inventory()
    (DEST/'rng_inventory.json').write_text(json.dumps(rows,indent=2)+'\n')
    lines=['# RNG source inventory','','Generated with `python steps/step18_theta_interface/audit_rng.py`.','',
           '| Code | Function | Call | Class | Pathway | Reason |','|---|---|---|---|---|---|']
    for r in rows:
        lines.append('| '+ ' | '.join(str(r[k]).replace('\n',' ').replace('|','/') for k in ('code','function','expression','classification','pathway','reason'))+' |')
    (DEST/'rng_inventory.md').write_text('\n'.join(lines)+'\n')
    print(f'{len(rows)} RNG calls inventoried')
