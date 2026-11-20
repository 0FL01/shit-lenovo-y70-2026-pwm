"""Offline only: project public target records onto the proposed hypotheses."""
import json
from pathlib import Path
from statistics import mean


ART = Path(__file__).resolve().parents[1]
DUMPS = ART / 'ddic_regdump_20261107'
DT = ART / 'device_tree/selected_boe_v4'
R22 = ART / 'ddic_round22_31_9dladder_20261120'


def load(path):
    return json.loads(path.read_text())


def check(ok, label):
    if not ok:
        raise ValueError(label)


def native_writes():
    writes = {}
    arrays = packets = 0
    for f in DT.rglob('*command'):
        if f.name == 'qcom,mdss-dsi-te-dcs-command':  # scalar DT property
            continue
        data = f.read_bytes()
        arrays += 1
        i, page = 0, 0
        while i < len(data):
            n = int.from_bytes(data[i + 5:i + 7], 'big')
            p = data[i + 7:i + 7 + n]
            check(n > 0 and len(p) == n, f)
            if len(p) == 4 and p[:3] == bytes.fromhex('ff 5a a5'):
                page = p[3]
            elif data[i] in (0x05, 0x15, 0x39):  # DCS writes only
                writes.setdefault(f'{page:02X}:{p[0]:02X}', set()).add(p[1:])
            i += 7 + n
            packets += 1
    check((arrays, packets) == (52, 1101), 'selected DT coverage')
    return writes


def main():
    triplet = ['23:A4', '23:AD', '23:B4']
    pairs = [('4F:80', '4F:81'), ('4F:C0', '4F:C1'), ('4F:C8', '4F:C9'),
             ('4F:D0', '4F:D1'), ('4F:D8', '4F:D9')]
    split = [('23:98', '23:99'), ('23:9A', '23:9B'), ('23:9C', '23:9D'),
             ('23:A0', '23:A1'), ('23:A2', '23:A3'), ('23:A9', '23:AA'),
             ('24:80', '24:81'), ('24:9B', '24:9C'), ('24:9D', '24:9E')]
    fields = triplet + ['23:A5', '23:AE', '23:B5', '23:C1', '23:C2', '23:C3', '23:C4', '00:52']
    fields += [k for pair in pairs + split for k in pair]
    print('DBV/refresh   A4 AD B4   C1 / C2 (prefix)   4F pairs: 80 C0 C8 D0 D8')
    for idx, (dbv, hz, last) in enumerate([(3584, 120, 0x65), (3646, 120, 0x10),
                                          (3584, 144, 0x55), (3584, 60, 0x65)], 1):
        path = DUMPS / f's{idx}_dbv{dbv}_{hz}'
        run = load(path / 'run.json')
        check(run['read_count'] == 9728 and not run['error_count'] and run['panel_dc_before'] == '0'
              and run['dbv_before'] == run['dbv_after'] == str(dbv)
              and float(run['refresh_request']) == hz, path.name)
        check(not ({x['reg'] for x in run['pass_mismatches']} & set(fields)), 'passes differ')
        reg = load(path / 'registers.json')
        b = {k: bytes.fromhex(reg[k]) for k in fields}
        check(all(len(v) == 40 for v in b.values()), 'legacy request length')
        def one(k):
            return b[k][0]

        t = bytes(map(one, triplet))
        c1, c2 = b['23:C1'][:3], b['23:C2'][:3]
        p = [bytes(map(one, pair)).hex() for pair in pairs]
        check(t == b'\x10' * 3 and not any(map(one, ['23:A5', '23:AE', '23:B5'])), 'triplets')
        check(c1 == bytes([0, 0, last]) and c2 == b['23:C3'][:3] == b['23:C4'][:3]
              == bytes.fromhex('00 03 84') and int.from_bytes(b['00:52'][:2], 'big') == dbv, 'C1/C2/DBV')
        check(p == ['0106'] * 4 + ['0110'], '4F pairs')
        check([bytes(map(one, pair)).hex() for pair in split] ==
              ['3fff', '17ff', '11ff', '3ffc', '3ffc'] + ['0e11'] * 4, 'split prefixes')
        print(f'{dbv}/{hz:<3d}      {t.hex(" ")}   {c1.hex(" ")} / {c2.hex(" ")}   {" ".join(p)}')

    qualified = sorted((ART / 'c1_live_20261108').glob('*_qualified.json'))
    qualified += sorted((ART / 'stock_c1_20261108_01').glob('P*.json'))
    check(len(qualified) == 11, 'C1 record count')
    codes = []
    for f in qualified:
        r = load(f)
        check(r['page'] == '23' and r['opcode'] == 'C1' and r['framing_qualified']
              and r['single_receive'] and r['header_hex'] == '1c 03 00 16'
              and len(r['data']) == r['requested'] == 3 and r['cleanup_verified'], f.name)
        codes.append((r['native_dbv'], round(r['software_refresh']), int.from_bytes(bytes(r['data']), 'big')))
    print('C1 WC=3 (DBV, software Hz, BE value):', sorted(set(codes)))

    latch = load(DUMPS / 'stock_latch.json')['phases']
    history = load(DUMPS / 'stock_timing_history.json')['phases']
    check([q['registers']['4F:81'] for q in history] == [[16], [6], [6], [16]], 'mode history')
    check([q['dc'] for q in latch] == [0, 1, 0] and
          [q['registers']['24:9D'] for q in latch] == [[14], [142], [14]], 'stock DC cycle')
    r3 = load(ART / 'ddic_round3_06x_dng_20261119/spec_round3_20261119.json')['candidates']
    c2 = next(r for r in r3 if r['name'] == '23:C2 (3B)')
    check(c2['write_attempt'].startswith('00 07 08') and not c2['readback_changed'] and
          c2['post_readback'] == '00 03 84', 'C2 direct write')
    w = native_writes()
    check(not any(k in w for k in triplet + ['23:C1', '23:C2']), 'unexpected native writer')
    check(w['4F:81'] == {b'\x06', b'\x10'}, '4F:81 writes')
    for k in triplet + ['23:C1', '23:C2', '4F:81', '23:AA', '24:9E']:
        print(k, 'native data:', ', '.join(v.hex(' ') for v in sorted(w.get(k, ()))) or '—')

    reads = load(R22 / 'spec_round22_31.json')['ddic_readbacks']
    optics = load(R22 / 'summary_round22_31.json')['phases']
    for req, rb in [('4e', '0e'), ('5e', '1e'), ('6e', '2e'), ('7e', '3e'), ('ce', '8e'), ('ee', 'ae')]:
        phase = ('r23' if int(req, 16) < 128 else 'r24') + '_9d' + req
        check(reads['r22_' + phase + '_apply']['24:9D'] == rb, f'9D {req}→{rb}')
    phases = ['r23_9d8e_ref', 'r24_9d8f']
    r0, r1 = (reads['r22_' + phase + '_apply'] for phase in phases)
    check(r0.keys() == r1.keys(), 'matched reported fields')
    delta = [k for k in r0 if r0[k] != r1[k]]
    levels = [[f['raw_mean_dn'] for f in optics[phase]] for phase in phases]
    check(delta == ['24:9D'] and [r0[delta[0]], r1[delta[0]]] == ['8e', '8f'] and
          r0 == {'00:52': '02 00', '23:A9': '8e', '24:9D': '8e', '23:80': '90', '23:C1': '00 00 10'}
          and max(levels[0]) < min(levels[1]), 'neighbor contrast')
    print('R22 contrast:', delta[0], [(len(x), round(mean(x), 3)) for x in levels], '(n, mean DN)')
    print(f'Assuming low byte 11: code ratio {0x0f11 / 0x0e11:.3f}; observed mean DN ratio '
          f'{mean(levels[1]) / mean(levels[0]):.2f}')
    # Rank low-byte probes: require an optical contrast in the adjacent high byte,
    # native 1-byte write shape and observed short stock 0x11 return on that very low address.
    eligible = [lo for hi, lo in split if hi in delta and w.get(lo) == {b'\x11'} and
                all(q['registers'].get(lo) == [0x11] for q in latch)]
    check(eligible == ['24:9E'], f'no unique low-byte candidate: {eligible}')
    print('Selected:', eligible[0], '11 → 91 → 11 (hypothesis, not authorized)')


if __name__ == '__main__':
    main()
