# Changed exposure control after demonstrated UI quantization

The first run stopped after100/500us holds because all tested recording-mode
positions jump from500000ns atx864 to1000000ns atx865. No value within the
unchanged5% tolerance of700us exists on that interval. Its partial video/run
are retained one directory above; target/camera rollback passed. This is not
a panel failure or an adverse optical result.

New explicit sequence: **100 →500 →1000 →1428.571 →2000 →100us**, ISO1600 fixed,
targetDC0/DBV3600/software120 fixed. The new variable is a supported lower/upper
exposure bracket around the putative1.4ms cancellation, not the unavailable
half-period control. A periodic integration notch predicts suppression near the
middle point and recovery beyond it; relative harmonic patterns at500/1000/2000
help discriminate conditional frequency hypotheses. Do not label a notch alone
as a calibrated fundamental, physical2–3× PWM increase or absence of an envelope.

All original metadata/native/cleanup/one-shot guards and the5% requested-shutter
tolerance remain. Use `--exposure-notch-supported`; new output/private/video
paths prevent replacing the aborted trial. Existing100/500 states are controls
inside this changed experiment, not a repeat of a completed unchanged test.
