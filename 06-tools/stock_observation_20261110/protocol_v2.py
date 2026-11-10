"""Prospective nominal10s protocol, not reinterpretation of protocol.py (v1)."""
import math

SCHEMA = 'stock-observation-v2-native10s'
WINDOWS = ((30, 90), (90, 150), (150, 210), (210, 270))
NATIVE_SECONDS = 10
OUTER_SECONDS = 15
ROI = {'left': (225,245,20,330), 'main': (255,245,20,330), 'right': (285,245,20,330)}
Q = .019775390625


def need(value, message):
    if not value:
        raise ValueError(message)


def timeline(pts, duration, *, early_controls_bound):
    need(early_controls_bound is True, 'frame30 controls unbound')
    need(type(duration) in (float, int) and math.isfinite(duration) and 9 <= duration <= 15,
         'media duration outside prospective bounds')
    need(isinstance(pts, (tuple,list)) and len(pts) >= 270, 'incomplete fixed windows')
    need(all(type(x) in (int,float) and math.isfinite(x) for x in pts), 'invalid PTS')
    need(all(abs((b-a)-1/30) <= .001 for a,b in zip(pts,pts[1:])), 'cadence/gap failure')
    need(pts[-1]-pts[0] < duration, 'PTS span exceeds duration')
    return WINDOWS


def admission(receipt, *, boots, source, now):
    """Strict missing-evidence rejection. Producer/byte binding still needs review.

    No device parser currently produces this complete receipt. A synthetic test
    receipt cannot authorize execution. No bare ready/mode/geometry booleans.
    """
    need(type(receipt) is dict and set(receipt) == {
        'schema','boots','source','observed_monotonic','native_mode','scene','geometry'},
        'mode/scene/geometry receipt missing')
    need(receipt['schema']=='stock-observation-prestart-v2' and receipt['boots']==boots
         and receipt['source']==source, 'receipt binding mismatch')
    t=receipt['observed_monotonic']
    need(type(t) in (int,float) and math.isfinite(t) and 0 <= now-t <= 30,
         'stale prestart receipt')
    mode=receipt['native_mode']
    need(type(mode) is dict and set(mode)=={'hz','group','evidence_sha256','parser_source_sha256'}
         and mode['hz']==120 and mode['group']==3, 'native mode missing')
    import re
    for key in ('evidence_sha256','parser_source_sha256'):
        need(type(mode[key]) is str and re.fullmatch('[a-f0-9]{64}',mode[key]), 'mode identity missing')
    scene=receipt['scene']; geometry=receipt['geometry']
    need(type(scene) is dict and set(scene)=={'component','evidence_sha256'} and
         scene['component']=='com.android.settings/.Settings$DisplaySettingsActivity' and
         re.fullmatch('[a-f0-9]{64}',str(scene['evidence_sha256'])), 'scene binding missing')
    need(type(geometry) is dict and set(geometry)=={'roi','image_sha256','review_source'} and
         geometry['roi']==ROI and re.fullmatch('[a-f0-9]{64}',str(geometry['image_sha256'])) and
         geometry['review_source']=='fresh_visual_review', 'fresh geometry receipt missing')
    return receipt
