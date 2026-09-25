"""Five small contract challenges; no real images or training data."""
from pathlib import Path
import json
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from run import run


def main():
    summary=[]
    for source in sorted(HERE.glob('0*.json')):
        output=HERE/'outputs'/source.stem
        manifest=run(source,output,size=420)
        requested=json.loads(source.read_text())['theta']
        resolved=json.loads((output/'resolved_theta.json').read_text())
        requested_entities=sum(len(f['controls'].get('openings',[])) for f in requested.get('facades',[]) if f['controls'].get('openings') is not None)
        requested_entities+=sum(len(f['controls'].get('opening_edits',[])) for f in requested.get('facades',[]) if f['controls'].get('opening_edits') is not None)
        resolved_entities=sum(len(w['facade']['openings']) for w in resolved['walls'])
        summary.append(dict(case=source.stem,lines=len(source.read_text().splitlines()),
                            explicit_opening_entities=requested_entities,
                            resolved_openings=resolved_entities,
                            completed=len(resolved['completed']),
                            fingerprint=manifest['mesh_sha256']))
    (HERE/'outputs'/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':
    main()
