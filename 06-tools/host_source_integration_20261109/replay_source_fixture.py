"""Test-only baseline/intended readers. Never imported by production modules."""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BINDING=json.loads((HERE/'replay_binding.json').read_text())
def checked(raw,pin,label):
    if hashlib.sha256(raw).hexdigest()!=pin:raise RuntimeError('Replay source mismatch: '+label)
    return raw
def baseline_inputs():
    manifest=json.loads((HERE/'combined_binding.json').read_text())
    result={}
    for p,pin in manifest['input_sha256'].items():
        record=BINDING['four_sources'].get(p)
        raw=(HERE/record['baseline_file']).read_bytes() if record else (ROOT/p).read_bytes()
        result[p]=checked(raw,pin,p)
    return result
def intended_sources(*,current=False):
    """Current means exactly intended disk bytes; never falls back to baseline."""
    result={}
    for p,pin in BINDING['hardware_source_sha256'].items():
        record=BINDING['four_sources'].get(p)
        raw=((HERE/record['intended_file']).read_bytes() if record and not current
             else (ROOT/p).read_bytes())
        result[p]=checked(raw,pin,p)
    return result
