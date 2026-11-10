"""Inert finite recording budget model. No transport, commands or live authority.

Not proof that any camera implements the limit. The independently verified
camera-local stop remains a prerequisite for a future reviewed coordinator.
"""
from dataclasses import dataclass
import math

WINDOWS = ((30, 90), (120, 180), (210, 270), (300, 360))
CAP_SECONDS = 15.0


def need(condition, message):
    if not condition:
        raise ValueError(message)


@dataclass
class Budget:
    state: str = 'new'
    started: float | None = None
    latest: float | None = None
    failure: str | None = None
    stop_attempted: bool = False

    def _time(self, now):
        need(type(now) in (int, float) and math.isfinite(now), 'finite monotonic time required')
        need(self.latest is None or now >= self.latest, 'clock moved backwards')
        self.latest = now

    def arm(self, *, preview_verified, local_stop_verified, roles_verified,
            originals_bound, source_bound, mutex_owned):
        need(self.state == 'new', 'one arm only')
        need(all(x is True for x in (preview_verified, local_stop_verified,
                                    roles_verified, originals_bound,
                                    source_bound, mutex_owned)), 'prerequisite missing')
        self.state = 'armed'

    def attempt_start(self, now):
        need(self.state == 'armed', 'no start retry or already-recording toggle')
        self._time(now)
        # Latch BEFORE issuing start. The budget never starts after settling.
        self.started = now
        self.state = 'start_uncertain'

    def observed_recording(self, now):
        need(self.state in ('start_uncertain', 'recording'), 'unexpected recording')
        self._time(now)
        if now - self.started >= CAP_SECONDS:
            self.fail('recording_at_deadline')
            return
        self.state = 'recording'

    def remaining(self, now):
        need(self.started is not None, 'start not attempted')
        self._time(now)
        return max(0.0, CAP_SECONDS - (now - self.started))

    def fail(self, reason):
        need(type(reason) is str and bool(reason), 'failure reason required')
        self.failure = self.failure or reason
        if self.state != 'stopped':
            self.state = 'cleanup_required'

    def stop_action(self, *, fresh_ui_state):
        need(self.started is not None, 'no ownership of recording')
        need(self.state != 'stopped', 'already verified stopped')
        need(fresh_ui_state in ('recording', 'preview', 'unknown'), 'bad UI state')
        # No retry of uncertain tap, no blind keyevent/toggle. Caller must inspect.
        if fresh_ui_state == 'recording':
            if self.stop_attempted:
                return 'retain_uncertainty_no_tap'
            self.stop_attempted = True
            return 'verified_stop_control_once'
        if fresh_ui_state == 'preview':
            return 'verify_preview_without_tap'
        return 'retain_uncertainty_no_tap'

    def observed_preview(self, now):
        need(self.started is not None and self.state != 'stopped', 'invalid stop observation')
        self._time(now)
        self.state = 'stopped'
        # Late observation does not prove late physical stop. It cannot prove
        # timely stop either; independent local receipt/media evidence is needed.
        return {'observed_elapsed': now - self.started,
                'timely_stop_proven_by_host': False}


def validate_timeline(pts, *, encoded_duration, early_controls_bound):
    """Reject-only timeline checks; never establishes a preventive camera cap."""
    need(early_controls_bound is True, 'early window controls not bound')
    need(type(encoded_duration) in (int, float) and
         math.isfinite(encoded_duration) and 0 < encoded_duration <= CAP_SECONDS,
         'encoded duration outside cap')
    need(isinstance(pts, (tuple, list)) and len(pts) >= WINDOWS[-1][1],
         'incomplete fixed windows')
    need(all(type(x) in (int, float) and math.isfinite(x) for x in pts), 'nonfinite PTS')
    need(all(abs((b-a)-1/30) <= .001 for a, b in zip(pts, pts[1:])),
         'PTS gap or changed cadence')
    need(pts[-1] - pts[0] < encoded_duration, 'PTS span exceeds duration')
    return WINDOWS
