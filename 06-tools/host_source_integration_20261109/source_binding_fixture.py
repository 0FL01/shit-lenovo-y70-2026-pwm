"""Offline source identity and original-guard fixtures. Never a runtime loader."""
import ast
import hashlib
import json
from pathlib import Path
import re
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
BINDING = json.loads((HERE / 'source_binding.json').read_text())

def require(value, message):
    if not value:
        raise RuntimeError(message)

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def baseline_sources():
    result = {}
    for path, expected in BINDING['baseline_sha256'].items():
        raw = (ROOT / path).read_bytes()
        require(sha(raw) == expected, 'Baseline source identity changed')
        result[path] = raw
    return result

def virtual_replace(raw, old, new, expected_original, expected_virtual):
    require(sha(raw) == expected_original, 'Original source mismatch')
    text = raw.decode()
    require(text.count(old) == 1, 'Non-unique exact replacement')
    virtual = text.replace(old, new).encode()
    require(sha(virtual) == expected_virtual, 'Virtual source mismatch')
    return virtual

def original_guard(fake_subprocess):
    raw = baseline_sources()['06-tools/run_p85_guarded_trial.py']
    tree = ast.parse(raw)
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                and n.name == 'source_provenance')
    module = ast.Module(body=[node], type_ignores=[])
    namespace = dict(Path=Path, re=re, subprocess=fake_subprocess,
                     SOURCE_FILES=tuple(BINDING['baseline_paths']), check=require)
    exec(compile(module, '<original-source-guard-fixture>', 'exec'), namespace)
    return namespace['source_provenance']

class GitFixture:
    """Models responses only; never invokes Git or creates a repository."""
    def __init__(self, *, missing=False, changed=False, diff=0, commit=None):
        self.paths = BINDING['baseline_paths']
        self.ids = {p: hashlib.sha1(p.encode()).hexdigest() for p in self.paths}
        self.missing, self.changed, self.diff = missing, changed, diff
        self.commit = commit or ('a' * 40)
        self.calls = []
    def run(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        args = argv[3:]
        cmd = args[0]
        output = ''
        rc = 0
        if cmd == 'rev-parse': output = self.commit
        elif cmd == 'ls-tree':
            selected = self.paths[:-1] if self.missing else self.paths
            output = '\n'.join('100644 blob '+self.ids[p]+'\t'+p for p in selected)
        elif cmd == 'hash-object':
            output = '\n'.join(('b'*40 if self.changed and i == 0 else self.ids[p])
                               for i,p in enumerate(self.paths))
        elif cmd == 'diff': rc = self.diff
        else: raise RuntimeError('Unexpected Git fixture operation')
        return SimpleNamespace(stdout=output, returncode=rc)
