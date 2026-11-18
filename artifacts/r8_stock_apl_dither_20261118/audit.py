#!/usr/bin/env python3
"""Bounded offline audit, standard library only; never opens ADB, sysfs or a network."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

CN = 'extracted/XT2611-1/W3WWL36.65-11-18/filesystems/vendor_a/etc/display/qdcm_calib_data_mipi_mot_cmd_boe_1440p_dsc_682.json'
PANEL = 'artifacts/device_tree/selected_boe_v4'
MODULE = 'artifacts/kernel/gki_r59/target_vendor/msm_drm.ko'
MID = '1bec69faec736e7288f38e4cb83314c37c60d33e6b383213316fd880aa0b1804'
CID = 'bda2618a08c53244d90a913c167d40ba386e954f02737ef6423bf79e735ca1db'
SID = 'mipi_mot_cmd_boe_1440p_dsc_682'


def asset(s):
    b = bytes.fromhex(s)
    i = len(b) % 2
    return json.loads(b[:i] + b''.join(b[q:q+2][::-1] for q in range(i,len(b),2)))


def decode_packets(b):
    index = 0
    out = []
    while index < len(b):
        h = b[index:index+7]
        if len(h) != 7:
            raise ValueError('truncated DSI descriptor')
        n = int.from_bytes(h[5:7], 'big')
        body = b[index+7:index+7+n]
        if n == 0 or len(body) != n:
            raise ValueError('truncated/empty DSI packet')
        out.append(body.hex(' '))
        index += 7+n
    return out


def text_section(b):
    if b[:6] != b'\x7fELF\x02\x01':
        raise ValueError('expected ELF64LE')
    shoff = struct.unpack_from('<Q',b,40)[0]
    size,num,names = struct.unpack_from('<HHH',b,58)
    def sh(i):
        return struct.unpack_from('<IIQQQQIIQQ',b,shoff+i*size)
    namesoff = sh(names)[4]
    for i in range(num):
        name,_,_,_,off,n,*_ = sh(i)
        if b[namesoff+name:namesoff+name+6] == b'.text\x00':
            return b[off:off+n]
    raise ValueError('no .text')


def evidence(root):
    dt = root / PANEL
    def get(s):
        return (dt/s).read_bytes()
    def u(s):
        v=get(s)
        if len(v) != 4:
            raise ValueError('not a single DT cell')
        return int.from_bytes(v,'big')
    cfg = (root/CN).read_bytes()
    if hashlib.sha256(cfg).hexdigest() != CID:
        raise ValueError('CN calibration file does not match reference')
    d = json.loads(cfg)
    profiles = {}
    for name, props in d[SID].items():
        profiles[name] = {k:asset(props[k]) for k in ('PostBlendDither','PostBlendPaDither')}
    b = (root/MODULE).read_bytes()
    ident = hashlib.sha256(b).hexdigest()
    if ident != MID:
        raise ValueError('target module does not match reference')
    code = text_section(b)
    # These opcodes correspond to the existing target annotated disassembly.
    probes = {0x1b5a6c:0x6b01013f,0x1b5a70:0x54000262,0x1b5a74:0x370001a8,
              0x1b5a7c:0x35000168,0x1b5ad4:0x94003e63,0x1b5afc:0x392122d4,
              0x1b5b04:0x34fffd35}
    actual={a:struct.unpack_from('<I',code,a)[0] for a in probes}
    if probes != actual:
        raise ValueError('target APL code anchor mismatch')
    return {'module_sha256':ident,'text_words':{hex(a):hex(w) for a,w in actual.items()},
            'dt_apl_enabled': get('qcom,apl-enabled') == b'',
            'threshold':u('qcom,mdss-dsi-panel-APL-THRESHOLD-BL'),
            'func_id':u('qcom,mdss-dsi-panel-APL-FUNC-ID'),
            'max_dbv':u('qcom,mdss-dsi-bl-max-level'),
            'payloads':{k:decode_packets(get('qcom,mdss-dsi-'+k+'-command'))
                        for k in ('panel-apl-on','panel-apl-off','hbm-on','hbm-off')},
            'cn_qdcm':{'sha256':hashlib.sha256(cfg).hexdigest(),'bytes':len(cfg),
                       'version':d['Version'],'panel':SID,'profiles':profiles,
                       'common_dither_fields':sorted(k for k in d['Common'] if 'dither' in k.lower())},
            'global_qdcm_identity':None,'manual_16001_reachability':None,
            'optical_pwm_hz':None,'device_actions':0}


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('source_repo', type=Path, help='checkout containing stock binaries and extracted firmware')
    args = ap.parse_args()
    print(json.dumps(evidence(args.source_repo), indent=2, sort_keys=True))
