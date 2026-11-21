#!/usr/bin/env python3
"""history.py ARCHIVE windows.csv dispatch.csv > history.csv

Bind one closed R47 main/control acquisition in receipt order. One row per
window, plus the validated unphotographed *_down steps. The initial OFF side
is inferred from inhdr at BL 13119. Thereafter basis_tag names the latest
corroborated APL send in THIS epoch (or inhdr until the first toggle).
This is software/dispatch history across sampled intervals, not DDIC readback.
"""

import argparse
import csv
from decimal import Decimal
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r43_20261121.windows import PHASE, PRE, POST, original, read_windows, require
from direct_camera_r47_20261121 import dispatch


INITIAL = 13119
THRESHOLD = 16000
REQUEST = r'(?:0(?:\.\d+)?|1(?:\.0+)?)'
POINT = re.compile(rf'POINT inhdr req=({REQUEST}) bl=({INITIAL})')
TX = re.compile(rf'TX ({PHASE}) request=({REQUEST}) settled=(\d+)')
DONE = {'R47_OPTICAL_DONE', 'R47_CONTROLS_DONE'}


def table(path, key):
    with path.open(newline='') as f:
        reader = csv.DictReader(f, strict=True)
        cols = reader.fieldnames or []
        require(key in cols and len(cols) == len(set(cols)), f'{path.name}: invalid header')
        rows = {}
        for r in reader:
            require(None not in r and None not in r.values() and r[key] not in rows and r[key],
                    f'{path.name}:{reader.line_num}: malformed or duplicate row')
            rows[r[key]] = r
        require(rows, f'{path.name}: no rows')
        return rows


def sample(archive, stem):
    """Wake epoch, native BL, display dump monotonic uptime (ms) on this target."""
    def text(ext):
        return original(archive / f'{stem}.{ext}').read_text().strip()

    times = re.findall(r'^ +mLightSensorEnableTime=(\d+) \((\d+) ms ago\)[ \t]*$', text('display'), re.M)
    require(len(times) == 1, f'{stem}: missing or ambiguous dump uptime')
    return int(text('wake')), int(text('bl')), sum(map(int, times[0]))


def verify_tx(archive, tag, prev, bl, supplied, refs):
    def check(ok, msg):
        require(ok, f'{tag}: {msg}')

    # Rebind provenance before using derived CSV evidence: a tag/BL pair can
    # repeat in another run. The three settle reads are outside R44_KLOG.
    klog = original(archive / f'{tag}.klog').read_text(errors='replace').splitlines()
    cap = original(archive / f'{tag}.capture').read_text(errors='replace').splitlines()
    check([s for s in cap if s.startswith('R47_SETTLE')] == [f'R47_SETTLE {bl}'] * 3,
          'settle samples differ from TX receipt')
    r = dispatch.summarize(tag, klog, refs)
    r.update(dispatch.trace_summary(tag, klog, cap))
    for k, v in r.items():
        check(supplied.get(k) == ('' if v is None else str(v)), f'dispatch.csv differs from this archive: {k}')
    check(r['bracket'] == r['trace_status'] == 'ok' and r['invalid_tx'] == r['loss_notices'] == 0,
          'incomplete TX/trace interval')
    check(all(r[p + '_profile_missed'] == 0 for p in dispatch.PROBES), 'missing probe or profile misses')
    check(not any(r[k] for k in ('exact_hbm_on', 'exact_hbm_off', 'hs_prefix_only_on', 'hs_prefix_only_off')),
          'HBM sequence or ambiguous HS prefix')

    was_on, now_on = prev > THRESHOLD, bl > THRESHOLD
    change = was_on != now_on
    check((r['exact_apl_on'], r['exact_apl_off']) == (int(change and now_on), int(change and not now_on)),
          'exact APL TX arrays disagree with threshold history')
    check(r['oem_apl_count'] == r['apl_send_returns'] == int(change) and
          r['apl_send_rc_hist'] == ('0:1' if change else ''), 'OEM count or APL caller return disagrees')

    # The OEM level can be an intermediate ramp step, especially on *_down.
    # Match it to the actual crossing entry and MOT sender's APL caller, not
    # necessarily to the final settled level. No-op shams may have zero entries.
    level, crossings, send_levels = prev, [], []
    for event in (r['apl_trace_events'] or '').split('; '):
        if m := re.fullmatch(r'\d+\.\d+ entry level=(\d+)', event):
            nxt = int(m[1])
            if (nxt > THRESHOLD) != (level > THRESHOLD):
                crossings.append(nxt)
            level = nxt
        elif event.endswith(' send caller=dsi_panel_set_apl rc=0'):
            send_levels.append(level)
    check(level == bl and len(crossings) == int(change) and crossings == send_levels,
          'entry levels, threshold crossings or APL sender context disagree')
    trigger = crossings[0] if change else None
    expected = f'threshold={THRESHOLD} state={int(now_on)} bl_lvl={trigger}' if change else ''
    check(r['oem_apl_config'] == expected, 'OEM threshold/state/bl_lvl disagree with crossing')
    return r, trigger


def bind(archive, windows_csv, dispatch_csv):
    windows, sends = table(windows_csv, 'phase'), table(dispatch_csv, 'tag')
    log = original(archive / 'acquisition.log')
    closed = {phase: len(sizes) for phase, *_, sizes in read_windows(log)}
    require(closed.keys() == windows.keys(), 'windows.csv inventory differs from closed windows')
    epoch = int(original(archive / 'epoch').read_text())
    start_epoch, start_bl, last_ms = sample(archive, 'inhdr')
    require(start_epoch == epoch and start_bl == INITIAL and epoch <= last_ms, 'inhdr baseline/epoch mismatch')
    refs = dispatch.references()
    rows, tx_seen, paired = [], set(), set()
    initial = done = in_window = pending = group = None
    prev, basis = INITIAL, 'inhdr'

    for n, line in enumerate(log.read_text().splitlines(), 1):
        kind = line.split(maxsplit=1)[:1]
        where = f'{log.name}:{n}'
        if kind == ['POINT']:
            require(POINT.fullmatch(line) and not initial and not rows and not done, f'{where}: unexpected POINT')
            initial = True
        elif kind == ['TX']:
            m = TX.fullmatch(line)
            require(initial and m and not (done or pending or in_window), f'{where}: malformed or unbound TX')
            tag, request, bl = m[1], m[2], int(m[3])
            slot, sep, leg = tag.rpartition('_')
            require(sep and slot and tag not in tx_seen and tag in sends and group in (None, slot),
                    f'{where}: duplicate, missing or out-of-excursion TX {tag}')
            require(not (leg == 'down' and (not group or bl != INITIAL)), f'{tag}: unexpected return')
            if leg == 'Sham':
                require(rows and rows[-1]['tx_tag'] == slot + '_B' and prev == bl and
                        Decimal(request) == Decimal(rows[-1]['request']), f'{tag}: not a repeat of the prior setter')
            r, trigger = verify_tx(archive, tag, prev, bl, sends[tag], refs)
            begin, end = (Decimal(r[k]) * 1000 for k in ('begin_s', 'end_s'))
            require(last_ms <= begin < end, f'{tag}: TX outside epoch or overlaps previous window/TX')
            last_ms = end
            if trigger is not None:
                basis = tag
            toggle = ('APL_ON' if bl > THRESHOLD else 'APL_OFF') if trigger is not None else 'none'
            rows.append(dict(kind='down' if leg == 'down' else 'window', phase='', tx_tag=tag, wake_epoch=epoch,
                             request=request, previous_bl=prev, settled_bl=bl, toggle=toggle,
                             exact_sets=r['exact_sets'], oem_trigger_bl=trigger, apl_entries=r['apl_entries'],
                             apl_caller_rc0=r['apl_send_returns'], basis_tag=basis,
                             history_basis='initial_below_threshold_inference' if basis == 'inhdr'
                             else 'corroborated_send_this_epoch', apl_side='ON' if bl > THRESHOLD else 'OFF',
                             ddic_readback='none'))
            pending = None if leg == 'down' else tag
            group = None if leg == 'down' else slot
            tx_seen.add(tag)
            prev = bl
        elif kind == ['PRE']:
            m = PRE.fullmatch(line)
            require(m and pending and not done and not in_window, f'{where}: PRE without a fresh TX')
            phase, scene, bl, hwc, hz, ns, wake = m.groups()
            require(phase in windows and phase not in paired, f'{phase}: missing or duplicate window')
            w = windows[phase]
            expected = dict(sysfs_bl=bl, wake_epoch=wake, frames=str(closed[phase]), scene=scene,
                            hwc_id=hwc, exposure_ns=ns)
            require(all(w.get(k) == v for k, v in expected.items()) and float(w.get('sf_refresh_hz', 'nan')) == int(hz)
                    and int(bl) == prev and int(wake) == epoch,
                    f'{phase}: windows.csv, TX settle, PRE or epoch disagree')
            # Control windows additionally publish the preceding request and
            # native-dispatch checks; compare them where supplied.
            step = rows[-1]
            native = dict(native_tag=pending, request_sdr=step['request'], native_apl_send=
                          {'APL_ON': 'on', 'APL_OFF': 'off', 'none': 'none'}[step['toggle']],
                          dispatch_begin_s=r['begin_s'], dispatch_end_s=r['end_s'])
            for k in ('exact_apl_on', 'exact_apl_off', 'apl_send_returns', 'apl_send_rc_hist'):
                native[k] = str(r[k])
            require(all(k not in w or w[k] == v for k, v in native.items()),
                    f'{phase}: control window disagrees with preceding TX')
            for side in ('pre', 'post'):
                actual_epoch, actual_bl, ms = sample(archive, f'{phase}-{side}')
                ordered = last_ms < ms + 1 if side == 'pre' else last_ms < ms  # dump uptime has ms resolution
                require((actual_epoch, actual_bl) == (epoch, prev) and ordered and
                        int(w.get(f'display_uptime_ms_{side}', ms)) == ms,
                        f'{phase}-{side}: BL/epoch or chronology differs from immediately preceding evidence')
                last_ms = ms
            rows[-1]['phase'] = phase
            paired.add(phase)
            in_window, pending = phase, None
        elif kind == ['POST']:
            m = POST.fullmatch(line)
            require(m and in_window == m[1], f'{where}: mismatched POST')
            in_window = None
        elif kind and kind[0] in DONE:
            require(line in DONE and initial and rows and not (done or pending or in_window or group)
                    and prev == INITIAL, f'{where}: duplicate or incomplete acquisition close')
            done = line

    require(done and paired == windows.keys(), 'acquisition not closed or unbound windows')
    require(tx_seen == sends.keys() == {p.stem for p in archive.glob('*.klog')} ==
            {p.stem for p in archive.glob('*.capture')}, 'TX, dispatch.csv and raw capture inventories differ')
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for dest, metavar in (('archive', 'ARCHIVE'), ('windows', 'windows.csv'), ('dispatch', 'dispatch.csv')):
        ap.add_argument(dest, metavar=metavar, type=Path)
    args = ap.parse_args()
    try:
        rows = bind(args.archive, args.windows, args.dispatch)
    except (OSError, ValueError, csv.Error) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, fieldnames=rows[0], lineterminator='\n')
    out.writeheader()
    out.writerows(rows)


if __name__ == '__main__':
    main()
