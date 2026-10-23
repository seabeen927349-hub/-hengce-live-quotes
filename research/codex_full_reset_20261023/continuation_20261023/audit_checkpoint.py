"""Check a git-anchored evidence checkpoint without executing model research."""
import hashlib
import json
from pathlib import Path


def verify(root):
    checkpoint = json.loads((root/'EVIDENCE_CHECKPOINT.json').read_text())
    expected = checkpoint['sha256']
    actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in (root/'results').iterdir() if p.is_file() and p.suffix != '.lock'}
    if actual != expected:
        raise ValueError('CHECKPOINT_INVENTORY_OR_HASH_MISMATCH')
    return {'checkpoint': 'PASS', 'files': len(actual)}


if __name__ == '__main__':
    print(json.dumps(verify(Path(__file__).resolve().parent)))
