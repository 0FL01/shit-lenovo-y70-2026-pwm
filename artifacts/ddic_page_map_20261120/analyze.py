#!/usr/bin/env python3
"""Offline archive audit. Reads saved files, writes a sanitized report to stdout."""
import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path

ART = Path(__file__).resolve().parents[1]
BASE = ART / 'ddic_regdump_20261107'
sys.dont_write_bytecode = True
sys.path.insert(0, str(ART.parent / '06-tools'))
from audit_pwm_archive import parse_packets

RUNS = ('s1_dbv3584_120', 's2_dbv3646_120', 's3_dbv3584_144', 's4_dbv3584_60')


def require(ok, what):
    if not ok:
        raise ValueError(what)


def hx(n):
    return f'{n:02X}'


def addr(k):
    return ':'.join(map(hx, k))


def nums(it):
    return ' '.join(map(hx, sorted(it))) or '-'


def load(path):
    return json.loads(path.read_text())


def dt_pages():
    pp = set()
    for f in (ART / 'device_tree/selected_boe_v4').rglob('*-command'):
        if f.stat().st_size > 4:  # omit TE scalar
            pp.update(q['page'] for q in parse_packets(f.read_bytes()) if q['is_page_selector'])
    return sorted(pp)


def broad(pages):
    print('S1..S4 | DBV before/after | SF vsync before/after | DC before | R | pass disagreements (40B)')
    allkeys = {(p, r) for p in pages for r in range(256)}
    tables = []
    for name in RUNS:
        here = BASE / name
        run = load(here / 'run.json')
        rows = (here / 'raw.txt').read_text().splitlines()
        header = 'BEGIN passes=2 len=40 pages=' + ' '.join(f'0x{p:02x}' for p in pages)
        require(rows[0] == header and rows[-2:] == ['END', 'ESD_RESTORED reg_read'], name)
        one, two = {}, {}
        for line in rows[1:-2]:
            kind, pas, page, reg, *data = line.split()
            require(kind == 'R' and pas in ('1', '2') and len(data) == 40, name)
            k = (int(page, 16), int(reg, 16))
            t = one if pas == '1' else two
            require(k not in t, f'duplicate in {name}')
            t[k] = bytes(int(x, 16) for x in data)
        n = len(one) + len(two)
        disag = sum(one[k] != two[k] for k in one)
        require(one.keys() == two.keys() == allkeys and n == run['read_count'] and
                not run['error_count'] and run['finished_at_utc'] and
                run['esd_mode_after'].rstrip('\0') == 'reg_read' and
                disag == len(run['pass_mismatches']), name)
        mode = [re.search(r'vsyncRate=([\d.]+)', run['refresh_' + s])[1] for s in ('before', 'after')]
        require(all(abs(float(m) - run['refresh_request']) < .01 for m in mode) and
                run['dbv_before'] == run['dbv_after'] and run['panel_dc_before'] == '0', name)
        print(name, run['dbv_before'] + '/' + run['dbv_after'], '/'.join(mode), 0, n, disag)
        tables.extend((one, two))
    print('\nOther attempts | raw R | raw E | successful FE(page:value) | finish timestamp')
    for meta in sorted(BASE.glob('*/run.json')):
        if meta.parent.name in RUNS:
            continue
        raw = meta.with_name('raw.txt')
        lines = raw.read_text().splitlines() if raw.exists() else []
        rr = [line.split() for line in lines if line.startswith('R ')]
        fe = [addr((int(l[2], 16), int(l[4], 16))) for l in rr if int(l[3], 16) == 254]
        print(meta.parent.name, len(rr) if raw.exists() else 'no-raw',
              sum(l.startswith('E ') for l in lines) if raw.exists() else '-',
              ' '.join(fe) or '-', bool(load(meta).get('finished_at_utc')))
        if load(meta).get('scope') == 'census':
            events = load(meta)['events']
            embedded = [l for e in events for l in e['stdout'].splitlines() if l.startswith(('R ', 'RD '))]
            print('  census files:', ', '.join(sorted(f.name for f in meta.parent.iterdir())),
                  '| events:', len(events), '| result lines in event stdout:', len(embedded))
    return tables


def chunks(directory):
    maps = {'pwm': {}, 'dc': {}}
    files = sorted(directory.glob('r22_p??_??_*.txt'))
    require(files, 'no R22 page chunks')
    for path in files:
        p, block, mode = re.fullmatch(r'r22_p([0-9A-F]{2})_(0[0-9A-F])_(dc|pwm)', path.stem).groups()
        p, block = int(p, 16), int(block, 16)
        lines = path.read_text().splitlines()
        require(len(lines) == 19 and lines[0] == 'ESD_ACTIVE esd_sw_sim_success' and
                lines[-2:] == ['PHASE_DONE fail=0', 'ESD_RESTORED reg_read'], path.name)
        for idx, line in enumerate(lines[1:-2]):
            page, reg, val = re.fullmatch(r'RD ([0-9A-Fa-f]{2}) 0x([\da-fA-F]{2}) 0x([\da-fA-F]{2})\s*', line).groups()
            k = (int(page, 16), int(reg, 16))
            require(k == (p, block * 16 + idx) and k not in maps[mode], path.name)
            maps[mode][k] = int(val, 16)
    print('\nR22 single-byte archive: chunks', len(files))
    for mode, t in maps.items():
        print(mode, len(t), 'page:count', ' '.join(f'{hx(p)}:{n}' for p, n in sorted(Counter(p for p, r in t).items())))
    pwm, dc = maps.values()
    both = pwm.keys() & dc.keys()
    print('paired', len(both), '| page:opcode PWM/DC')
    for k in sorted(both):
        if pwm[k] != dc[k]:
            print(addr(k), hx(pwm[k]) + '/' + hx(dc[k]))
    print('Separate fresh recipe reference, R23 ret/apply; not filled into the R22 grid:')
    for stage in ('ret', 'apply'):
        lines = (directory / f'r22_r23_9d8e_ref_{stage}.txt').read_text().splitlines()
        require(lines[-2:] == ['PHASE_DONE fail=0', 'ESD_RESTORED reg_read'], stage)
        fields = {addr((int(p, 16), int(r, 16))): bytes(int(x, 16) for x in data).hex().upper()
                  for kind, p, r, *data in (l.split() for l in lines if l.startswith('RD '))}
        print(stage, *(k + '=' + fields[k] for k in ('00:52', '23:A9', '24:9D', '23:80', '23:C1')))
    return maps


def page_test(pages, ts, r22):
    print('\nCorpus | FE matched/observed')
    for label, pairs in [('S1..S4', [(p, t[p, 254][0]) for t in ts for p in pages]),
                         *((m, [(p, x) for (p, r), x in t.items() if r == 254]) for m, t in r22.items())]:
        print(label, f'{sum(p == x for p, x in pairs)}/{len(pairs)}')
    def same(p, r, v):
        return all(t[p, r][0] == v for t in ts)
    print('Opcodes whose first byte echoes ALL 19 pages in ALL eight passes:',
          nums(r for r in range(256) if all(same(p, r, p) for p in pages)))
    print('Coincidental matches on nonzero pages, excluding FE (all eight passes):',
          ' '.join(addr((p, r)) for p in pages if p for r in range(256) if r != 254 and same(p, r, p)))
    print('Page 00 other opcodes stable first byte 00:', sum(same(0, r, 0) for r in range(256) if r != 254))
    print('Shared responses over 19 pages x 8 passes: 04=D2, 0A=9C:',
          all(same(p, 4, 0xD2) and same(p, 10, 0x9C) for p in pages))

    # High-opcode first-byte tuples independent of FE; allow mode variants per page.
    regs = (0x80, 0x82, 0xBA)
    sig = {p: {tuple(t[p, r][0] for r in regs) for t in ts} for p in pages}
    for t in r22.values():
        for p in pages:
            if all((p, r) in t for r in regs):
                sig[p].add(tuple(t[p, r] for r in regs))
    require(not any(sig[p] & sig[q] for p, q in combinations(pages, 2)) and
            all((0, 0, 0) not in s for s in sig.values()), 'signature collision/blank')
    print('Page | 80.82.BA first-byte signature (observed variants; cell-ID page redacted)')
    for p in pages:
        print(hx(p), 'distinct/redacted' if p == 0x1D else ' / '.join(bytes(v).hex('.').upper() for v in sorted(sig[p])))
    print('4F pairs at 80,C0,C8,D0,D8; first bytes of adjacent opcodes in S1..S4:')
    for r in (0x80, 0xC0, 0xC8, 0xD0, 0xD8):
        print(hx(r), ' / '.join(sorted({hx(t[0x4F, r][0]) + '.' + hx(t[0x4F, r+1][0]) for t in ts})))


def repeats(pages, ts):
    # Exact repeats in opcode space; equality of the first six saved bytes only.
    print('\nConsecutive structured repeats in 80..FD stable over eight passes | page start stride copies')
    for p in pages:
        samples = [{s[p, r][:6] for s in ts} for r in range(256)]
        seq = [next(iter(s)) if len(s) == 1 else None for s in samples]
        for w in (2, 4, 6, 8, 12, 16):
            best = (0, 0)
            for i in range(0x80, 0xFE - 4 * w + 1):
                block = seq[i:i+w]
                if None in block:
                    continue
                if (len(set(block)) < 2 or len({v for row in block for v in row} - {0, 255}) < 2
                        or any(block == block[:d]*(w//d) for d in range(1, w) if w % d == 0)):
                    continue
                n = 1
                while i+(n+1)*w <= 0xFE and seq[i+n*w:i+(n+1)*w] == block:
                    n += 1
                best = max(best, (n, -i))
            n, neg_i = best
            if n >= 4:
                print(hx(p), hx(-neg_i), w, n)


def differentials(pages, ts):
    print('\nBroad differential: values in S1,S2,S3,S4 order. Require agreement within EVERY run.')
    for width in (1, 3, 40):
        groups = defaultdict(list)
        unstable = []
        for k in sorted(ts[0]):
            a = [t[k][:width] for t in ts]
            if a[::2] != a[1::2]:
                unstable.append(k)
            elif len(set(a[::2])) > 1:
                groups[k[1], tuple(a[::2])].append(k[0])
        print('width', width, 'unstable', len(unstable), 'stable-different', sum(map(len, groups.values())))
        if width == 3:
            print('excluded:', ' '.join(map(addr, unstable)))
            for (r, vals), ps in groups.items():
                print(('*' if len(ps) == len(pages) else '+'.join(map(hx, ps))) + ':' + hx(r),
                      '/'.join(v.hex().upper() for v in vals), f'n={len(ps)}')
    for stem in ('stock_latch', 'stock_timing_history'):
        d = load(BASE / (stem + '.json'))
        require(d['restored'] and not d['cleanup_errors'], stem)
        phases = d['phases']
        keys = phases[0]['registers'].keys()
        require(all(p['registers'].keys() == keys for p in phases), stem)
        print(stem, len(keys), 'opcodes;', ' / '.join(str(p.get('label', f"DC{p['dc']}")) for p in phases))
        for k in sorted(keys):
            v = [bytes(p['registers'][k]).hex().upper() for p in phases]
            if len(set(v)) > 1:
                print(k, '/'.join(v))
    print('Independent single-opcode captures, DBV / SF-Hz / 23:C1 (qualified WC3)')
    for f in sorted((ART / 'c1_live_20261108').glob('*_qualified.json'), key=lambda f: load(f)['started_at_utc']):
        d = load(f)
        require(d['framing_qualified'] and d['single_receive'] and d['cleanup_verified'] and
                (d['page'], d['opcode'], d['header_hex'], len(d['data'])) == ('23', 'C1', '1c 03 00 16', 3), f.name)
        print(d['native_dbv'], d['software_refresh'], bytes(d['data']).hex().upper())


def queue(pages):
    lo = set(range(128)) - set(pages)
    cn = load(ART / 'cn_panel_commands.json')
    donors = {q['page'] for e in cn['entries'] for panel in e['boe_panels']
              for side in ('dc_on', 'dc_off') for q in parse_packets(bytes.fromhex(panel[side]['raw_hex']))
              if q['is_page_selector']} & lo
    # Older same-model v2 timing reference: ddic_table_format_20261107/result.md:65-71.
    ref = {2} & lo
    near = {p + i for p in (0x23, 0x24, 0x4F, 0x51, 0x52, 0x53, 0x63) for i in (-1, 1)} & lo
    print('\nUnobserved selector IDs (offline queue, not an execution list)')
    for label, group in [('archived ILI97701A v2 only', ref), ('regional DC donor only', donors),
                         ('numeric neighbors only', near), ('other low IDs', lo.copy())]:
        take = lo & group
        print(label, len(take), nums(take))
        lo -= take
    print('outside S5 scope, independent backlog:', nums(set(range(128, 256)) - set(pages)))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--r22', type=Path, help='existing private R22 chunk directory; omit for public-only audit')
    args = ap.parse_args()
    pages = dt_pages()
    tables = broad(pages)
    maps = chunks(args.r22) if args.r22 else {}
    if not maps:
        print('Private R22 not supplied; no R22 coverage claimed.')
    page_test(pages, tables, maps)
    repeats(pages, tables)
    differentials(pages, tables)
    queue(pages)
