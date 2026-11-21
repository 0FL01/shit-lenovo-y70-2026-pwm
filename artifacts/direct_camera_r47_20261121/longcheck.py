#!/usr/bin/env python3
"""R47 auxiliary recurrence check: python3 -B longcheck.py FRAMES > longcheck.csv

Use the frozen R46 strip, not coordinates selected on R47. Qualify all three
states before using DAY: if 1250 us clips, use a fresh 500-us CAL pair for each
state on the same strip. A shorter shutter cannot rescue a non-clipping failure.
For timing only use the four independent DAY releases at each of 125/200/312.5
us per state. R46 frame() applies the native/half-strip, fine/ripple, spatial
and blur-shape tests, including 100 Bayer cells beyond the outer event bounds.

Both shutter-pair fits must pass in each state, with no individual search-edge
optimum and <=10% spread / mean between gradients. All qualified adjacent gaps
in that state must agree (range <=10% of median) across >=2 distinct releases.
Only a state passing every timing gate on the jointly qualified field reports
a conditional period, using the 125 vs 312.5 gradient and a median of per-frame
median gaps. A failed state prevents an A/B/C comparison, not another state's
own measurement. No pooled period or reciprocal of a single gap is reported.
This assumes stationary recurring broad events and a constant local phase
gradient. It does not measure physical PWM Hz. See windows.py for state binding.
"""

import argparse
import csv
from pathlib import Path
from statistics import median
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from direct_camera_r46_20261121 import strip, timing
from direct_camera_r47_20261121.field import STATES, releases


ROI = (580, 1365, 725, 790)  # y0, y1, x0, x1 in native Bayer cells
SHUTTERS = {'125': 125., '200': 200., '312': 312.5}
FIELDS = ('kind state phase frame_n exposure_us status y0 y1 x0 x1 guard margin_cells '
          'cal_1250_status cal_1250_clip_n cal_500_status field_us state_field_status '
          'field_clip_n field_floor_n uncovered_rows lateral_bad_rows min_release_quarter_lit_frac '
          'min_pair_score mean_dn left_mean_dn right_mean_dn clip_n floor_n fine_status free_status '
          'free_semiamp_pct free_gate_pct r35_177p35_status r35_177p35_gate_pct '
          'r35_188p50_status r35_188p50_gate_pct morph_n broad_n bounds70_raw_y centers_raw_y '
          'fwhm_raw_rows rejected gaps_raw_rows blur_status blur_center_raw_y blur_other_edge_flag '
          'short_us long_us short_n long_n pairs effective_us_per_raw_row pair_median pair_min pair_max '
          'median_shape_r2_pct search_edge individual_edge_n near_min near_max fit_125_312_status '
          'fit_200_312_status scale_status spacing_status spacing_frames spacing_n spacing_min_raw_rows '
          'spacing_max_raw_rows spacing_median_raw_rows bracket_status conditional_period_us '
          'conditional_broad_recurrence_hz '
          'physical_pwm_hz_status').split()


def geometry(frames, seen):
    if strip.ROI != ROI or strip.MARGIN != 100:
        raise ValueError('R46 strip or outer clearance changed')
    rows = strip.cal_rows(frames, STATES, seen, 1250)
    use_500 = any(r['exposure_us'] == 1250 and r['status'].startswith('CLIPPED') for r in rows)

    def gate(group):
        return next((r['status'] for r in group if r['status'] != 'PASS'), 'PASS' if group else 'MISSING_CAL')

    def count(group, name):
        # The rail counts repeat unchanged across the four quarter diagnostics.
        if group and name+'1' in group[0]:
            return group[0][name+'1'] + group[0][name+'2']

    for state in STATES:
        primary, fallback = ([r for r in rows if r['scene'] == state and r['exposure_us'] == us]
                             for us in (1250, 500))
        p = gate(primary).removesuffix('_REPLACED_BY_500')
        f = gate(fallback)
        selected = fallback if use_500 else primary
        status = (f'1250_{p}' if p not in ('PASS', 'CLIPPED') else
                  f'500_{f}' if (use_500 or fallback) and f != 'PASS' else 'PASS')
        row = dict(kind='state', state=state, state_field_status=status, cal_1250_status=p,
                   cal_1250_clip_n=count(primary, 'clip'), cal_500_status=f, field_us=500 if use_500 else 1250,
                   field_clip_n=count(selected, 'clip'), field_floor_n=count(selected, 'floor'),
                   guard=strip.GUARD, margin_cells=strip.MARGIN, physical_pwm_hz_status='unidentified',
                   **dict(zip(('y0', 'y1', 'x0', 'x1'), ROI)))
        if selected and 'quarter' in selected[0]:
            row.update(uncovered_rows=sum(r['uncovered_rows'] for r in selected),
                       lateral_bad_rows=sum(r['lateral_bad_rows1'] + r['lateral_bad_rows2'] for r in selected),
                       min_release_quarter_lit_frac=min(min(r['lit_frac1'], r['lit_frac2']) for r in selected),
                       min_pair_score=min(r['min_pair_score'] for r in selected))
        yield row


def measure(frames, summary, seen):
    state = summary['state']
    events, intervals = {}, []
    for token, us in SHUTTERS.items():
        phase = f'day_{state}_{token}'
        paths = releases(frames, phase)
        if set(paths) != {1, 2, 3, 4}:
            raise ValueError(f'{phase}: expected the four R47 DAY releases')
        events[token] = []
        for n, path in paths.items():
            # One seen set for all CALs and DAYs: renamed copies are not independent.
            row, event, gaps = timing.frame(path, ROI, us, seen)
            if 'fwhm_raw_rows' in row:
                row['fwhm_raw_rows'] = timing.series(row['fwhm_raw_rows'])
            yield dict(kind='frame', state=state, phase=phase, frame_n=n, exposure_us=us, **row)
            if event is not None:
                events[token].append(event)
            if gaps:
                intervals.append(gaps)  # one entry per release; only qualified gaps from frame()

    scales = []
    for token in ('125', '200'):
        fit = timing.fit(events[token], events['312'])
        if fit['status'] == 'ok' and fit['individual_edge_n']:
            fit.update(status='skipped_individual_search_edge', effective_us_per_raw_row=None)
        if fit['status'] == 'ok':
            scales.append(fit['effective_us_per_raw_row'])
        summary[f'fit_{token}_312_status'] = fit['status']
        yield dict(kind='fit', state=state, short_us=SHUTTERS[token], long_us=SHUTTERS['312'], **fit)
    scale_gate = ('too_few_qualified_fits' if len(scales) != 2 else
                  'disagreeing_shutter_scales' if not timing.agree(scales) else 'ok')
    gaps = [gap for group in intervals for gap in group]
    spacing_gate = ('too_few_within_frame_spacings' if len(intervals) < 2 else
                    'inconsistent_spacings' if max(gaps)-min(gaps) > .10*median(gaps) else 'ok')
    summary.update(scale_status=scale_gate, spacing_status=spacing_gate, spacing_frames=len(intervals),
                   spacing_n=len(gaps), status=scale_gate if scale_gate != 'ok' else spacing_gate)
    if gaps:
        summary.update(spacing_min_raw_rows=min(gaps), spacing_max_raw_rows=max(gaps))
    if spacing_gate == 'ok':
        summary['spacing_median_raw_rows'] = median(map(median, intervals))
    if scale_gate == 'ok':
        summary['effective_us_per_raw_row'] = scales[0]


def analyze(frames):
    seen = set()
    summaries = list(geometry(frames, seen))
    if any(r['state_field_status'] != 'PASS' for r in summaries):
        for r in summaries:
            gate = r['state_field_status']
            yield dict(r, status='blocked_other_CAL' if gate == 'PASS' else gate, bracket_status='failed_geometry',
                       scale_status='not_run', spacing_status='not_run')
        return
    for r in summaries:
        yield from measure(frames, r, seen)
    passed = all(r['status'] == 'ok' for r in summaries)
    for r in summaries:
        r['bracket_status'] = 'all_states_qualified' if passed else 'incomplete_for_ABC_comparison'
        if r['status'] == 'ok':
            period = r['spacing_median_raw_rows'] * r['effective_us_per_raw_row']
            r.update(status='conditional', conditional_period_us=period, conditional_broad_recurrence_hz=1e6/period)
        yield r


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('frames', metavar='FRAMES', type=Path)
    args = ap.parse_args()
    try:
        rows = list(analyze(args.frames))
    except (ValueError, OSError) as exc:
        ap.error(str(exc))
    out = csv.DictWriter(sys.stdout, FIELDS, lineterminator='\n')
    out.writeheader()
    for row in rows:
        out.writerow({k: format(v, '.9g') if isinstance(v, float) else v for k, v in row.items()})


if __name__ == '__main__':
    main()
