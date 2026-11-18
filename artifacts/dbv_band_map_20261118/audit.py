"""Compare prefixes from four existing stock dump files. No I/O to devices."""
import json
from pathlib import Path
from xml.etree import ElementTree

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
STATES = ('s1_dbv3584_120', 's2_dbv3646_120', 's3_dbv3584_144', 's4_dbv3584_60')
WIDTH = {'24:D2':12, '24:D3':10, '24:D0':24, '24:D1':24, '24:AC':8,
         '24:AD':8, '24:AE':8, '24:A5':8, '24:A6':8, '24:A7':8,
         '24:A8':6, '1E:89':30, '1E:8A':30, '53:89':20,
         '4F:A2':1, '4F:A3':1, '4F:A4':1, '4F:A5':1}

def require(ok, message):
    if not ok:
        raise ValueError(message)

def parse(lines):
    passes = {1:{}, 2:{}}
    for n, line in enumerate(lines, 1):
        if not line.startswith('R '):
            continue
        f = line.split()
        require(len(f) == 44, f'wrong record size at {n}')
        key = '%02X:%02X' % (int(f[2],16), int(f[3],16))
        if key not in WIDTH:
            continue
        i = int(f[1])
        require(i in passes and key not in passes[i], f'duplicate/unknown pass at {n}')
        bs = bytes(int(x,16) for x in f[4:])
        passes[i][key] = bs[:WIDTH[key]]
    require(all(set(v) == set(WIDTH) for v in passes.values()), 'missing scoped record')
    return list(passes.values())

def words(b):
    require(len(b)%2 == 0, 'odd word slice')
    return [int.from_bytes(b[i:i+2], 'big') for i in range(0,len(b),2)]

def inspect(r):
    rich = r['24:A5'] + r['24:A6'] + r['24:A7'] + r['24:A8']
    small = r['24:AC'] + r['24:AD'] + r['24:AE']
    require(rich == r['1E:89'] == r['1E:8A'], '30-byte repeat')
    require(small == r['24:D0'] == r['24:D1'], '24-byte repeat')
    a,b = words(rich),words(small)
    require([a[i] for i in (1,2,5,6,7,8,9,10,11,12,13,14)] == b, 'nested arrays')
    require(r['53:89'][2:20] == small[6:24], 'cross-page 18-byte repeat')
    x,y = words(r['24:D2']),words(r['24:D3'])
    require(x == [b[0]] + b[7:] and [k+1 for k in x[1:]] == y, 'shifted adjacent edges')
    pair = words(b''.join(r['4F:'+key] for key in ('A2','A3','A4','A5')))
    require(pair == [x[2], y[1]], '4F four independent byte prefixes')
    return {'broad_axis':a, 'short_axis':b, '24_D2':x, '24_D3':y,
            'adjacent_pairs':[list(p) for p in zip(x[1:],y)], '4F_pairs':pair}

def run():
    sets = []
    for s in STATES:
        path = BASE/'ddic_regdump_20261107'/s/'raw.txt'
        with path.open() as f:
            sets.extend(parse(f))
    require(all(r == sets[0] for r in sets[1:]), 'scoped prefixes differ between archives')
    inference = inspect(sets[0])
    config = ElementTree.parse(BASE/'current_display_path/als/als_comp_config.xml')
    vals = {c.findtext('name'): c.findtext('value') for c in config.findall(".//config[@type='default']/configuration")}
    anchors = {k: int(vals[k]) for k in ('pwmToDcDbv','brightnessRange')}
    require(anchors['pwmToDcDbv'] == inference['24_D3'][0]
            and anchors['brightnessRange'] in inference['short_axis'], 'ALS anchors differ')
    return dict(archive_states=list(STATES), passes=len(sets), scoped_prefixes_per_pass=len(WIDTH),
                interpretation='BE16 arithmetic on captured prefixes only; no verified word counts or optical measurements',
                als_anchors=anchors,physical_pwm_hz=None,**inference)

if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
