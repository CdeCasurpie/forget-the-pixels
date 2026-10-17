"""Phase 0 contract evaluation; does not generate meshes or evaluate fidelity."""
import json
from pathlib import Path
from domain.building_intent import validate_intent, operation_order


def evaluate(root):
    results=[]
    for path in sorted((root/'cases').glob('*/*.json')):
        case=json.loads(path.read_text())
        request=validate_intent(case['request'])
        assert request.data['building']['organization']==case['expectations']['organization']
        assert [op['kind'] for op in request.data['building'].get('operations',[])]==case['expectations']['operations']
        results.append(dict(id=case['id'],split=case['split'],valid=True,
                            order=operation_order(request),evidence_present='evidence' in request.data))
    assert len(results)==20
    return {'scope':'intent_contract_only','geometry_generated':False,'cases':results,
            'passed':len(results),'tuning':sum(r['split']=='tuning' for r in results),
            'evaluation':sum(r['split']=='evaluation' for r in results)}


if __name__=='__main__':
    root=Path(__file__).parent
    report=evaluate(root)
    (root/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f"{report['passed']} valid cases; {report['tuning']} tuning / {report['evaluation']} evaluation; no geometry generated")
