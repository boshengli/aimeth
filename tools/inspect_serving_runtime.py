import importlib.metadata as metadata
import hashlib
import json
from pathlib import Path
records = []
for package in ['sglang', 'vllm']:
    try:
        dist = metadata.distribution(package)
    except metadata.PackageNotFoundError:
        continue
    root = Path(dist.locate_file(package))
    if not root.is_dir():
        import importlib.util
        root = Path(importlib.util.find_spec(package).origin).parent
    matches = []
    for p in root.rglob('*.py'):
        if p.stat().st_size > 3000000:
            continue
        raw = p.read_bytes()
        symbols = [s for s in ['Glm5NextForConditionalGeneration','DeepseekV4ForCausalLM','glm5_next','deepseek-v4','glm45','glm47'] if s.encode() in raw]
        if symbols:
            matches.append({'file':str(p.relative_to(root)),'sha256':hashlib.sha256(raw).hexdigest(),'symbols':symbols})
    records.append({'package':package,'version':dist.version,'matches':matches})
print(json.dumps(records, indent=2))
