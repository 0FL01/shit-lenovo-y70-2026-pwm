#!/usr/bin/env python3
"""Bind R49 acquisition windows: bind.py ARCHIVE frames.csv > windows.csv.

Read only the offline archive and R48 measurement CSV. A bound window has
four distinct native releases and matching endpoint snapshots, not continuous
state telemetry, a DDIC/native receipt, or evidence of register rollback.
Wake, DBV, DC, preference and scene color are BOUND log assertions; the
five saved snapshots corroborate mode, range, HBM, thermal, session and app.
"Complete" covers the window schedule only, not the bench cleanup or return.
--owner-context binds a separate ordinary-session checkpoint, not a main R leg.
"""

import argparse
import csv
from dataclasses import dataclass
from hashlib import blake2b
from math import isclose
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
ARTIFACTS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ARTIFACTS))
from direct_camera_r42_20261121.measure import ROI, decode_dng_bytes, extract_metadata


NS = {'25000': 25000000, '4000': 4000000, '6667': 6666667, '1250': 1250000}
STOCK = ('dark_S_25000', 'cal_S_25000', 'day_S_4000')
OWNER = ('dark_O_25000', 'cal_O_25000', 'day_O_4000')
MAIN = tuple(f'{group}_{leg}_{token}' for leg in 'ABR' for group, token in
             (('cal', '25000'), ('day', '4000'), ('day', '6667'), ('day', '1250')))
RELEASES = 4
BOUND = re.compile(r'BOUND ([A-Za-z0-9_]+) wake=([1-9][0-9]*) '
                   r'bl=512 dc=0 pref=0 hwc=0 hz=120 sdr hbm=off thermal=0 color=([0-9a-f]{6})')
FRAME = re.compile(r'frame (\w+__[1-4]) ([1-9][0-9]*)')
SOURCE = r'/sdcard/DCIM/Camera/IMG_[A-Za-z0-9_]+\.DNG'
QUEUE = re.compile(rf'(\w+__[1-4]) ([1-9][0-9]*) ({SOURCE})')
EXIF = {'iso': 'iso', 'width': 'width', 'height': 'height', 'orientation': 'orientation',
        'focal_mm': 'focal_length_mm', 'white_dn': 'white_level', 'exposure_us': 'exposure_us'}
CSV_FIELDS = {'phase', 'group', 'scene', 'frame_n', 'cfa', 'black_dn', 'mean_dn',
              'y0', 'y1', 'x0', 'x1', *EXIF}


@dataclass(frozen=True)
class Window:
    phase: str
    wake: int
    ns: int
    color: str
    frames: tuple[tuple[str, int], ...]
    pre_line: int
    post_line: int


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lines(path):
    require(not path.is_symlink() and path.is_file(), f'{path.name}: missing or non-original archive file')
    return path.read_text(encoding='utf-8').splitlines()


def acquisition(archive, allow_incomplete, *, owner_context=False):
    records = [(n, line) for n, line in enumerate(lines(archive / 'acquisition.log'), 1)
               if re.match(r'\s*(?:BOUND|PRE|POST|frame)(?:\s|$)', line)]
    require(records, 'acquisition.log: no window records')
    opening = BOUND.fullmatch(records[0][1])
    if owner_context:
        kind, schedule, wake = 'owner', OWNER, None
    elif opening and opening[1] == 'entry':
        kind, schedule, wake = 'main', MAIN, opening[2]
        require(opening[3] == 'ffffff' and lines(archive / 'epoch') == [wake],
                'main BOUND entry color or epoch file mismatch')
        records = records[1:]
    else:
        kind, schedule, wake = 'stock', STOCK, None
    require(records, 'acquisition.log: no capture windows')

    windows = []
    span = RELEASES + 4  # BOUND pre, PRE, four frame records, BOUND post, POST
    for start in range(0, len(records), span):
        block = records[start:start + span]
        where = f'acquisition.log:{block[0][0]}'
        before = BOUND.fullmatch(block[0][1])
        require(len(windows) < len(schedule), f'{where}: unexpected extra {kind} window')
        phase = schedule[len(windows)]
        require(before and before[1] == f'{phase}_pre', f'{where}: expected BOUND {phase}_pre')
        epoch, color = before[2], before[3]
        expected_color = '000000' if phase.startswith('dark_') else 'ffffff'
        require(color == expected_color, f'{where}: unexpected color for {phase}')
        if wake is None:
            wake = epoch
        require(epoch == wake, f'{where}: changed wake epoch')
        require(len(block) == span, f'{where}: {phase} has no complete PRE/POST window')
        ns = NS[phase.rsplit('_', 1)[1]]
        require(block[1][1] == f'PRE {phase} ns={ns}', f'{where}: missing/mismatched PRE')
        frames = []
        for i, (n, line) in enumerate(block[2:-2], 1):
            match = FRAME.fullmatch(line)
            require(match and match[1] == f'{phase}__{i}', f'acquisition.log:{n}: expected frame {phase}__{i}')
            frames.append((match[1], int(match[2])))
        after = BOUND.fullmatch(block[-2][1])
        require(after and after.groups() == (f'{phase}_post', wake, color),
                f'{where}: missing/mismatched BOUND post')
        require(block[-1][1] == f'POST {phase} ns={ns} count={RELEASES}', f'{where}: missing/mismatched POST')
        windows.append(Window(phase, int(wake), ns, color, tuple(frames), block[1][0], block[-1][0]))

    missing = schedule[len(windows):]
    require(not missing or (allow_incomplete and not owner_context),
            f'{kind} archive missing windows: {", ".join(missing)}')
    return windows, kind, 'diagnostic_incomplete' if missing else 'complete'


def queue_sources(archive, windows):
    queue = lines(archive / 'queue')
    entries = [item for w in windows for item in w.frames]
    require(len(queue) == len(entries), 'queue: frame count differs from closed acquisition windows')
    sources, by_frame = set(), {}
    for n, (line, (name, size)) in enumerate(zip(queue, entries), 1):
        match = QUEUE.fullmatch(line)
        require(match and (match[1], int(match[2])) == (name, size),
                f'queue:{n}: expected {name} with logged original size {size}')
        source = match[3]
        require(source not in sources, f'queue:{n}: reused camera source for {name}')
        sources.add(source)
        by_frame[name] = source
    for w in windows:
        burst = archive / f'{w.phase}.burst'
        require(lines(burst) == [f'{size} {by_frame[name]}' for name, size in w.frames],
                f'{burst.name}: size/source order differs from queue')


def snapshot(archive, tag, *, owner_wake=None):
    def values(text, field):
        return [line[len(field):] for raw in text
                if (line := raw.strip()).startswith(field)]

    # Read active modes, not the list of supported modes or refresh requests.
    sf = lines(archive / f'{tag}.sf')
    modes = values(sf, 'activeMode=')
    require(modes and all(re.fullmatch(r'\{id=[0-9]+, hwcId=0, .*\bvsyncRate=120\.00 Hz(?:,.*)?\}',
                                      mode) for mode in modes), f'{tag}.sf: not actual HWC0 / 120 Hz')
    require(values(sf, 'current dynamic_range:') == [' SDR'], f'{tag}.sf: not SDR')
    display = lines(archive / f'{tag}.display')
    require(values(display, 'mHbmMode=') == ['off'], f'{tag}.display: HBM not off')
    thermal = lines(archive / f'{tag}.thermal')
    require(values(thermal, 'Thermal Status:') == [' 0'] and values(thermal, 'IsStatusOverride:') == [' false'],
            f'{tag}.thermal: nonzero/overridden status')
    session = lines(archive / f'{tag}.session')
    if owner_wake is None:
        require(session and session[0] == 'inactive', f'{tag}.session: expected inactive session')
    else:
        require(session == ['running', f'active: verified wake={owner_wake}'],
                f'{tag}.session: expected only running and active: verified wake={owner_wake}')
    top = values(lines(archive / f'{tag}.top'), 'topResumedActivity=')
    require(len(top) == 1 and re.fullmatch(r'ActivityRecord\{[^}]+ com\.android\.htmlviewer/'
                                          r'\.HTMLViewerActivity(?: [^}]*)?\}', top[0]),
            f'{tag}.top: HTMLViewer is not top resumed')


def read_csv(path):
    rows = {}
    with path.open(newline='', encoding='utf-8') as stream:
        reader = csv.DictReader(stream, strict=True)
        header = reader.fieldnames or []
        require(len(set(header)) == len(header) and CSV_FIELDS <= set(header),
                f'{path.name}: missing measurement fields or duplicate headers')
        for row in reader:
            line = f'{path.name}:{reader.line_num}'
            require(None not in row and None not in row.values() and row['frame_n'] in ('1', '2', '3', '4'),
                    f'{line}: malformed frame row')
            name = f'{row["phase"]}__{row["frame_n"]}'
            require(name not in rows, f'{line}: duplicate {name}')
            rows[name] = row
    return rows


def check_frame(path, size, row, window, seen_raw):
    require(path.is_file() and not path.is_symlink() and path.stat().st_size == size,
            f'{path.name}: missing original or byte size mismatch')
    data = path.read_bytes()
    require(len(data) == size, f'{path.name}: size changed during read')
    try:
        raw, tags = decode_dng_bytes(data)
        meta = extract_metadata(tags)
        require((meta['make'], meta['model'], meta['iso'], meta['width'], meta['height'],
                 meta['orientation'], meta['focal_length_mm'], meta['cfa_pattern_2x2'], meta['white_level']) ==
                ('Nothing', 'A001', 6400, 4080, 3072, 6, 5.56, [1, 2, 0, 1], 1023),
                'unexpected camera EXIF, orientation, CFA or size')
        require(isclose(meta['exposure_us'], window.ns / 1000, rel_tol=0, abs_tol=.001),
                'DNG exposure disagrees with PRE/POST')

        group, leg, _ = window.phase.split('_')
        require((row['group'], row['scene'], row['cfa']) == (group, leg, 'GBRG'), 'CSV group/scene/CFA mismatch')
        y0, y1, x0, x1 = ROI
        require(tuple(int(row[k]) for k in ('y0', 'y1', 'x0', 'x1')) == ROI, 'CSV ROI mismatch')
        black = meta['black_levels'][0]
        g1 = raw[2*y0:2*y1:2, 2*x0:2*x1:2]
        # An extra inexpensive witness: matching EXIF alone cannot bind rows
        # to different files from the same shutter setting.
        checks = {k: meta[v] for k, v in EXIF.items()}
        checks.update(black_dn=black, mean_dn=(g1.astype(float) - black).mean())
        for field, expected in checks.items():
            require(float(row[field]) == float(format(expected, '.9g')), f'CSV {field} does not match DNG')

        digest = blake2b(memoryview(raw), digest_size=32).digest()
        require(digest not in seen_raw, f'duplicate native RAW plane (also {seen_raw.get(digest)})')
        seen_raw[digest] = path.name
    except ValueError as exc:
        raise ValueError(f'{path.name}: {exc}') from None


def bind(archive, frame_csv, allow_incomplete, *, owner_context=False):
    windows, kind, status = acquisition(archive, allow_incomplete, owner_context=owner_context)
    queue_sources(archive, windows)
    rows = read_csv(frame_csv)
    expected = {name for w in windows for name, _ in w.frames}
    require(rows.keys() == expected, 'frames.csv keys differ from acquisition window inventory')
    frames_dir = archive / 'frames'
    require(not frames_dir.is_symlink() and frames_dir.is_dir(), 'frames/: missing original frame directory')
    files = {p.name for p in frames_dir.iterdir() if p.suffix.lower() in ('.dng', '.partial')}
    require(files == {f'{name}.dng' for name in expected}, 'frames/: extra, missing or unfinished originals')
    seen_raw = {}
    for window in windows:
        for side in ('pre', 'post'):
            snapshot(archive, f'{window.phase}_{side}', owner_wake=window.wake if owner_context else None)
        for name, size in window.frames:
            check_frame(frames_dir / f'{name}.dng', size, rows[name], window, seen_raw)
    return [dict(archive=kind, archive_status=status, phase=w.phase, wake=w.wake, color=w.color,
                 bl=512, dc=0, pref=0, hwc=0, hz=120, dynamic_range='SDR', hbm='off', thermal=0,
                 exposure_ns=w.ns, frame_count=len(w.frames), raw_bytes=';'.join(str(size) for _, size in w.frames),
                 pre_log_line=w.pre_line,
                 post_log_line=w.post_line) for w in windows]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path, metavar='ARCHIVE')
    parser.add_argument('frames', type=Path, metavar='frames.csv')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--allow-incomplete', action='store_true',
                      help='diagnostic only: allow a prefix of fully closed, otherwise valid windows')
    mode.add_argument('--owner-context', action='store_true',
                      help='require the full O schedule and an active owner session at the BOUND wake')
    args = parser.parse_args()
    try:
        rows = bind(args.archive, args.frames, args.allow_incomplete, owner_context=args.owner_context)
    except (OSError, ValueError, csv.Error) as exc:
        parser.exit(1, f'FAIL: {exc}\n')
    output = csv.DictWriter(sys.stdout, rows[0], lineterminator='\n')
    output.writeheader()
    output.writerows(rows)


if __name__ == '__main__':
    main()
