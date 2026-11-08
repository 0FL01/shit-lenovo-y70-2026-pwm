# Qualitative camera baseline — 2026-11-06

Status: **partial / two separate recordings inspected**. Latest16:30 capture was
started, stopped, downloaded and analysed by the agent using the owner's Pacman over
Wi-Fi ADB. Exact optical Hz, duty, modulation depth and comfort acceptance remain
**unknown**; the earlier owner-recorded DC ON/OFF comparison is retained below.
No oscilloscope is available; it is not a prerequisite for this comparison.

## Latest: fixed-exposure brightness boundary — `confirmed-on-target`

[Analysis](pacman_boundary_analysis_20261106.json) /
[capture state](pacman_boundary_capture_20261106.json) /
[video](optical/pacman_boundary_20261106.mp4) /
[frame comparison](optical/pacman_boundary_comparison.png).
Pacman A142P, installed Open Camera1.56.2/Camera2: verified100µs exposure, ISO6400,
AE OFF, stable reported focus position, EIS OFF. Actual video1280×720/~30fps,40.064s
container duration. Camera2 rolling-shutter metadata was retained, not treated as
a calibrated panel-frequency measurement. The image is defocused but the band
pattern and fixed on-screen analysis region remain usable for this comparison.

| Repeated state | Android brightness / DBV | Observed optical image pattern |
|---|---|---|
| 1 and3 | 52 /3584 | Fine repeated dark bands, approximately96 image-pixel row spacing, plus stronger band |
| 2 and4 | 53 /3646 | Fine train absent; sparse stronger bands remain |

Stock DC OFF/software120Hz throughout; no new panel commands. Three transitions
match brightness-command order/timing. This brackets a real optical regime change
between3584 and3646, **not yet exactly3601 or a known register/comparator**.
Band density is not a certified Hz value, and the stronger band is not eliminated.
No owner comfort/reference-phone acceptance was collected in this autonomous run.
Both phones restored, including Pacman's original30-minute screen timeout and
camera API. Future recordings can be agent-controlled; no manual video handoff is
required while this authorized camera connection is available.

## Earlier owner recording — device conditions, `confirmed-on-target` software state

BOE ILI97701A cmd_v4/ID0xd2, XT2611-1/W3WWS36.65-64-4-1, persistent KernelSU/Enforcing.
Owner selected «Готов снимать сейчас» for a separate camera trial; no new image or
DSI profile was applied. [Run record](stock_dc_camera_run_20261106.json) confirms:

| Stable interval UTC | Android brightness | sysfs brightness | Native DC |
|---|---:|---:|---:|
| 14:09:40.56–14:09:52.56 | 78 | 5197 | OFF0 |
| 14:09:56.07–14:10:08.07 | 78 | 5197 | ON1 |
| 14:10:11.56–14:10:23.56 | 40 | 2839 | OFF0 |
| 14:10:27.02–14:10:39.02 | 40 | 2839 | ON1 |

Requested min/peak120Hz, manual brightness during the trial. Actual software120Hz
and wire `51 14 4D` / `51 0B 17` were verified in the **preceding transport run**,
not independently re-logged in this camera run: [trace](stock_dc_trace_analysis_20261106.json).
Foreground content was stock Display Settings/Flicker prevention. The supplied
video shows **light theme**, correcting the earlier assumption based on the prior
UI session. A USB dialog temporarily changes/dims content. Logger/probes were not
enabled for camera; content therefore was not fully constant throughout this take.

At14:10:39–14:10:42 cleanup: DC OFF, requested brightness78 then auto1, min/peak keys
removed. Cleanup verified; final automatic brightness/refresh are not a fixed repeat
of the first manual condition. This deliberate reset is the likely fifth transition.

## Owner's initial observation — `reported`

Owner reports a video of approximately **1 minute30 seconds** and five chronological
states. Initial alignment was provisional; the subsequent decoded switch timeline
below now supports the OFF/ON condition assignment:

| # | Owner observation | Aligned condition |
|---|---|---|
| 1 | «Ходит медленно одна толстая полоса по экрану (по диагонали примерно)» | 78 / DC OFF |
| 2 | «полоса жирная стала быстрее бегать по экрану» | 78 / DC ON |
| 3 | «много полос по тоньше и все они быстро бегают по диагонали» | 40 / DC OFF |
| 4 | «полос вообще не видно через камеру и как будто всё окей» | 40 / DC ON |
| 5 | «полоса вернулась снова жирная такая которая ходит по диагонали» | Cleanup: DC OFF / auto / normal refresh policy |

Owner interpreted state4 as a good sign of higher PWM frequency. Preserve that as
the owner's interpretation, **not a measured frequency conclusion**.

## Supported interpretation and limits

- `reported`: visible camera-band structure changes with stock settings, including
  a substantial difference between OFF and ON at the same lower brightness.
- `hypothesis`: many thin bands in state3 are consistent with a higher-pulse native
  low-DBV mode. BOE/Honor emission/DC examples motivate this interpretation; target
  pulse count/Hz have not been decoded.
- State4 is promising for reducing **visible camera banding**, but no bands does NOT
  establish higher frequency or PWM absence. Global-DC/high-duty emission, exposure
  integration, rolling-shutter aliasing and camera processing are possible causes.
  A stripe's travel speed/diagonal angle is not a frequency counter.
- Camera model, shutter/ISO, AE/AF lock, sensor readout and panel/thermal/ambient
  conditions remain unknown. File frame rate is29.9167fps, not an emission-frequency
  measurement. Agent suggested fixed exposure/focus and1/4000 if available, but
  cannot claim these were used. No reference-phone clip or brief
  direct-comfort assessment has been reported yet; do not provoke symptoms to obtain it.
- Offline CN `vendor_a/etc/sensors/als_comp_config.xml:43–44` has `pwmToDcDbv=3601`;
  the tested sysfs values straddle it. This is **sensor-compensation configuration**,
  not a PWM-Hz setter or proof of the target DDIC transition threshold. It is not
  edited, and its logical panelId1 is not live physical/profile ID0xd2.

## Supplied video — offline inspection, no device actions

Input: `/home/stfu/Torrents/Android/VID_20261106_170959931_rotated_180.mp4`.
HEVC1080×1920, **87.810585s**,48394921bytes; file frame rate359/12≈29.9167fps.
The rotated file has a Lavf container tag; source-camera exposure/readout cannot be
inferred from that metadata. Audio was not analysed. [Analysis record](video_analysis_20261106.json).
Decoded frames/crops stay private0600 in the analysis cache listed there.

| Approximate video interval | Assigned condition |
|---|---|
| 00:00–00:10.0 | 78 / DC OFF |
| 00:10.0–00:25.8 | 78 / DC ON |
| 00:25.8–00:41.0 | 40 / DC OFF |
| 00:41.0–00:56.6 | 40 / DC ON |
| From00:56.6 | DC OFF cleanup, then auto/normal refresh policy; tail not fixed conditions |

Switch colour changes sampled every0.2s; timings are approximate, not exact hardware
switch times. All four transitions match the four native input-tap intervals with
only0.287s offset spread; do not synchronize by the video filename clock.

- `confirmed-on-target` (supplied video correlated to native event record): low-OFF
  frames26–28s show repeated narrow band structure before the USB popup around29s.
  USB popup/scrim, visible at32s, is excluded from the clean comparison.
- Low-ON samples44–48s are substantially less visibly banded. This supports the
  owner's mode4 observation, not PWM absence or a proven frequency increase.
- Camera/phone move; fine coloured moiré is also visible. Do not count every fine
  pattern as an EM pulse. A fixed screen-edge pixel strip was discarded because
  handheld movement brings the phone border through it; no intensity/depth/FFT/Hz
  claim is based on that invalid ROI or on compressed camera pixel codes.

## Next evidence

Candidate mode4 is reproducible through existing stock Android controls, without
another kernel flash, but is not an established solution. The next technical task
is identifying emission count/timing controls, not repeatedly presenting this same
DC preset as higher-frequency PWM. Reference-camera comparison remains optional
qualitative evidence; numerical >=2000Hz has not been demonstrated.

## Brief reproduction and latest owner feedback

`confirmed-on-target`: [bounded trial](mode4_brief_trial_20261106.json) held mode4
at15:24:57.87–15:25:27.87UTC: DC1/manual40/sysfs2839/software120.00001Hz/Enforcing.
By15:25:32, verified restoration to captured brightness69/auto1/DC0/min-peak absent;
screen-off command accepted. No new DSI sequence, image or persistent PWM profile.

`reported`, subsequent owner message: «щас вот на профиле полосы видны, но чуть менее
заметно, но они есть». Owner explicitly requests further PWM frequency increase,
not acceptance of this stock preset; wants less repetitive safety discussion and
faster substantive investigation. The message does not timestamp the observation
inside versus after the automatically restored trial. It does not establish a
comfort outcome, exact frequency or stability across conditions. The earlier
camera interval with no obvious stripes must not be generalized to all observations.
