"""Offline matched-mode comparison. No hardware or network access."""
import gzip
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DT = HERE.parent / 'device_tree/selected_boe_v4/qcom,mdss-dsi-display-timings'
BLOBS = {'parent': 'b0d7a1695fefb1c217336b5b1d4a3809b1e1fc1c',
         'released': 'bccd97fa5e77ba0cbfbd4e05698514dbed308cc7'}
KINDS = ('on-command', 'timing-switch-command')


def require(condition, why):
    if not condition:
        raise ValueError(why)


def source(name):
    raw = gzip.decompress((HERE / 'upstream' / (name + '.dtsi.gz')).read_bytes())
    oid = hashlib.sha1(b'blob %d\0' % len(raw) + raw).hexdigest()
    require(oid == BLOBS[name], 'source identity: ' + name)
    return raw.decode()


def nodes(text):
    text = re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)
    rows = re.findall(r'\btiming@(\d+)\s*\{([^{}]*)\}\s*;', text)
    require(len(rows) == len(re.findall(r'\btiming@\d+\s*\{', text)), 'nested/invalid timing node')
    out = {int(i): body for i, body in rows}
    require(len(rows) == len(out), 'duplicate timing node')
    return out


def prop(node, key, pattern):
    values = re.findall(r'\bqcom,mdss-dsi-' + re.escape(key) + r'\s*=\s*' + pattern + r'\s*;', node)
    require(len(values) == 1, 'missing or duplicate ' + key)
    return values[0]


def packets(blob):
    result = []
    page = None
    i = 0
    while i < len(blob):
        header = blob[i:i+7]
        size = int.from_bytes(header[5:7], 'big')
        data = blob[i+7:i+7+size]
        require(len(header) == 7 and size and len(data) == size, 'invalid descriptor')
        if len(data) == 4 and data[:3] == b'\xff\x5a\xa5':
            page = data[3]
        result.append((page, header, data))
        i += size + 7
    require(result, 'empty DSI property')
    return result


def command(node, key):
    return packets(bytes.fromhex(prop(node, key, r'\[([^\]]+)\]')))


def matched(a, b):
    require(len(a) == len(b), 'extra descriptor')
    diffs = []
    for i, ((p, h, x), (q, j, y)) in enumerate(zip(a, b)):
        require((p, h, x[0]) == (q, j, y[0]), 'framing/page/opcode mismatch')
        if x != y:
            diffs.append(i)
    chains = [i for i, (p, _, x) in enumerate(a) if (p, x[0]) == (7, 0x81)]
    require(len(chains) == 1, 'missing/extra PPS head')
    k = chains[0]
    geometry = []
    for seq in (a, b):
        chain = seq[k:k+10]
        require(len(chain) == 10 and all(p == 7 and x[0] == 0xfe for p, _, x in chain[1:]), 'PPS continuation')
        wire = b''.join(x[1:] for _, _, x in chain)
        require(len(wire) == 99 and wire[:6] == b'\0'*5 + b'\x11', 'PPS prefix')
        # Five leading vendor bytes; DSC PPS offsets 6,8 hold height,width.
        pps = wire[5:]
        geometry.append([int.from_bytes(pps[8:10], 'big'), int.from_bytes(pps[6:8], 'big')])
    require(geometry == [[1440,3168],[1080,2376]], 'PPS raster')
    idx = [i for i in diffs if a[i][0] == 0 and a[i][2] == b'\x4b\0' and b[i][2] == b'\x4b\1']
    require(len(idx) == 1 and set(diffs) == {*range(k+1,k+4), *idx}, 'unexpected paired profile delta')
    return {'packets_per_array': len(a), 'changed_indices': diffs, 'scaler_index': idx[0],
            'pps_dimensions': geometry}


def idle():
    def raw(i, key):
        return (DT / f'timing@{i}' / ('qcom,mdss-dsi-' + key)).read_bytes()

    def integer(i, key):
        return int.from_bytes(raw(i, key), 'big')

    def field(seq, op):
        rows = [x[1:] for p, _, x in seq if p == 0x2d and x[0] == op]
        require(len(rows) == 1, 'missing or duplicate page2D:' + hex(op))
        return rows[0]

    offsets = {}
    for key in KINDS:
        arrays = [raw(i, key) for i in (0,6,7)]
        require(len({len(a) for a in arrays}) == 1, 'idle lengths')
        diffs = [i for i, v in enumerate(zip(*arrays)) if len(set(v)) > 1]
        require(len(diffs) == 1, 'idle non-single byte contrast')
        offset = diffs[0]
        for array, v in zip(arrays, (0,11,119)):
            require(field(packets(array), 0x83) == bytes((v,0)) and
                    array[offset-1:offset+2] == bytes((0x83,v,0)), 'idle field mismatch')
        offsets[key] = {'size': len(arrays[0]), 'packets': len(packets(arrays[0])), 'byte_offset': offset}
    rows = []
    for i, label, x, te in ((0,120,0,0),(3,60,1,1),(4,30,3,3),(5,24,4,4),(6,10,11,0),(7,1,119,0)):
        seq = packets(raw(i, 'timing-switch-command'))
        require(field(seq, 0x83) == bytes((x,0)) and field(seq, 0xf2) == bytes([te]), 'rate selector')
        require((1+x)*label == 120, 'nonmatching code')
        nominal = integer(i,'panel-framerate')
        if i < 6:
            require(nominal == label, 'unexpected regular mode')
        else:
            require(nominal == 120 and (DT/f'timing@{i}'/f'qcom,framerate-group-special-idle-{label}hz').exists(), 'idle label')
        t = DT / f'timing@{i}' / 'qcom,mdss-mdp-transfer-time-us'
        rows.append({'node':i, 'group_rate_label':label, 'nominal_rate':nominal, '2d:83_first_byte':x, '2d:f2':te,
                     'hfront':integer(i,'h-front-porch'), 'transfer_us':int.from_bytes(t.read_bytes(),'big') if t.exists() else None})
    return {'command_comparison_0_6_7': offsets, 'stock_120_family': rows}


def audit():
    before, after = nodes(source('parent')), nodes(source('released'))
    require(set(before) == set(range(16)) and set(after) == set(range(8)), 'unexpected mode inventory')
    rows = []
    for i, fps in enumerate((120,144,90,60,30,24,120,120)):
        for body, w, h in ((before[i],1440,3168),(before[i+8],1080,2376),(after[i],1440,3168)):
            values = [int(prop(body,k,r'<(\d+)>')) for k in ('panel-framerate','panel-width','panel-height')]
            require(values == [fps,w,h], 'unmatched raster/rate')
        pair = {k: matched(command(before[i],k), command(before[i+8],k)) for k in KINDS}
        rows.append({'parent_nodes':[i,i+8], 'nominal_rate':fps, **pair})
    return {'source_blobs':BLOBS, 'parent_pairs':rows, 'selected_target':idle(),
            'physical_pwm_hz':None, 'device_io':False}


if __name__ == '__main__':
    print(json.dumps(audit(), indent=2))
