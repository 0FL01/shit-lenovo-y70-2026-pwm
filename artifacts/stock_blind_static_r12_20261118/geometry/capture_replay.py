"""Exact ordinal R12b replay, no label map or refit."""
import argparse,hashlib
from pathlib import Path
import replay
NAMES=tuple(f'p{p:02}_{s}.png' for p in range(1,7) for s in range(1,4))
def paths(directory):
 directory=Path(directory)
 if {p.name for p in directory.glob('*.png')}!=set(NAMES):raise ValueError('require exact 18 ordinal PNG set')
 result=[directory/n for n in NAMES]
 hashes=[hashlib.sha256(p.read_bytes()).hexdigest() for p in result]
 if len(set(hashes))!=18:raise ValueError('duplicate ordinal image')
 return result
def run(reference,directory):return replay.replay(reference,paths(directory))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reference',required=True,type=Path);p.add_argument('directory',type=Path);a=p.parse_args();print(replay.render(run(a.reference,a.directory)),end='')
