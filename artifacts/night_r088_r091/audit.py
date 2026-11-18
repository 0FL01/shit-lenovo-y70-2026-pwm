"""Offline archive inventory; no scope or device interface. Python stdlib."""
import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

ART = Path(__file__).resolve().parent.parent


def rows(path):
    with path.open(encoding='utf-8', newline='') as f:
        return list(csv.DictReader(f))


def inventory(art=ART):
    labels = rows(art/'night_r031_r033'/'legend_reads.csv')
    cal = rows(art/'scope_calibration_20261118'/'frames.csv')
    ts = [datetime.strptime(r['capture_start_utc'], '%Y%m%dT%H%M%SZ') for r in cal]
    if len(set(r['slot'] for r in labels)) != len(labels):
        raise ValueError('duplicate slot')
    if len(set(r['sha256'] for r in cal)) != len(cal):
        raise ValueError('duplicate calibration photo')
    result = {
        'r7_qc': dict(Counter(r['original_qc'] for r in labels)),
        'r7_visible_legends_by_qc': dict(Counter(
            ':'.join(r[k] for k in ('original_qc', 'time_label', 'coupling', 'multiplier'))
            for r in labels if r['time_label'])),
        'calibration_screenshot_count_by_phase': dict(Counter(r['phase'] for r in cal)),
        'calibration_host_start_span_s_not_record_length': int((max(ts)-min(ts)).total_seconds()),
        'sleep_screenshot_count_by_phase': dict(Counter(r['phase'] for r in rows(
            art/'scope_calibration_20261118'/'sleep_frames.csv'))),
        'stock_sessions': {},
    }
    for dbv, folder in [('3600', 'scope_dc_divergence_20261118'),
                        ('3601', 'scope_dc3601_divergence_20261118')]:
        frames = rows(art/folder/'frames.csv')
        pairs = [p for p in rows(art/folder/'pairs.csv') if
                 (p['ref_q'], p['dx'], p['dy']) == ('0.97', '0', '0') and p['a'] != p['b']]
        if len(set((p['a'], p['b']) for p in pairs)) != len(pairs):
            raise ValueError('duplicate phase-pair')
        result['stock_sessions'][dbv] = {
            'phase_status': dict(Counter(r['phase']+':'+r['status'] for r in frames)),
            'raster_Dmed': {p['a']+' : '+p['b']: float(p['Dmed']) for p in pairs},
        }
    return result


if __name__ == '__main__':
    print(json.dumps(inventory(), indent=2, sort_keys=True))
