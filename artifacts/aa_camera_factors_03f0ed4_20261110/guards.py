"""Small offline guards. No evidence reads at import."""
import hashlib
from pathlib import Path
CACHE=Path('/home/opencode/.cache')
def private_destination(path):
 path=Path(path)
 if not path.is_absolute() or path.parent.resolve()!=CACHE or path.parent!=CACHE or path.is_symlink() or path.exists():
  raise ValueError('Require a new direct child of authorized private cache')
 if not path.name.startswith('legion-y70-camera-factors-03f0ed4-'):
  raise ValueError('Wrong private output prefix')
 return path
def pinned_bytes(path,expected,cap):
 path=Path(path)
 if path.is_symlink() or path.stat().st_size>cap:raise ValueError('Unsafe input')
 raw=path.read_bytes()
 if len(raw)>cap or hashlib.sha256(raw).hexdigest()!=expected:raise ValueError('Input digest mismatch')
 return raw
