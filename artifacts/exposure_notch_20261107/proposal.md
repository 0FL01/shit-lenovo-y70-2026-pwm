# Stock optical integration-notch control, not a PWM increase

Scope: autonomous camera/stock optical work. No new composed DSI sequence,
page-select/readback, ESD change, flash or reboot. Exact S0C1 approval remains
pending and is not bypassed by this measurement.

Question: does increasing integration time near1.4ms attenuate the entire fine
train much more than~0.7ms, while~0.5ms still retains its first component? This
tests exposure-time cancellation independently of the poorly conditioned camera
row/panel scan geometry. Carrier hypotheses around720,1440 and2160Hz predict
different notch/harmonic patterns. These are predictions, not measured baseline.
An integer-period integration attenuates all time harmonics of an ideal periodic
source regardless of a static spatial phase; a notch alone still has integer
multiple ambiguity and cannot certify fundamental frequency or no envelope.

One sequence, camera at constantISO1600: requested exposures
**100 →500 →700 →1400 →700 →100 microseconds**, six7s holds. Select available
manual values within5% of targets; log both native request and result, not just
UI text. All phases use targetDC0/DBV3600/software120 and a fixed scene/geometry,
AE-AF/stabilization OFF and unchanged lens position. Camera exposure controls may
have different quantization during recording; calibration occurs before each
hold and is excluded from the analysis window. A tap inside a SeekBar thumb may
be ignored, so reset to the independently verified100us endpoint before changing
coordinates; verify selected values repeat. Do not present these exposure steps
as the owner's requested2–3× increase of physical PWM.

Use original sensor video Y, full spatial spectra without temporal demeaning;
inspect raw means/clipping/noise and local harmonics, not just q93 amplitude.
ISO stays fixed to avoid gain changes between phases; tone curve/black level
remain uncalibrated. Numerical sinc fits are conditional on photometric assumptions.

Fresh transport/build/root/Enforcing checks and fresh one-shot output required.
Abort on invalid camera state, unavailable shutter tolerance, trace loss/native
error or target DBV/refresh change. Restore camera100us/ISO6400 and its existing
manual focus/AE/stabilization, stop own recording, remove own tracing/logger/UI
files and restore captured target Android policy/native DBV. Keep camera awake.
No indefinite camera wait or automatic repeat of a completed capture.
