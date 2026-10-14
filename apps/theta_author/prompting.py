"""Edit this module/template to evolve prompting without touching jobs or UI."""
import json
import hashlib
from pathlib import Path
from .contracts import Proposal


def build_package(snapshot, form, evidence):
    guide = (Path(__file__).parent/'prompts/guide_v1.txt').read_text()
    payload = dict(snapshot=snapshot, human_parameters=form, evidence=evidence,
                   response_schema=Proposal.model_json_schema())
    root = Path(__file__).resolve().parents[2]
    sources = [Path(__file__).parent/p for p in ('contracts.py', 'compiler.py', 'prompting.py', 'prompts/guide_v1.txt')]
    sources.append(root/'house_grammar/src/domain/theta.py')
    hashes = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources if p.exists()}
    return dict(package_version='theta-package-v1', prompt_version='guide-v1-provisional',
                authoring_version='authoring-v1', theta_version='0.3',
                source_hashes=hashes,
                prompt_status='provisional', examples=[], **payload,
                prompt=guide+'\n\n'+json.dumps(payload, ensure_ascii=False, indent=2))
